/** 下注區域面板 */

import { Container, Graphics, Text } from 'pixi.js';
import { BET_ZONES, type BetZoneConfig } from '../game/MessageTypes';
import type { GameState } from '../game/GameState';

const ZONE_W = 130;
const ZONE_H = 70;
const GAP = 10;

export class BettingPanel extends Container {
  private zones: Map<string, { bg: Graphics; betLabel: Text }> = new Map();
  private onBetClick: (zone: string) => void;

  constructor(onBetClick: (zone: string) => void) {
    super();
    this.onBetClick = onBetClick;
    this.buildZones();
  }

  private buildZones(): void {
    // 主下注區：閒對、閒、和、莊、莊對（第一行）
    const mainZones = BET_ZONES.slice(0, 5);
    const totalMainWidth = mainZones.length * ZONE_W + (mainZones.length - 1) * GAP;
    const startX = -totalMainWidth / 2;

    mainZones.forEach((zone, i) => {
      const zoneContainer = this.createZone(zone);
      zoneContainer.x = startX + i * (ZONE_W + GAP);
      zoneContainer.y = 0;
      this.addChild(zoneContainer);
    });

    // 副下注區：金三條、聚寶六（第二行）
    const subZones = BET_ZONES.slice(5);
    const subWidth = subZones.length * ZONE_W * 1.5 + GAP;
    const subStartX = -subWidth / 2;

    subZones.forEach((zone, i) => {
      const zoneContainer = this.createZone(zone, ZONE_W * 1.5);
      zoneContainer.x = subStartX + i * (ZONE_W * 1.5 + GAP);
      zoneContainer.y = ZONE_H + GAP;
      this.addChild(zoneContainer);
    });
  }

  private createZone(config: BetZoneConfig, width = ZONE_W): Container {
    const c = new Container();
    c.eventMode = 'static';
    c.cursor = 'pointer';

    // 背景
    const bg = new Graphics();
    bg.roundRect(0, 0, width, ZONE_H, 8);
    bg.fill({ color: parseInt(config.color.replace('#', '0x')), alpha: 0.8 });
    bg.stroke({ color: 0x484F58, width: 1 });
    c.addChild(bg);

    // 標題
    const title = new Text({
      text: config.label,
      style: { fontFamily: 'Arial', fontSize: 20, fill: 0xE6EDF3, fontWeight: 'bold' },
    });
    title.anchor.set(0.5);
    title.x = width / 2;
    title.y = 20;
    c.addChild(title);

    // 賠率
    const payout = new Text({
      text: config.payoutText,
      style: { fontFamily: 'Arial', fontSize: 12, fill: 0x8B949E },
    });
    payout.anchor.set(0.5);
    payout.x = width / 2;
    payout.y = 38;
    c.addChild(payout);

    // 下注金額
    const betLabel = new Text({
      text: '',
      style: { fontFamily: 'Arial', fontSize: 14, fill: 0xF0C040, fontWeight: 'bold' },
    });
    betLabel.anchor.set(0.5);
    betLabel.x = width / 2;
    betLabel.y = 56;
    c.addChild(betLabel);

    this.zones.set(config.key, { bg, betLabel });

    // 點擊事件
    c.on('pointerdown', () => this.onBetClick(config.key));

    return c;
  }

  update(state: GameState): void {
    for (const [key, { bg, betLabel }] of this.zones) {
      const amount = (state.currentBets as any)[key] || 0;
      betLabel.text = amount > 0 ? `$${amount}` : '';

      // 高亮勝出的押注區
      if (state.winner) {
        const isWinning = this.isWinningZone(key, state);
        if (isWinning) {
          bg.alpha = 1.0;
        } else {
          bg.alpha = 0.5;
        }
      } else {
        bg.alpha = state.currentState === 'BETTING' ? 0.8 : 0.6;
      }
    }
  }

  private isWinningZone(key: string, state: GameState): boolean {
    if (key === 'banker' && state.winner === 'banker') return true;
    if (key === 'player' && state.winner === 'player') return true;
    if (key === 'tie' && state.winner === 'tie') return true;
    if (key === 'banker_pair' && state.bankerPair) return true;
    if (key === 'player_pair' && state.playerPair) return true;
    return false;
  }
}
