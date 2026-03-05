/** 結算動畫覆蓋層 - 顯示勝負與損益 */

import { Container, Graphics, Text, Ticker } from 'pixi.js';
import type { GameResultPayload, SettleResultPayload } from '../game/MessageTypes';

const COLORS = {
  playerWin: 0x4A9EFF,
  bankerWin: 0xFF6B6B,
  tie: 0x2EA043,
  gold: 0xF0C040,
  green: 0x2EA043,
  red: 0xDA3633,
  white: 0xE6EDF3,
  subtext: 0x8B949E,
};

const WINNER_TEXT: Record<string, string> = {
  player: '閒 贏',
  banker: '莊 贏',
  tie: '和 局',
};

const WINNER_COLOR: Record<string, number> = {
  player: COLORS.playerWin,
  banker: COLORS.bankerWin,
  tie: COLORS.tie,
};

const BET_LABELS: Record<string, string> = {
  banker: '莊',
  player: '閒',
  tie: '和',
  banker_pair: '莊對',
  player_pair: '閒對',
  golden_three: '金三條',
  treasure_six: '聚寶六',
};

export class ResultOverlay extends Container {
  private bg: Graphics;
  private winnerText: Text;
  private scoreText: Text;
  private netChangeText: Text;
  private detailContainer: Container;
  private ticker: Ticker;

  // 動畫狀態
  private animTime = 0;
  private phase: 'idle' | 'show_winner' | 'show_settle' | 'fadeout' = 'idle';
  private autoHideTimer = 0;

  constructor(width: number, height: number, ticker: Ticker) {
    super();
    this.ticker = ticker;
    this.visible = false;

    // 半透明黑色背景
    this.bg = new Graphics();
    this.bg.rect(0, 0, width, height);
    this.bg.fill({ color: 0x000000, alpha: 0.7 });
    this.addChild(this.bg);

    // 勝負大字
    this.winnerText = new Text({
      text: '',
      style: {
        fontFamily: 'Arial',
        fontSize: 72,
        fill: COLORS.gold,
        fontWeight: 'bold',
        dropShadow: {
          alpha: 0.6,
          angle: Math.PI / 4,
          blur: 8,
          color: 0x000000,
          distance: 4,
        },
      },
    });
    this.winnerText.anchor.set(0.5);
    this.winnerText.x = width / 2;
    this.winnerText.y = height / 2 - 80;
    this.addChild(this.winnerText);

    // 比分
    this.scoreText = new Text({
      text: '',
      style: { fontFamily: 'Arial', fontSize: 28, fill: COLORS.white },
    });
    this.scoreText.anchor.set(0.5);
    this.scoreText.x = width / 2;
    this.scoreText.y = height / 2 - 20;
    this.addChild(this.scoreText);

    // 損益金額（大字飄動）
    this.netChangeText = new Text({
      text: '',
      style: {
        fontFamily: 'Arial',
        fontSize: 48,
        fill: COLORS.green,
        fontWeight: 'bold',
      },
    });
    this.netChangeText.anchor.set(0.5);
    this.netChangeText.x = width / 2;
    this.netChangeText.y = height / 2 + 40;
    this.addChild(this.netChangeText);

    // 各押注區明細
    this.detailContainer = new Container();
    this.detailContainer.x = width / 2;
    this.detailContainer.y = height / 2 + 100;
    this.addChild(this.detailContainer);

    // 動畫 ticker
    this.ticker.add(this.animate, this);
  }

  /** 顯示遊戲結果（第一階段：勝負） */
  showResult(result: GameResultPayload): void {
    this.visible = true;
    this.alpha = 1;
    this.phase = 'show_winner';
    this.animTime = 0;
    this.autoHideTimer = 0;

    // 勝負文字
    this.winnerText.text = WINNER_TEXT[result.winner] || '';
    this.winnerText.style.fill = WINNER_COLOR[result.winner] || COLORS.gold;
    this.winnerText.scale.set(0.3);
    this.winnerText.alpha = 0;

    // 比分
    this.scoreText.text = `閒 ${result.player_total}  vs  莊 ${result.banker_total}`;
    this.scoreText.alpha = 0;

    // 清空損益
    this.netChangeText.text = '';
    this.netChangeText.alpha = 0;
    this.detailContainer.removeChildren();
  }

  /** 顯示結算明細（第二階段：損益） */
  showSettle(settle: SettleResultPayload): void {
    this.phase = 'show_settle';
    this.animTime = 0;

    // 損益金額
    if (settle.net_change > 0) {
      this.netChangeText.text = `+$${settle.net_change.toFixed(0)}`;
      this.netChangeText.style.fill = COLORS.green;
    } else if (settle.net_change < 0) {
      this.netChangeText.text = `-$${Math.abs(settle.net_change).toFixed(0)}`;
      this.netChangeText.style.fill = COLORS.red;
    } else {
      this.netChangeText.text = '$0';
      this.netChangeText.style.fill = COLORS.subtext;
    }
    this.netChangeText.alpha = 0;
    this.netChangeText.scale.set(1.5);

    // 各押注區結算明細
    this.detailContainer.removeChildren();
    const entries = Object.entries(settle.bets);
    const totalWidth = entries.length * 120;
    const startX = -totalWidth / 2 + 60;

    entries.forEach(([key, detail], i) => {
      const label = BET_LABELS[key] || key;
      const text = new Text({
        text: detail.won
          ? `${label}\n✓ +$${detail.payout.toFixed(0)}`
          : `${label}\n✗ $${detail.payout.toFixed(0)}`,
        style: {
          fontFamily: 'Arial',
          fontSize: 16,
          fill: detail.won ? COLORS.green : COLORS.red,
          fontWeight: 'bold',
          align: 'center',
        },
      });
      text.anchor.set(0.5, 0);
      text.x = startX + i * 120;
      text.y = 0;
      text.alpha = 0;
      this.detailContainer.addChild(text);
    });
  }

  /** 隱藏覆蓋層 */
  hide(): void {
    this.phase = 'fadeout';
    this.animTime = 0;
  }

  private animate = (ticker: Ticker): void => {
    if (!this.visible || this.phase === 'idle') return;

    const dt = ticker.deltaMS / 1000; // 秒
    this.animTime += dt;

    if (this.phase === 'show_winner') {
      // 勝負文字：縮放淡入（0 → 0.5s）
      const t = Math.min(this.animTime / 0.5, 1);
      const ease = 1 - Math.pow(1 - t, 3); // easeOutCubic
      this.winnerText.scale.set(0.3 + 0.7 * ease);
      this.winnerText.alpha = ease;

      // 比分文字延遲出現（0.3s → 0.6s）
      if (this.animTime > 0.3) {
        const t2 = Math.min((this.animTime - 0.3) / 0.3, 1);
        this.scoreText.alpha = t2;
      }
    }

    if (this.phase === 'show_settle') {
      // 損益金額：放大後縮回（彈跳效果）
      const t = Math.min(this.animTime / 0.6, 1);
      const bounce = t < 0.5
        ? 1.5 - 0.5 * Math.pow(1 - t * 2, 2)  // 放大到 1.5
        : 1.0 + 0.5 * Math.pow(1 - (t - 0.5) * 2, 2);  // 縮回到 1.0
      this.netChangeText.scale.set(bounce);
      this.netChangeText.alpha = Math.min(t / 0.3, 1);

      // 明細逐一出現（每個間隔 0.15s）
      for (let i = 0; i < this.detailContainer.children.length; i++) {
        const child = this.detailContainer.children[i];
        const delay = 0.3 + i * 0.15;
        if (this.animTime > delay) {
          const t3 = Math.min((this.animTime - delay) / 0.3, 1);
          child.alpha = t3;
        }
      }

      // 自動隱藏計時（明細全部顯示後 3 秒）
      const totalDetailTime = 0.3 + this.detailContainer.children.length * 0.15 + 0.3;
      if (this.animTime > totalDetailTime) {
        this.autoHideTimer += dt;
        if (this.autoHideTimer > 3) {
          this.hide();
        }
      }
    }

    if (this.phase === 'fadeout') {
      const t = Math.min(this.animTime / 0.5, 1);
      this.alpha = 1 - t;
      if (t >= 1) {
        this.visible = false;
        this.phase = 'idle';
      }
    }
  };

  destroy(): void {
    this.ticker.remove(this.animate, this);
    super.destroy();
  }
}
