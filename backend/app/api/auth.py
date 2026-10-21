from fastapi import APIRouter, HTTPException, Request

from app.connection import Connection, SignInInProgress, Status
from app.youtube.errors import AuthExpired, GatewayError

router = APIRouter(prefix="/api/auth")


def _connection(request: Request) -> Connection:
    return request.app.state.connection


def _body(status: Status) -> dict:
    ch = status.channel
    return {
        "state": status.state,
        "channel": {"id": ch.id, "title": ch.title, "avatar_url": ch.avatar_url} if ch else None,
    }


@router.get("/status")
def status(request: Request):
    connection = _connection(request)
    try:
        return _body(connection.status())
    except AuthExpired:
        return _body(connection.status())  # now reports "expired"
    except GatewayError as e:
        raise HTTPException(502, str(e)) from e


@router.post("/connect")
def connect(request: Request):
    connection = _connection(request)
    if not connection.has_client_secret():
        raise HTTPException(409, "data/client_secret.json is missing. See the README's Google Cloud setup.")
    try:
        return _body(connection.connect())
    except SignInInProgress as e:
        raise HTTPException(409, "A Google sign-in is already in progress.") from e
    except GatewayError as e:
        raise HTTPException(502, str(e)) from e


@router.post("/disconnect")
def disconnect(request: Request):
    return _body(_connection(request).disconnect())
