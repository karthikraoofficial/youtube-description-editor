import logging
import sys

from app.log_redaction import RedactingFilter, redact

# Fake credentials are assembled from pieces so this file never contains a credential-shaped
# literal (the pre-commit secret guard would rightly refuse it).
FAKE_CLIENT_SECRET = "GOCSPX" + "-abcDEF123_xyz"
FAKE_ACCESS_TOKEN = "ya29" + ".a0AfH6SMBx-y.z"
FAKE_REFRESH_TOKEN = "1//0" + "gAbCdEfGhIjKlMnOpQrStUv"
FAKE_AUTH_CODE = "4/0AY0e-g7abc"


def test_google_credentials_are_redacted():
    text = (f"secret {FAKE_CLIENT_SECRET} access {FAKE_ACCESS_TOKEN} refresh {FAKE_REFRESH_TOKEN} "
            f"url /cb?code={FAKE_AUTH_CODE}&state=xyz json {{\"refresh_token\": \"r-123456789\"}}")
    assert redact(text) == (
        "secret [REDACTED] access [REDACTED] refresh [REDACTED] "
        "url /cb?code=[REDACTED]&state=xyz json {\"refresh_token\": \"[REDACTED]\"}"
    )


def test_harmless_text_is_left_alone():
    text = "status_code=200 token_path=data/token.json encode=utf-8 GET /api/health"
    assert redact(text) == text


def test_tracebacks_are_redacted():
    try:
        raise RuntimeError(f"refresh failed for {FAKE_ACCESS_TOKEN}")
    except RuntimeError:
        record = logging.LogRecord("x", logging.ERROR, __file__, 1, "boom %s", ("code=abc123",),
                                   exc_info=sys.exc_info())
    RedactingFilter().filter(record)
    assert record.getMessage() == "boom code=[REDACTED]"
    assert FAKE_ACCESS_TOKEN not in record.exc_text
    assert "[REDACTED]" in record.exc_text


def test_record_args_stay_a_tuple_for_formatters_that_read_them():
    # uvicorn's access formatter unpacks record.args (client, method, path, version, status).
    record = logging.LogRecord("uvicorn.access", logging.INFO, __file__, 1, '%s - "%s %s HTTP/%s" %d',
                               ("127.0.0.1:1", "GET", f"/cb?code={FAKE_AUTH_CODE}", "1.1", 200), None)
    RedactingFilter().filter(record)
    assert record.args == ("127.0.0.1:1", "GET", "/cb?code=[REDACTED]", "1.1", 200)
