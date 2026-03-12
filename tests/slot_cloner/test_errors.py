"""錯誤類別單元測試"""
import pytest
from slot_cloner.errors import (
    SlotClonerError, PipelineError, ReconError, ScrapeError,
    ReverseError, BuildError, CheckpointError,
    AdapterError, ConfigError, ValidationError,
)


def test_base_error():
    err = SlotClonerError("test error", details="some details")
    assert str(err) == "test error"
    assert err.details == "some details"


def test_pipeline_error_has_phase():
    err = PipelineError("recon", "browser crashed")
    assert err.phase == "recon"
    assert "[recon]" in str(err)


def test_recon_error():
    err = ReconError("timeout after 60s")
    assert err.phase == "recon"
    assert isinstance(err, PipelineError)
    assert isinstance(err, SlotClonerError)


def test_scrape_error():
    err = ScrapeError("network error")
    assert err.phase == "scrape"


def test_reverse_error():
    err = ReverseError("JS parse failed", details="SyntaxError at line 42")
    assert err.phase == "reverse"
    assert err.details == "SyntaxError at line 42"


def test_build_error():
    err = BuildError("npm install failed")
    assert err.phase == "build"


def test_checkpoint_error():
    err = CheckpointError("file corrupted")
    assert err.phase == "checkpoint"


def test_adapter_error():
    err = AdapterError("no adapter found")
    assert isinstance(err, SlotClonerError)


def test_config_error():
    err = ConfigError("missing required field")
    assert isinstance(err, SlotClonerError)


def test_validation_error():
    err = ValidationError("invalid URL format")
    assert isinstance(err, SlotClonerError)


def test_error_hierarchy():
    """驗證錯誤繼承關係"""
    assert issubclass(PipelineError, SlotClonerError)
    assert issubclass(ReconError, PipelineError)
    assert issubclass(ScrapeError, PipelineError)
    assert issubclass(ReverseError, PipelineError)
    assert issubclass(BuildError, PipelineError)
    assert issubclass(AdapterError, SlotClonerError)
    assert issubclass(ConfigError, SlotClonerError)
    assert issubclass(ValidationError, SlotClonerError)
