"""Start the backend and frontend together and open the browser.

    python dev.py            # real YouTube (needs data/client_secret.json)
    python dev.py --fake     # in-memory fake YouTube, no Google calls
    python dev.py --no-browser
    python dev.py --reload   # restart the backend when its code changes (development)
"""
import argparse
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
BACKEND_URL = "http://127.0.0.1:8000/api/health"
FRONTEND_URL = "http://localhost:5173"


def venv_python() -> Path:
    for rel in ("Scripts/python.exe", "bin/python"):
        p = BACKEND / ".venv" / rel
        if p.exists():
            return p
    sys.exit(
        "Backend virtualenv not found. Set it up once:\n"
        "  cd backend\n  python -m venv .venv\n"
        "  .venv/Scripts/python -m pip install -e \".[dev]\"   (macOS/Linux: .venv/bin/python)"
    )


def npm() -> str:
    exe = shutil.which("npm") or shutil.which("npm.cmd")
    if not exe:
        sys.exit("npm not found. Install Node.js 20+.")
    return exe


def wait_for(url: str, timeout: float = 60) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fake", action="store_true", help="use the in-memory fake YouTube")
    ap.add_argument("--no-browser", action="store_true", help="don't open the browser")
    ap.add_argument("--reload", action="store_true",
                    help="restart the backend on code changes (can hang on Windows; off by default)")
    args = ap.parse_args()

    py = venv_python()
    if not (FRONTEND / "node_modules").exists():
        print("Installing frontend dependencies…")
        subprocess.run([npm(), "install", "--no-fund", "--no-audit"], cwd=FRONTEND, check=True)

    env = {**os.environ, "YDE_FAKE": "1" if args.fake else "0"}
    procs = [
        subprocess.Popen([str(py), "-m", "uvicorn", "--factory", "app.main:create_app_from_env",
                          "--host", "127.0.0.1", "--port", "8000",
                          *(["--reload", "--reload-dir", "app"] if args.reload else [])],
                         cwd=BACKEND, env=env),
        subprocess.Popen([npm(), "run", "dev"], cwd=FRONTEND, env=env),
    ]
    try:
        if not wait_for(BACKEND_URL):
            print("Backend did not become healthy within 60 s.")
            return 1
        if not wait_for(FRONTEND_URL):
            print("Frontend did not start within 60 s.")
            return 1
        print(f"\n  YouTube Description Editor running at {FRONTEND_URL}"
              f"{'  (FAKE MODE)' if args.fake else ''}\n  Press Ctrl+C to stop.\n")
        if not args.no_browser:
            webbrowser.open(FRONTEND_URL)
        while all(p.poll() is None for p in procs):
            time.sleep(0.5)
        return 1
    except KeyboardInterrupt:
        return 0
    finally:
        for p in procs:
            if p.poll() is None:
                p.terminate()
        for p in procs:
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()


if __name__ == "__main__":
    sys.exit(main())
