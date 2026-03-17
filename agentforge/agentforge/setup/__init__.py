# -*- coding: utf-8 -*-
"""AgentForge Setup 模組 — 安裝精靈與環境設定工具。

公開 API：
- EnvironmentDetector: 偵測本機環境（Python 版本、CLI 工具）
- CredentialManager: 管理 API 通行證的儲存與驗證
- ConfigWriter: 產生 agentforge.yaml 設定檔
- SetupWizard: 互動式安裝精靈主流程（CLI 版）
- WizardController: GUI 安裝精靈的業務邏輯控制器
"""

from agentforge.setup.config_writer import ConfigWriter
from agentforge.setup.credential import CredentialManager
from agentforge.setup.detector import EnvironmentDetector
from agentforge.setup.gui_wizard import WizardController
from agentforge.setup.wizard import SetupWizard

__all__ = [
    "EnvironmentDetector",
    "CredentialManager",
    "ConfigWriter",
    "SetupWizard",
    "WizardController",
]
