from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Every mutating request must carry this header (ADR-0006); the frontend client sends it.
CLIENT_HEADER = "X-YDE-Client"
CLIENT_HEADER_VALUE = "1"


@dataclass(frozen=True)
class Settings:
    """Runtime settings. Secrets and personal data live under data_dir (gitignored), or in the database
    that database_url names, whose password it carries: never print it."""

    data_dir: Path = REPO_ROOT / "data"
    fake: bool = False
    database_url: str | None = field(default=None, repr=False)  # Postgres when set, else SQLite (ADR-0016)
    blob_backups: bool = False  # Backup copies to Vercel Blob instead of backups_dir (ADR-0018)
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
