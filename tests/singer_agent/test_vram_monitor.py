# -*- coding: utf-8 -*-
"""
DEV-3: vram_monitor.py 測試。

測試覆蓋：
- get_vram_usage()：有 GPU / 無 GPU
- log_vram()：記錄 VRAM 到 log
- check_vram_safety()：安全 / 警告 / 危險
- force_cleanup()：gc.collect + empty_cache
- free_comfyui_models()：POST /free 成功 / 失敗
"""
from unittest.mock import MagicMock, patch, ANY

import pytest


class TestGetVramUsage:
    """get_vram_usage() 測試。"""

    def test_returns_none_when_no_torch(self):
        """torch 不可用時回傳 None。"""
        with patch(
            "src.singer_agent.vram_monitor._get_torch_cuda", return_value=None
        ):
            from src.singer_agent.vram_monitor import get_vram_usage
            assert get_vram_usage() is None

    def test_returns_vram_status_with_gpu(self):
        """有 GPU 時回傳 VramStatus。"""
        mock_cuda = MagicMock()
        mock_cuda.memory_allocated.return_value = 4 * 1024 * 1024 * 1024  # 4GB
        mock_props = MagicMock()
        mock_props.total_mem = 12 * 1024 * 1024 * 1024  # 12GB
        mock_cuda.get_device_properties.return_value = mock_props

        with patch(
            "src.singer_agent.vram_monitor._get_torch_cuda",
            return_value=mock_cuda,
        ):
            from src.singer_agent.vram_monitor import get_vram_usage
            status = get_vram_usage()
            assert status is not None
            assert abs(status.used_mb - 4096) < 1
            assert abs(status.total_mb - 12288) < 1
            assert abs(status.available_mb - 8192) < 1

    def test_returns_none_on_exception(self):
        """取得資訊失敗時回傳 None。"""
        mock_cuda = MagicMock()
        mock_cuda.memory_allocated.side_effect = RuntimeError("GPU error")

        with patch(
            "src.singer_agent.vram_monitor._get_torch_cuda",
            return_value=mock_cuda,
        ):
            from src.singer_agent.vram_monitor import get_vram_usage
            assert get_vram_usage() is None


class TestLogVram:
    """log_vram() 測試。"""

    def test_logs_vram_info(self, caplog):
        """有 GPU 時記錄 VRAM 到 log。"""
        mock_cuda = MagicMock()
        mock_cuda.memory_allocated.return_value = 2 * 1024 * 1024 * 1024
        mock_props = MagicMock()
        mock_props.total_mem = 12 * 1024 * 1024 * 1024
        mock_cuda.get_device_properties.return_value = mock_props

        with patch(
            "src.singer_agent.vram_monitor._get_torch_cuda",
            return_value=mock_cuda,
        ):
            import logging
            with caplog.at_level(logging.INFO):
                from src.singer_agent.vram_monitor import log_vram
                result = log_vram("Step 4 完成")
                assert result is not None
                assert "VRAM" in caplog.text

    def test_logs_no_gpu_message(self, caplog):
        """無 GPU 時記錄訊息。"""
        with patch(
            "src.singer_agent.vram_monitor._get_torch_cuda", return_value=None
        ):
            import logging
            with caplog.at_level(logging.INFO):
                from src.singer_agent.vram_monitor import log_vram
                result = log_vram("測試")
                assert result is None
                assert "無法偵測" in caplog.text


class TestCheckVramSafety:
    """check_vram_safety() 測試。"""

    def test_safe_when_no_gpu(self):
        """無 GPU 時回傳 True（假定安全）。"""
        with patch(
            "src.singer_agent.vram_monitor._get_torch_cuda", return_value=None
        ):
            from src.singer_agent.vram_monitor import check_vram_safety
            assert check_vram_safety("test") is True

    def test_safe_when_low_usage(self):
        """VRAM 用量低時回傳 True。"""
        mock_cuda = MagicMock()
        mock_cuda.memory_allocated.return_value = 4 * 1024 * 1024 * 1024  # 4GB
        mock_props = MagicMock()
        mock_props.total_mem = 12 * 1024 * 1024 * 1024
        mock_cuda.get_device_properties.return_value = mock_props

        with patch(
            "src.singer_agent.vram_monitor._get_torch_cuda",
            return_value=mock_cuda,
        ):
            from src.singer_agent.vram_monitor import check_vram_safety
            assert check_vram_safety("test") is True

    def test_warning_when_above_10gb(self, caplog):
        """VRAM > 10GB 時 log WARNING 但回傳 True。"""
        mock_cuda = MagicMock()
        # 10.5GB
        mock_cuda.memory_allocated.return_value = int(10.5 * 1024 * 1024 * 1024)
        mock_props = MagicMock()
        mock_props.total_mem = 12 * 1024 * 1024 * 1024
        mock_cuda.get_device_properties.return_value = mock_props

        with patch(
            "src.singer_agent.vram_monitor._get_torch_cuda",
            return_value=mock_cuda,
        ):
            import logging
            with caplog.at_level(logging.WARNING):
                from src.singer_agent.vram_monitor import check_vram_safety
                assert check_vram_safety("test") is True
                assert "WARNING" in caplog.text

    def test_critical_when_above_11_5gb(self, caplog):
        """VRAM > 11.5GB 時回傳 False 並嘗試清理。"""
        mock_cuda = MagicMock()
        # 11.8GB
        mock_cuda.memory_allocated.return_value = int(11.8 * 1024 * 1024 * 1024)
        mock_props = MagicMock()
        mock_props.total_mem = 12 * 1024 * 1024 * 1024
        mock_cuda.get_device_properties.return_value = mock_props

        with patch(
            "src.singer_agent.vram_monitor._get_torch_cuda",
            return_value=mock_cuda,
        ):
            import logging
            with caplog.at_level(logging.CRITICAL):
                from src.singer_agent.vram_monitor import check_vram_safety
                assert check_vram_safety("test") is False
                assert "CRITICAL" in caplog.text
                # 驗證 empty_cache 被呼叫
                mock_cuda.empty_cache.assert_called()


class TestForceCleanup:
    """force_cleanup() 測試。"""

    def test_calls_gc_and_empty_cache(self):
        """執行 gc.collect + empty_cache。"""
        mock_cuda = MagicMock()

        with patch(
            "src.singer_agent.vram_monitor._get_torch_cuda",
            return_value=mock_cuda,
        ), patch("src.singer_agent.vram_monitor.gc") as mock_gc:
            from src.singer_agent.vram_monitor import force_cleanup
            force_cleanup()
            mock_gc.collect.assert_called_once()
            mock_cuda.empty_cache.assert_called_once()

    def test_handles_no_cuda(self):
        """無 CUDA 時只跑 gc.collect。"""
        with patch(
            "src.singer_agent.vram_monitor._get_torch_cuda", return_value=None
        ), patch("src.singer_agent.vram_monitor.gc") as mock_gc:
            from src.singer_agent.vram_monitor import force_cleanup
            force_cleanup()
            mock_gc.collect.assert_called_once()


class TestFreeComfyuiModels:
    """free_comfyui_models() 測試。"""

    def test_success_returns_true(self):
        """POST /free 成功回傳 True。"""
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch(
            "src.singer_agent.vram_monitor.urllib.request.urlopen",
            return_value=mock_resp,
        ):
            from src.singer_agent.vram_monitor import free_comfyui_models
            assert free_comfyui_models("http://localhost:8188") is True

    def test_failure_returns_false(self):
        """POST /free 失敗回傳 False。"""
        import urllib.error
        with patch(
            "src.singer_agent.vram_monitor.urllib.request.urlopen",
            side_effect=urllib.error.URLError("Connection refused"),
        ):
            from src.singer_agent.vram_monitor import free_comfyui_models
            assert free_comfyui_models("http://localhost:8188") is False

    def test_sends_correct_payload(self):
        """確認送出正確的 JSON payload。"""
        import json

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch(
            "src.singer_agent.vram_monitor.urllib.request.urlopen",
            return_value=mock_resp,
        ) as mock_urlopen:
            from src.singer_agent.vram_monitor import free_comfyui_models
            free_comfyui_models("http://localhost:8188")

            # 驗證 Request 的 URL 和 data
            call_args = mock_urlopen.call_args
            req = call_args[0][0]
            assert "/free" in req.full_url
            payload = json.loads(req.data)
            assert payload == {"unload_models": True}
