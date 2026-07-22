import csv
import json
import os
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class Store:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = Path(db_path or "po_stall_agent.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connect()
        self._init_schema()

    def _connect(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row

    def _init_schema(self):
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS checkpoints (
                gsm_id TEXT PRIMARY KEY,
                last_message_id TEXT,
                updated_at TEXT
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS state_rows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                gsm_id TEXT NOT NULL,
                po_ref TEXT NOT NULL,
                track TEXT NOT NULL,
                status TEXT NOT NULL,
                source_message_id TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS discard_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                gsm_id TEXT NOT NULL,
                message_id TEXT NOT NULL,
                sender TEXT,
                subject TEXT,
                reason TEXT NOT NULL
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS review_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                gsm_id TEXT NOT NULL,
                message_id TEXT NOT NULL,
                reason TEXT NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS drafts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                gsm_id TEXT NOT NULL,
                message_id TEXT NOT NULL,
                po_ref TEXT NOT NULL,
                draft_id TEXT NOT NULL,
                run_key TEXT NOT NULL
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS digests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                gsm_id TEXT NOT NULL,
                run_key TEXT NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )
        self.conn.commit()

    def get_checkpoint(self, gsm_id: str) -> Optional[str]:
        row = self.conn.execute(
            "SELECT last_message_id FROM checkpoints WHERE gsm_id = ?", (gsm_id,)
        ).fetchone()
        return row["last_message_id"] if row else None

    def set_checkpoint(self, gsm_id: str, last_message_id: str):
        self.conn.execute(
            "INSERT INTO checkpoints(gsm_id, last_message_id, updated_at) VALUES(?, ?, datetime('now')) "
            "ON CONFLICT(gsm_id) DO UPDATE SET last_message_id = excluded.last_message_id, updated_at = datetime('now')",
            (gsm_id, last_message_id),
        )
        self.conn.commit()

    def append_state(self, gsm_id: str, po_ref: str, track: str, status: str, source_message_id: str, timestamp: str):
        self.conn.execute(
            "INSERT INTO state_rows(gsm_id, po_ref, track, status, source_message_id, timestamp) VALUES(?, ?, ?, ?, ?, ?)",
            (gsm_id, po_ref, track, status, source_message_id, timestamp),
        )
        self.conn.commit()

    def current_state(self, gsm_id: str) -> List[Dict[str, object]]:
        rows = self.conn.execute(
            """
            SELECT gsm_id, po_ref, track, status, source_message_id, timestamp
            FROM state_rows
            WHERE gsm_id = ?
            ORDER BY id ASC
            """,
            (gsm_id,),
        ).fetchall()
        latest = {}
        for row in rows:
            latest[(row["po_ref"], row["track"])] = dict(row)
        return list(latest.values())

    def log_discard(self, gsm_id: str, message_id: str, sender: Optional[str], subject: Optional[str], reason: str):
        self.conn.execute(
            "INSERT INTO discard_logs(gsm_id, message_id, sender, subject, reason) VALUES(?, ?, ?, ?, ?)",
            (gsm_id, message_id, sender, subject, reason),
        )
        self.conn.commit()

    def log_review(self, gsm_id: str, message_id: str, reason: str, payload: Dict[str, object]):
        self.conn.execute(
            "INSERT INTO review_items(gsm_id, message_id, reason, payload) VALUES(?, ?, ?, ?)",
            (gsm_id, message_id, reason, json.dumps(payload)),
        )
        self.conn.commit()

    def load_pos(self, po_seed_file: str) -> Dict[str, Dict[str, object]]:
        pos = {}
        path = Path(po_seed_file)
        if not path.is_absolute():
            repo_root = Path(__file__).resolve().parents[2]
            path = repo_root / path
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                pos[row["po_ref"]] = {
                    "po_ref": row["po_ref"],
                    "supplier": row["supplier"],
                    "supplier_email": row["supplier_email"],
                    "amount": int(row["amount"]),
                    "stage": row["stage"],
                    "opened": row["opened"],
                }
        return pos

    def draft_seen(self, gsm_id: str, message_id: str, po_ref: str, run_key: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM drafts WHERE gsm_id=? AND message_id=? AND po_ref=? AND run_key=? LIMIT 1",
            (gsm_id, message_id, po_ref, run_key),
        ).fetchone()
        return row is not None

    def record_draft(self, gsm_id: str, message_id: str, po_ref: str, draft_id: str, run_key: str):
        self.conn.execute(
            "INSERT INTO drafts(gsm_id, message_id, po_ref, draft_id, run_key) VALUES(?, ?, ?, ?, ?)",
            (gsm_id, message_id, po_ref, draft_id, run_key),
        )
        self.conn.commit()

    def digest_seen(self, gsm_id: str, run_key: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM digests WHERE gsm_id=? AND run_key=? LIMIT 1", (gsm_id, run_key)
        ).fetchone()
        return row is not None

    def record_digest(self, gsm_id: str, run_key: str, payload: Dict[str, object]):
        self.conn.execute(
            "INSERT INTO digests(gsm_id, run_key, payload) VALUES(?, ?, ?)",
            (gsm_id, run_key, json.dumps(payload)),
        )
        self.conn.commit()
