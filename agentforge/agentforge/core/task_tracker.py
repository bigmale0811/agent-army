# -*- coding: utf-8 -*-
"""TaskTracker — SQLite 持久化執行記錄與成本追蹤。

使用 SQLite WAL 模式，三張表：
- runs：Pipeline 執行記錄
- step_runs：步驟執行記錄
- cost_log：成本記錄
"""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RunRecord:
    """Pipeline 執行記錄（不可變）。"""

    run_id: str
    agent_name: str
    status: str
    started_at: str
    finished_at: str
    total_cost_usd: float
    total_seconds: float


@dataclass(frozen=True)
class AgentStats:
    """Agent 統計資料（不可變）。"""

    agent_name: str
    total_runs: int
    success_count: int
    fail_count: int
    total_cost_usd: float
    success_rate: float


class TaskTracker:
    """SQLite 執行記錄追蹤器。"""

    def __init__(self, db_path: Path | str) -> None:
        """初始化追蹤器，建立資料庫與表結構。

        Args:
            db_path: SQLite 資料庫路徑。
        """
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = self._connect()
        self._init_tables()

    def _connect(self) -> sqlite3.Connection:
        """建立 SQLite 連線（WAL 模式）。"""
        conn = sqlite3.connect(str(self._db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self) -> None:
        """建立資料表結構。"""
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                agent_name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'running',
                started_at TEXT NOT NULL,
                finished_at TEXT,
                total_cost_usd REAL DEFAULT 0.0,
                total_seconds REAL DEFAULT 0.0
            );

            CREATE TABLE IF NOT EXISTS step_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                step_name TEXT NOT NULL,
                action TEXT NOT NULL,
                success INTEGER NOT NULL,
                output TEXT,
                error TEXT,
                cost_usd REAL DEFAULT 0.0,
                tokens INTEGER DEFAULT 0,
                elapsed_seconds REAL DEFAULT 0.0,
                FOREIGN KEY (run_id) REFERENCES runs(run_id)
            );

            CREATE TABLE IF NOT EXISTS cost_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                step_name TEXT NOT NULL,
                model TEXT,
                tokens_in INTEGER DEFAULT 0,
                tokens_out INTEGER DEFAULT 0,
                cost_usd REAL DEFAULT 0.0,
                logged_at TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES runs(run_id)
            );
        """)
        self._conn.commit()

    def start_run(self, agent_name: str) -> str:
        """開始新的 Pipeline 執行記錄。

        Args:
            agent_name: Agent 名稱。

        Returns:
            新建的 run_id。
        """
        run_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT INTO runs (run_id, agent_name, status, started_at) VALUES (?, ?, 'running', ?)",
            (run_id, agent_name, now),
        )
        self._conn.commit()
        return run_id

    def record_step(
        self,
        run_id: str,
        step_name: str,
        action: str,
        success: bool,
        output: str = "",
        error: str = "",
        cost_usd: float = 0.0,
        tokens: int = 0,
        elapsed_seconds: float = 0.0,
    ) -> None:
        """記錄步驟執行結果。"""
        self._conn.execute(
            """INSERT INTO step_runs
               (run_id, step_name, action, success, output, error, cost_usd, tokens, elapsed_seconds)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (run_id, step_name, action, int(success), output, error, cost_usd, tokens, elapsed_seconds),
        )
        self._conn.commit()

    def finish_run(
        self,
        run_id: str,
        success: bool,
        total_cost_usd: float = 0.0,
        total_seconds: float = 0.0,
    ) -> None:
        """完成 Pipeline 執行記錄。"""
        now = datetime.now(timezone.utc).isoformat()
        status = "success" if success else "failed"
        self._conn.execute(
            "UPDATE runs SET status=?, finished_at=?, total_cost_usd=?, total_seconds=? WHERE run_id=?",
            (status, now, total_cost_usd, total_seconds, run_id),
        )
        self._conn.commit()

    def get_recent_runs(self, limit: int = 10) -> list[RunRecord]:
        """取得最近的執行記錄。"""
        rows = self._conn.execute(
            "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            RunRecord(
                run_id=r["run_id"],
                agent_name=r["agent_name"],
                status=r["status"],
                started_at=r["started_at"],
                finished_at=r["finished_at"] or "",
                total_cost_usd=r["total_cost_usd"],
                total_seconds=r["total_seconds"],
            )
            for r in rows
        ]

    def get_agent_stats(self, agent_name: str) -> AgentStats:
        """取得特定 Agent 的統計。"""
        row = self._conn.execute(
            """SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) as ok,
                SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) as fail,
                SUM(total_cost_usd) as cost
               FROM runs WHERE agent_name=?""",
            (agent_name,),
        ).fetchone()
        total = row["total"] or 0
        ok = row["ok"] or 0
        return AgentStats(
            agent_name=agent_name,
            total_runs=total,
            success_count=ok,
            fail_count=row["fail"] or 0,
            total_cost_usd=row["cost"] or 0.0,
            success_rate=(ok / total * 100) if total > 0 else 0.0,
        )

    def get_all_stats(self) -> list[AgentStats]:
        """取得所有 Agent 的統計（單一聚合查詢，避免 N+1）。"""
        rows = self._conn.execute("""
            SELECT agent_name,
                   COUNT(*) as total,
                   SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) as ok,
                   SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) as fail,
                   SUM(total_cost_usd) as cost
            FROM runs
            GROUP BY agent_name
            ORDER BY agent_name
        """).fetchall()
        return [
            AgentStats(
                agent_name=r["agent_name"],
                total_runs=r["total"] or 0,
                success_count=r["ok"] or 0,
                fail_count=r["fail"] or 0,
                total_cost_usd=r["cost"] or 0.0,
                success_rate=((r["ok"] or 0) / r["total"] * 100) if r["total"] else 0.0,
            )
            for r in rows
        ]

    def __enter__(self) -> "TaskTracker":
        """支援 context manager 協定。"""
        return self

    def __exit__(self, *_: object) -> None:
        """離開 context manager 時自動關閉連線。"""
        self.close()

    def close(self) -> None:
        """關閉資料庫連線。"""
        self._conn.close()
