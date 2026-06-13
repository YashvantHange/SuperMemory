"""Tier 2: SQLite storage — wraps file adapter with SQLite index for structured data."""

import json
import sqlite3
from pathlib import Path
from typing import Any

from storage.adapters.file import FileStorageAdapter
from uall_core.schemas.common import Experiment, PolicyVersion, Skill
from uall_core.schemas.events import Event, Feedback, RunEnd, RunStart
from uall_core.schemas.lesson import Lesson, MemorySearchRequest, PendingLesson
from uall_core.schemas.common import RetrievalTelemetryEvent, VersionRecord


class SQLiteStorageAdapter(FileStorageAdapter):
    """File storage + SQLite index for querying."""

    def __init__(self, base_dir: str | Path = ".uall"):
        super().__init__(base_dir)
        self.db_path = self.base / "uall.db"

    async def init(self) -> None:
        await super().init()
        conn = sqlite3.connect(self.db_path)
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS lessons_index (
                lesson_id TEXT PRIMARY KEY,
                status TEXT,
                workflow TEXT,
                step TEXT,
                namespace_id TEXT,
                overall_confidence REAL,
                data_json TEXT
            );
            CREATE TABLE IF NOT EXISTS runs_index (
                run_id TEXT PRIMARY KEY,
                workflow_id TEXT,
                status TEXT,
                data_json TEXT
            );
            CREATE TABLE IF NOT EXISTS pending_index (
                pending_id TEXT PRIMARY KEY,
                status TEXT,
                data_json TEXT
            );
            """
        )
        conn.commit()
        conn.close()

    def _index_lesson(self, lesson: Lesson) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """INSERT OR REPLACE INTO lessons_index
               (lesson_id, status, workflow, step, namespace_id, overall_confidence, data_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                lesson.lesson_id,
                lesson.status,
                lesson.stage.workflow,
                lesson.stage.step,
                lesson.namespace.namespace_id,
                lesson.confidence.overall,
                lesson.model_dump_json(),
            ),
        )
        conn.commit()
        conn.close()

    async def save_lesson(self, lesson: Lesson) -> str:
        result = await super().save_lesson(lesson)
        self._index_lesson(lesson)
        return result

    async def update_lesson(self, lesson: Lesson) -> None:
        await super().update_lesson(lesson)
        self._index_lesson(lesson)

    async def search_lessons(self, request: MemorySearchRequest) -> list[Lesson]:
        conn = sqlite3.connect(self.db_path)
        query = "SELECT data_json FROM lessons_index WHERE status='active'"
        params: list[Any] = []
        if request.workflow:
            query += " AND workflow=?"
            params.append(request.workflow)
        if request.step:
            query += " AND step=?"
            params.append(request.step)
        rows = conn.execute(query, params).fetchall()
        conn.close()
        if rows:
            lessons = [Lesson.model_validate_json(r[0]) for r in rows]
            return lessons[: request.top_k * 4]
        return await super().search_lessons(request)
