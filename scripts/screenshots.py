"""Walk the app in fake mode and screenshot every screen, light and dark, at 390 (phone), 1024 and 1280 px wide.
Also reports horizontal overflow and browser console errors, and checks that the phone menu closes on Esc, a backdrop tap
and picking a page, handing focus back to its button, and that the phone Filter button folds the Video filters.

    pip install -e "backend[screenshots]" && python -m playwright install chromium
    python dev.py --fake --no-browser          # in another terminal, with a fresh data/fake/
    python scripts/screenshots.py out/         # writes PNGs to out/
"""
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from _fake_app import BASE, open_nav, require_fake_app

require_fake_app()  # the walk presses Apply, so it must never run against a real Channel

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
ROWS_PER_PASS = 3
VIEWPORTS = ((390, 844), (1024, 800), (1280, 800))  # (width, height)
problems = []


def check(page, name):
    over = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    if over > 0:
        problems.append(f"{name}: horizontal overflow {over}px")


def check_menu_closes(page, tag):
    """The phone menu closes on Esc and on a backdrop tap, and gives focus back to its button."""
    menu = page.get_by_role("dialog", name="Menu")
    for how in ("Esc", "backdrop"):
        if how == "Esc":
            page.keyboard.press("Escape")
        else:
            page.mouse.click(page.viewport_size["width"] - 10, page.viewport_size["height"] // 2)
        try:
            menu.wait_for(state="detached", timeout=3000)
        except Exception:
            problems.append(f"{tag}: the menu didn't close on {how}")
            return
        page.wait_for_timeout(100)
        if page.evaluate("document.activeElement?.getAttribute('aria-label')") != "Open menu":
            problems.append(f"{tag}: focus didn't return to the menu button after {how}")
        if how == "Esc":
            open_nav(page)


def check_filter_fold(page, tag):
    """On a phone the Video filters fold behind a Filter button; elsewhere they're always shown."""
    shorts = page.get_by_label("Shorts filter")
    toggle = page.get_by_role("button", name=re.compile(r"^Filter( \(\d+ on\))?$"))
    if not toggle.count():
        if not shorts.is_visible():
            problems.append(f"{tag}: the filters aren't shown")
        return
    if shorts.count():
        problems.append(f"{tag}: the filters should start folded on a phone")
    toggle.click()
    if not shorts.is_visible():
        problems.append(f"{tag}: Filter didn't unfold the filters")
    shot(page, f"{tag}-02b-filters")
    toggle.click()
    if shorts.count():
        problems.append(f"{tag}: Filter didn't fold the filters again")


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
            check_filter_fold(page, tag)
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
            if open_nav(page):
                shot(page, f"{tag}-06b-menu")
                check_menu_closes(page, tag)
                open_nav(page)
            page.get_by_role("button", name="History").click()
            page.get_by_role("heading", name="History").wait_for()
            if page.get_by_role("dialog", name="Menu").count():
                problems.append(f"{tag}: the menu stayed open after picking History")
            shot(page, f"{tag}-07-history")
            if errors:
                problems.append(f"{tag}: console errors: {errors[:3]}")
            ctx.close()
    browser.close()

print("\n".join(problems) or "no overflow, no console errors")
sys.exit(1 if problems else 0)
