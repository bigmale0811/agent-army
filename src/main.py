"""百家樂遊戲伺服器入口"""

import logging
import os
import re

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .api.ws_handler import GameRoom

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="百家樂遊戲伺服器", version="1.0.0")

# 遊戲房間（單房間模式）
game_room = GameRoom()

# 前端靜態檔案
frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
frontend_root = os.path.join(os.path.dirname(__file__), "..", "frontend")


@app.get("/")
async def serve_index():
    """提供前端首頁"""
    index_path = os.path.join(frontend_dist, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    # 開發模式：直接回傳 frontend/index.html
    dev_index = os.path.join(frontend_root, "index.html")
    if os.path.exists(dev_index):
        return FileResponse(dev_index)
    return {"message": "百家樂遊戲伺服器運行中，前端尚未建置"}


@app.websocket("/ws/{player_id}")
async def websocket_endpoint(websocket: WebSocket, player_id: str):
    """WebSocket 遊戲端點"""
    # 驗證 player_id 格式：只允許英數字和底線，長度 3-32
    # 防止任意字串作為 session key，避免 session 覆蓋與日誌注入
    if not re.match(r'^[a-zA-Z0-9_]{3,32}$', player_id):
        await websocket.close(code=1008)
        logger.warning("player_id 格式不合法，拒絕連線: %r", player_id)
        return
    await game_room.connect(player_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await game_room.handle_message(player_id, data)
    except WebSocketDisconnect:
        await game_room.disconnect(player_id)
        logger.info("玩家 %s 斷線", player_id)


@app.get("/health")
async def health():
    """健康檢查"""
    return {
        "status": "ok",
        "active_players": game_room.sessions.active_count,
        "game_state": game_room.state_machine.state.value,
        "cards_remaining": game_room.shoe.remaining,
    }


# 掛載靜態資源（放在路由之後，避免覆蓋 API 端點）
if os.path.exists(frontend_dist):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")
