"""The Owner's session (ADR-0019): a cookie naming the signed-in email, when it expires, and the session epoch it
was issued under, signed with HMAC. The epoch lives in the Store; Disconnect bumps it, which ends every copy of
every earlier session cookie at once. Nothing else is kept server-side."""
import base64
import hashlib
import hmac

from app.store.db import Store

COOKIE = "yde_session"
MAX_AGE_S = 30 * 24 * 3600
EPOCH = "session_epoch"  # the Store setting


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(secret: str, payload: str) -> str:
    return _b64(hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest())


def same(a: str, b: str) -> bool:
    """Constant-time comparison that also copes with non-ASCII input (an altered cookie or state)."""
    return hmac.compare_digest(a.encode(), b.encode())


def current_epoch(store: Store) -> int:
    return int(store.get_setting(EPOCH) or 0)


def end_all(store: Store) -> None:
    """Invalidate every session issued so far."""
    store.set_setting(EPOCH, str(current_epoch(store) + 1))


def issue(secret: str, email: str, now: float, epoch: int) -> str:
    payload = f"{_b64(email.encode())}.{int(now) + MAX_AGE_S}.{epoch}"
    return f"{payload}.{_sign(secret, payload)}"


def verify(secret: str, value: str | None, now: float, epoch: int) -> str | None:
    """The session's email, or None if the cookie is missing, altered, expired or from an ended epoch."""
    try:
        email_b64, expires, cookie_epoch, signature = (value or "").split(".")
        payload = f"{email_b64}.{expires}.{cookie_epoch}"
        if not same(signature, _sign(secret, payload)) or int(expires) < now or int(cookie_epoch) != epoch:
            return None
        return _unb64(email_b64).decode()
    except ValueError:  # includes a malformed cookie and non-UTF-8 content
        return None


def is_owner(email: str, owner_email: str | None) -> bool:
    """Whether `email` is the Owner's; anyone counts when no owner is set (local mode)."""
    return owner_email is None or email.casefold() == owner_email.casefold()
