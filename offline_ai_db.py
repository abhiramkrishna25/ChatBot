"""Offline multi-AI storage and enquiry search database.

This module provides a local SQLite-backed database that works fully offline.
It stores records for multiple AI systems and supports keyword search queries.
"""

from __future__ import annotations

import argparse
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class AIRecord:
    name: str
    provider: str
    description: str
    capabilities: str
    tags: str


class MultiAIDatabase:
    """SQLite-backed offline database for storing and searching AI records."""

    def __init__(self, db_path: str | Path = "multi_ai_offline.db") -> None:
        self.db_path = str(db_path)
        self._connection = sqlite3.connect(self.db_path)
        self._connection.row_factory = sqlite3.Row
        self._initialize_schema()

    def _initialize_schema(self) -> None:
        cursor = self._connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                provider TEXT NOT NULL,
                description TEXT NOT NULL,
                capabilities TEXT NOT NULL,
                tags TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS ai_records_fts USING fts5(
                name,
                provider,
                description,
                capabilities,
                tags,
                content='ai_records',
                content_rowid='id'
            )
            """
        )
        cursor.execute(
            """
            CREATE TRIGGER IF NOT EXISTS ai_records_ai AFTER INSERT ON ai_records BEGIN
                INSERT INTO ai_records_fts(rowid, name, provider, description, capabilities, tags)
                VALUES (new.id, new.name, new.provider, new.description, new.capabilities, new.tags);
            END;
            """
        )
        cursor.execute(
            """
            CREATE TRIGGER IF NOT EXISTS ai_records_ad AFTER DELETE ON ai_records BEGIN
                INSERT INTO ai_records_fts(ai_records_fts, rowid, name, provider, description, capabilities, tags)
                VALUES('delete', old.id, old.name, old.provider, old.description, old.capabilities, old.tags);
            END;
            """
        )
        cursor.execute(
            """
            CREATE TRIGGER IF NOT EXISTS ai_records_au AFTER UPDATE ON ai_records BEGIN
                INSERT INTO ai_records_fts(ai_records_fts, rowid, name, provider, description, capabilities, tags)
                VALUES('delete', old.id, old.name, old.provider, old.description, old.capabilities, old.tags);
                INSERT INTO ai_records_fts(rowid, name, provider, description, capabilities, tags)
                VALUES (new.id, new.name, new.provider, new.description, new.capabilities, new.tags);
            END;
            """
        )
        self._connection.commit()

    def add_ai(self, record: AIRecord) -> int:
        cursor = self._connection.cursor()
        cursor.execute(
            """
            INSERT INTO ai_records(name, provider, description, capabilities, tags)
            VALUES (?, ?, ?, ?, ?)
            """,
            (record.name, record.provider, record.description, record.capabilities, record.tags),
        )
        self._connection.commit()
        return int(cursor.lastrowid)

    def bulk_add(self, records: Iterable[AIRecord]) -> int:
        cursor = self._connection.cursor()
        payload = [
            (r.name, r.provider, r.description, r.capabilities, r.tags)
            for r in records
        ]
        cursor.executemany(
            """
            INSERT INTO ai_records(name, provider, description, capabilities, tags)
            VALUES (?, ?, ?, ?, ?)
            """,
            payload,
        )
        self._connection.commit()
        return cursor.rowcount

    def search(self, query: str, limit: int = 20) -> list[dict]:
        cursor = self._connection.cursor()
        cursor.execute(
            """
            SELECT r.id, r.name, r.provider, r.description, r.capabilities, r.tags,
                   bm25(ai_records_fts) AS score
            FROM ai_records_fts f
            JOIN ai_records r ON r.id = f.rowid
            WHERE ai_records_fts MATCH ?
            ORDER BY score
            LIMIT ?
            """,
            (query, limit),
        )
        return [dict(row) for row in cursor.fetchall()]

    def list_all(self) -> list[dict]:
        cursor = self._connection.cursor()
        cursor.execute(
            """
            SELECT id, name, provider, description, capabilities, tags, created_at
            FROM ai_records
            ORDER BY id
            """
        )
        return [dict(row) for row in cursor.fetchall()]

    def remove(self, record_id: int) -> bool:
        cursor = self._connection.cursor()
        cursor.execute("DELETE FROM ai_records WHERE id = ?", (record_id,))
        self._connection.commit()
        return cursor.rowcount > 0

    def close(self) -> None:
        self._connection.close()



def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Offline multi-AI storage and search database")
    parser.add_argument("--db", default="multi_ai_offline.db", help="SQLite database path")
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="Add one AI record")
    add.add_argument("name")
    add.add_argument("provider")
    add.add_argument("description")
    add.add_argument("capabilities")
    add.add_argument("tags")

    search = sub.add_parser("search", help="Search AI records")
    search.add_argument("query", help="FTS query, e.g. 'vision OR chatbot'")
    search.add_argument("--limit", type=int, default=20)

    sub.add_parser("list", help="List all records")

    remove = sub.add_parser("remove", help="Remove by record ID")
    remove.add_argument("id", type=int)

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    db = MultiAIDatabase(args.db)

    try:
        if args.command == "add":
            rid = db.add_ai(
                AIRecord(
                    name=args.name,
                    provider=args.provider,
                    description=args.description,
                    capabilities=args.capabilities,
                    tags=args.tags,
                )
            )
            print(f"Added record ID: {rid}")
        elif args.command == "search":
            results = db.search(args.query, args.limit)
            for item in results:
                print(f"[{item['id']}] {item['name']} ({item['provider']}) - {item['description']}")
                print(f"  capabilities: {item['capabilities']}")
                print(f"  tags: {item['tags']}")
                print(f"  score: {item['score']}")
        elif args.command == "list":
            for item in db.list_all():
                print(f"[{item['id']}] {item['name']} ({item['provider']})")
        elif args.command == "remove":
            removed = db.remove(args.id)
            print("Removed" if removed else "Not found")
    finally:
        db.close()


if __name__ == "__main__":
    main()
