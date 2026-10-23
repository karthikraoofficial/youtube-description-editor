import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

import time
from collections.abc import Callable

from app import session
from app.api import auth, changesets, preview, runs, videos
from app.backups import BackupArchive, BlobArchive, LocalFileArchive
from app.changesets import Changesets
from app.config import CLIENT_HEADER, CLIENT_HEADER_VALUE, REPO_ROOT, Settings
from app.connection import Connection
from app.log_redaction import configure_logging
from app.quota import QuotaLedger
from app.runs import Runs
from app.shorts import FakeShortsProber, HttpShortsProber, ShortsProber
from app.store.db import open_store
from app.token_box import TokenBox
from app.sync import Syncer
from app.youtube.fake import FakeGateway, FakeGatewayProvider, sample_videos
from app.youtube.gateway import GatewayProvider

MUTATING_METHODS = ("POST", "PUT", "PATCH", "DELETE")
PUBLIC_PATHS = ("/api/health", "/api/auth/login", "/api/auth/callback")  # reachable without a session


def default_provider(settings: Settings) -> GatewayProvider:
    if settings.fake:
        gateway = FakeGateway()
        gateway.videos = sample_videos()
        return FakeGatewayProvider(gateway)
    from app.youtube.google import GoogleGatewayProvider  # keeps Google libs out of fake mode and tests

    return GoogleGatewayProvider.from_settings(settings)


def default_prober(settings: Settings) -> ShortsProber:
    if settings.fake:
        # Fake mode: the sample channel marks its Shorts in the title.
        return FakeShortsProber({v.id: "#Shorts" in v.title for v in sample_videos()})
    return HttpShortsProber()


def check_safeguards(settings: Settings) -> None:
    """A deployment (an https address, or a session secret) must have every safeguard, or it doesn't start:
    otherwise the API would be open, anyone could sign in, or the Google token would be stored readable."""
    if not (settings.session_secret or settings.public_url.startswith("https://")):
        return  # local mode
    missing = [name for name, ok in (
        ("YDE_SESSION_SECRET", settings.session_secret),
        ("YDE_OWNER_EMAIL", settings.owner_email),
        ("YDE_TOKEN_KEY", settings.token_key),
        ("an https YDE_PUBLIC_URL", settings.public_url.startswith("https://")),
    ) if not ok]
    if missing:
        raise ValueError(f"Deployed without {', '.join(missing)}: refusing to start (ADR-0019).")


def default_archive(settings: Settings) -> BackupArchive:
    return BlobArchive() if settings.blob_backups else LocalFileArchive(settings.backups_dir)


def create_app(settings: Settings | None = None, provider: GatewayProvider | None = None,
               prober: ShortsProber | None = None, clock: Callable[[], float] | None = None,
               archive: BackupArchive | None = None) -> FastAPI:
    """`provider`, `prober`, `clock` and `archive` are the dependency overrides: tests pass fakes, and a clock
    they move by hand for Run leases and Step budgets."""
    settings = settings or Settings()
    check_safeguards(settings)
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    store = open_store(settings)
    ledger = QuotaLedger(store)
    connection = Connection(provider or default_provider(settings), store, ledger, TokenBox(settings.token_key))
    clock = clock or time.time

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
    app.state.clock = clock
    app.state.syncer = Syncer(store, prober or default_prober(settings))
    app.state.changesets = Changesets(store)
    app.state.runs = Runs(store, connection, ledger, archive or default_archive(settings), clock=clock)

    @app.middleware("http")
    async def require_owner_session(request: Request, call_next):
        # With a session secret (the cloud), only the Owner's signed session reaches the API (ADR-0019).
        if settings.session_secret and request.url.path.startswith("/api/") \
                and request.url.path not in PUBLIC_PATHS:
            email = session.verify(settings.session_secret, request.cookies.get(session.COOKIE), clock(),
                                   await run_in_threadpool(session.current_epoch, store))
            if email is None or not session.is_owner(email, settings.owner_email):
                return JSONResponse({"detail": "Sign in first."}, status_code=401)
        return await call_next(request)

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
    app.include_router(preview.router)
    app.include_router(changesets.router)
    app.include_router(runs.router)
    return app


def create_app_from_env() -> FastAPI:
    """Entry point for `uvicorn --factory app.main:create_app_from_env`; dev.py sets YDE_FAKE=1 for fake mode."""
    configure_logging()
    if os.environ.get("YDE_FAKE") == "1":
        # Fake mode keeps its own database so fake videos never mix with the real channel's.
        return create_app(Settings(data_dir=REPO_ROOT / "data" / "fake", fake=True,
                                   public_url=os.environ.get("YDE_PUBLIC_URL") or Settings.public_url))
    return create_app(settings_from_env())


def settings_from_env() -> Settings:
    env = lambda name: os.environ.get(name) or None  # noqa: E731 - an empty variable counts as unset
    return Settings(
        database_url=env("DATABASE_URL"),  # Postgres instead of SQLite (ADR-0016)
        # A connected Vercel Blob store (a token, or OIDC with a store id) takes the Backup copies (ADR-0018).
        blob_backups=bool(env("BLOB_READ_WRITE_TOKEN") or env("BLOB_STORE_ID")),
        # Owner sign-in (ADR-0019)
        public_url=env("YDE_PUBLIC_URL") or Settings.public_url,
        owner_email=env("YDE_OWNER_EMAIL"),
        session_secret=env("YDE_SESSION_SECRET"),
        token_key=env("YDE_TOKEN_KEY"),
        google_client_id=env("GOOGLE_CLIENT_ID"),
        google_client_secret=env("GOOGLE_CLIENT_SECRET"),
    )
