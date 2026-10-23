"""Google implementations of the gateway. Never log credentials objects or token values."""
import json
import logging
import re
from typing import TYPE_CHECKING

import httplib2
import httpx
from google.auth.exceptions import GoogleAuthError, RefreshError, TransportError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from oauthlib.oauth2.rfc6749.errors import OAuth2Error

if TYPE_CHECKING:
    from app.config import Settings

from app.youtube.errors import AuthExpired, GatewayError, PlaylistNotFound, QuotaExceeded, RetryableError
from app.youtube.gateway import Channel, FreshSnippet, SignIn, UploadsPage, VideoDetails

# Identity (who is signing in: only the Owner may) and YouTube, in one consent (ADR-0019).
SCOPES = ["openid", "https://www.googleapis.com/auth/userinfo.email",
          "https://www.googleapis.com/auth/youtube.force-ssl"]
TOKEN_URI = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
# Socket errors (dropped connection, timeout, SSL), DNS failure, and a token refresh that couldn't
# reach Google. HttpError is not among them: YouTube answered, so _execute maps it by status.
NETWORK_ERRORS = (OSError, httplib2.HttpLib2Error, TransportError)

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
            return self._send(request)
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

    @staticmethod
    def _send(request):
        """Sends the request, retrying once on a network error. The HTTPS connection is kept open
        between requests, and it goes stale when the PC sleeps or changes network; closing it makes
        the retry open a fresh one. Retrying is safe for writes too: an update sends the full snippet."""
        for attempt in (1, 2):
            try:
                return request.execute()
            except NETWORK_ERRORS as e:
                close = getattr(request.http, "close", None)
                if close:
                    close()
                if attempt == 2:
                    raise RetryableError(f"Couldn't reach YouTube ({type(e).__name__})") from e

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
    """Google's web sign-in flow for a Web OAuth client (ADR-0019). The client comes from GOOGLE_CLIENT_ID and
    GOOGLE_CLIENT_SECRET, or from data/client_secret.json. Credentials are handed back to the app to store."""

    def __init__(self, client_config: dict | None) -> None:
        self._config = client_config  # {"web": {...}}, or None when no client is set up

    @classmethod
    def from_settings(cls, settings: "Settings") -> "GoogleGatewayProvider":
        if settings.google_client_id and settings.google_client_secret:
            return cls({"web": {"client_id": settings.google_client_id, "client_secret": settings.google_client_secret,
                                "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": TOKEN_URI}})
        path = settings.client_secret_path
        if not path.exists():
            return cls(None)
        config = json.loads(path.read_text(encoding="utf-8"))
        return cls(config if "web" in config else None)  # a Desktop ("installed") client can't do the web flow

    def has_client_secret(self) -> bool:
        return self._config is not None

    def _flow(self, redirect_uri: str) -> Flow:
        # No PKCE: this is a confidential client (it has a secret), and the state cookie ties the callback to
        # the browser that started it.
        return Flow.from_client_config(self._config, scopes=SCOPES, redirect_uri=redirect_uri,
                                       autogenerate_code_verifier=False)

    def authorization_url(self, state: str, redirect_uri: str) -> str:
        url, _ = self._flow(redirect_uri).authorization_url(state=state, access_type="offline", prompt="consent")
        return url

    def exchange_code(self, code: str, redirect_uri: str) -> SignIn:
        flow = self._flow(redirect_uri)
        try:
            flow.fetch_token(code=code)
            creds = flow.credentials
            claims = id_token.verify_oauth2_token(creds.id_token, Request(), self._config["web"]["client_id"])
        except OAuth2Error as e:
            raise GatewayError(f"Google sign-in failed: {e.error}") from e
        except (GoogleAuthError, ValueError, KeyError) as e:
            raise GatewayError(f"Google sign-in failed: {type(e).__name__}") from e
        return SignIn(email=claims.get("email", ""), email_verified=bool(claims.get("email_verified")),
                      credentials_json=creds.to_json())

    def gateway_for(self, credentials_json: str) -> tuple[GoogleGateway, str | None]:
        try:
            creds = Credentials.from_authorized_user_info(json.loads(credentials_json), SCOPES)
        except (ValueError, KeyError) as e:
            raise AuthExpired("Stored Google sign-in is unreadable") from e
        if creds.valid:
            return GoogleGateway(creds), None
        if not creds.refresh_token:
            raise AuthExpired("Google sign-in expired")
        try:
            creds.refresh(Request())
        except RefreshError as e:
            raise AuthExpired("Google sign-in expired") from e
        return GoogleGateway(creds), creds.to_json()

    def revoke(self, credentials_json: str) -> None:
        try:
            creds = json.loads(credentials_json)
            token = creds.get("refresh_token") or creds.get("token")
            if token:
                resp = httpx.post(REVOKE_URL, data={"token": token}, timeout=10)
                if resp.status_code != 200:
                    log.warning("Google did not confirm the token revoke (HTTP %s)", resp.status_code)
        except (ValueError, httpx.HTTPError):
            log.warning("Could not revoke the Google token")
