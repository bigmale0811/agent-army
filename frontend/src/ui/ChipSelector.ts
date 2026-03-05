/** 籌碼選擇器 + 操作按鈕 */

import { Container, Graphics, Text, Ticker } from 'pixi.js';
import { CHIP_VALUES } from '../game/MessageTypes';
import type { GameState } from '../game/GameState';

const CHIP_RADIUS = 25;
const GAP = 15;

const CHIP_COLORS: Record<number, number> = {
  10: 0x2196F3,     // 藍
  50: 0x4CAF50,     // 綠
  100: 0xF44336,    // 紅
  500: 0x9C27B0,    // 紫
  1000: 0xF0C040,   // 金
};

export class ChipSelector extends Container {
  private chipGraphics: Map<number, Graphics> = new Map();
  private selectedValue = 100;
  private onClear: () => void;
  private onConfirm: () => void;
  private onChipSelect: (value: number) => void;

  private confirmBtnBg!: Graphics;
  private confirmLabel!: Text;
  private confirmContainer!: Container;

  constructor(
    onChipSelect: (value: number) => void,
    onClear: () => void,
    onConfirm: () => void,
  ) {
    super();
    this.onChipSelect = onChipSelect;
    this.onClear = onClear;
    this.onConfirm = onConfirm;
    this.buildChips();
    this.buildButtons();
    this.updateSelection(100);
  }

  private buildChips(): void {
    const totalWidth = CHIP_VALUES.length * (CHIP_RADIUS * 2 + GAP) - GAP;
    const startX = -totalWidth / 2 + CHIP_RADIUS;

    CHIP_VALUES.forEach((value, i) => {
      const chip = this.createChip(value);
      chip.x = startX + i * (CHIP_RADIUS * 2 + GAP);
      chip.y = 0;
      this.addChild(chip);
    });
  }

  private createChip(value: number): Container {
    const c = new Container();
    c.eventMode = 'static';
    c.cursor = 'pointer';

    const color = CHIP_COLORS[value] || 0x888888;

    // 外圈
    const outer = new Graphics();
    outer.circle(0, 0, CHIP_RADIUS);
    outer.fill({ color });
    outer.stroke({ color: 0xFFFFFF, width: 2 });
    c.addChild(outer);

    // 內圈虛線效果
    const inner = new Graphics();
    inner.circle(0, 0, CHIP_RADIUS - 6);
    inner.stroke({ color: 0xFFFFFF, width: 1, alpha: 0.5 });
    c.addChild(inner);

    // 金額文字
    const label = new Text({
      text: value >= 1000 ? `${value / 1000}K` : `${value}`,
      style: { fontFamily: 'Arial', fontSize: 14, fill: 0xFFFFFF, fontWeight: 'bold' },
    });
    label.anchor.set(0.5);
    c.addChild(label);

    this.chipGraphics.set(value, outer);

    c.on('pointerdown', () => {
      this.updateSelection(value);
      this.onChipSelect(value);
    });

    return c;
  }

  private buildButtons(): void {
    // 清除按鈕
    const clearBtn = this.createButton('清除', 0x484F58, -70, 65);
    clearBtn.on('pointerdown', () => this.onClear());
    this.addChild(clearBtn);

    // 確認下注按鈕
    this.confirmContainer = new Container();
    this.confirmContainer.eventMode = 'static';
    this.confirmContainer.cursor = 'pointer';
    this.confirmContainer.x = 70;
    this.confirmContainer.y = 65;

    this.confirmBtnBg = new Graphics();
    this.confirmBtnBg.roundRect(-55, -18, 110, 36, 6);
    this.confirmBtnBg.fill({ color: 0x2EA043 });
    this.confirmContainer.addChild(this.confirmBtnBg);

    this.confirmLabel = new Text({
      text: '確認下注',
      style: { fontFamily: 'Arial', fontSize: 16, fill: 0xE6EDF3, fontWeight: 'bold' },
    });
    this.confirmLabel.anchor.set(0.5);
    this.confirmContainer.addChild(this.confirmLabel);

    this.confirmContainer.on('pointerdown', () => {
      this.onConfirm();
      this.playConfirmFlash();
    });

    this.addChild(this.confirmContainer);
  }

  /** 確認按鈕閃爍動畫 */
  private playConfirmFlash(): void {
    // 變色 + 文字變更
    this.confirmBtnBg.clear();
    this.confirmBtnBg.roundRect(-55, -18, 110, 36, 6);
    this.confirmBtnBg.fill({ color: 0xF0C040 });
    this.confirmLabel.text = '已確認 ✓';
    this.confirmLabel.style.fill = 0x0D1117;
    this.confirmContainer.scale.set(1.1);

    // 300ms 後縮回
    let elapsed = 0;
    const animFn = (ticker: Ticker) => {
      elapsed += ticker.deltaMS;
      if (elapsed > 300) {
        this.confirmContainer.scale.set(1.0);
        Ticker.shared.remove(animFn);
      }
    };
    Ticker.shared.add(animFn);
  }

  /** 根據遊戲狀態更新按鈕外觀 */
  update(state: GameState): void {
    if (state.betConfirmed) {
      // 已確認狀態：金色底
      this.confirmBtnBg.clear();
      this.confirmBtnBg.roundRect(-55, -18, 110, 36, 6);
      this.confirmBtnBg.fill({ color: 0xF0C040 });
      this.confirmLabel.text = '已確認 ✓';
      this.confirmLabel.style.fill = 0x0D1117;
    } else if (state.currentState === 'BETTING') {
      // 下注中：綠色底
      this.confirmBtnBg.clear();
      this.confirmBtnBg.roundRect(-55, -18, 110, 36, 6);
      this.confirmBtnBg.fill({ color: 0x2EA043 });
      this.confirmLabel.text = '確認下注';
      this.confirmLabel.style.fill = 0xE6EDF3;
    } else {
      // 非下注階段：灰色
      this.confirmBtnBg.clear();
      this.confirmBtnBg.roundRect(-55, -18, 110, 36, 6);
      this.confirmBtnBg.fill({ color: 0x30363D });
      this.confirmLabel.text = '等待中...';
      this.confirmLabel.style.fill = 0x8B949E;
    }
  }

  private createButton(text: string, color: number, x: number, y: number): Container {
    const c = new Container();
    c.eventMode = 'static';
    c.cursor = 'pointer';

    const bg = new Graphics();
    bg.roundRect(-55, -18, 110, 36, 6);
    bg.fill({ color });
    c.addChild(bg);

    const label = new Text({
      text,
      style: { fontFamily: 'Arial', fontSize: 16, fill: 0xE6EDF3, fontWeight: 'bold' },
    });
    label.anchor.set(0.5);
    c.addChild(label);

    c.x = x;
    c.y = y;
    return c;
  }

  updateSelection(value: number): void {
    this.selectedValue = value;
    for (const [v, gfx] of this.chipGraphics) {
      gfx.alpha = v === value ? 1.0 : 0.5;
      gfx.scale.set(v === value ? 1.1 : 1.0);
    }
  }
}
