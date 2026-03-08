# -*- coding: utf-8 -*-
"""
DEV-3: VRAM 監控模組。

提供 GPU 顯存使用量監控、安全檢查與自動清理功能。
用於 Singer Agent 管線中，確保 12GB VRAM 不會被撐爆。

功能：
- get_vram_usage()：取得 VRAM 使用量
- log_vram()：記錄 VRAM 到 log
- check_vram_safety()：安全閾值檢查（10GB 警告 / 11.5GB 危險）
- force_cleanup()：gc.collect + torch.cuda.empty_cache
- free_comfyui_models()：POST /free 卸載 ComfyUI 模型
"""
import gc
import json
import logging
import urllib.request
import urllib.error
from typing import NamedTuple

_logger = logging.getLogger(__name__)

# VRAM 閾值（MB）
VRAM_WARNING_MB = 10 * 1024    # 10GB
VRAM_CRITICAL_MB = 11.5 * 1024  # 11.5GB


class VramStatus(NamedTuple):
    """VRAM 狀態。"""
    used_mb: float
    total_mb: float
    available_mb: float


def _get_torch_cuda():
    """
    安全取得 torch.cuda 模組。

    Returns:
        torch.cuda 模組，或 None（torch 不可用 / 無 GPU）
    """
    try:
        import torch
        if torch.cuda.is_available():
            return torch.cuda
    except ImportError:
        pass
    return None


def get_vram_usage() -> VramStatus | None:
    """
    取得目前 GPU VRAM 使用量。

    Returns:
        VramStatus 或 None（無 GPU / torch 不可用）
    """
    cuda = _get_torch_cuda()
    if cuda is None:
        return None

    try:
        used = cuda.memory_allocated() / (1024 * 1024)
        total = cuda.get_device_properties(0).total_mem / (1024 * 1024)
        available = total - used
        return VramStatus(used_mb=used, total_mb=total, available_mb=available)
    except Exception as exc:
        _logger.warning("無法取得 VRAM 資訊：%s", exc)
        return None


def log_vram(label: str) -> VramStatus | None:
    """
    記錄目前 VRAM 使用量到 log。

    Args:
        label: 標籤（如 "Step 4 完成後"）

    Returns:
        VramStatus 或 None
    """
    status = get_vram_usage()
    if status is None:
        _logger.info("[VRAM] %s：無法偵測（無 GPU 或 torch 不可用）", label)
        return None

    _logger.info(
        "[VRAM] %s：%.0f MB / %.0f MB（剩餘 %.0f MB）",
        label, status.used_mb, status.total_mb, status.available_mb,
    )
    return status


def check_vram_safety(label: str = "") -> bool:
    """
    檢查 VRAM 是否在安全範圍內。

    - > 10GB (10240 MB)：WARNING
    - > 11.5GB (11776 MB)：CRITICAL + 嘗試 empty_cache

    Args:
        label: 檢查點標籤

    Returns:
        True = 安全，False = 危險
    """
    status = get_vram_usage()
    if status is None:
        return True  # 無法偵測，假定安全

    if status.used_mb > VRAM_CRITICAL_MB:
        _logger.critical(
            "[VRAM] CRITICAL %s：%.0f MB（超過 %.0f MB 紅線），嘗試緊急清理",
            label, status.used_mb, VRAM_CRITICAL_MB,
        )
        force_cleanup()
        return False

    if status.used_mb > VRAM_WARNING_MB:
        _logger.warning(
            "[VRAM] WARNING %s：%.0f MB（超過 %.0f MB 警戒線）",
            label, status.used_mb, VRAM_WARNING_MB,
        )
        return True

    return True


def force_cleanup() -> None:
    """
    強制清理 GPU 記憶體。

    執行 gc.collect() + torch.cuda.empty_cache()。
    """
    gc.collect()

    cuda = _get_torch_cuda()
    if cuda is not None:
        try:
            cuda.empty_cache()
            _logger.info("[VRAM] 已執行 gc.collect() + torch.cuda.empty_cache()")
        except Exception as exc:
            _logger.warning("[VRAM] empty_cache 失敗：%s", exc)
    else:
        _logger.info("[VRAM] 已執行 gc.collect()（torch 不可用，跳過 empty_cache）")


def free_comfyui_models(comfyui_url: str) -> bool:
    """
    呼叫 ComfyUI POST /free 卸載模型，釋放 VRAM。

    Args:
        comfyui_url: ComfyUI 服務 URL（如 http://localhost:8188）

    Returns:
        True = 成功，False = 失敗（僅 log warning，不拋出例外）
    """
    try:
        payload = json.dumps({"unload_models": True}).encode("utf-8")
        req = urllib.request.Request(
            f"{comfyui_url}/free",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            _logger.info(
                "[VRAM] ComfyUI 模型已卸載（POST /free，status=%d）",
                resp.status,
            )
        return True
    except Exception as exc:
        _logger.warning("[VRAM] ComfyUI 模型卸載失敗：%s", exc)
        return False
