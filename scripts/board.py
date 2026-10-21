"""Move an issue on the project board: python scripts/board.py <issue-number> <status>

Status is one of: backlog, ready, in-progress, in-review, done.
"""
import json
import subprocess
import sys

OWNER = "karthikraoofficial"
REPO = f"{OWNER}/youtube-description-editor"
PROJECT_NUMBER = 5
PROJECT_ID = "PVT_kwHODa_sGc4BoG6J"
STATUS_FIELD_ID = "PVTSSF_lAHODa_sGc4BoG6JzhmofHE"
OPTIONS = {
    "backlog": "5176ad8b",
    "ready": "33efda3c",
    "in-progress": "c664fd1c",
    "in-review": "ad320782",
    "done": "7cf48867",
}


def gh(*args: str) -> str:
    return subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8",
                          check=True).stdout


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[2] not in OPTIONS:
        print(__doc__)
        return 2
    url = f"https://github.com/{REPO}/issues/{sys.argv[1]}"
    # item-add is idempotent: it returns the existing item if already on the board.
    item = json.loads(gh("project", "item-add", str(PROJECT_NUMBER), "--owner", OWNER,
                         "--url", url, "--format", "json"))
    gh("project", "item-edit", "--id", item["id"], "--project-id", PROJECT_ID,
       "--field-id", STATUS_FIELD_ID, "--single-select-option-id", OPTIONS[sys.argv[2]])
    print(f"#{sys.argv[1]} -> {sys.argv[2]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
