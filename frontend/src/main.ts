/** 百家樂遊戲入口 */

import { GameScene } from './scenes/GameScene';

async function main() {
  const scene = new GameScene();
  await scene.init();
}

main().catch((err) => {
  console.error('遊戲初始化失敗:', err);
  document.body.innerHTML = `
    <div style="color: #E6EDF3; font-family: Arial; text-align: center; padding-top: 200px; background: #0D1117; height: 100vh;">
      <h1 style="color: #F0C040;">百家樂 Baccarat</h1>
      <p style="color: #DA3633; margin-top: 20px;">遊戲載入失敗</p>
      <p style="color: #8B949E; margin-top: 10px;">請確認後端伺服器已啟動：python -m uvicorn src.main:app --reload</p>
      <p style="color: #8B949E; margin-top: 5px;">錯誤: ${err.message}</p>
    </div>
  `;
});
