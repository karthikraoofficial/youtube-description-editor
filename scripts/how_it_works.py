"""Capture the How It Works screenshots at phone size, and write the how-it-works.html page.

The steps (image, alt text, caption) come from frontend/src/lib/howItWorksSteps.json. The sign-in card's
How It Works button opens the page this writes. Images go to frontend/public/how-it-works/. They show
fake-mode data only, so they're safe to commit to this public repo.

    python dev.py --fake --no-browser                              # with a fresh data/fake/
    backend/.venv/Scripts/python scripts/how_it_works.py
"""
import html
import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

from _fake_app import BASE, open_nav, require_fake_app

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "frontend" / "public"
OUT = PUBLIC / "how-it-works"
CONTENT = json.loads((ROOT / "frontend" / "src" / "lib" / "howItWorksSteps.json").read_text(encoding="utf-8"))
STEPS = CONTENT["steps"]
PHONE = {"width": 390, "height": 844}
# What the walk below captures, by file name. It must match the list, so a step added or reordered there can't
# silently save one screen under another step's name.
CAPTURED = ["01-sign-in.png", "02-select.png", "03-edit.png", "04-review.png", "05-apply.png", "06-restore.png"]


def capture() -> None:
    if [s["image"] for s in STEPS] != CAPTURED:
        raise SystemExit(f"howItWorksSteps.json lists {[s['image'] for s in STEPS]}, but this script captures "
                         f"{CAPTURED}. Update both together.")
    OUT.mkdir(parents=True, exist_ok=True)

    def shot(page, image: str) -> None:
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(400)
        page.screenshot(path=str(OUT / image))

    with sync_playwright() as p:
        browser = p.chromium.launch()
        # Pacific time, like the Quota reset, so the times shown don't reveal where the screenshots were taken.
        page = browser.new_page(viewport=PHONE, color_scheme="light", device_scale_factor=2,
                                timezone_id="America/Los_Angeles")
        page.on("dialog", lambda d: d.accept())  # Disconnect asks to confirm
        # Visitors see the real app, so leave out the badge that says this one is the fake. An init script, because
        # signing in reloads the page.
        page.add_init_script("""document.addEventListener("DOMContentLoaded", () => {
            const style = document.createElement("style");
            style.textContent = "[data-fake-badge] { display: none !important; }";
            document.head.append(style);
        });""")
        page.goto(BASE)
        page.wait_for_load_state("networkidle")
        open_nav(page)
        if page.get_by_role("button", name="Disconnect").count():
            page.get_by_role("button", name="Disconnect").click()
        page.get_by_role("button", name="Sign in with Google").wait_for()
        shot(page, "01-sign-in.png")

        page.get_by_role("button", name="Sign in with Google").click()
        page.get_by_text("Not synced yet").or_(page.get_by_text("last synced")).first.wait_for()
        if page.get_by_role("button", name="Sync videos").count():
            page.get_by_role("button", name="Sync videos").click()
        page.get_by_text("Select all").first.wait_for(timeout=60000)
        boxes = page.get_by_role("checkbox", name="Select ", exact=False)
        for i in (1, 2, 3):  # 0 is "select all"
            boxes.nth(i).check()
        shot(page, "02-select.png")

        page.get_by_role("button", name="Edit 3 selected").click()
        page.get_by_role("radio", name="Append to Description").click()
        page.get_by_label("Text to add", exact=False).fill("Guitar lessons: https://example.com/lessons")
        page.get_by_text("All 3 selected").wait_for(timeout=10000)
        shot(page, "03-edit.png")

        page.get_by_role("button", name="Review all 3").click()
        page.get_by_text("Review changes").wait_for()
        shot(page, "04-review.png")

        page.get_by_role("button", name="Apply", exact=False).first.click()
        page.get_by_role("dialog").get_by_role("button", name="Apply", exact=False).click()
        page.get_by_text("Finished").first.wait_for(timeout=20000)
        shot(page, "05-apply.png")

        page.get_by_role("button", name="Restore all", exact=False).click()
        page.get_by_role("dialog").wait_for()
        shot(page, "06-restore.png")
        browser.close()


# The app's brand mark (lucide's pen icon) and name, at the top of every static page. This is the one copy:
# write_page() also puts it into privacy.html and terms.html.
BRAND_HEADER = (
    '<header><a class="brand" href="/"><span class="mark" aria-hidden="true"><svg width="16" height="16" '
    'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
    'stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.376 3.622a1 1 0 0 1 3.002 3.002L7.368 18.635a2 2 0 0 '
    '1-.855.506l-2.872.838a.5.5 0 0 1-.62-.62l.838-2.872a2 2 0 0 1 .506-.855z"/></svg></span>'
    '<span>Description Editor<small>for YouTube</small></span></a></header>'
)


def write_page() -> None:
    """The How It Works page, viewable without signing in (served like privacy.html)."""
    figures = "\n".join(
        f'    <li><img src="/how-it-works/{html.escape(s["image"])}" alt="{html.escape(s["alt"])}" width="390" '
        f'height="844" loading="lazy"><p><span class="step">{n}</span> {html.escape(s["caption"])}</p></li>'
        for n, s in enumerate(STEPS, 1))
    (PUBLIC / "how-it-works.html").write_text(f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(CONTENT["heading"])} · YouTube Description Editor</title>
  <!-- Written by scripts/how_it_works.py from frontend/src/lib/howItWorksSteps.json; edit those, not this. -->
  <link rel="stylesheet" href="/pages.css">
  <style>
    main {{ max-width: 72rem; }}
    h1, .lead {{ text-align: center; }}
    .lead {{ margin: 0 0 2rem; }}
    ol {{ list-style: none; margin: 0; padding: 0 0 0.5rem; display: flex; gap: 1rem; overflow-x: auto;
          scroll-snap-type: x mandatory; }}
    li {{ flex: 0 0 12rem; scroll-snap-align: center; }}
    @media (min-width: 64rem) {{ ol {{ display: grid; grid-template-columns: repeat(6, 1fr); overflow: visible; }} }}
    img {{ display: block; width: 100%; height: auto; border: 1px solid var(--line); border-radius: 1.25rem;
           box-shadow: var(--shadow); background: var(--surface); }}
    li p {{ margin: 0.75rem 0 0; text-align: center; font-size: 0.875rem; }}
    .step {{ display: inline-flex; width: 1.5rem; height: 1.5rem; align-items: center; justify-content: center;
             margin-right: 0.25rem; border-radius: 999px; background: var(--accent); color: var(--on-accent);
             font-size: 0.75rem; font-weight: 600; }}
  </style>
</head>
<body>
{BRAND_HEADER}
<main>
  <h1>{html.escape(CONTENT["heading"])}</h1>
  <p class="lead">{html.escape(CONTENT["lead"])}</p>
  <ol role="list" tabindex="0" aria-label="Steps">
{figures}
  </ol>
</main>
<footer><a href="/">Open the app</a> · <a href="/privacy.html">Privacy Policy</a> · <a href="/terms.html">Terms of Service</a></footer>
</body>
</html>
""", encoding="utf-8", newline="\n")


def sync_brand_header() -> None:
    """Keep the brand header on the privacy and terms pages the same as on How It Works."""
    for name in ("privacy.html", "terms.html"):
        path = PUBLIC / name
        page = path.read_text(encoding="utf-8")
        synced = re.sub(r"<header>.*?</header>", lambda _: BRAND_HEADER, page, count=1, flags=re.S)
        if synced != page:
            path.write_text(synced, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    require_fake_app()  # the walk presses Apply, so it must never run against a real Channel
    capture()
    write_page()
    sync_brand_header()
    print(f"wrote {len(STEPS)} screenshots to {OUT} and {PUBLIC / 'how-it-works.html'}")
