class GatewayError(Exception):
    """YouTube or Google rejected a request. The message is safe to show and log (no secrets)."""


class PlaylistNotFound(GatewayError):
    """YouTube has no such playlist (a Channel with no uploads has no uploads playlist yet)."""


class ChannelChanged(GatewayError):
    """A different Channel was connected while a Sync was running; its results were discarded."""


class QuotaExceeded(GatewayError):
    """The project's daily YouTube quota is used up; it resets at midnight Pacific time."""


class AuthExpired(GatewayError):
    """The cached sign-in can no longer be refreshed (e.g. Testing-mode tokens expire after 7 days)."""
