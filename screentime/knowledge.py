"""Mac app usage from knowledgeC.db (`/app/usage` stream), read from a temp copy."""

from __future__ import annotations

import shutil
import sqlite3
import tempfile
from pathlib import Path

KNOWLEDGE_DB = Path.home() / "Library/Application Support/Knowledge/knowledgeC.db"
COCOA_EPOCH = 978307200

_QUERY = """
SELECT ZSTARTDATE, ZENDDATE, ZVALUESTRING
FROM ZOBJECT
WHERE ZSTREAMNAME = '/app/usage' AND ZSTARTDATE IS NOT NULL AND ZENDDATE IS NOT NULL
"""


class KnowledgeError(RuntimeError):
    pass


def read_app_usage(db: Path = KNOWLEDGE_DB) -> list[tuple[float, float, str | None]]:
    """Return (start_unix, end_unix, bundle_id) rows. Copies the DB (+WAL) to a
    temp dir first so Apple's live database is never locked or written."""
    if not db.exists():
        raise KnowledgeError(f"{db} not found")
    with tempfile.TemporaryDirectory(prefix="island-kc-") as tmp:
        try:
            for suffix in ("", "-wal", "-shm"):
                src = Path(str(db) + suffix)
                if src.exists():
                    shutil.copy2(src, Path(tmp) / (db.name + suffix))
        except PermissionError as exc:
            raise KnowledgeError(
                "macOS blocked reading knowledgeC.db: give your terminal Full Disk "
                "Access (System Settings > Privacy & Security)"
            ) from exc
        uri = f"file:{Path(tmp) / db.name}?mode=ro"
        try:
            with sqlite3.connect(uri, uri=True) as conn:
                rows = conn.execute(_QUERY).fetchall()
        except sqlite3.Error as exc:
            raise KnowledgeError(f"could not query knowledgeC.db: {exc}") from exc
    return [(s + COCOA_EPOCH, e + COCOA_EPOCH, b) for s, e, b in rows]
