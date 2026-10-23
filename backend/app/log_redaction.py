"""Logging that never prints credentials: Google's, the Blob token, a database password (ADR-0006)."""
import logging
import re

_PATTERNS = [
    re.compile(r"GOCSPX-[A-Za-z0-9_\-]+"),  # OAuth client secret
    re.compile(r"ya29\.[A-Za-z0-9_\-\.]+"),  # access token
    re.compile(r"1//0[A-Za-z0-9_\-]+"),  # refresh token
    re.compile(r"vercel_blob_rw_[A-Za-z0-9_\-]+"),  # Vercel Blob read-write token
    re.compile(r"(\bBearer\s+)[A-Za-z0-9_\-\.]+"),  # any token in an Authorization header
    re.compile(r"(\bpostgres(?:ql)?://[^:/@\s]+:)[^@\s]+(?=@)"),  # a database URL's password
    # Whole-word keys only, so status_code= or token_path= are left alone.
    re.compile(r"(\b(?:client_secret|refresh_token|access_token|id_token|token|code)\b[\"']?\s*[:=]\s*[\"']?)"
               r"[^\s\"'&,}]+", re.IGNORECASE),
]

# Loggers that don't propagate to root (uvicorn.access) or that may echo URLs with auth codes.
_DIRECT_LOGGERS = ("uvicorn", "uvicorn.error", "uvicorn.access")


def redact(text: str) -> str:
    for p in _PATTERNS:
        text = p.sub(lambda m: (m.group(1) if m.groups() else "") + "[REDACTED]", text)
    return text


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Redact the format string and each string arg in place: some formatters (uvicorn.access)
        # read record.args directly, so they must keep their shape.
        if isinstance(record.msg, str):
            record.msg = redact(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(redact(a) if isinstance(a, str) else a for a in record.args)
        elif isinstance(record.args, dict):
            record.args = {k: redact(v) if isinstance(v, str) else v for k, v in record.args.items()}
        if record.exc_info:
            # Format the traceback now so it can be redacted, then drop the raw exception.
            record.exc_text = logging.Formatter().formatException(record.exc_info)
            record.exc_info = None
        if record.exc_text:
            record.exc_text = redact(record.exc_text)
        return True


def configure_logging(level: int = logging.INFO) -> None:
    redacting = RedactingFilter()
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    handler.addFilter(redacting)
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    # Logger-level filters run for records logged directly to these loggers, whatever handlers they use.
    for name in _DIRECT_LOGGERS:
        logging.getLogger(name).addFilter(redacting)
    for name in ("googleapiclient.discovery", "urllib3", "oauthlib", "requests_oauthlib"):
        logging.getLogger(name).setLevel(logging.WARNING)
