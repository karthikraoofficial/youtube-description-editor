class GatewayError(Exception):
    """YouTube or Google rejected a request. The message is safe to show and log (no secrets)."""


class AuthExpired(GatewayError):
    """The cached sign-in can no longer be refreshed (e.g. Testing-mode tokens expire after 7 days)."""
