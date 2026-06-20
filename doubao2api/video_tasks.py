from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from typing import Any, Dict, Optional


def video_task_db_path() -> str:
    explicit = os.environ.get("DOUBAO_VIDEO_TASK_DB")
    if explicit:
        return explicit
    data_root = os.environ.get("DOUBAO_DATA_DIR")
    if not data_root:
        session_file = os.environ.get("DOUBAO_SESSION_FILE")
        if session_file:
            data_root = os.path.dirname(session_file)
    if not data_root:
        browser_data = os.environ.get("DOUBAO_BROWSER_DATA")
        if browser_data:
            data_root = os.path.dirname(browser_data)
    if not data_root:
        data_root = os.getcwd()
    return os.path.join(data_root, "video_tasks.sqlite3")


class VideoTaskStore:
    """Small SQLite-backed task registry for NewAPI-style video polling."""

    def __init__(self, path: str):
        self.path = path
        self._lock = threading.RLock()
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def _connection(self):
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._lock, self._connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS video_tasks (
                    task_id TEXT PRIMARY KEY,
                    created INTEGER NOT NULL,
                    updated INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    model TEXT,
                    provider_model TEXT,
                    account_id TEXT,
                    ratio TEXT,
                    duration INTEGER,
                    ref_image_key TEXT,
                    reference_image_keys TEXT,
                    request_json TEXT,
                    result_json TEXT,
                    error TEXT,
                    message TEXT
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_video_tasks_created ON video_tasks(created)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_video_tasks_status ON video_tasks(status)"
            )
            cols = {row["name"] for row in conn.execute("PRAGMA table_info(video_tasks)").fetchall()}
            if "account_id" not in cols:
                conn.execute("ALTER TABLE video_tasks ADD COLUMN account_id TEXT")
            if "reference_image_keys" not in cols:
                conn.execute("ALTER TABLE video_tasks ADD COLUMN reference_image_keys TEXT")

    def mark_interrupted(self) -> None:
        now = int(time.time())
        with self._lock, self._connection() as conn:
            conn.execute(
                """
                UPDATE video_tasks
                   SET status = 'failed',
                       updated = ?,
                       error = COALESCE(error, 'server restarted before task completed'),
                       message = COALESCE(message, 'server restarted before task completed')
                 WHERE status IN ('queued', 'in_progress')
                """,
                (now,),
            )

    def cleanup(self, max_age_seconds: int = 7 * 24 * 3600) -> None:
        cutoff = int(time.time()) - max_age_seconds
        with self._lock, self._connection() as conn:
            conn.execute(
                "DELETE FROM video_tasks WHERE created < ? AND status IN ('completed', 'failed')",
                (cutoff,),
            )

    def create(self, task_id: str, params: Dict[str, Any], request_body: Dict[str, Any]) -> Dict[str, Any]:
        now = int(time.time())
        with self._lock, self._connection() as conn:
            conn.execute(
                """
                INSERT INTO video_tasks (
                    task_id, created, updated, status, prompt, model, provider_model,
                    account_id, ratio, duration, ref_image_key, reference_image_keys, request_json
                ) VALUES (?, ?, ?, 'queued', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    now,
                    now,
                    params["prompt"],
                    params.get("model"),
                    params.get("provider_model"),
                    params.get("account_id"),
                    params.get("ratio"),
                    params.get("duration"),
                    params.get("ref_image_key"),
                    json.dumps(params.get("reference_image_keys") or [], ensure_ascii=False),
                    json.dumps(request_body, ensure_ascii=False),
                ),
            )
        task = self.get(task_id)
        if task is None:
            raise RuntimeError("Failed to create video task")
        return task

    def update(self, task_id: str, status: str, **fields: Any) -> None:
        allowed = {
            "result_json",
            "error",
            "message",
            "account_id",
            "ref_image_key",
            "reference_image_keys",
        }
        assignments = ["status = ?", "updated = ?"]
        values: list[Any] = [status, int(time.time())]
        for key, value in fields.items():
            if key not in allowed:
                continue
            assignments.append(f"{key} = ?")
            values.append(value)
        values.append(task_id)
        with self._lock, self._connection() as conn:
            conn.execute(
                f"UPDATE video_tasks SET {', '.join(assignments)} WHERE task_id = ?",
                values,
            )

    def get(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self._lock, self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM video_tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone()
        return dict(row) if row else None

    def counts(self) -> Dict[str, int]:
        with self._lock, self._connection() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) AS count FROM video_tasks GROUP BY status"
            ).fetchall()
        return {str(row["status"]): int(row["count"]) for row in rows}
