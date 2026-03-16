# -*- coding: utf-8 -*-
"""FailureHandler 三級修復測試。"""

import pytest

from agentforge.core.failure import (
    FailureHandler,
    FailureRecord,
    RepairLevel,
)


class TestRepairLevel:
    """修復等級判定測試。"""

    def test_level_1_retry_with_fix(self) -> None:
        handler = FailureHandler()
        assert handler.get_repair_level(1) == RepairLevel.RETRY_WITH_FIX

    def test_level_2_replan(self) -> None:
        handler = FailureHandler()
        assert handler.get_repair_level(2) == RepairLevel.REPLAN_PIPELINE

    def test_level_3_halt(self) -> None:
        handler = FailureHandler()
        assert handler.get_repair_level(3) == RepairLevel.HALT

    def test_level_4_still_halt(self) -> None:
        handler = FailureHandler()
        assert handler.get_repair_level(4) == RepairLevel.HALT


class TestRecordFailure:
    """失敗記錄測試。"""

    def test_record_first_failure(self) -> None:
        handler = FailureHandler()
        record = handler.record_failure("step1", "timeout", 1)
        assert record.step_name == "step1"
        assert record.error == "timeout"
        assert record.repair_level == RepairLevel.RETRY_WITH_FIX
        assert record.fix_prompt  # 非空
        assert handler.failure_count == 1

    def test_record_second_failure(self) -> None:
        handler = FailureHandler()
        handler.record_failure("step1", "error1", 1)
        record = handler.record_failure("step1", "error2", 2)
        assert record.repair_level == RepairLevel.REPLAN_PIPELINE
        assert record.fix_prompt == ""  # Level 2 無 fix_prompt
        assert handler.failure_count == 2

    def test_record_third_failure_halt(self) -> None:
        handler = FailureHandler()
        handler.record_failure("s1", "e1", 1)
        handler.record_failure("s1", "e2", 2)
        record = handler.record_failure("s1", "e3", 3)
        assert record.repair_level == RepairLevel.HALT
        assert handler.should_halt()


class TestFixPrompt:
    """修復 prompt 測試。"""

    def test_fix_prompt_contains_error(self) -> None:
        handler = FailureHandler()
        prompt = handler.build_fix_prompt("step1", "connection refused")
        assert "step1" in prompt
        assert "connection refused" in prompt

    def test_fix_prompt_contains_history(self) -> None:
        handler = FailureHandler()
        handler.record_failure("step0", "prev error", 1)
        prompt = handler.build_fix_prompt("step1", "new error")
        assert "prev error" in prompt


class TestReport:
    """錯誤報告測試。"""

    def test_empty_report(self) -> None:
        handler = FailureHandler()
        report = handler.generate_report()
        assert "無失敗記錄" in report

    def test_report_contains_all_failures(self) -> None:
        handler = FailureHandler()
        handler.record_failure("step1", "error1", 1)
        handler.record_failure("step2", "error2", 2)
        report = handler.generate_report()
        assert "step1" in report
        assert "step2" in report
        assert "error1" in report
        assert "error2" in report
        assert "總失敗次數" in report


class TestReset:
    """重置測試。"""

    def test_reset_clears_failures(self) -> None:
        handler = FailureHandler()
        handler.record_failure("s1", "e1", 1)
        handler.reset()
        assert handler.failure_count == 0
        assert not handler.should_halt()


class TestFailureRecordFrozen:
    """FailureRecord 不可變測試。"""

    def test_frozen(self) -> None:
        record = FailureRecord(
            step_name="s", error="e", retry_count=1,
            repair_level=RepairLevel.HALT,
        )
        with pytest.raises(AttributeError):
            record.step_name = "x"  # type: ignore[misc]
