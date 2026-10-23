"""The app's Connection to the Channel: who it is signed in as, and the gateway every YouTube call uses.

Owner sign-in and the Connection are one Google sign-in (ADR-0019). The credentials it returns are kept in the
Store, sealed by the TokenBox, so any instance of the app can pick them up."""
import logging
import threading
from dataclasses import dataclass
from typing import Literal

from app.quota import MeteredGateway, QuotaLedger
from app.session import is_owner
from app.store.db import Store
from app.token_box import TokenBox
from app.youtube.errors import AuthExpired, GatewayError
from app.youtube.gateway import Channel, GatewayProvider, YouTubeGateway

State = Literal["no_client_secret", "disconnected", "expired", "connected"]
CREDENTIALS = "google_credentials"  # the Store setting holding the sealed Google credentials

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Status:
    state: State
    channel: Channel | None


class NotConnected(Exception):
    pass


class NotOwner(Exception):
    """A Google account other than the Owner's tried to sign in."""


class ChannelUnavailable(Exception):
    """Signed in, but the account's Channel couldn't be loaded (no Channel, API disabled, YouTube down)."""


class Connection:
    def __init__(self, provider: GatewayProvider, store: Store, ledger: QuotaLedger, box: TokenBox) -> None:
        self._provider = provider
        self._store = store
        self._ledger = ledger
        self._box = box
        self._gateway: YouTubeGateway | None = None
        self._expired = False
        self._state_lock = threading.RLock()  # held only briefly

    def restore(self) -> None:
        """Pick up the stored sign-in at startup. Makes no YouTube calls, so it can't fail on YouTube."""
        gateway, expired = None, False
        credentials = self._box.open(self._store.get_setting(CREDENTIALS))
        if credentials:
            try:
                gateway, refreshed = self._provider.gateway_for(credentials)
                if refreshed:
                    self._save(refreshed)
                gateway = self._metered(gateway)
            except AuthExpired:
                gateway, expired = None, True
        with self._state_lock:
            self._gateway, self._expired = gateway, expired

    def has_client_secret(self) -> bool:
        return self._provider.has_client_secret()

    def status(self) -> Status:
        """Raises GatewayError if the Channel must be fetched and YouTube can't be reached."""
        if not self.has_client_secret():
            return Status("no_client_secret", None)
        with self._state_lock:
            gateway, expired = self._gateway, self._expired
        if not gateway:
            return Status("expired" if expired else "disconnected", None)
        channel = self._store.get_channel()
        if channel is None:
            channel = self._fetch_channel(gateway)
        return Status("connected", channel)

    def sign_in_url(self, state: str, redirect_uri: str) -> str:
        return self._provider.authorization_url(state, redirect_uri)

    def complete_sign_in(self, code: str, redirect_uri: str, owner_email: str | None) -> str:
        """Finish Google's callback: check it's the Owner, then connect the Channel. Returns the email.
        Raises NotOwner or ChannelUnavailable (nothing is kept, and Google's grant is withdrawn), or GatewayError
        if Google refused the code."""
        sign_in = self._provider.exchange_code(code, redirect_uri)
        if owner_email is not None and not (sign_in.email_verified and is_owner(sign_in.email, owner_email)):
            self._provider.revoke(sign_in.credentials_json)
            log.warning("Refused a sign-in by an account that isn't the owner")
            raise NotOwner()
        try:
            gateway, refreshed = self._provider.gateway_for(sign_in.credentials_json)
            gateway = self._metered(gateway)
            self._store.save_channel(gateway.get_my_channel())
        except GatewayError as e:
            # Signed in but unusable (no Channel, API disabled): don't keep a token behind.
            self._provider.revoke(sign_in.credentials_json)
            raise ChannelUnavailable(str(e)) from e
        self._save(refreshed or sign_in.credentials_json)
        with self._state_lock:
            self._gateway, self._expired = gateway, False
        log.info("Google sign-in completed")
        return sign_in.email

    def disconnect(self) -> Status:
        credentials = self._box.open(self._store.get_setting(CREDENTIALS))
        if credentials:
            self._provider.revoke(credentials)
        self._store.delete_setting(CREDENTIALS)
        with self._state_lock:
            self._gateway, self._expired = None, False
        return self.status()

    def gateway(self) -> YouTubeGateway:
        with self._state_lock:
            if not self._gateway:
                raise NotConnected()
            return self._gateway

    def mark_expired(self) -> None:
        """Called when any API call reports AuthExpired."""
        with self._state_lock:
            self._gateway, self._expired = None, True

    def _save(self, credentials_json: str) -> None:
        self._store.set_setting(CREDENTIALS, self._box.seal(credentials_json))

    def _metered(self, gateway: YouTubeGateway) -> YouTubeGateway:
        """Every gateway the app uses records its requests in the Quota ledger."""
        return MeteredGateway(gateway, self._ledger)

    def _fetch_channel(self, gateway: YouTubeGateway) -> Channel:
        try:
            channel = gateway.get_my_channel()
        except AuthExpired:
            self.mark_expired()
            raise
        self._store.save_channel(channel)
        return channel
