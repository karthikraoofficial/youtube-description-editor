"""Cloud mode serves the built frontend and the API from one app (ADR-0021)."""
import dataclasses
import html
import importlib.util
import json
import pathlib

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.main import create_app
from app.shorts import FakeShortsProber

from .conftest import TEST_DATABASE_URL, FakeClock


def built_frontend(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>Description Editor</title>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log('hi')", encoding="utf-8")
    return dist


def test_the_frontend_and_the_api_are_served_together(settings, provider, tmp_path):
    app = create_app(settings, provider=provider, prober=FakeShortsProber(default=False), clock=FakeClock(),
                     frontend_dir=built_frontend(tmp_path))
    with TestClient(app, base_url="http://127.0.0.1") as c:
        page = c.get("/")
        assert page.status_code == 200 and "Description Editor" in page.text
        assert c.get("/assets/app.js").status_code == 200
        assert c.get("/api/health").json()["status"] == "ok"


def test_the_frontend_shell_needs_no_session_but_the_api_does(settings, provider, tmp_path):
    cloud = dataclasses.replace(settings, public_url="https://127.0.0.1", owner_email="owner@example.com",
                                session_secret="s" * 32, token_key=Fernet.generate_key().decode())
    app = create_app(cloud, provider=provider, prober=FakeShortsProber(default=False), clock=FakeClock(),
                     frontend_dir=built_frontend(tmp_path))
    with TestClient(app, base_url="https://127.0.0.1") as c:
        assert c.get("/").status_code == 200  # the sign-in page itself has to load
        assert c.get("/api/videos").status_code == 401


@pytest.mark.skipif(not TEST_DATABASE_URL, reason="set YDE_TEST_DATABASE_URL: cloud mode needs Postgres")
def test_the_vercel_entrypoint_builds_the_cloud_app_from_the_environment(monkeypatch):
    entry = pathlib.Path(__file__).resolve().parents[2] / "index.py"
    for name, value in {"YDE_PUBLIC_URL": "https://127.0.0.1", "YDE_OWNER_EMAIL": "owner@example.com",
                        "YDE_SESSION_SECRET": "s" * 32, "YDE_TOKEN_KEY": Fernet.generate_key().decode(),
                        "DATABASE_URL": TEST_DATABASE_URL, "BLOB_STORE_ID": "store_test"}.items():
        monkeypatch.setenv(name, value)
    spec = importlib.util.spec_from_file_location("vercel_index", entry)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    with TestClient(module.app, base_url="https://127.0.0.1") as c:
        assert c.get("/api/health").json()["status"] == "ok"
        assert c.get("/api/videos").status_code == 401
        assert c.get("/api/health", headers={"host": "evil.example"}).status_code == 400


def test_a_vercel_deployment_without_cloud_settings_refuses_to_start(monkeypatch):
    """A Preview deployment gets no YDE_* variables but may get the production database: it must not start."""
    from app.main import settings_from_env

    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@db.example/yde")
    monkeypatch.delenv("YDE_PUBLIC_URL", raising=False)
    with pytest.raises(ValueError, match="YDE_PUBLIC_URL"):
        settings_from_env()


def test_cloud_mode_without_a_frontend_build_refuses_to_start(settings, provider, tmp_path):
    cloud = dataclasses.replace(settings, public_url="https://127.0.0.1", owner_email="owner@example.com",
                                session_secret="s" * 32, token_key=Fernet.generate_key().decode())
    with pytest.raises(RuntimeError, match="frontend"):
        create_app(cloud, provider=provider, frontend_dir=tmp_path / "no-build-here")


def test_the_privacy_policy_and_terms_are_public(settings, provider):
    """Google's consent screen links to them, so anyone must be able to read them without signing in."""
    public = pathlib.Path(__file__).resolve().parents[2] / "frontend" / "public"
    cloud = dataclasses.replace(settings, public_url="https://127.0.0.1", owner_email="owner@example.com",
                                session_secret="s" * 32, token_key=Fernet.generate_key().decode())
    app = create_app(cloud, provider=provider, prober=FakeShortsProber(default=False), clock=FakeClock(),
                     frontend_dir=public)
    with TestClient(app, base_url="https://127.0.0.1") as c:
        privacy, terms = c.get("/privacy.html"), c.get("/terms.html")
    assert privacy.status_code == 200 and "Limited Use" in privacy.text
    assert terms.status_code == 200 and "Terms" in terms.text


def test_how_it_works_and_its_screenshots_are_public(settings, provider):
    """Visitors see How It Works before signing in, so the page and every screenshot it shows need no session."""
    public = pathlib.Path(__file__).resolve().parents[2] / "frontend" / "public"
    content = json.loads((public.parent / "src" / "lib" / "howItWorksSteps.json").read_text(encoding="utf-8"))
    steps = content["steps"]
    cloud = dataclasses.replace(settings, public_url="https://127.0.0.1", owner_email="owner@example.com",
                                session_secret="s" * 32, token_key=Fernet.generate_key().decode())
    app = create_app(cloud, provider=provider, prober=FakeShortsProber(default=False), clock=FakeClock(),
                     frontend_dir=public)
    with TestClient(app, base_url="https://127.0.0.1") as c:
        page = c.get("/how-it-works.html")
        images = [c.get(f"/how-it-works/{s['image']}") for s in steps]
    assert page.status_code == 200 and html.escape(content["heading"]) in page.text
    assert len(steps) >= 5
    for step, image in zip(steps, images):
        assert image.status_code == 200 and image.headers["content-type"] == "image/png", step["image"]
        assert step["image"] in page.text and html.escape(step["caption"]) in page.text
