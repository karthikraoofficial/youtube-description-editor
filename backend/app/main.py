import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.config import CLIENT_HEADER, CLIENT_HEADER_VALUE, Settings
from app.log_redaction import configure_logging
from app.youtube.fake import FakeGateway

MUTATING_METHODS = ("POST", "PUT", "PATCH", "DELETE")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)

    app = FastAPI(title="YouTube Description Editor", docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.state.settings = settings
    # The real gateway arrives with the Connect feature; fake mode never talks to Google.
    app.state.gateway = FakeGateway() if settings.fake else None

    @app.middleware("http")
    async def require_client_header(request: Request, call_next):
        # Browsers can't add a custom header cross-origin without a CORS preflight we refuse,
        # so this blocks other web pages from driving the local API (ADR-0006).
        if request.method in MUTATING_METHODS and request.headers.get(CLIENT_HEADER) != CLIENT_HEADER_VALUE:
            return JSONResponse({"detail": "missing client header"}, status_code=403)
        return await call_next(request)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_methods=["GET", *MUTATING_METHODS],
        allow_headers=["Content-Type", CLIENT_HEADER],
    )
    # Rejects DNS-rebinding requests whose Host isn't this machine (ADR-0006).
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(settings.allowed_hosts))

    @app.get("/api/health")
    def health(request: Request):
        return {"status": "ok", "fake": isinstance(request.app.state.gateway, FakeGateway)}

    return app


def create_app_from_env() -> FastAPI:
    """Entry point for `uvicorn --factory app.main:create_app_from_env`; dev.py sets YDE_FAKE=1 for fake mode."""
    configure_logging()
    return create_app(Settings(fake=os.environ.get("YDE_FAKE") == "1"))
