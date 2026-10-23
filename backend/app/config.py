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
    # Owner sign-in (ADR-0019). With a session secret, every API route but sign-in needs the Owner's session.
    public_url: str = "http://localhost:5173"  # where the browser reaches the app; Google returns there
    owner_email: str | None = None  # the only Google account allowed in; anyone may sign in locally if unset
    session_secret: str | None = field(default=None, repr=False)
    token_key: str | None = field(default=None, repr=False)  # Fernet key sealing the stored Google token
    google_client_id: str | None = None  # else data/client_secret.json (a Web client)
    google_client_secret: str | None = field(default=None, repr=False)
    frontend_origin: str = "http://localhost:5173"
    allowed_hosts: tuple[str, ...] = ("127.0.0.1", "localhost")

    @property
    def client_secret_path(self) -> Path:
        return self.data_dir / "client_secret.json"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "app.db"

    @property
    def backups_dir(self) -> Path:
        return self.data_dir / "backups"
