import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api import auth, videos
from app.config import CLIENT_HEADER, CLIENT_HEADER_VALUE, REPO_ROOT, Settings
from app.connection import Connection
from app.log_redaction import configure_logging
from app.quota import QuotaLedger
from app.store.db import Store
from app.sync import Syncer
from app.youtube.fake import FakeGateway, FakeGatewayProvider, sample_videos
from app.youtube.gateway import GatewayProvider

MUTATING_METHODS = ("POST", "PUT", "PATCH", "DELETE")


def default_provider(settings: Settings) -> GatewayProvider:
    if settings.fake:
        gateway = FakeGateway()
        gateway.videos = sample_videos()
        return FakeGatewayProvider(gateway)
    from app.youtube.google import GoogleGatewayProvider  # keeps Google libs out of fake mode and tests

    return GoogleGatewayProvider(settings.client_secret_path, settings.token_path)


def create_app(settings: Settings | None = None, provider: GatewayProvider | None = None) -> FastAPI:
    """`provider` is the gateway dependency override: tests pass a FakeGatewayProvider."""
    settings = settings or Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    store = Store(settings.db_path)
    ledger = QuotaLedger(store)
    connection = Connection(provider or default_provider(settings), store, ledger)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        connection.restore()
        yield

    app = FastAPI(title="YouTube Description Editor", docs_url="/api/docs",
                  openapi_url="/api/openapi.json", lifespan=lifespan)
    app.state.settings = settings
    app.state.store = store
    app.state.connection = connection
    app.state.ledger = ledger
    app.state.syncer = Syncer(store)

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
    def health():
        return {"status": "ok", "fake": settings.fake}

    app.include_router(auth.router)
    app.include_router(videos.router)
    return app


def create_app_from_env() -> FastAPI:
    """Entry point for `uvicorn --factory app.main:create_app_from_env`; dev.py sets YDE_FAKE=1 for fake mode."""
    configure_logging()
    if os.environ.get("YDE_FAKE") == "1":
        # Fake mode keeps its own database so fake videos never mix with the real channel's.
        return create_app(Settings(data_dir=REPO_ROOT / "data" / "fake", fake=True))
    return create_app(Settings())
