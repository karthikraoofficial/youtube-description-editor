"""Owner sign-in through Google's web flow (ADR-0019). The browser goes to /login, Google sends it back to
/callback, and the callback returns it to the app, with `?signin_error=<reason>` if something went wrong."""
import secrets
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, Response

from app import session
from app.connection import ChannelUnavailable, Connection, NotOwner, Status
from app.youtube.errors import AuthExpired, GatewayError

router = APIRouter(prefix="/api/auth")

STATE_COOKIE = "yde_oauth_state"
STATE_MAX_AGE_S = 600  # time allowed on Google's pages
REFUSED_COOKIE = "yde_refused_account"  # tells the refused browser, and only it, which account Google reported


def _connection(request: Request) -> Connection:
    return request.app.state.connection


def _body(status: Status) -> dict:
    ch = status.channel
    return {
        "state": status.state,
        "channel": {"id": ch.id, "title": ch.title, "avatar_url": ch.avatar_url} if ch else None,
    }


def _redirect_uri(request: Request) -> str:
    return request.app.state.settings.public_url.rstrip("/") + "/api/auth/callback"


def _cookie_flags(request: Request) -> dict:
    """Script can't read the cookies, other sites' requests don't carry them, and https sends them only over TLS."""
    return {"httponly": True, "samesite": "lax", "secure": request.app.state.settings.cloud}


def _back_to_app(error: str | None = None) -> RedirectResponse:
    return RedirectResponse("/" if error is None else f"/?signin_error={error}", status_code=302)


@router.get("/status")
def status(request: Request):
    connection = _connection(request)
    try:
        return _body(connection.status())
    except AuthExpired:
        return _body(connection.status())  # now reports "expired"
    except GatewayError as e:
        raise HTTPException(502, str(e)) from e


@router.get("/login")
def login(request: Request):
    """Send the browser to Google. The state cookie ties Google's answer to this browser."""
    connection = _connection(request)
    if not connection.has_client_secret():
        return _back_to_app("no_client_secret")
    state = secrets.token_urlsafe(24)
    response = RedirectResponse(connection.sign_in_url(state, _redirect_uri(request)), status_code=302)
    response.set_cookie(STATE_COOKIE, state, max_age=STATE_MAX_AGE_S, path="/api/auth", **_cookie_flags(request))
    return response


@router.get("/callback")
def callback(request: Request, state: str = "", code: str | None = None, error: str | None = None):
    """Google's answer. Only the Owner gets a session; anyone else leaves nothing behind."""
    expected = request.cookies.get(STATE_COOKIE)
    if not expected or not session.same(state, expected):
        return _clear_state(_back_to_app("state"))
    if error or not code:
        return _clear_state(_back_to_app("access_denied" if error == "access_denied" else "google"))
    settings = request.app.state.settings
    try:
        email = _connection(request).complete_sign_in(code, _redirect_uri(request), settings.owner_email)
    except NotOwner as e:
        # In a cookie rather than the URL, so it never reaches access logs; the sign-in page reads it once.
        response = _clear_state(_back_to_app("not_allowed"))
        flags = {**_cookie_flags(request), "httponly": False}  # the page's script must read it
        response.set_cookie(REFUSED_COOKIE, quote(e.email, safe=""), max_age=120, **flags)
        return response
    except ChannelUnavailable:
        return _clear_state(_back_to_app("channel"))
    except GatewayError:
        return _clear_state(_back_to_app("google"))
    response = _clear_state(_back_to_app())
    if settings.session_secret:
        cookie = session.issue(settings.session_secret, email, request.app.state.clock(),
                               session.current_epoch(request.app.state.store))
        response.set_cookie(session.COOKIE, cookie, max_age=session.MAX_AGE_S, **_cookie_flags(request))
    return response


@router.post("/disconnect")
def disconnect(request: Request, response: Response):
    """Withdraw Google's grant, forget the credentials, and end the session."""
    body = _body(_connection(request).disconnect())
    session.end_all(request.app.state.store)  # every copy of every session cookie, not just this browser's
    response.delete_cookie(session.COOKIE, **_cookie_flags(request))
    return body


def _clear_state(response: RedirectResponse) -> RedirectResponse:
    response.delete_cookie(STATE_COOKIE, path="/api/auth")
    return response
