"""The app's Connection to the Channel: who it is signed in as, and the gateway every YouTube call uses."""
import logging
import threading
from dataclasses import dataclass
from typing import Literal

from app.quota import MeteredGateway, QuotaLedger
from app.store.db import Store
from app.youtube.errors import AuthExpired, GatewayError
from app.youtube.gateway import Channel, GatewayProvider, YouTubeGateway

State = Literal["no_client_secret", "disconnected", "expired", "connected"]

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Status:
    state: State
    channel: Channel | None


class NotConnected(Exception):
    pass


class SignInInProgress(Exception):
    pass


class Connection:
    def __init__(self, provider: GatewayProvider, store: Store, ledger: QuotaLedger) -> None:
        self._provider = provider
        self._store = store
        self._ledger = ledger
        self._gateway: YouTubeGateway | None = None
        self._expired = False
        self._state_lock = threading.RLock()  # held only briefly
        self._sign_in_lock = threading.Lock()  # held for the whole consent flow

    def restore(self) -> None:
        """Pick up a cached sign-in at startup. Makes no API calls, so it can't fail on the network."""
        try:
            restored = self._provider.restore()
            gateway = self._metered(restored) if restored else None
        except AuthExpired:
            gateway = None
            with self._state_lock:
                self._expired = True
        with self._state_lock:
            self._gateway = gateway

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

    def connect(self) -> Status:
        if not self._sign_in_lock.acquire(blocking=False):
            raise SignInInProgress()
        try:
            gateway = self._metered(self._provider.connect())
            try:
                self._store.save_channel(gateway.get_my_channel())
            except GatewayError:
                # Signed in but unusable (no channel, API disabled): don't leave a token behind.
                self._provider.disconnect()
                raise
            with self._state_lock:
                self._gateway, self._expired = gateway, False
        finally:
            self._sign_in_lock.release()
        return self.status()

    def disconnect(self) -> Status:
        self._provider.disconnect()
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
