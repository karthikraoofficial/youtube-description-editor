"""The exact HTTP requests GoogleGateway sends for reads and writes, with the network replaced by a recorder."""
import json
from urllib.parse import parse_qs, urlparse

import httplib2

from app.youtube.google import GoogleGateway


class RecordingHttp:
    """Stands in for httplib2.Http: records each request and returns canned JSON."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def request(self, uri, method="GET", body=None, headers=None, **_kwargs):
        self.requests.append({"uri": uri, "method": method, "body": body})
        return httplib2.Response({"status": "200"}), json.dumps(self.responses.pop(0)).encode()


def gateway_with(responses):
    http = RecordingHttp(responses)
    return GoogleGateway(credentials=None, http=http), http


def test_update_sends_part_snippet_with_the_id_and_the_snippet_body():
    gw, http = gateway_with([{"id": "abc"}])
    body = {"title": "T", "description": "New", "categoryId": "10", "tags": ["a"]}

    gw.update_snippet("abc", body)

    [req] = http.requests
    url = urlparse(req["uri"])
    assert (req["method"], url.path) == ("PUT", "/youtube/v3/videos")
    assert parse_qs(url.query)["part"] == ["snippet"]
    assert json.loads(req["body"]) == {"id": "abc", "snippet": body}


def test_fresh_fetch_asks_for_snippet_and_status_and_keeps_the_raw_snippet():
    raw = {"title": "T", "description": "Old", "categoryId": "10", "localized": {"title": "T"}}
    gw, http = gateway_with([{"items": [{"id": "abc", "snippet": raw, "status": {"privacyStatus": "public"}}]}])

    [snap] = gw.get_snippets(["abc", "def"])

    query = parse_qs(urlparse(http.requests[0]["uri"]).query)
    assert (query["part"], query["id"]) == (["snippet,status"], ["abc,def"])
    assert (snap.id, snap.snippet, snap.privacy_status) == ("abc", raw, "public")


def test_quota_exceeded_is_recognised_from_youtubes_error_reason():
    import pytest

    from app.youtube.errors import QuotaExceeded

    class ErrorHttp(RecordingHttp):
        def request(self, uri, method="GET", body=None, headers=None, **_kwargs):
            err = {"error": {"code": 403, "message": "quota", "errors": [{"reason": "quotaExceeded"}]}}
            return httplib2.Response({"status": "403"}), json.dumps(err).encode()

    gw = GoogleGateway(credentials=None, http=ErrorHttp([]))
    with pytest.raises(QuotaExceeded):
        gw.update_snippet("abc", {"title": "T", "description": "d", "categoryId": "10"})
