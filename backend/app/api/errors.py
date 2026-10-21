from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import HTTPException

from app.connection import Connection, NotConnected
from app.youtube.errors import AuthExpired, GatewayError


CONNECT_FIRST = "Connect your channel first."
SIGN_IN_EXPIRED = "Your Google sign-in expired. Sign in again."


@contextmanager
def youtube_errors(connection: Connection) -> Iterator[None]:
    """Map gateway failures to HTTP: 409 not connected, 401 sign-in expired, 502 YouTube error."""
    try:
        yield
    except NotConnected as e:
        raise HTTPException(409, CONNECT_FIRST) from e
    except AuthExpired as e:
        connection.mark_expired()
        raise HTTPException(401, SIGN_IN_EXPIRED) from e
    except GatewayError as e:
        raise HTTPException(502, str(e)) from e
