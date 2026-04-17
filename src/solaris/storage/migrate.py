# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from pathlib import Path

from .db import Database


def apply_migrations(db: Database, migrations_dir: Path) -> None:
    files = sorted(Path(migrations_dir).glob("*.sql"))
    with db.transaction() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations(
                filename TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        applied = {
            row["filename"]
            for row in connection.execute("SELECT filename FROM schema_migrations").fetchall()
        }
        for path in files:
            if path.name in applied:
                continue
            connection.executescript(path.read_text(encoding="utf-8"))
            connection.execute(
                "INSERT INTO schema_migrations(filename) VALUES (?)",
                (path.name,),
            )
