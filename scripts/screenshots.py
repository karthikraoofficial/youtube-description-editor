"""Walk the app in fake mode and screenshot every screen, light and dark, at 390 (phone), 1024 and 1280 px wide.
Also reports horizontal overflow and browser console errors.

    pip install -e "backend[screenshots]" && python -m playwright install chromium
    python dev.py --fake --no-browser          # in another terminal, with a fresh data/fake/
    python scripts/screenshots.py out/         # writes PNGs to out/
"""
import json
import sys
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

# The walk presses Apply, so it must never run against a real Channel.
try:
    with urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=5) as resp:
        fake = json.load(resp).get("fake")
except OSError:
    sys.exit("The app isn't answering at :8000. Start `python dev.py --fake` first.")
if not fake:
    sys.exit("The app at :8000 is not in fake mode. Stop it and start `python dev.py --fake` first.")

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
BASE = "http://localhost:5173"
ROWS_PER_PASS = 3
VIEWPORTS = ((390, 844), (1024, 800), (1280, 800))  # (width, height)
problems = []


def check(page, name):
    over = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    if over > 0:
        problems.append(f"{name}: horizontal overflow {over}px")


def shot(page, name):
    page.wait_for_timeout(400)
    check(page, name)
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=False)


with sync_playwright() as p:
    browser = p.chromium.launch()
    passes = 0
    for theme in ("light", "dark"):
        for width, height in VIEWPORTS:
            passes += 1
            tag = f"{theme}-{width}"
            ctx = browser.new_context(viewport={"width": width, "height": height}, color_scheme=theme)
            page = ctx.new_page()
            errors = []
            page.on("console", lambda m, errors=errors: m.type == "error" and errors.append(m.text))
            page.goto(BASE)
            page.wait_for_load_state("networkidle")
            if page.get_by_role("button", name="Sign in with Google").count():
                shot(page, f"{tag}-01-connect")
                page.get_by_role("button", name="Sign in with Google").click()
            page.get_by_text("Videos", exact=True).first.wait_for()
            # Wait until the Videos screen knows whether anything is cached yet.
            page.get_by_text("Not synced yet").or_(page.get_by_text("last synced")).first.wait_for()
            if page.get_by_role("button", name="Sync videos").count():
                page.get_by_role("button", name="Sync videos").click()
                page.get_by_text("Select all").first.wait_for(timeout=60000)
            shot(page, f"{tag}-02-videos")
            # Each pass edits fresh videos; reusing earlier ones would leave nothing to apply.
            boxes = page.get_by_role("checkbox", name="Select ", exact=False)
            first_row = 1 + ROWS_PER_PASS * (passes - 1)  # row 0 is the "select all" box
            for i in range(first_row, first_row + ROWS_PER_PASS):
                boxes.nth(i).check()
            page.get_by_role("button", name="Edit 3 selected").click()
            page.get_by_role("radio", name="Append to Description").click()
            page.get_by_label("Text to add", exact=False).fill("Guitar lessons: https://example.com/lessons")
            page.get_by_text("All 3 selected").wait_for(timeout=10000)
            shot(page, f"{tag}-03-edit")
            page.get_by_role("button", name="Review all 3").click()
            page.get_by_text("Review changes").wait_for()
            shot(page, f"{tag}-04-review")
            page.get_by_role("button", name="Apply", exact=False).first.click()
            page.get_by_role("dialog").wait_for()
            shot(page, f"{tag}-05-confirm")
            page.get_by_role("dialog").get_by_role("button", name="Apply", exact=False).click()
            page.get_by_text("Run #").first.wait_for()
            page.get_by_text("Finished").first.wait_for(timeout=20000)
            shot(page, f"{tag}-06-run")
            page.get_by_role("button", name="History").click()
            page.get_by_role("heading", name="History").wait_for()
            shot(page, f"{tag}-07-history")
            if errors:
                problems.append(f"{tag}: console errors: {errors[:3]}")
            ctx.close()
    browser.close()

print("\n".join(problems) or "no overflow, no console errors")
sys.exit(1 if problems else 0)
