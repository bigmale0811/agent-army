# -*- coding: utf-8 -*-
"""TaskTracker SQLite 持久化測試。"""

import pytest

from agentforge.core.task_tracker import AgentStats, RunRecord, TaskTracker


@pytest.fixture()
def tracker(tmp_path):
    """建立臨時 TaskTracker。"""
    db = tmp_path / ".agentforge" / "tracker.db"
    t = TaskTracker(db)
    yield t
    t.close()


class TestRunLifecycle:
    """Pipeline 執行生命週期測試。"""

    def test_start_and_finish_run(self, tracker: TaskTracker) -> None:
        run_id = tracker.start_run("test-agent")
        assert isinstance(run_id, str)
        assert len(run_id) == 36  # Full UUID
        tracker.finish_run(run_id, success=True, total_cost_usd=0.01, total_seconds=1.5)
        runs = tracker.get_recent_runs()
        assert len(runs) == 1
        assert runs[0].status == "success"
        assert runs[0].total_cost_usd == 0.01

    def test_failed_run(self, tracker: TaskTracker) -> None:
        run_id = tracker.start_run("test-agent")
        tracker.finish_run(run_id, success=False)
        runs = tracker.get_recent_runs()
        assert runs[0].status == "failed"


class TestStepRecording:
    """步驟記錄測試。"""

    def test_record_step(self, tracker: TaskTracker) -> None:
        run_id = tracker.start_run("agent1")
        tracker.record_step(
            run_id, "step1", "shell", True,
            output="hello", elapsed_seconds=0.1,
        )
        tracker.record_step(
            run_id, "step2", "llm", True,
            output="result", cost_usd=0.003, tokens=150,
        )
        tracker.finish_run(run_id, success=True, total_cost_usd=0.003)


class TestStats:
    """統計查詢測試。"""

    def test_agent_stats(self, tracker: TaskTracker) -> None:
        r1 = tracker.start_run("agent1")
        tracker.finish_run(r1, success=True, total_cost_usd=0.01)
        r2 = tracker.start_run("agent1")
        tracker.finish_run(r2, success=False, total_cost_usd=0.02)

        stats = tracker.get_agent_stats("agent1")
        assert stats.total_runs == 2
        assert stats.success_count == 1
        assert stats.fail_count == 1
        assert stats.success_rate == 50.0
        assert stats.total_cost_usd == pytest.approx(0.03)

    def test_all_stats(self, tracker: TaskTracker) -> None:
        r1 = tracker.start_run("a1")
        tracker.finish_run(r1, True)
        r2 = tracker.start_run("a2")
        tracker.finish_run(r2, True)
        all_stats = tracker.get_all_stats()
        assert len(all_stats) == 2

    def test_empty_stats(self, tracker: TaskTracker) -> None:
        stats = tracker.get_agent_stats("nonexistent")
        assert stats.total_runs == 0
        assert stats.success_rate == 0.0


class TestRecentRuns:
    """最近記錄查詢測試。"""

    def test_recent_runs_limit(self, tracker: TaskTracker) -> None:
        for i in range(5):
            r = tracker.start_run(f"agent{i}")
            tracker.finish_run(r, True)
        runs = tracker.get_recent_runs(limit=3)
        assert len(runs) == 3


class TestWALMode:
    """WAL 模式測試。"""

    def test_wal_mode_enabled(self, tracker: TaskTracker) -> None:
        mode = tracker._conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"


class TestFrozenRecords:
    """不可變記錄測試。"""

    def test_run_record_frozen(self) -> None:
        r = RunRecord("id", "name", "ok", "t1", "t2", 0.0, 0.0)
        with pytest.raises(AttributeError):
            r.status = "x"  # type: ignore[misc]

    def test_agent_stats_frozen(self) -> None:
        s = AgentStats("a", 1, 1, 0, 0.0, 100.0)
        with pytest.raises(AttributeError):
            s.total_runs = 5  # type: ignore[misc]
