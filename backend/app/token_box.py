"""How the stored Google credentials are kept (ADR-0019): encrypted with YDE_TOKEN_KEY when one is set (always,
in the cloud), as plain JSON otherwise (local mode, where the database file is the owner's own)."""
import logging

from cryptography.fernet import Fernet, InvalidToken

log = logging.getLogger(__name__)

_SEALED = "fernet:"
_PLAIN = "plain:"


class TokenBox:
    def __init__(self, key: str | None) -> None:
        self._fernet = Fernet(key.encode()) if key else None

    def seal(self, credentials_json: str) -> str:
        if self._fernet is None:
            return _PLAIN + credentials_json
        return _SEALED + self._fernet.encrypt(credentials_json.encode()).decode()

    def open(self, stored: str | None) -> str | None:
        """The credentials, or None if nothing is stored or they can't be read with this key (sign in again)."""
        if not stored:
            return None
        if stored.startswith(_SEALED) and self._fernet is not None:
            try:
                return self._fernet.decrypt(stored.removeprefix(_SEALED).encode()).decode()
            except InvalidToken:
                pass
        elif stored.startswith(_PLAIN) and self._fernet is None:
            return stored.removeprefix(_PLAIN)
        # Sealed with another key, sealed without a key, or plain where a key is required. Google's grant for it
        # can't be withdrawn from here: remove the app at myaccount.google.com/permissions if it matters.
        log.warning("The stored Google sign-in can't be read with this YDE_TOKEN_KEY; sign in again")
        return None
