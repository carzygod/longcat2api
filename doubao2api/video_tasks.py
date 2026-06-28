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
                    message TEXT,
                    provider_task_id TEXT,
                    conversation_id TEXT,
                    local_conversation_id TEXT,
                    accepted_at INTEGER,
                    last_recovery_at INTEGER,
                    recovery_attempts INTEGER DEFAULT 0,
                    quota_reservation_id TEXT,
                    quota_units INTEGER
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
            migrations = {
                "account_id": "ALTER TABLE video_tasks ADD COLUMN account_id TEXT",
                "reference_image_keys": "ALTER TABLE video_tasks ADD COLUMN reference_image_keys TEXT",
                "provider_task_id": "ALTER TABLE video_tasks ADD COLUMN provider_task_id TEXT",
                "conversation_id": "ALTER TABLE video_tasks ADD COLUMN conversation_id TEXT",
                "local_conversation_id": "ALTER TABLE video_tasks ADD COLUMN local_conversation_id TEXT",
                "accepted_at": "ALTER TABLE video_tasks ADD COLUMN accepted_at INTEGER",
                "last_recovery_at": "ALTER TABLE video_tasks ADD COLUMN last_recovery_at INTEGER",
                "recovery_attempts": "ALTER TABLE video_tasks ADD COLUMN recovery_attempts INTEGER DEFAULT 0",
                "quota_reservation_id": "ALTER TABLE video_tasks ADD COLUMN quota_reservation_id TEXT",
                "quota_units": "ALTER TABLE video_tasks ADD COLUMN quota_units INTEGER",
            }
            for name, sql in migrations.items():
                if name not in cols:
                    conn.execute(sql)

    @staticmethod
    def _is_terminal_failure_message(message: Any = "") -> bool:
        text = str(message or "").lower()
        if "视频生成" in text and any(marker in text for marker in (
            "今日视频生成免费次数已用完",
            "视频生成免费次数已用完",
            "免费次数已用完",
            "次数已用完",
            "即可继续使用视频生成",
            "继续使用视频生成",
            "开通豆包专业版",
            "开通加强套餐",
            "开通套餐",
        )):
            return True
        return any(marker in text for marker in (
            "积分不足",
            "余额不足",
            "权益不足",
            "没有相关权益",
            "没有视频生成权益",
            "额度不足",
            "额度已用完",
            "视频生成额度已用完",
            "quota exceeded",
            "quota exhausted",
            "quota insufficient",
            "quota limit",
        ))

    @staticmethod
    def _is_accepted_pending_result(
        result_json: Any,
        message: Any = "",
        *,
        provider_task_id: Any = "",
        conversation_id: Any = "",
    ) -> bool:
        if isinstance(result_json, str) and result_json.strip():
            try:
                result_json = json.loads(result_json)
            except json.JSONDecodeError:
                result_json = {}
        has_binding_id = bool(str(provider_task_id or "").strip() or str(conversation_id or "").strip())
        if isinstance(result_json, dict):
            message = message or result_json.get("message", "")
            if VideoTaskStore._is_terminal_failure_message(message):
                return False
            has_binding_id = has_binding_id or bool(
                str(result_json.get("conversation_id") or "").strip()
                or str(result_json.get("provider_task_id") or "").strip()
            )
            if has_binding_id and result_json.get("pending"):
                return True
        text = str(message or "").lower()
        if VideoTaskStore._is_terminal_failure_message(text):
            return False
        if not has_binding_id:
            return False
        return any(
            marker in text
            for marker in (
                "video generation accepted",
                "generating video",
                "will notify",
                "accepted the video request",
                "video is being generated",
                "生成好后",
                "正在为您生成",
                "正在生成",
                "预计等待",
                "视频生成",
            )
        )

    def mark_interrupted(self) -> None:
        now = int(time.time())
        with self._lock, self._connection() as conn:
            rows = conn.execute(
                """
                SELECT task_id, status, result_json, message, provider_task_id, conversation_id
                  FROM video_tasks
                 WHERE status IN ('queued', 'in_progress')
                """
            ).fetchall()
            for row in rows:
                task_id = row["task_id"]
                if self._is_accepted_pending_result(
                    row["result_json"],
                    row["message"],
                    provider_task_id=row["provider_task_id"],
                    conversation_id=row["conversation_id"],
                ):
                    conn.execute(
                        """
                        UPDATE video_tasks
                           SET status = 'in_progress',
                               updated = ?,
                               error = NULL
                         WHERE task_id = ?
                        """,
                        (now, task_id),
                    )
                    continue
                conn.execute(
                    """
                    UPDATE video_tasks
                       SET status = 'failed',
                           updated = ?,
                           error = COALESCE(error, 'server restarted before task completed'),
                           message = COALESCE(message, 'server restarted before task completed')
                     WHERE task_id = ?
                    """,
                    (now, task_id),
                )

    def normalize_completed(self) -> None:
        with self._lock, self._connection() as conn:
            conn.execute(
                """
                UPDATE video_tasks
                   SET error = NULL
                 WHERE status = 'completed'
                   AND result_json IS NOT NULL
                """
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
                    account_id, ratio, duration, ref_image_key, reference_image_keys,
                    request_json, provider_task_id, conversation_id, local_conversation_id,
                    quota_reservation_id, quota_units
                ) VALUES (?, ?, ?, 'queued', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    params.get("provider_task_id"),
                    params.get("conversation_id"),
                    params.get("local_conversation_id"),
                    params.get("quota_reservation_id"),
                    params.get("quota_units"),
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
            "provider_task_id",
            "conversation_id",
            "local_conversation_id",
            "accepted_at",
            "last_recovery_at",
            "recovery_attempts",
            "quota_reservation_id",
            "quota_units",
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

    def mark_recovery_attempt(self, task_id: str) -> None:
        now = int(time.time())
        with self._lock, self._connection() as conn:
            conn.execute(
                """
                UPDATE video_tasks
                   SET updated = ?,
                       last_recovery_at = ?,
                       recovery_attempts = COALESCE(recovery_attempts, 0) + 1
                 WHERE task_id = ?
                """,
                (now, now, task_id),
            )

    def recovery_candidates(
        self,
        *,
        min_interval_seconds: int = 30,
        limit: int = 20,
    ) -> list[Dict[str, Any]]:
        cutoff = int(time.time()) - max(0, int(min_interval_seconds))
        with self._lock, self._connection() as conn:
            rows = conn.execute(
                """
                SELECT *
                  FROM video_tasks
                 WHERE status = 'in_progress'
                   AND (accepted_at IS NOT NULL OR result_json IS NOT NULL OR message IS NOT NULL)
                   AND (last_recovery_at IS NULL OR last_recovery_at <= ?)
                 ORDER BY updated ASC
                 LIMIT ?
                """,
                (cutoff, max(1, int(limit))),
            ).fetchall()
        return [
            dict(row)
            for row in rows
            if self._is_accepted_pending_result(
                row["result_json"],
                row["message"],
                provider_task_id=row["provider_task_id"],
                conversation_id=row["conversation_id"],
            )
        ]

    def counts(self) -> Dict[str, int]:
        with self._lock, self._connection() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) AS count FROM video_tasks GROUP BY status"
            ).fetchall()
        return {str(row["status"]): int(row["count"]) for row in rows}
