/** 餘額與下注資訊顯示 */

import { Container, Graphics, Text } from 'pixi.js';
import type { GameState } from '../game/GameState';

const COLORS = {
  panel: 0x161B22,
  gold: 0xF0C040,
  text: 0xE6EDF3,
  subtext: 0x8B949E,
  green: 0x2EA043,
  red: 0xDA3633,
};

export class BalanceDisplay extends Container {
  private balanceText: Text;
  private betText: Text;
  private messageText: Text;
  private countdownText: Text;

  constructor(width: number) {
    super();

    // 背景
    const bg = new Graphics();
    bg.roundRect(0, 0, width, 50, 8);
    bg.fill({ color: COLORS.panel, alpha: 0.9 });
    this.addChild(bg);

    this.balanceText = new Text({
      text: '餘額: $10,000',
      style: { fontFamily: 'Arial', fontSize: 18, fill: COLORS.gold, fontWeight: 'bold' },
    });
    this.balanceText.x = 20;
    this.balanceText.y = 14;
    this.addChild(this.balanceText);

    this.betText = new Text({
      text: '下注: $0',
      style: { fontFamily: 'Arial', fontSize: 16, fill: COLORS.subtext },
    });
    this.betText.x = 220;
    this.betText.y = 16;
    this.addChild(this.betText);

    this.countdownText = new Text({
      text: '',
      style: { fontFamily: 'Arial', fontSize: 20, fill: COLORS.gold, fontWeight: 'bold' },
    });
    this.countdownText.anchor.set(0.5, 0);
    this.countdownText.x = width / 2;
    this.countdownText.y = 14;
    this.addChild(this.countdownText);

    this.messageText = new Text({
      text: '',
      style: { fontFamily: 'Arial', fontSize: 16, fill: COLORS.text },
    });
    this.messageText.x = width - 20;
    this.messageText.anchor.set(1, 0);
    this.messageText.y = 16;
    this.addChild(this.messageText);
  }

  update(state: GameState): void {
    this.balanceText.text = `餘額: $${state.balance.toLocaleString()}`;
    this.betText.text = `下注: $${state.totalBet.toLocaleString()}`;

    if (state.currentState === 'BETTING' && state.countdown > 0) {
      this.countdownText.text = `⏱ ${state.countdown}s`;
    } else {
      this.countdownText.text = '';
    }

    this.messageText.text = state.message;
    if (state.lastNetChange > 0) {
      this.messageText.style.fill = COLORS.green;
    } else if (state.lastNetChange < 0) {
      this.messageText.style.fill = COLORS.red;
    } else {
      this.messageText.style.fill = COLORS.text;
    }
  }
}
