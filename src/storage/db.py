"""
SQLite storage for call-analysis records.
=========================================
Stores one row per processed call with all the analysis artifacts.

Schema:
    id              INTEGER PRIMARY KEY AUTOINCREMENT
    filename        TEXT
    timestamp       TEXT  (ISO 8601, UTC)
    duration_sec    REAL
    intent          TEXT
    intent_confidence  REAL
    sentiment       TEXT
    sentiment_score REAL
    speech_emotion  TEXT
    score_listening      INTEGER
    score_communication  INTEGER
    score_persuasion     INTEGER
    score_outcome        INTEGER
    transcript      TEXT
    entities_json   TEXT (JSON-encoded)
    turns_json      TEXT (JSON-encoded)
    intent_scores_json TEXT (JSON-encoded)
"""

import os
import json
import sqlite3
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Union

from src.utils import get_logger, get_intent_label, get_intent_confidence

logger = get_logger(__name__)

DEFAULT_DB_PATH = os.path.join("outputs", "calls.db")


SCHEMA = """
CREATE TABLE IF NOT EXISTS calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT,
    timestamp TEXT NOT NULL,
    duration_sec REAL,
    intent TEXT,
    intent_confidence REAL,
    sentiment TEXT,
    sentiment_score REAL,
    speech_emotion TEXT,
    score_listening INTEGER,
    score_communication INTEGER,
    score_persuasion INTEGER,
    score_outcome INTEGER,
    transcript TEXT,
    entities_json TEXT,
    turns_json TEXT,
    intent_scores_json TEXT,
    audio_tone_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_calls_timestamp ON calls(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_calls_intent ON calls(intent);
"""


def _connect(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """Create the table if it doesn't exist; add new columns idempotently."""
    with _connect(db_path) as conn:
        conn.executescript(SCHEMA)
        # Idempotent migration: add audio_tone_json to old DBs that pre-date it.
        try:
            cols = {row["name"] for row in conn.execute("PRAGMA table_info(calls)")}
            if "audio_tone_json" not in cols:
                conn.execute("ALTER TABLE calls ADD COLUMN audio_tone_json TEXT")
                logger.info("[DB] Migrated: added column audio_tone_json")
        except Exception as e:
            logger.warning(f"[DB] Migration check failed: {e}")
        conn.commit()
    logger.info(f"[DB] Initialized at {db_path}")


def save_call(
    filename: str,
    transcript: str,
    intent: Union[str, Dict],
    entities: Dict,
    scores: Dict,
    sentiment: Optional[Dict] = None,
    speech_emotion: Optional[Dict] = None,
    turns: Optional[List[Dict]] = None,
    duration_sec: Optional[float] = None,
    audio_tone: Optional[Dict] = None,
    db_path: str = DEFAULT_DB_PATH,
) -> int:
    """
    Insert a new call record. Returns the new row's id.
    Tolerant of intent being a plain string (legacy) or a dict.
    """
    init_db(db_path)

    intent_label = get_intent_label(intent)
    intent_conf = get_intent_confidence(intent)
    intent_scores = intent.get("all_scores") if isinstance(intent, dict) else None

    ts = datetime.now(timezone.utc).isoformat()

    with _connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO calls (
                filename, timestamp, duration_sec,
                intent, intent_confidence,
                sentiment, sentiment_score, speech_emotion,
                score_listening, score_communication, score_persuasion, score_outcome,
                transcript, entities_json, turns_json, intent_scores_json,
                audio_tone_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                filename,
                ts,
                float(duration_sec) if duration_sec is not None else None,
                intent_label,
                intent_conf,
                (sentiment or {}).get("label"),
                float((sentiment or {}).get("score") or 0.0),
                (speech_emotion or {}).get("label_pretty"),
                int(scores.get("Listening", 0) or 0),
                int(scores.get("Communication", 0) or 0),
                int(scores.get("Persuasion", 0) or 0),
                int(scores.get("Outcome", 0) or 0),
                transcript or "",
                json.dumps(entities or {}, ensure_ascii=False),
                json.dumps(turns or [], ensure_ascii=False, default=str),
                json.dumps(intent_scores, ensure_ascii=False) if intent_scores else None,
                json.dumps(audio_tone, ensure_ascii=False) if audio_tone else None,
            ),
        )
        conn.commit()
        new_id = cur.lastrowid
    logger.info(f"[DB] Inserted call id={new_id}  file={filename}  intent={intent_label}")
    return new_id


def get_all_calls(db_path: str = DEFAULT_DB_PATH, limit: int = 200) -> List[Dict[str, Any]]:
    """Return latest calls as a list of dicts (most recent first)."""
    init_db(db_path)
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT id, filename, timestamp, duration_sec, intent, intent_confidence,"
            " sentiment, sentiment_score, speech_emotion,"
            " score_listening, score_communication, score_persuasion, score_outcome"
            " FROM calls ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_call_by_id(call_id: int, db_path: str = DEFAULT_DB_PATH) -> Optional[Dict[str, Any]]:
    """Return a single call (full record) or None."""
    init_db(db_path)
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM calls WHERE id = ?", (call_id,)).fetchone()
    if not row:
        return None
    rec = dict(row)
    # Decode JSON columns
    for k in ("entities_json", "turns_json", "intent_scores_json", "audio_tone_json"):
        if rec.get(k):
            try:
                rec[k.replace("_json", "")] = json.loads(rec[k])
            except json.JSONDecodeError:
                pass
    return rec


def count_calls(db_path: str = DEFAULT_DB_PATH) -> int:
    init_db(db_path)
    with _connect(db_path) as conn:
        return conn.execute("SELECT COUNT(*) FROM calls").fetchone()[0]


def delete_call(call_id: int, db_path: str = DEFAULT_DB_PATH) -> bool:
    init_db(db_path)
    with _connect(db_path) as conn:
        cur = conn.execute("DELETE FROM calls WHERE id = ?", (call_id,))
        conn.commit()
    return cur.rowcount > 0
