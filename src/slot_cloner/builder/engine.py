"""遊戲建置引擎 — 組裝 PixiJS 遊戲專案"""
from __future__ import annotations
import logging
import shutil
import subprocess
from pathlib import Path
from slot_cloner.models.game import GameModel
from slot_cloner.builder.config_generator import ConfigGenerator

logger = logging.getLogger(__name__)

# PixiJS 遊戲模板目錄（相對於此檔案）
TEMPLATE_DIR = Path(__file__).parent / "template"


class GameBuilder:
    """遊戲建置引擎

    將 PixiJS 模板 + game-config.json + 資源檔案組裝成可運行的 HTML5 遊戲。
    """

    def __init__(self, skip_npm: bool = False) -> None:
        self._skip_npm = skip_npm

    def build(
        self,
        game_model: GameModel,
        assets_dir: Path,
        output_dir: Path,
    ) -> Path:
        """建置遊戲

        Args:
            game_model: 遊戲模型
            assets_dir: 已擷取的資源目錄
            output_dir: 遊戲輸出目錄（game/）

        Returns:
            遊戲輸出目錄
        """
        game_dir = output_dir / "game"
        game_dir.mkdir(parents=True, exist_ok=True)

        # Step 1: 複製 PixiJS 模板
        self._copy_template(game_dir)

        # Step 2: 產出 game-config.json
        config_gen = ConfigGenerator()
        config_gen.generate(game_model, game_dir / "game-config.json")

        # Step 3: 複製資源到遊戲目錄
        self._copy_assets(assets_dir, game_dir / "public" / "assets")

        # Step 4: 執行 npm install + build（可選）
        if not self._skip_npm:
            self._run_npm_build(game_dir)

        logger.info("遊戲建置完成: %s", game_dir)
        return game_dir

    def _copy_template(self, target_dir: Path) -> None:
        """複製 PixiJS 遊戲模板"""
        # 判斷模板目錄是否存在且有內容
        template_files = list(TEMPLATE_DIR.iterdir()) if TEMPLATE_DIR.exists() else []
        if template_files:
            # 複製模板中的所有檔案
            for item in template_files:
                dest = target_dir / item.name
                if item.is_dir():
                    if dest.exists():
                        shutil.rmtree(dest)
                    shutil.copytree(item, dest)
                else:
                    shutil.copy2(item, dest)
            logger.info("模板已複製到 %s", target_dir)
        else:
            # 模板尚未建立（Sprint 2 DEV-2.6），建立最小 index.html
            self._create_minimal_game(target_dir)

    def _create_minimal_game(self, game_dir: Path) -> None:
        """建立最小可運行的遊戲頁面（模板未就緒時的備案）"""
        index_html = game_dir / "index.html"
        index_html.write_text("""<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Slot Clone</title>
    <style>
        body { margin: 0; background: #1a1a2e; display: flex; justify-content: center; align-items: center; min-height: 100vh; font-family: sans-serif; color: #e0e0e0; }
        #game { text-align: center; }
        h1 { color: #ffd700; }
        p { color: #aaa; }
    </style>
</head>
<body>
    <div id="game">
        <h1>Slot Clone</h1>
        <p>遊戲引擎載入中... 請用 PixiJS 模板替換此頁面</p>
        <p>game-config.json 已產出，可搭配 PixiJS 引擎使用</p>
        <script>
            fetch('./game-config.json')
                .then(r => r.json())
                .then(config => {
                    const info = document.createElement('pre');
                    info.style.cssText = 'text-align:left;background:#0d1117;padding:20px;border-radius:8px;max-width:600px;overflow:auto;';
                    info.textContent = JSON.stringify(config, null, 2);
                    document.getElementById('game').appendChild(info);
                });
        </script>
    </div>
</body>
</html>
""", encoding="utf-8")
        logger.info("建立最小遊戲頁面: %s", index_html)

    @staticmethod
    def _copy_assets(src: Path, dest: Path) -> None:
        """複製資源檔案"""
        if not src.exists():
            logger.warning("資源目錄不存在: %s", src)
            return
        dest.mkdir(parents=True, exist_ok=True)
        for item in src.rglob("*"):
            if item.is_file():
                rel = item.relative_to(src)
                target = dest / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, target)
        logger.info("資源已複製到 %s", dest)

    @staticmethod
    def _run_npm_build(game_dir: Path) -> None:
        """執行 npm install + build"""
        if not (game_dir / "package.json").exists():
            logger.info("無 package.json，跳過 npm build")
            return

        try:
            logger.info("執行 npm install...")
            subprocess.run(
                ["npm", "install"],
                cwd=str(game_dir),
                check=True,
                capture_output=True,
                text=True,
                timeout=120,
            )
            logger.info("執行 npm run build...")
            subprocess.run(
                ["npm", "run", "build"],
                cwd=str(game_dir),
                check=True,
                capture_output=True,
                text=True,
                timeout=120,
            )
            logger.info("npm build 完成")
        except FileNotFoundError:
            logger.warning("npm 未安裝，跳過 build")
        except subprocess.TimeoutExpired:
            logger.warning("npm build 逾時")
        except subprocess.CalledProcessError as e:
            logger.warning("npm build 失敗: %s", e.stderr[:500])
