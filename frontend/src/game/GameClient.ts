/** WebSocket 遊戲客戶端 */

import type { WSMessage, BetAmounts } from './MessageTypes';

type MessageHandler = (payload: any) => void;

export class GameClient {
  private ws: WebSocket | null = null;
  private handlers: Map<string, MessageHandler[]> = new Map();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private playerId: string;
  private url: string;

  constructor(playerId: string) {
    this.playerId = playerId;
    // 自動判斷 ws/wss
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    this.url = `${protocol}//${location.host}/ws/${playerId}`;
  }

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        console.log('[WS] 已連線');
        this.reconnectAttempts = 0;
        resolve();
      };

      this.ws.onmessage = (event) => {
        try {
          const msg: WSMessage = JSON.parse(event.data);
          this.dispatch(msg.type, msg.payload);
        } catch (e) {
          console.error('[WS] 訊息解析失敗:', e);
        }
      };

      this.ws.onclose = () => {
        console.log('[WS] 連線關閉');
        this.tryReconnect();
      };

      this.ws.onerror = (err) => {
        console.error('[WS] 連線錯誤:', err);
        reject(err);
      };
    });
  }

  disconnect(): void {
    this.maxReconnectAttempts = 0; // 停止重連
    this.ws?.close();
    this.ws = null;
  }

  /** 註冊訊息處理器 */
  on(type: string, handler: MessageHandler): void {
    if (!this.handlers.has(type)) {
      this.handlers.set(type, []);
    }
    this.handlers.get(type)!.push(handler);
  }

  /** 發送下注 */
  placeBet(bets: BetAmounts): void {
    this.send('PLACE_BET', { bets });
  }

  /** 確認下注 */
  confirmBet(): void {
    this.send('BET_CONFIRMED', {});
  }

  private send(type: string, payload: object): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type,
        payload,
        timestamp: Date.now(),
      }));
    }
  }

  private dispatch(type: string, payload: any): void {
    const handlers = this.handlers.get(type) || [];
    for (const handler of handlers) {
      handler(payload);
    }
  }

  /** 指數退避重連 */
  private tryReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) return;
    this.reconnectAttempts++;
    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
    console.log(`[WS] ${delay}ms 後重連 (第 ${this.reconnectAttempts} 次)`);
    setTimeout(() => this.connect().catch(() => {}), delay);
  }
}
