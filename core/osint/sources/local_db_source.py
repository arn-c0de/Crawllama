"""Local breach database source."""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from .base import BreachResult, BreachSource, SourceType

logger = logging.getLogger("crawllama")


class LocalDBBreachSource(BreachSource):
    name = "local_db"
    source_type = SourceType.LOCAL_DB
    rate_limit_delay = 0.0

    def is_configured(self) -> bool:
        breach_dir = Path("data/breaches")
        if not breach_dir.exists():
            return False
        if (breach_dir / "breach_index.db").exists():
            return True
        return any(breach_dir.glob("*.txt"))

    def _query(self, email: str) -> list[BreachResult]:
        breach_dir = Path("data/breaches")
        db_path = breach_dir / "breach_index.db"

        if db_path.exists():
            return self._query_sqlite(db_path, email)
        return self._scan_files(breach_dir, email)

    @staticmethod
    def _fts_quote(term: str) -> str:
        """Quote a term as an FTS5 string literal.

        Without quoting, FTS5 interprets characters such as ``"``, ``*``,
        ``:``, ``-`` and keywords like ``OR``/``NEAR`` as query syntax, which
        raises OperationalError (swallowed -> false "not found") or matches
        unintended rows. Wrapping in double quotes (escaping embedded quotes)
        forces an exact phrase match.
        """
        return '"' + term.replace('"', '""') + '"'

    @staticmethod
    def _redact_raw(raw: str) -> str:
        """Mask the credential portion of a ``email:password`` breach line so
        plaintext passwords are not propagated into results/reports."""
        if not raw:
            return ""
        identifier, sep, _secret = str(raw).partition(":")
        return f"{identifier}:***" if sep else "***"

    def _query_sqlite(self, db_path: Path, email: str) -> list[BreachResult]:
        breaches: list[BreachResult] = []
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.execute(
                "SELECT source, raw FROM breaches WHERE breaches MATCH ? LIMIT 20",
                (self._fts_quote(email),)
            )
            rows = cursor.fetchall()
            conn.close()

            for source_name, raw in rows:
                breaches.append(
                    BreachResult(
                        name=source_name or "Local DB",
                        title=source_name or "Local DB",
                        breach_date="Unknown",
                        description=f"Email found in local breach database ({source_name}).",
                        data_classes=["Email addresses"],
                        is_verified=False,
                        is_sensitive=True,
                        source="LocalDB",
                        metadata={"raw": self._redact_raw(raw)}
                    )
                )
        except Exception as exc:
            logger.debug(f"Local DB SQLite query failed: {exc}")

        return breaches

    def _scan_files(self, breach_dir: Path, email: str) -> list[BreachResult]:
        breaches: list[BreachResult] = []
        try:
            for file_path in breach_dir.glob("*.txt"):
                try:
                    with open(file_path, encoding="utf-8", errors="ignore") as f:
                        for line_num, line in enumerate(f, 1):
                            if email.lower() in line.lower():
                                breaches.append(
                                    BreachResult(
                                        name=f"Local List: {file_path.name}",
                                        title=file_path.name,
                                        breach_date="Unknown",
                                        description=f"Found in local breach file {file_path.name}",
                                        data_classes=["Email addresses"],
                                        is_verified=False,
                                        is_sensitive=True,
                                        source="LocalDB",
                                        metadata={"line": line_num}
                                    )
                                )
                                break
                except Exception as exc:
                    logger.error(f"Error scanning {file_path.name}: {exc}")
        except Exception as exc:
            logger.error(f"Error accessing breach directory: {exc}")

        return breaches
