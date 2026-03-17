# -*- coding: utf-8 -*-
"""GUI 安裝精靈 — tkinter 視窗介面，引導使用者完成 AgentForge 設定。

包含兩個主要類別：
- WizardController: 業務邏輯控制器（不依賴 tkinter，可單獨測試）
- GuiWizardApp: tkinter GUI 視窗（依賴 WizardController）

四步驟流程：
1. 選擇 AI 服務（Gemini / Claude / OpenAI / Ollama）
2. 設定通行證（API Key 或 CLI 安裝）
3. 測試連線
4. 完成！
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from threading import Thread
from typing import Any, Callable

from agentforge.setup.config_writer import ConfigWriter
from agentforge.setup.credential import CredentialManager
from agentforge.setup.detector import EnvironmentDetector


# ━━━━━━━━━━━━━━━━━━━━ Provider 資料定義 ━━━━━━━━━━━━━━━━━━━━

# 每個 provider 的顯示名稱、說明、是否需要 API Key、預設模型
PROVIDERS: dict[str, dict[str, Any]] = {
    "gemini": {
        "name": "Google Gemini ⭐ 推薦",
        "desc": "免費、速度快，推薦新手使用",
        "needs_key": True,
        "key_hint": "前往 https://aistudio.google.com/app/apikey 取得免費通行證",
        "key_prefix": "以 AIza 開頭的長字串",
        "default_model": "gemini/gemini-2.0-flash",
    },
    "claude-code": {
        "name": "Claude（訂閱制）",
        "desc": "需要 Claude Pro/Max 訂閱，不需要 API Key",
        "needs_key": False,
        "default_model": "claude-code/sonnet",
    },
    "openai": {
        "name": "OpenAI / ChatGPT",
        "desc": "付費 API，需要 API Key",
        "key_hint": "前往 https://platform.openai.com/api-keys 取得通行證",
        "key_prefix": "以 sk- 開頭的長字串",
        "needs_key": True,
        "default_model": "openai/gpt-4o-mini",
    },
    "ollama": {
        "name": "Ollama（本機執行）",
        "desc": "完全免費、私密，需先安裝 Ollama",
        "needs_key": False,
        "default_model": "ollama/qwen3:14b",
    },
}

# Provider 選擇順序（決定 radio button 排列）
PROVIDER_ORDER: list[str] = ["gemini", "claude-code", "openai", "ollama"]


# ━━━━━━━━━━━━━━━━━━━━ WizardState 資料結構 ━━━━━━━━━━━━━━━━━━━━


@dataclass
class GuiWizardState:
    """GUI 精靈的執行狀態。

    Attributes:
        current_step: 目前步驟（1-4）
        provider: 選擇的 AI Provider
        api_key: API Key（gemini/openai 需要，其他留空）
        model: 預設模型字串
        project_path: 專案根目錄路徑
        dry_run: True 表示模擬執行
        connection_ok: 連線測試是否通過
        connection_msg: 連線測試結果訊息
        created_files: 已建立的檔案路徑清單
    """

    current_step: int = 1
    provider: str = ""
    api_key: str = ""
    model: str = ""
    project_path: Path = field(default_factory=Path.cwd)
    dry_run: bool = False
    connection_ok: bool = False
    connection_msg: str = ""
    created_files: list[Path] = field(default_factory=list)


# ━━━━━━━━━━━━━━━━━━━━ WizardController ━━━━━━━━━━━━━━━━━━━━


class WizardController:
    """業務邏輯控制器 — 不依賴 tkinter，純 Python 可單獨測試。

    負責狀態管理、Provider 選擇邏輯、API Key 驗證、
    連線測試、設定檔寫入等所有業務操作。
    GUI 層只負責顯示和收集使用者輸入。

    Args:
        dry_run: True 表示模擬執行，不實際寫入檔案。
        project_path: 專案根目錄路徑，預設為當前工作目錄。
    """

    def __init__(
        self,
        dry_run: bool = False,
        project_path: Path | None = None,
    ) -> None:
        self.state = GuiWizardState(
            dry_run=dry_run,
            project_path=project_path or Path.cwd(),
        )
        self._detector = EnvironmentDetector()
        self._credential = CredentialManager()
        self._writer = ConfigWriter()

    # ── Provider 選擇 ──

    def select_provider(self, provider_key: str) -> None:
        """設定選擇的 Provider 並更新預設模型。

        Args:
            provider_key: Provider 識別碼（gemini / claude-code / openai / ollama）。
        """
        if provider_key not in PROVIDERS:
            return
        self.state.provider = provider_key
        self.state.model = PROVIDERS[provider_key]["default_model"]

    def needs_api_key(self) -> bool:
        """目前選擇的 Provider 是否需要 API Key 輸入。"""
        provider = PROVIDERS.get(self.state.provider, {})
        return provider.get("needs_key", False)

    # ── API Key 驗證 ──

    def validate_api_key(self, key: str) -> tuple[bool, str]:
        """驗證 API Key 格式。

        Args:
            key: 使用者輸入的 API Key。

        Returns:
            (是否通過, 結果訊息)
        """
        provider = self.state.provider
        if provider == "gemini":
            ok = self._credential.validate_gemini_key(key)
            if ok:
                return True, "格式正確"
            return False, "格式不正確（應以 AIza 開頭，長度 30 以上）"
        elif provider == "openai":
            ok = self._credential.validate_openai_key(key)
            if ok:
                return True, "格式正確"
            return False, "格式不正確（應以 sk- 開頭，長度 20 以上）"
        return True, ""

    # ── Claude CLI 偵測與安裝 ──

    def check_claude_cli(self) -> tuple[bool, str]:
        """偵測 Claude CLI 是否已安裝。阻塞式，需在背景執行緒呼叫。"""
        return self._detector.check_claude_cli()

    def check_node_npm(self) -> tuple[bool, str]:
        """偵測 npm 是否可用。阻塞式，需在背景執行緒呼叫。"""
        return self._detector.check_node_npm()

    def install_claude_cli(self) -> tuple[bool, str]:
        """透過 npm 安裝 Claude CLI。阻塞式，最長 5 分鐘。"""
        return self._detector.install_claude_cli()

    # ── Ollama 偵測 ──

    def check_ollama(self) -> tuple[bool, str]:
        """偵測 Ollama 是否在執行中。阻塞式，需在背景執行緒呼叫。"""
        return self._detector.check_ollama()

    # ── 連線測試 ──

    def run_connection_test(self) -> tuple[bool, str]:
        """執行連線測試。阻塞式，需在背景執行緒呼叫。

        Returns:
            (是否通過, 結果訊息)
        """
        provider = self.state.provider

        if provider == "gemini":
            # Gemini 只做格式驗證（不實際呼叫 API）
            if self.state.api_key:
                ok = self._credential.validate_gemini_key(self.state.api_key)
                msg = "通行證格式驗證通過" if ok else "通行證格式有誤"
                self.state.connection_ok = ok
                self.state.connection_msg = msg
                return ok, msg
            self.state.connection_ok = False
            self.state.connection_msg = "未提供通行證"
            return False, "未提供通行證"

        elif provider == "claude-code":
            ok, msg = self._detector.check_claude_cli()
            self.state.connection_ok = ok
            self.state.connection_msg = msg if ok else f"Claude CLI 未就緒：{msg}"
            return self.state.connection_ok, self.state.connection_msg

        elif provider == "openai":
            if self.state.api_key:
                ok = self._credential.validate_openai_key(self.state.api_key)
                msg = "通行證格式驗證通過" if ok else "通行證格式有誤"
                self.state.connection_ok = ok
                self.state.connection_msg = msg
                return ok, msg
            self.state.connection_ok = False
            self.state.connection_msg = "未提供通行證"
            return False, "未提供通行證"

        elif provider == "ollama":
            ok, msg = self._detector.check_ollama()
            self.state.connection_ok = ok
            self.state.connection_msg = msg if ok else f"Ollama 未就緒：{msg}"
            return self.state.connection_ok, self.state.connection_msg

        self.state.connection_ok = False
        self.state.connection_msg = "未知的 Provider"
        return False, "未知的 Provider"

    # ── 寫入設定檔 ──

    def write_all_config(self) -> list[Path]:
        """寫入所有設定檔（agentforge.yaml + example.yaml + credentials）。

        Returns:
            已建立的檔案路徑清單。
        """
        path = self.state.project_path
        provider = self.state.provider
        model = self.state.model
        dry_run = self.state.dry_run

        # 寫入主設定檔 + 範例 agent
        created = self._writer.write_config(
            project_path=path,
            provider=provider,
            model=model,
            dry_run=dry_run,
        )

        # 儲存通行證
        api_key = self.state.api_key if self.needs_api_key() else ""
        self._credential.save_credentials(
            path=path,
            provider=provider,
            api_key=api_key,
            dry_run=dry_run,
        )

        self.state.created_files = created
        return created

    # ── 導航控制 ──

    def can_go_next(self) -> tuple[bool, str]:
        """檢查目前步驟是否可以前進。

        Returns:
            (是否可前進, 原因說明)
        """
        step = self.state.current_step

        if step == 1:
            if not self.state.provider:
                return False, "請先選擇一個 AI 服務"
            return True, ""

        elif step == 2:
            if self.needs_api_key() and not self.state.api_key:
                return False, "請先輸入通行證"
            return True, ""

        elif step == 3:
            # 連線測試不強制通過，可以跳過
            return True, ""

        return False, "已經是最後一步"

    def go_next(self) -> int:
        """前進到下一步。

        Returns:
            新的步驟編號。
        """
        ok, _ = self.can_go_next()
        if ok and self.state.current_step < 4:
            self.state.current_step += 1
        return self.state.current_step

    def go_back(self) -> int:
        """退回上一步。

        Returns:
            新的步驟編號。
        """
        if self.state.current_step > 1:
            self.state.current_step -= 1
        return self.state.current_step


# ━━━━━━━━━━━━━━━━━━━━ GuiWizardApp（tkinter）━━━━━━━━━━━━━━━━━━━━


def _launch_gui(dry_run: bool = False, project_path: Path | None = None) -> None:
    """啟動 GUI 安裝精靈。

    獨立函式，方便從 CLI 進入點呼叫。
    tkinter import 延遲到此處，避免在無 GUI 環境下出錯。

    Args:
        dry_run: True 表示模擬執行。
        project_path: 專案根目錄路徑。
    """
    import tkinter as tk
    from tkinter import messagebox, ttk

    # 常數定義
    WIN_W, WIN_H = 600, 480
    # 微軟正黑體（Windows 內建，支援繁體中文）
    FONT_TITLE = ("Microsoft JhengHei UI", 16, "bold")
    FONT_BODY = ("Microsoft JhengHei UI", 11)
    FONT_SMALL = ("Microsoft JhengHei UI", 9)
    FONT_HINT = ("Microsoft JhengHei UI", 9, "italic")
    BG_COLOR = "#f5f5f5"
    ACCENT = "#2563eb"

    ctrl = WizardController(dry_run=dry_run, project_path=project_path)

    root = tk.Tk()
    root.title("AgentForge 安裝精靈")
    root.configure(bg=BG_COLOR)
    root.resizable(False, False)

    # 視窗置中
    sx = root.winfo_screenwidth()
    sy = root.winfo_screenheight()
    root.geometry(f"{WIN_W}x{WIN_H}+{(sx - WIN_W) // 2}+{(sy - WIN_H) // 2}")

    # ── 狀態變數 ──
    provider_var = tk.StringVar(value="gemini")
    api_key_var = tk.StringVar()
    step2_status_var = tk.StringVar()
    step3_status_var = tk.StringVar()
    busy = tk.BooleanVar(value=False)

    # ── 框架容器 ──
    content_frame = tk.Frame(root, bg=BG_COLOR)
    content_frame.pack(fill="both", expand=True, padx=20, pady=(10, 0))

    nav_frame = tk.Frame(root, bg=BG_COLOR)
    nav_frame.pack(fill="x", padx=20, pady=10)

    frames: dict[int, tk.Frame] = {}

    # ── 工具函式 ──

    def run_in_thread(task_fn: Callable, on_done_fn: Callable) -> None:
        """在背景執行緒執行 task_fn，完成後在主執行緒呼叫 on_done_fn。"""
        def wrapper() -> None:
            result = task_fn()
            root.after(0, lambda: on_done_fn(result))
        thread = Thread(target=wrapper, daemon=True)
        thread.start()

    def set_busy(is_busy: bool) -> None:
        """設定忙碌狀態，停用/啟用導航按鈕。"""
        busy.set(is_busy)
        state = "disabled" if is_busy else "normal"
        btn_next.config(state=state)
        btn_back.config(state=state)

    def show_step(step: int) -> None:
        """顯示指定步驟的框架，隱藏其他。"""
        for f in frames.values():
            f.pack_forget()
        frames[step].pack(fill="both", expand=True)
        # 更新導航按鈕
        btn_back.config(state="normal" if step > 1 else "disabled")
        if step == 4:
            btn_next.config(text="完成")
        else:
            btn_next.config(text="下一步 >")

    # ━━ Step 1：歡迎 + 選擇 Provider ━━

    f1 = tk.Frame(content_frame, bg=BG_COLOR)
    frames[1] = f1

    tk.Label(f1, text="歡迎使用 AgentForge", font=FONT_TITLE, bg=BG_COLOR).pack(
        anchor="w", pady=(10, 5)
    )
    tk.Label(
        f1,
        text="這個精靈會幫你一步步完成初始設定。\n請選擇你想使用的 AI 服務：",
        font=FONT_BODY,
        bg=BG_COLOR,
        justify="left",
    ).pack(anchor="w", pady=(0, 15))

    for key in PROVIDER_ORDER:
        info = PROVIDERS[key]
        radio_frame = tk.Frame(f1, bg=BG_COLOR)
        radio_frame.pack(fill="x", pady=3)
        tk.Radiobutton(
            radio_frame,
            text=info["name"],
            variable=provider_var,
            value=key,
            font=FONT_BODY,
            bg=BG_COLOR,
            activebackground=BG_COLOR,
            anchor="w",
        ).pack(side="left")
        tk.Label(
            radio_frame,
            text=f"  — {info['desc']}",
            font=FONT_SMALL,
            fg="#666",
            bg=BG_COLOR,
        ).pack(side="left")

    if dry_run:
        tk.Label(
            f1, text="（DRY-RUN 模式：不會寫入任何實際檔案）",
            font=FONT_HINT, fg="orange", bg=BG_COLOR,
        ).pack(anchor="w", pady=(15, 0))

    # ━━ Step 2：設定通行證 ━━

    f2 = tk.Frame(content_frame, bg=BG_COLOR)
    frames[2] = f2

    step2_title = tk.Label(f2, text="設定通行證", font=FONT_TITLE, bg=BG_COLOR)
    step2_title.pack(anchor="w", pady=(10, 5))

    step2_desc = tk.Label(f2, text="", font=FONT_BODY, bg=BG_COLOR, justify="left", wraplength=540)
    step2_desc.pack(anchor="w", pady=(0, 10))

    # API Key 輸入區（Gemini / OpenAI 時顯示）
    key_frame = tk.Frame(f2, bg=BG_COLOR)
    key_label = tk.Label(key_frame, text="通行證（API Key）：", font=FONT_BODY, bg=BG_COLOR)
    key_label.pack(anchor="w")
    key_entry = tk.Entry(key_frame, textvariable=api_key_var, font=FONT_BODY, width=50, show="*")
    key_entry.pack(fill="x", pady=(2, 5))
    key_validation_label = tk.Label(key_frame, text="", font=FONT_SMALL, bg=BG_COLOR)
    key_validation_label.pack(anchor="w")

    # Claude / Ollama 狀態區
    status_frame = tk.Frame(f2, bg=BG_COLOR)
    status_label = tk.Label(status_frame, textvariable=step2_status_var, font=FONT_BODY, bg=BG_COLOR, wraplength=540, justify="left")
    status_label.pack(anchor="w", pady=5)
    step2_progress = ttk.Progressbar(status_frame, mode="indeterminate", length=400)
    step2_install_btn = tk.Button(status_frame, text="安裝 Claude CLI", font=FONT_BODY)

    def validate_key_realtime(*_args: Any) -> None:
        """即時驗證 API Key 格式。"""
        key = api_key_var.get()
        if not key:
            key_validation_label.config(text="", fg="black")
            return
        ok, msg = ctrl.validate_api_key(key)
        if ok:
            key_validation_label.config(text=f"✅ {msg}", fg="green")
            ctrl.state.api_key = key
        else:
            key_validation_label.config(text=f"❌ {msg}", fg="red")

    api_key_var.trace_add("write", validate_key_realtime)

    def setup_step2_for_provider() -> None:
        """根據 provider 動態配置 Step 2 的顯示內容。"""
        # 先隱藏所有動態元件
        key_frame.pack_forget()
        status_frame.pack_forget()
        step2_progress.pack_forget()
        step2_install_btn.pack_forget()

        provider = ctrl.state.provider
        info = PROVIDERS.get(provider, {})

        if info.get("needs_key"):
            # Gemini / OpenAI：顯示 API Key 輸入框
            hint = info.get("key_hint", "")
            prefix = info.get("key_prefix", "")
            step2_desc.config(text=f"{hint}\n格式：{prefix}")
            key_frame.pack(fill="x", pady=5)
            api_key_var.set("")
            key_validation_label.config(text="")

        elif provider == "claude-code":
            step2_desc.config(text="Claude Code 使用訂閱制，不需要 API Key。\n正在偵測 Claude CLI...")
            status_frame.pack(fill="x", pady=5)
            step2_status_var.set("偵測中...")
            step2_progress.pack(pady=5)
            step2_progress.start(15)

            # 背景偵測 Claude CLI
            def check_claude() -> tuple[bool, str]:
                return ctrl.check_claude_cli()

            def on_claude_checked(result: tuple[bool, str]) -> None:
                ok, msg = result
                step2_progress.stop()
                step2_progress.pack_forget()
                if ok:
                    step2_status_var.set(f"✅ 找到 Claude CLI：{msg}")
                else:
                    # 偵測 npm 決定是否能自動安裝
                    npm_ok, npm_msg = ctrl.check_node_npm()
                    if npm_ok:
                        step2_status_var.set(
                            f"⚠️ 未找到 Claude CLI\n{npm_msg} 可用，點擊下方按鈕自動安裝。"
                        )
                        step2_install_btn.config(command=do_install_claude)
                        step2_install_btn.pack(pady=5)
                    else:
                        step2_status_var.set(
                            "⚠️ 未找到 Claude CLI，也找不到 npm。\n\n"
                            "請先安裝 Node.js：https://nodejs.org\n"
                            "安裝後重新開啟此精靈，或手動執行：\n"
                            "npm install -g @anthropic-ai/claude-code\n\n"
                            "你可以先按「下一步」繼續設定，之後再安裝。"
                        )

            run_in_thread(check_claude, on_claude_checked)

        elif provider == "ollama":
            step2_desc.config(text="Ollama 在本機執行，完全免費且私密。\n正在偵測 Ollama 服務...")
            status_frame.pack(fill="x", pady=5)
            step2_status_var.set("偵測中...")
            step2_progress.pack(pady=5)
            step2_progress.start(15)

            def check_oll() -> tuple[bool, str]:
                return ctrl.check_ollama()

            def on_oll_checked(result: tuple[bool, str]) -> None:
                ok, msg = result
                step2_progress.stop()
                step2_progress.pack_forget()
                if ok:
                    step2_status_var.set(f"✅ Ollama 執行中")
                else:
                    step2_status_var.set(
                        f"⚠️ Ollama 未執行：{msg}\n\n"
                        "請確認已安裝並啟動：https://ollama.ai\n"
                        "你可以先按「下一步」繼續設定，之後再啟動。"
                    )

            run_in_thread(check_oll, on_oll_checked)

    def do_install_claude() -> None:
        """執行 Claude CLI 自動安裝。"""
        step2_install_btn.pack_forget()
        step2_status_var.set("正在安裝 Claude CLI，請稍候...\n（大約 1-2 分鐘）")
        step2_progress.pack(pady=5)
        step2_progress.start(15)
        set_busy(True)

        def install_task() -> tuple[bool, str]:
            return ctrl.install_claude_cli()

        def on_installed(result: tuple[bool, str]) -> None:
            ok, msg = result
            step2_progress.stop()
            step2_progress.pack_forget()
            set_busy(False)
            if ok:
                step2_status_var.set(f"✅ {msg}")
            else:
                step2_status_var.set(
                    f"❌ 安裝失敗：{msg}\n\n"
                    "你可以之後手動執行：npm install -g @anthropic-ai/claude-code\n"
                    "或按「下一步」先繼續設定。"
                )

        run_in_thread(install_task, on_installed)

    # ━━ Step 3：測試連線 ━━

    f3 = tk.Frame(content_frame, bg=BG_COLOR)
    frames[3] = f3

    tk.Label(f3, text="測試連線", font=FONT_TITLE, bg=BG_COLOR).pack(
        anchor="w", pady=(10, 5)
    )
    tk.Label(
        f3, text="正在驗證你的設定是否正確...", font=FONT_BODY, bg=BG_COLOR,
    ).pack(anchor="w", pady=(0, 15))

    step3_progress = ttk.Progressbar(f3, mode="indeterminate", length=400)
    step3_result = tk.Label(
        f3, textvariable=step3_status_var, font=FONT_BODY,
        bg=BG_COLOR, wraplength=540, justify="left",
    )
    step3_result.pack(anchor="w", pady=10)

    def start_connection_test() -> None:
        """啟動連線測試。"""
        step3_status_var.set("測試中...")
        step3_progress.pack(pady=5)
        step3_progress.start(15)
        set_busy(True)

        def test_task() -> tuple[bool, str]:
            return ctrl.run_connection_test()

        def on_tested(result: tuple[bool, str]) -> None:
            ok, msg = result
            step3_progress.stop()
            step3_progress.pack_forget()
            set_busy(False)
            if ok:
                step3_status_var.set(f"✅ {msg}")
                step3_result.config(fg="green")
            else:
                step3_status_var.set(f"⚠️ {msg}\n\n（可以按「下一步」繼續，之後再處理）")
                step3_result.config(fg="#b45309")

        run_in_thread(test_task, on_tested)

    # ━━ Step 4：完成 ━━

    f4 = tk.Frame(content_frame, bg=BG_COLOR)
    frames[4] = f4

    tk.Label(f4, text="設定完成！", font=FONT_TITLE, bg=BG_COLOR, fg="green").pack(
        anchor="w", pady=(10, 5)
    )

    step4_files_label = tk.Label(
        f4, text="", font=FONT_BODY, bg=BG_COLOR, justify="left",
    )
    step4_files_label.pack(anchor="w", pady=10)

    tk.Label(
        f4,
        text="下一步：\n"
        "  在終端機中輸入以下指令試跑 AI：\n\n"
        "  python -m agentforge run example",
        font=FONT_BODY,
        bg=BG_COLOR,
        justify="left",
    ).pack(anchor="w", pady=10)

    def setup_step4() -> None:
        """設定 Step 4 的顯示內容（完成頁面）。"""
        # 寫入設定檔
        files = ctrl.write_all_config()

        if ctrl.state.dry_run:
            step4_files_label.config(
                text="（DRY-RUN 模式：以下檔案未實際建立）\n\n"
                + "\n".join(f"  📄 {f}" for f in files),
            )
        else:
            step4_files_label.config(
                text="已建立以下檔案：\n\n"
                + "\n".join(f"  ✅ {f}" for f in files),
            )

    # ━━ 導航列 ━━

    ttk.Separator(nav_frame, orient="horizontal").pack(fill="x", pady=(0, 8))

    btn_back = tk.Button(
        nav_frame, text="< 上一步", font=FONT_BODY, width=10, state="disabled",
    )
    btn_back.pack(side="left")

    btn_cancel = tk.Button(
        nav_frame, text="取消", font=FONT_BODY, width=8,
    )
    btn_cancel.pack(side="left", padx=10)

    btn_next = tk.Button(
        nav_frame, text="下一步 >", font=FONT_BODY, width=10,
        bg=ACCENT, fg="white", activebackground="#1d4ed8", activeforeground="white",
    )
    btn_next.pack(side="right")

    # ── 導航事件處理 ──

    def on_next() -> None:
        """處理「下一步」按鈕點擊。"""
        step = ctrl.state.current_step

        if step == 1:
            ctrl.select_provider(provider_var.get())
            ok, reason = ctrl.can_go_next()
            if not ok:
                messagebox.showwarning("提示", reason)
                return
            ctrl.go_next()
            setup_step2_for_provider()
            show_step(2)

        elif step == 2:
            if ctrl.needs_api_key():
                key = api_key_var.get()
                valid, msg = ctrl.validate_api_key(key)
                if not valid:
                    messagebox.showwarning("通行證格式有誤", msg)
                    return
                ctrl.state.api_key = key
            ctrl.go_next()
            show_step(3)
            start_connection_test()

        elif step == 3:
            ctrl.go_next()
            setup_step4()
            show_step(4)

        elif step == 4:
            root.destroy()

    def on_back() -> None:
        """處理「上一步」按鈕點擊。"""
        ctrl.go_back()
        show_step(ctrl.state.current_step)

    def on_cancel() -> None:
        """處理「取消」按鈕點擊。"""
        if messagebox.askyesno("取消安裝", "確定要取消安裝嗎？"):
            root.destroy()

    btn_next.config(command=on_next)
    btn_back.config(command=on_back)
    btn_cancel.config(command=on_cancel)

    # ── 啟動 ──
    show_step(1)
    root.mainloop()
