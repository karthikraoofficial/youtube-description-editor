"""Google implementations of the gateway. Never log credentials objects or token values."""
import logging
from pathlib import Path

import httpx
from google.auth.exceptions import GoogleAuthError, RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.youtube.errors import AuthExpired, GatewayError
from app.youtube.gateway import Channel

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
SIGN_IN_TIMEOUT_S = 300

log = logging.getLogger(__name__)


class GoogleGateway:
    def __init__(self, credentials: Credentials) -> None:
        self._yt = build("youtube", "v3", credentials=credentials, cache_discovery=False)

    def _execute(self, request):
        try:
            return request.execute()
        except RefreshError as e:
            raise AuthExpired("Google sign-in expired") from e
        except HttpError as e:
            raise GatewayError(f"YouTube API error {e.status_code}: {e.reason}") from e

    def get_my_channel(self) -> Channel:
        resp = self._execute(self._yt.channels().list(part="snippet,contentDetails", mine=True))
        items = resp.get("items") or []
        if not items:
            raise GatewayError("This Google account has no YouTube channel.")
        ch = items[0]
        thumbs = ch["snippet"].get("thumbnails", {})
        avatar = (thumbs.get("medium") or thumbs.get("default") or {}).get("url")
        return Channel(id=ch["id"], title=ch["snippet"]["title"], avatar_url=avatar,
                       uploads_playlist_id=ch["contentDetails"]["relatedPlaylists"]["uploads"])


class GoogleGatewayProvider:
    def __init__(self, client_secret_path: Path, token_path: Path) -> None:
        self._client_secret_path = client_secret_path
        self._token_path = token_path

    def has_client_secret(self) -> bool:
        return self._client_secret_path.exists()

    def connect(self) -> GoogleGateway:
        flow = InstalledAppFlow.from_client_secrets_file(str(self._client_secret_path), scopes=SCOPES)
        try:
            # Google redirects to this one-off local server, never to /api, so the auth code
            # never appears in our or Vite's request logs.
            creds = flow.run_local_server(
                port=0, open_browser=True, timeout_seconds=SIGN_IN_TIMEOUT_S,
                authorization_prompt_message="", success_message=(
                    "Connected to YouTube Description Editor. You can close this tab."),
                access_type="offline", prompt="consent")
        except (GoogleAuthError, ValueError) as e:
            raise GatewayError(f"Google sign-in failed: {type(e).__name__}") from e
        except AttributeError as e:
            # oauthlib's local server returns None on timeout, which surfaces as AttributeError.
            raise GatewayError("Google sign-in timed out. Please try again.") from e
        self._save(creds)
        log.info("Google sign-in completed")
        return GoogleGateway(creds)

    def restore(self) -> GoogleGateway | None:
        if not self._token_path.exists():
            return None
        try:
            creds = Credentials.from_authorized_user_file(str(self._token_path), SCOPES)
        except (ValueError, KeyError):
            raise AuthExpired("Cached Google sign-in is unreadable")
        if not creds.valid:
            if not creds.refresh_token:
                raise AuthExpired("Google sign-in expired")
            try:
                creds.refresh(Request())
            except RefreshError as e:
                raise AuthExpired("Google sign-in expired") from e
            self._save(creds)
        return GoogleGateway(creds)

    def disconnect(self) -> None:
        if self._token_path.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(self._token_path), SCOPES)
                token = creds.refresh_token or creds.token
                if token:
                    resp = httpx.post(REVOKE_URL, data={"token": token}, timeout=10)
                    if resp.status_code != 200:
                        log.warning("Google did not confirm the token revoke (HTTP %s); deleting it locally",
                                    resp.status_code)
            except (ValueError, KeyError, httpx.HTTPError):
                log.warning("Could not revoke the Google token; deleting it locally anyway")
            self._token_path.unlink(missing_ok=True)

    def _save(self, creds: Credentials) -> None:
        self._token_path.parent.mkdir(parents=True, exist_ok=True)
        self._token_path.write_text(creds.to_json(), encoding="utf-8")
        self._token_path.chmod(0o600)  # owner-only where the OS supports it
