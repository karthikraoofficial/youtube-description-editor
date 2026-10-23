"""Vercel's entrypoint (ADR-0021): the whole app, API and built frontend, as one Python function.

Vercel finds `app` here, installs the backend package from requirements.txt, and runs the frontend build first
(vercel.json). Every setting comes from the project's environment variables; see the README's deploy section.
"""
from pathlib import Path

from app.main import create_app_from_env

app = create_app_from_env(frontend_dir=Path(__file__).parent / "frontend" / "dist")
