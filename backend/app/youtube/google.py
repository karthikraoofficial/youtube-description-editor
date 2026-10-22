"""Google implementations of the gateway. Never log credentials objects or token values."""
import logging
import re
from pathlib import Path

import httpx
from google.auth.exceptions import GoogleAuthError, RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from oauthlib.oauth2.rfc6749.errors import OAuth2Error

from app.youtube.errors import AuthExpired, GatewayError, PlaylistNotFound, QuotaExceeded, RetryableError
from app.youtube.gateway import Channel, FreshSnippet, UploadsPage, VideoDetails

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
SIGN_IN_TIMEOUT_S = 180

log = logging.getLogger(__name__)


class GoogleGateway:
    def __init__(self, credentials: Credentials | None, http=None) -> None:
        """`http` replaces the network in tests; normally the credentials' own authorized HTTP is used."""
        if http is not None:
            self._yt = build("youtube", "v3", http=http, cache_discovery=False, static_discovery=True)
        else:
            self._yt = build("youtube", "v3", credentials=credentials, cache_discovery=False)

    def _execute(self, request, not_found: type[GatewayError] = GatewayError):
        try:
            return request.execute()
        except RefreshError as e:
            raise AuthExpired("Google sign-in expired") from e
        except HttpError as e:
            reasons = {d.get("reason") for d in (e.error_details or []) if isinstance(d, dict)}
            if e.status_code == 403 and reasons & {"quotaExceeded", "dailyLimitExceeded"}:
                raise QuotaExceeded("YouTube's daily quota for this project is used up") from e
            if e.status_code >= 500 or e.status_code == 429 or (
                    e.status_code == 403 and reasons & {"rateLimitExceeded", "userRateLimitExceeded"}):
                raise RetryableError(f"YouTube API error {e.status_code}: {e.reason}") from e
            if e.status_code == 404:
                raise not_found(f"YouTube API error 404: {e.reason}") from e
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

    def list_uploads_page(self, playlist_id: str, page_token: str | None) -> UploadsPage:
        resp = self._execute(self._yt.playlistItems().list(
            part="contentDetails", playlistId=playlist_id, maxResults=50, pageToken=page_token),
            not_found=PlaylistNotFound)
        ids = [item["contentDetails"]["videoId"] for item in resp.get("items", [])]
        return UploadsPage(ids, resp.get("nextPageToken"))

    def get_videos(self, video_ids: list[str]) -> list[VideoDetails]:
        if not video_ids:
            return []
        resp = self._execute(self._yt.videos().list(
            part="snippet,contentDetails,status", id=",".join(video_ids)))
        return [_video_details(item) for item in resp.get("items", [])]


    def get_snippets(self, video_ids: list[str]) -> list[FreshSnippet]:
        if not video_ids:
            return []
        resp = self._execute(self._yt.videos().list(part="snippet,status", id=",".join(video_ids)))
        return [FreshSnippet(item["id"], item["snippet"], item.get("status", {}).get("privacyStatus", "private"))
                for item in resp.get("items", [])]

    def update_snippet(self, video_id: str, snippet: dict) -> None:
        self._execute(self._yt.videos().update(part="snippet", body={"id": video_id, "snippet": snippet}))


_DURATION = re.compile(r"^P(?:(\d+)W)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$")


def parse_iso_duration(iso: str) -> int:
    """ISO 8601 duration as used by YouTube (e.g. PT1H2M3S) to seconds; 0 if unparseable."""
    m = _DURATION.match(iso or "")
    if not m:
        return 0
    w, d, h, mi, s = (int(x) if x else 0 for x in m.groups())
    return (((w * 7 + d) * 24 + h) * 60 + mi) * 60 + s


def _video_details(item: dict) -> VideoDetails:
    sn = item["snippet"]
    thumbs = sn.get("thumbnails", {})
    thumb = (thumbs.get("medium") or thumbs.get("default") or {}).get("url")
    return VideoDetails(
        id=item["id"], title=sn["title"], description=sn.get("description", ""),
        category_id=sn.get("categoryId", ""), tags=tuple(sn.get("tags", [])),
        default_language=sn.get("defaultLanguage"), default_audio_language=sn.get("defaultAudioLanguage"),
        published_at=sn.get("publishedAt", ""),
        duration_s=parse_iso_duration(item.get("contentDetails", {}).get("duration", "")),
        privacy_status=item.get("status", {}).get("privacyStatus", "private"), thumbnail_url=thumb)


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
        except OAuth2Error as e:
            # e.g. access_denied when the owner presses Cancel on Google's consent page.
            raise GatewayError(f"Google sign-in failed: {e.error}") from e
        except (GoogleAuthError, ValueError) as e:
            raise GatewayError(f"Google sign-in failed: {type(e).__name__}") from e
        except AttributeError as e:
            # WSGITimeoutError (an AttributeError): Google never redirected back, which is what
            # happens when Google shows "Access blocked" because the account isn't a test user.
            raise GatewayError(
                "Google sign-in timed out. If Google said \"Access blocked\", add your account as a "
                "test user on the OAuth consent screen (see the README).") from e
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
