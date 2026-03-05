/** WebSocket 訊息類型定義 - 對應後端協定 */

export type GameStateType =
  | 'IDLE' | 'BETTING' | 'DEALING'
  | 'PLAYER_DRAW' | 'BANKER_DRAW' | 'RESULT' | 'SETTLE';

export type SuitType = 'hearts' | 'diamonds' | 'clubs' | 'spades';

export interface CardData {
  suit: SuitType;
  rank: string;
  value: number;
}

export interface BetAmounts {
  banker?: number;
  player?: number;
  tie?: number;
  banker_pair?: number;
  player_pair?: number;
  golden_three?: number;
  treasure_six?: number;
}

// Server → Client 訊息
export interface PlayerInitPayload {
  player_id: string;
  balance: number;
  min_bet: number;
  max_bet: number;
}

export interface StateChangePayload {
  state: GameStateType;
  countdown?: number;
}

export interface CardDealtPayload {
  target: 'player' | 'banker';
  card: CardData;
  hand_value: number;
  card_index: number;
}

export interface GameResultPayload {
  winner: 'player' | 'banker' | 'tie';
  player_total: number;
  banker_total: number;
  player_pair: boolean;
  banker_pair: boolean;
  player_cards: CardData[];
  banker_cards: CardData[];
}

export interface BetSettleDetail {
  amount: number;
  won: boolean;
  payout: number;
}

export interface SettleResultPayload {
  bets: Record<string, BetSettleDetail>;
  net_change: number;
  new_balance: number;
}

export interface ErrorPayload {
  code: string;
  message: string;
}

export interface WSMessage {
  type: string;
  payload: any;
  timestamp: number;
}

// 押注區配置
export interface BetZoneConfig {
  key: string;
  label: string;
  color: string;
  payoutText: string;
}

export const BET_ZONES: BetZoneConfig[] = [
  { key: 'player_pair', label: '閒對', color: '#3D2B5F', payoutText: '1:11' },
  { key: 'player', label: '閒', color: '#1E3A5F', payoutText: '1:1' },
  { key: 'tie', label: '和', color: '#1E4D2B', payoutText: '1:8' },
  { key: 'banker', label: '莊', color: '#5F1E1E', payoutText: '1:0.95' },
  { key: 'banker_pair', label: '莊對', color: '#3D2B5F', payoutText: '1:11' },
  { key: 'golden_three', label: '金三條', color: '#5F4B1E', payoutText: '待定' },
  { key: 'treasure_six', label: '聚寶六', color: '#1E4D5F', payoutText: '待定' },
];

export const CHIP_VALUES = [10, 50, 100, 500, 1000];
