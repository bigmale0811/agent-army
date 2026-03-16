# -*- coding: utf-8 -*-
"""SaveStep 單元測試。

測試 Save 步驟的檔案寫入邏輯，使用 tmp_path fixture 確保測試隔離。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agentforge.schema import StepDef
from agentforge.steps.save_step import SaveStep
from agentforge.utils.template import TemplateEngine


@pytest.fixture
def template_engine() -> TemplateEngine:
    """建立 TemplateEngine 實例。"""
    return TemplateEngine()


@pytest.fixture
def simple_save_step_def(tmp_path: Path) -> StepDef:
    """建立簡單的 save StepDef（固定路徑）。"""
    output_file = tmp_path / "output.txt"
    return StepDef(
        name="save_result",
        action="save",
        path=str(output_file),
        content="Hello, AgentForge!",
    )


@pytest.fixture
def template_save_step_def(tmp_path: Path) -> StepDef:
    """建立含模板的 save StepDef。"""
    output_file = tmp_path / "{{ steps.analyze.output }}.txt"
    return StepDef(
        name="save_with_template",
        action="save",
        path=str(tmp_path / "report.md"),
        content="{{ steps.analyze.output }}",
    )


class TestSaveStepExecute:
    """execute() 方法測試。"""

    def test_execute_creates_file(
        self,
        simple_save_step_def: StepDef,
        template_engine: TemplateEngine,
        tmp_path: Path,
    ) -> None:
        """執行應建立指定路徑的檔案。"""
        step = SaveStep(simple_save_step_def, template_engine)
        output = step.execute({})

        assert output.success is True
        output_file = tmp_path / "output.txt"
        assert output_file.exists()

    def test_execute_writes_correct_content(
        self,
        simple_save_step_def: StepDef,
        template_engine: TemplateEngine,
        tmp_path: Path,
    ) -> None:
        """執行應寫入正確內容到檔案。"""
        step = SaveStep(simple_save_step_def, template_engine)
        step.execute({})

        content = (tmp_path / "output.txt").read_text(encoding="utf-8")
        assert content == "Hello, AgentForge!"

    def test_execute_creates_parent_dirs(
        self,
        template_engine: TemplateEngine,
        tmp_path: Path,
    ) -> None:
        """執行應自動建立不存在的父目錄。"""
        deep_path = tmp_path / "a" / "b" / "c" / "output.txt"
        step_def = StepDef(
            name="deep_save",
            action="save",
            path=str(deep_path),
            content="deep content",
        )
        step = SaveStep(step_def, template_engine)
        output = step.execute({})

        assert output.success is True
        assert deep_path.exists()

    def test_execute_output_contains_path(
        self,
        simple_save_step_def: StepDef,
        template_engine: TemplateEngine,
        tmp_path: Path,
    ) -> None:
        """執行結果的 output 應包含儲存路徑。"""
        step = SaveStep(simple_save_step_def, template_engine)
        output = step.execute({})

        assert "output.txt" in output.output
        assert "Saved to" in output.output

    def test_execute_with_template_content(
        self,
        template_engine: TemplateEngine,
        tmp_path: Path,
    ) -> None:
        """content 中的模板應被正確替換。"""
        step_def = StepDef(
            name="template_save",
            action="save",
            path=str(tmp_path / "result.txt"),
            content="{{ steps.process.output }}",
        )
        step = SaveStep(step_def, template_engine)
        context = {"steps": {"process": {"output": "processed data", "error": ""}}}
        output = step.execute(context)

        assert output.success is True
        content = (tmp_path / "result.txt").read_text(encoding="utf-8")
        assert content == "processed data"

    def test_execute_utf8_encoding(
        self,
        template_engine: TemplateEngine,
        tmp_path: Path,
    ) -> None:
        """應以 UTF-8 編碼寫入中文內容。"""
        step_def = StepDef(
            name="utf8_save",
            action="save",
            path=str(tmp_path / "chinese.txt"),
            content="你好，世界！繁體中文測試。",
        )
        step = SaveStep(step_def, template_engine)
        output = step.execute({})

        assert output.success is True
        content = (tmp_path / "chinese.txt").read_text(encoding="utf-8")
        assert content == "你好，世界！繁體中文測試。"

    def test_execute_success_zero_cost(
        self,
        simple_save_step_def: StepDef,
        template_engine: TemplateEngine,
    ) -> None:
        """save 步驟不應有 API 費用。"""
        step = SaveStep(simple_save_step_def, template_engine)
        output = step.execute({})

        assert output.cost_usd == 0.0
        assert output.tokens == 0


class TestSaveStepDryRun:
    """dry_run() 方法測試。"""

    def test_dry_run_does_not_create_file(
        self,
        simple_save_step_def: StepDef,
        template_engine: TemplateEngine,
        tmp_path: Path,
    ) -> None:
        """dry_run 不應實際建立檔案。"""
        step = SaveStep(simple_save_step_def, template_engine)
        output = step.dry_run({})

        assert output.success is True
        assert not (tmp_path / "output.txt").exists()

    def test_dry_run_output_contains_path(
        self,
        simple_save_step_def: StepDef,
        template_engine: TemplateEngine,
        tmp_path: Path,
    ) -> None:
        """dry_run 輸出應包含目標路徑資訊。"""
        step = SaveStep(simple_save_step_def, template_engine)
        output = step.dry_run({})

        assert "DRY-RUN" in output.output
        assert "SAVE" in output.output
        assert "output.txt" in output.output

    def test_dry_run_output_contains_content_preview(
        self,
        simple_save_step_def: StepDef,
        template_engine: TemplateEngine,
    ) -> None:
        """dry_run 輸出應包含內容預覽。"""
        step = SaveStep(simple_save_step_def, template_engine)
        output = step.dry_run({})

        assert "Hello, AgentForge!" in output.output
