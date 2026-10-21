from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Every mutating request must carry this header (ADR-0006); the frontend client sends it.
CLIENT_HEADER = "X-YDE-Client"
CLIENT_HEADER_VALUE = "1"


@dataclass(frozen=True)
class Settings:
    """Runtime settings. Everything secret or personal lives under data_dir (gitignored)."""

    data_dir: Path = REPO_ROOT / "data"
    fake: bool = False
    frontend_origin: str = "http://localhost:5173"
    allowed_hosts: tuple[str, ...] = ("127.0.0.1", "localhost")

    @property
    def client_secret_path(self) -> Path:
        return self.data_dir / "client_secret.json"

    @property
    def token_path(self) -> Path:
        return self.data_dir / "token.json"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "app.db"

    @property
    def backups_dir(self) -> Path:
        return self.data_dir / "backups"
