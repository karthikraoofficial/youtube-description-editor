"""Where the JSON copy of a Run's Backups goes (ADR-0018): files under data/backups in local mode, a private
Vercel Blob store in the cloud. The database copy is the primary Backup; this is the second one."""
import json
from collections.abc import Callable
from pathlib import Path
from typing import Protocol


class BackupArchiveError(Exception):
    """The copy couldn't be saved. The message is safe to show and log: it never carries the token."""


class BackupArchive(Protocol):
    def save(self, run_id: int, document: dict) -> None:
        """Store the Run's whole Backup document, replacing any earlier copy. Raises BackupArchiveError."""


def _encode(document: dict) -> bytes:
    return json.dumps(document, ensure_ascii=False, indent=1).encode("utf-8")


class LocalFileArchive:
    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def save(self, run_id: int, document: dict) -> None:
        try:
            self._directory.mkdir(parents=True, exist_ok=True)
            path = self._directory / f"run-{run_id}.json"
            tmp = path.with_suffix(".json.tmp")
            tmp.write_bytes(_encode(document))
            tmp.replace(path)  # the file appears whole or not at all
        except OSError as e:
            raise BackupArchiveError(f"couldn't write the file ({type(e).__name__})") from e


class BlobArchive:
    """One private blob per Run, overwritten as the Run goes on. Credentials come from the environment
    (BLOB_READ_WRITE_TOKEN, or Vercel's OIDC token with BLOB_STORE_ID); `put` replaces the SDK in tests."""

    def __init__(self, put: Callable[..., object] | None = None) -> None:
        if put is None:
            from vercel.blob.sync import put_blob  # imported only in cloud mode

            put = put_blob
        self._put = put

    def save(self, run_id: int, document: dict) -> None:
        try:
            self._put(f"backups/run-{run_id}.json", _encode(document), access="private", allow_overwrite=True,
                      content_type="application/json")
        except Exception as e:  # SDK errors, network errors: the Run must not write without its copy
            raise BackupArchiveError(f"Vercel Blob upload failed ({type(e).__name__})") from e
