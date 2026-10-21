"""In-memory YouTube used by tests and `python dev.py --fake`. Never talks to Google."""
import threading

from app.youtube.errors import AuthExpired, GatewayError
from app.youtube.gateway import Channel

FAKE_CHANNEL = Channel(id="UC_fake_channel", title="Fake Channel", avatar_url=None,
                       uploads_playlist_id="UU_fake_channel")


class FakeGateway:
    def __init__(self, channel: Channel = FAKE_CHANNEL) -> None:
        self.channel = channel
        self.calls: list[str] = []  # API method names, in call order
        self.fail_with: Exception | None = None  # raised by every call while set

    def _call(self, method: str) -> None:
        self.calls.append(method)
        if self.fail_with:
            raise self.fail_with

    def get_my_channel(self) -> Channel:
        self._call("channels.list")
        return self.channel


class FakeGatewayProvider:
    """Sign-in that succeeds instantly; scriptable for missing secrets, expiry, errors and slow flows."""

    def __init__(self, gateway: FakeGateway, *, has_client_secret: bool = True,
                 connect_error: str | None = None, block_until: threading.Event | None = None) -> None:
        self.gateway = gateway
        self._has_client_secret = has_client_secret
        self._connect_error = connect_error
        self._block_until = block_until
        self.flow_started = threading.Event()
        self.connected = False  # whether a token is "cached"
        self.expired = False
        self.revoked = False

    def has_client_secret(self) -> bool:
        return self._has_client_secret

    def connect(self) -> FakeGateway:
        self.flow_started.set()
        if self._block_until:
            self._block_until.wait(10)
        if self._connect_error:
            raise GatewayError(f"Google sign-in failed: {self._connect_error}")
        self.connected, self.expired, self.revoked = True, False, False
        return self.gateway

    def restore(self) -> FakeGateway | None:
        if self.expired:
            raise AuthExpired("Google sign-in expired")
        return self.gateway if self.connected else None

    def disconnect(self) -> None:
        self.revoked = True
        self.connected = False
        self.expired = False

    def expire(self) -> None:
        """Simulate the cached token becoming unrefreshable."""
        self.expired = True
