"""Step 3: 下載 agent-army — 從 GitHub clone 專案。

處理路徑選擇、既有專案偵測、clone、依賴安裝、結構驗證。
只使用 Python 標準庫。
"""

import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

# agent-army 預設 repo URL
AGENT_ARMY_REPO_URL = "https://github.com/bigmale0811/agent-army.git"

# 專案必要結構
_REQUIRED_ITEMS = [
    "CLAUDE.md",
    ".claude/settings.json",
    ".claude/rules/common",
    "scripts/hooks",
    "data/memory",
]


def check_target_path(path: Path) -> str:
    """檢查目標路徑的狀態。

    Returns:
        "new" — 路徑不存在或為空目錄，可以 clone
        "existing" — 已是有效的 agent-army 專案
        "occupied" — 路徑有檔案但不是 agent-army 專案
    """
    if not path.exists():
        return "new"

    # 空目錄視為 new
    if path.is_dir() and not any(path.iterdir()):
        return "new"

    # 檢查是否為有效的 agent-army 專案
    has_claude_md = (path / "CLAUDE.md").exists()
    has_settings = (path / ".claude" / "settings.json").exists()

    if has_claude_md and has_settings:
        return "existing"

    return "occupied"


def clone_agent_army(
    target_path: Path,
    repo_url: Optional[str] = None,
) -> bool:
    """從 GitHub clone agent-army。

    Args:
        target_path: 安裝目標路徑。
        repo_url: 自訂 repo URL（預設使用 AGENT_ARMY_REPO_URL）。

    Returns:
        True 代表 clone 成功。
    """
    url = repo_url or AGENT_ARMY_REPO_URL

    try:
        result = subprocess.run(
            ["git", "clone", url, str(target_path)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        return False
    except FileNotFoundError:
        return False
    except OSError:
        return False


def install_dependencies(project_path: Path) -> bool:
    """安裝 Python 依賴。

    Args:
        project_path: 專案路徑。

    Returns:
        True 代表安裝成功。
    """
    req_file = project_path / "requirements.txt"

    if not req_file.exists():
        return False

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(req_file)],
            capture_output=True,
            text=True,
            timeout=300,
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        return False
    except Exception:
        return False


def verify_project_structure(project_path: Path) -> List[str]:
    """驗證專案結構是否完整。

    Args:
        project_path: 專案路徑。

    Returns:
        缺少的項目列表，空 list 代表結構完整。
    """
    missing = []
    for item in _REQUIRED_ITEMS:
        if not (project_path / item).exists():
            missing.append(item)
    return missing


def setup_download(context: Dict) -> Dict:
    """互動式下載 agent-army 專案。

    流程：
    1. 詢問安裝路徑
    2. 檢查路徑狀態（new/existing/occupied）
    3. clone 或使用既有專案
    4. 安裝依賴
    5. 驗證結構

    Args:
        context: 安裝精靈的上下文 dict。

    Returns:
        更新後的 context。
    """
    from .wizard import ask_input, ask_yes_no, print_fail, print_info, print_ok, print_warn

    # 1. 詢問安裝路徑
    default_path = "D:\\Projects\\agent-army"
    path_str = ask_input("agent-army 安裝路徑", default=default_path)
    target_path = Path(path_str)

    # 2. 檢查路徑狀態
    status = check_target_path(target_path)

    if status == "existing":
        print_ok(f"偵測到既有專案：{target_path}")
        context["project_path"] = target_path
        context["is_existing_project"] = True
    elif status == "occupied":
        print_warn(f"路徑 {target_path} 已有檔案但不是 agent-army 專案")
        if not ask_yes_no("要覆蓋嗎？", default=False):
            print_info("請選擇其他路徑")
            return context
        # 繼續 clone（git clone 會失敗如果目錄不空，
        # 使用者需要自己清理）
        context["project_path"] = target_path
        context["is_existing_project"] = False
    else:
        # new — 直接 clone
        context["project_path"] = target_path
        context["is_existing_project"] = False

    # 3. Clone（如果不是既有專案）
    if not context.get("is_existing_project"):
        print_info("正在從 GitHub 下載 agent-army...")
        print_info(f"來源：{AGENT_ARMY_REPO_URL}")

        success = clone_agent_army(target_path)
        if success:
            print_ok("下載完成！")
        else:
            print_fail("下載失敗，請確認網路連線和 Git 設定")
            print_info(f"手動下載：git clone {AGENT_ARMY_REPO_URL} {target_path}")
            return context

    # 4. 安裝依賴
    print_info("正在安裝 Python 依賴...")
    if install_dependencies(target_path):
        print_ok("依賴安裝完成")
    else:
        print_warn("依賴安裝失敗或找不到 requirements.txt")
        print_info(f"稍後可手動執行：pip install -r {target_path}/requirements.txt")

    # 5. 驗證結構
    missing = verify_project_structure(target_path)
    if not missing:
        print_ok("專案結構驗證通過")
    else:
        print_warn(f"缺少 {len(missing)} 個項目：{', '.join(missing)}")

    context["project_name"] = target_path.name
    return context
