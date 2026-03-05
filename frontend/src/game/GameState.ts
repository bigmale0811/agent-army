/** 前端遊戲狀態管理 */

import type {
  GameStateType, CardData, BetAmounts,
  PlayerInitPayload, StateChangePayload, CardDealtPayload,
  GameResultPayload, SettleResultPayload,
} from './MessageTypes';

type StateListener = () => void;

export class GameState {
  // 玩家資料
  playerId = '';
  balance = 0;
  minBet = 10;
  maxBet = 5000;

  // 遊戲狀態
  currentState: GameStateType = 'IDLE';
  countdown = 0;

  // 下注
  currentBets: BetAmounts = {};
  selectedChip = 100;
  betConfirmed = false;

  // 牌面
  playerCards: CardData[] = [];
  bankerCards: CardData[] = [];
  playerTotal = 0;
  bankerTotal = 0;

  // 結果
  winner: 'player' | 'banker' | 'tie' | null = null;
  playerPair = false;
  bankerPair = false;
  lastNetChange = 0;

  // 訊息
  message = '';

  private listeners: StateListener[] = [];

  /** 註冊狀態變更監聽器 */
  subscribe(listener: StateListener): () => void {
    this.listeners.push(listener);
    return () => {
      this.listeners = this.listeners.filter(l => l !== listener);
    };
  }

  private notify(): void {
    for (const listener of this.listeners) {
      listener();
    }
  }

  /** 處理 PLAYER_INIT */
  handlePlayerInit(payload: PlayerInitPayload): void {
    this.playerId = payload.player_id;
    this.balance = payload.balance;
    this.minBet = payload.min_bet;
    this.maxBet = payload.max_bet;
    this.notify();
  }

  /** 處理 STATE_CHANGE */
  handleStateChange(payload: StateChangePayload): void {
    const prevState = this.currentState;
    this.currentState = payload.state;
    this.countdown = payload.countdown ?? 0;

    // 只在「進入」BETTING 時清空，倒數 tick 不清空
    if (payload.state === 'BETTING' && prevState !== 'BETTING') {
      this.playerCards = [];
      this.bankerCards = [];
      this.playerTotal = 0;
      this.bankerTotal = 0;
      this.winner = null;
      this.playerPair = false;
      this.bankerPair = false;
      this.lastNetChange = 0;
      this.message = '';
      this.currentBets = {};
      this.betConfirmed = false;
    }
    this.notify();
  }

  /** 處理 CARD_DEALT */
  handleCardDealt(payload: CardDealtPayload): void {
    if (payload.target === 'player') {
      this.playerCards.push(payload.card);
      this.playerTotal = payload.hand_value;
    } else {
      this.bankerCards.push(payload.card);
      this.bankerTotal = payload.hand_value;
    }
    this.notify();
  }

  /** 處理 GAME_RESULT */
  handleGameResult(payload: GameResultPayload): void {
    this.winner = payload.winner;
    this.playerTotal = payload.player_total;
    this.bankerTotal = payload.banker_total;
    this.playerPair = payload.player_pair;
    this.bankerPair = payload.banker_pair;

    const winnerText = { player: '閒贏', banker: '莊贏', tie: '和局' };
    this.message = `${winnerText[payload.winner]}！ 閒 ${payload.player_total} vs 莊 ${payload.banker_total}`;
    this.notify();
  }

  /** 處理 SETTLE_RESULT */
  handleSettleResult(payload: SettleResultPayload): void {
    this.balance = payload.new_balance;
    this.lastNetChange = payload.net_change;

    if (payload.net_change > 0) {
      this.message += ` | +$${payload.net_change.toFixed(0)}`;
    } else if (payload.net_change < 0) {
      this.message += ` | -$${Math.abs(payload.net_change).toFixed(0)}`;
    }
    this.notify();
  }

  /** 處理錯誤 */
  handleError(payload: { code: string; message: string }): void {
    this.message = `錯誤: ${payload.message}`;
    this.notify();
  }

  /** 在指定押注區加注 */
  addBet(zone: string): void {
    if (this.currentState !== 'BETTING') return;

    const current = (this.currentBets as any)[zone] || 0;
    const totalBets = Object.values(this.currentBets).reduce(
      (sum: number, v) => sum + ((v as number) || 0), 0
    );

    if (totalBets + this.selectedChip > this.balance) return;

    (this.currentBets as any)[zone] = current + this.selectedChip;
    this.notify();
  }

  /** 設置確認下注狀態（觸發 UI 更新） */
  setBetConfirmed(): void {
    this.betConfirmed = true;
    this.notify();
  }

  /** 清除所有下注 */
  clearBets(): void {
    this.currentBets = {};
    this.notify();
  }

  /** 取得總下注金額 */
  get totalBet(): number {
    return Object.values(this.currentBets).reduce(
      (sum: number, v) => sum + ((v as number) || 0), 0
    );
  }
}
