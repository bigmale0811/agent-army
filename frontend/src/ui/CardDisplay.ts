/** 牌面顯示區 */

import { Container, Graphics, Text, Ticker } from 'pixi.js';
import type { CardData } from '../game/MessageTypes';

const CARD_W = 70;
const CARD_H = 100;
const CARD_GAP = 10;

const SUIT_SYMBOLS: Record<string, string> = {
  hearts: '♥',
  diamonds: '♦',
  clubs: '♣',
  spades: '♠',
};

const SUIT_COLORS: Record<string, number> = {
  hearts: 0xE53935,
  diamonds: 0xE53935,
  clubs: 0x212121,
  spades: 0x212121,
};

export class CardDisplay extends Container {
  private cardContainer: Container;
  private titleText: Text;
  private totalText: Text;
  private cards: CardData[] = [];

  constructor(title: string, titleColor: number) {
    super();

    this.titleText = new Text({
      text: title,
      style: { fontFamily: 'Arial', fontSize: 22, fill: titleColor, fontWeight: 'bold' },
    });
    this.titleText.anchor.set(0.5, 0);
    this.titleText.x = (CARD_W * 3 + CARD_GAP * 2) / 2;
    this.addChild(this.titleText);

    this.cardContainer = new Container();
    this.cardContainer.y = 35;
    this.addChild(this.cardContainer);

    this.totalText = new Text({
      text: '',
      style: { fontFamily: 'Arial', fontSize: 28, fill: 0xF0C040, fontWeight: 'bold' },
    });
    this.totalText.anchor.set(0.5, 0);
    this.totalText.x = (CARD_W * 3 + CARD_GAP * 2) / 2;
    this.totalText.y = CARD_H + 45;
    this.addChild(this.totalText);

    // 畫空牌位
    this.drawEmptySlots();
  }

  private drawEmptySlots(): void {
    this.cardContainer.removeChildren();
    for (let i = 0; i < 3; i++) {
      const slot = new Graphics();
      slot.roundRect(0, 0, CARD_W, CARD_H, 6);
      slot.fill({ color: 0x21262D, alpha: 0.6 });
      slot.stroke({ color: 0x30363D, width: 1 });
      slot.x = i * (CARD_W + CARD_GAP);
      this.cardContainer.addChild(slot);
    }
  }

  /** 清除所有牌 */
  clear(): void {
    this.cards = [];
    this.drawEmptySlots();
    this.totalText.text = '';
  }

  /** 加入一張牌（帶翻牌動畫） */
  addCard(card: CardData, total: number): void {
    this.cards.push(card);
    const index = this.cards.length - 1;

    // 畫牌
    const cardGfx = this.createCard(card);
    cardGfx.x = index * (CARD_W + CARD_GAP);

    // 替換空牌位
    if (index < this.cardContainer.children.length) {
      this.cardContainer.removeChildAt(index);
    }
    this.cardContainer.addChildAt(cardGfx, index);

    // 翻牌動畫：從 scaleX=0 展開到 1（300ms）
    cardGfx.pivot.x = CARD_W / 2;
    cardGfx.x += CARD_W / 2;
    cardGfx.scale.x = 0;
    cardGfx.alpha = 0.5;

    let elapsed = 0;
    const duration = 300; // ms
    const animateFn = (ticker: Ticker) => {
      elapsed += ticker.deltaMS;
      const t = Math.min(elapsed / duration, 1);
      const ease = 1 - Math.pow(1 - t, 3); // easeOutCubic
      cardGfx.scale.x = ease;
      cardGfx.alpha = 0.5 + 0.5 * ease;
      if (t >= 1) {
        Ticker.shared.remove(animateFn);
      }
    };
    Ticker.shared.add(animateFn);

    this.totalText.text = `${total}`;
  }

  private createCard(card: CardData): Container {
    const c = new Container();

    // 卡片背景
    const bg = new Graphics();
    bg.roundRect(0, 0, CARD_W, CARD_H, 6);
    bg.fill({ color: 0xFFFFFF });
    bg.stroke({ color: 0xC0C0C0, width: 1 });
    c.addChild(bg);

    const suitColor = SUIT_COLORS[card.suit] || 0x212121;
    const suitSymbol = SUIT_SYMBOLS[card.suit] || '?';

    // 左上角 rank
    const rankText = new Text({
      text: card.rank,
      style: { fontFamily: 'Arial', fontSize: 18, fill: suitColor, fontWeight: 'bold' },
    });
    rankText.x = 6;
    rankText.y = 4;
    c.addChild(rankText);

    // 中央花色
    const suitText = new Text({
      text: suitSymbol,
      style: { fontFamily: 'Arial', fontSize: 32, fill: suitColor },
    });
    suitText.anchor.set(0.5);
    suitText.x = CARD_W / 2;
    suitText.y = CARD_H / 2;
    c.addChild(suitText);

    // 左上小花色
    const smallSuit = new Text({
      text: suitSymbol,
      style: { fontFamily: 'Arial', fontSize: 14, fill: suitColor },
    });
    smallSuit.x = 6;
    smallSuit.y = 22;
    c.addChild(smallSuit);

    return c;
  }
}
