"""Pipeline Orchestrator 測試"""
import pytest
from pathlib import Path
from slot_cloner.pipeline.context import PipelineContext
from slot_cloner.pipeline.orchestrator import PipelineOrchestrator, PHASE_ORDER
from slot_cloner.models.enums import PipelinePhase


@pytest.fixture
def orchestrator():
    return PipelineOrchestrator()


@pytest.fixture
def base_context(tmp_path):
    return PipelineContext(url="https://example.com", game_name="test", output_dir=tmp_path)


class TestPipelineOrchestrator:
    @pytest.mark.asyncio
    async def test_empty_run(self, orchestrator, base_context):
        """無任何 handler 時應能完成（全部跳過）"""
        result = await orchestrator.run(base_context)
        assert result.checkpoint == PipelinePhase.DONE

    @pytest.mark.asyncio
    async def test_single_phase(self, orchestrator, base_context):
        """單一 Phase 執行"""
        async def fake_recon(ctx):
            return ctx
        orchestrator.register(PipelinePhase.RECON, fake_recon)
        result = await orchestrator.run(base_context)
        assert result.checkpoint == PipelinePhase.DONE

    @pytest.mark.asyncio
    async def test_all_phases(self, orchestrator, base_context):
        """所有 Phase 依序執行"""
        executed = []
        for phase in PHASE_ORDER:
            async def make_handler(p=phase):
                async def handler(ctx):
                    executed.append(p)
                    return ctx
                return handler
            orchestrator.register(phase, await make_handler())
        result = await orchestrator.run(base_context)
        assert executed == list(PHASE_ORDER)
        assert result.checkpoint == PipelinePhase.DONE

    @pytest.mark.asyncio
    async def test_selective_phases(self, orchestrator, base_context):
        """只執行指定的 Phase"""
        executed = []
        for phase in PHASE_ORDER:
            async def make_handler(p=phase):
                async def handler(ctx):
                    executed.append(p)
                    return ctx
                return handler
            orchestrator.register(phase, await make_handler())

        result = await orchestrator.run(
            base_context,
            phases=(PipelinePhase.RECON, PipelinePhase.REPORT),
        )
        assert PipelinePhase.RECON in executed
        assert PipelinePhase.REPORT in executed
        assert PipelinePhase.SCRAPE not in executed

    @pytest.mark.asyncio
    async def test_dry_run(self, orchestrator, base_context):
        """Dry-run 模式不執行 handler"""
        executed = []
        async def fake_recon(ctx):
            executed.append("recon")
            return ctx
        orchestrator.register(PipelinePhase.RECON, fake_recon)

        dry_ctx = base_context.model_copy(update={"dry_run": True})
        result = await orchestrator.run(dry_ctx)
        assert len(executed) == 0  # handler 未被呼叫
        assert result.checkpoint == PipelinePhase.DONE

    @pytest.mark.asyncio
    async def test_checkpoint_skip(self, orchestrator):
        """從 checkpoint 恢復時跳過已完成的 Phase"""
        executed = []
        for phase in PHASE_ORDER:
            async def make_handler(p=phase):
                async def handler(ctx):
                    executed.append(p)
                    return ctx
                return handler
            orchestrator.register(phase, await make_handler())

        # 假設已完成到 SCRAPE
        ctx = PipelineContext(
            url="https://example.com",
            game_name="test",
            output_dir=Path("."),
            checkpoint=PipelinePhase.SCRAPE,
        )
        result = await orchestrator.run(ctx)
        # RECON 和 SCRAPE 應被跳過
        assert PipelinePhase.RECON not in executed
        assert PipelinePhase.SCRAPE not in executed
        assert PipelinePhase.REVERSE in executed

    @pytest.mark.asyncio
    async def test_phase_error_propagates(self, orchestrator, base_context):
        """Phase 錯誤應向上傳播"""
        async def failing_recon(ctx):
            raise RuntimeError("Recon failed")
        orchestrator.register(PipelinePhase.RECON, failing_recon)
        with pytest.raises(RuntimeError, match="Recon failed"):
            await orchestrator.run(base_context)
