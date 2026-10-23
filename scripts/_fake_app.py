"""Shared by the screenshot scripts: they press Apply, so they must only ever drive the fake YouTube."""
import json
import sys
import urllib.request

BASE = "http://localhost:5173"
HEALTH = "http://127.0.0.1:8000/api/health"


def require_fake_app() -> None:
    """Exit unless the app is running in fake mode."""
    try:
        with urllib.request.urlopen(HEALTH, timeout=5) as resp:
            fake = json.load(resp).get("fake")
    except OSError:
        sys.exit("The app isn't answering at :8000. Start `python dev.py --fake` first.")
    if not fake:
        sys.exit("The app at :8000 is not in fake mode. Stop it and start `python dev.py --fake` first.")
