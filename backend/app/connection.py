"""The app's Connection to the Channel: who it is signed in as, and the gateway every YouTube call uses.

Owner sign-in and the Connection are one Google sign-in (ADR-0019). The credentials it returns, and whether Google
has stopped accepting them, are kept in the Store, so every instance of the app agrees on the Connection
(ADR-0020). An instance only caches the gateway built from the credentials it last read."""
import hashlib
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
EXPIRED = "google_expired"  # the fingerprint of the credentials Google stopped accepting

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Status:
    state: State
    channel: Channel | None


class NotConnected(Exception):
    pass


class NotOwner(Exception):
    """A Google account other than the Owner's tried to sign in. `email` is the account Google reported."""

    def __init__(self, email: str) -> None:
        super().__init__("not the owner")
        self.email = email


# A YouTube Brand Account signs in as a Google-issued identity in this domain, which may not carry
# email_verified. Nobody but Google can issue these addresses, and they arrive in Google's signed ID token.
BRAND_ACCOUNT_DOMAIN = "@pages.plusgoogle.com"


def _trustworthy(email: str, verified: bool) -> bool:
    return verified or email.casefold().endswith(BRAND_ACCOUNT_DOMAIN)


class ChannelUnavailable(Exception):
    """Signed in, but the account's Channel couldn't be loaded (no Channel, API disabled, YouTube down)."""


class Connection:
    def __init__(self, provider: GatewayProvider, store: Store, ledger: QuotaLedger, box: TokenBox) -> None:
        self._provider = provider
        self._store = store
        self._ledger = ledger
        self._box = box
        self._cache: tuple[str, YouTubeGateway] | None = None  # (the sealed credentials, their gateway)
        self._cache_lock = threading.Lock()  # held only briefly

    def _current(self) -> YouTubeGateway | None:
        """The gateway for the credentials stored now, or None if there are none or Google stopped accepting
        them. Makes no YouTube calls; a token refresh, if due, goes to Google's sign-in service only."""
        stored = self._store.get_settings(CREDENTIALS, EXPIRED)
        sealed = stored.get(CREDENTIALS)
        if not sealed or stored.get(EXPIRED) == _tag(sealed):
            return None
        with self._cache_lock:
            if self._cache and self._cache[0] == sealed:
                return self._cache[1]
        credentials = self._box.open(sealed)
        if not credentials:
            return None
        try:
            gateway, refreshed = self._provider.gateway_for(credentials)
        except AuthExpired:
            self._expire(sealed)
            return None
        if refreshed:
            renewed = self._box.seal(refreshed)
            # Only if nobody signed in again or disconnected meanwhile; otherwise use what they stored.
            if not self._store.replace_setting(CREDENTIALS, sealed, renewed):
                return None if self._store.get_setting(CREDENTIALS) is None else self._current()
            sealed = renewed
        gateway = self._metered(gateway, sealed)
        with self._cache_lock:
            self._cache = (sealed, gateway)
        return gateway

    def has_client_secret(self) -> bool:
        return self._provider.has_client_secret()

    def status(self) -> Status:
        """Raises GatewayError if the Channel must be fetched and YouTube can't be reached."""
        if not self.has_client_secret():
            return Status("no_client_secret", None)
        gateway = self._current()
        if not gateway:
            stored = self._store.get_settings(CREDENTIALS, EXPIRED)
            expired = CREDENTIALS in stored and stored.get(EXPIRED) == _tag(stored[CREDENTIALS])
            return Status("expired" if expired else "disconnected", None)
        channel = self._store.get_channel()
        if channel is None:
            channel = gateway.get_my_channel()  # an expiry here is recorded by the gateway itself
            self._store.save_channel(channel)
        return Status("connected", channel)

    def sign_in_url(self, state: str, redirect_uri: str) -> str:
        return self._provider.authorization_url(state, redirect_uri)

    def complete_sign_in(self, code: str, redirect_uri: str, owner_email: str | None) -> str:
        """Finish Google's callback: check it's the Owner, then connect the Channel. Returns the email.
        Raises NotOwner or ChannelUnavailable (nothing is kept, and Google's grant is withdrawn), or GatewayError
        if Google refused the code."""
        sign_in = self._provider.exchange_code(code, redirect_uri)
        if owner_email is not None and not (_trustworthy(sign_in.email, sign_in.email_verified)
                                            and is_owner(sign_in.email, owner_email)):
            self._provider.revoke(sign_in.credentials_json)
            log.warning("Refused a sign-in by an account that isn't the owner")  # never log whose
            raise NotOwner(sign_in.email)
        sealed = self._box.seal(sign_in.credentials_json)
        try:
            gateway, refreshed = self._provider.gateway_for(sign_in.credentials_json)
            if refreshed:
                sealed = self._box.seal(refreshed)
            gateway = self._metered(gateway, sealed)
            self._store.save_channel(gateway.get_my_channel())
        except GatewayError as e:
            # Signed in but unusable (no Channel, API disabled): don't keep a token behind.
            self._provider.revoke(sign_in.credentials_json)
            raise ChannelUnavailable(str(e)) from e
        self._store.set_setting(CREDENTIALS, sealed)
        self._store.delete_setting(EXPIRED)  # a fresh sign-in; an older one's late expiry can't match it (_tag)
        with self._cache_lock:
            self._cache = (sealed, gateway)
        log.info("Google sign-in completed")
        return sign_in.email

    def disconnect(self) -> Status:
        credentials = self._box.open(self._store.get_setting(CREDENTIALS))
        if credentials:
            self._provider.revoke(credentials)
        self._store.delete_setting(CREDENTIALS)
        self._store.delete_setting(EXPIRED)
        with self._cache_lock:
            self._cache = None
        return self.status()

    def gateway(self) -> YouTubeGateway:
        gateway = self._current()
        if not gateway:
            raise NotConnected()
        return gateway

    def _expire(self, sealed: str) -> None:
        """Google stopped accepting these credentials: every instance now shows them as expired. Tagged with
        the credentials it applies to, so a request still using an older sign-in can't expire a newer one."""
        self._store.set_setting(EXPIRED, _tag(sealed))
        with self._cache_lock:
            self._cache = None

    def _metered(self, gateway: YouTubeGateway, sealed: str) -> YouTubeGateway:
        """Every gateway the app uses records its requests in the Quota ledger, and reports its own expiry."""
        return MeteredGateway(gateway, self._ledger, on_expired=lambda: self._expire(sealed))


def _tag(sealed: str) -> str:
    """A short fingerprint of the stored credentials, never the credentials themselves."""
    return hashlib.sha256(sealed.encode()).hexdigest()[:16]
