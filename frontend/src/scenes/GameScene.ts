/** 百家樂主遊戲場景 - 整合所有 UI 組件 */

import { Application, Container, Graphics, Text } from 'pixi.js';
import { GameClient } from '../game/GameClient';
import { GameState } from '../game/GameState';
import { BalanceDisplay } from '../ui/BalanceDisplay';
import { CardDisplay } from '../ui/CardDisplay';
import { BettingPanel } from '../ui/BettingPanel';
import { ChipSelector } from '../ui/ChipSelector';
import { ResultOverlay } from '../ui/ResultOverlay';

const WIDTH = 1280;
const HEIGHT = 720;

export class GameScene {
  private app: Application;
  private client: GameClient;
  private state: GameState;

  private balanceDisplay!: BalanceDisplay;
  private playerCards!: CardDisplay;
  private bankerCards!: CardDisplay;
  private bettingPanel!: BettingPanel;
  private chipSelector!: ChipSelector;
  private resultOverlay!: ResultOverlay;
  private tableGfx!: Graphics;

  constructor() {
    this.app = new Application();
    this.state = new GameState();

    // 產生唯一玩家 ID
    const playerId = `player_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    this.client = new GameClient(playerId);
  }

  async init(): Promise<void> {
    await this.app.init({
      width: WIDTH,
      height: HEIGHT,
      backgroundColor: 0x0D1117,
      antialias: true,
      resolution: window.devicePixelRatio || 1,
      autoDensity: true,
    });

    document.body.appendChild(this.app.canvas);
    this.buildUI();
    this.bindEvents();
    this.state.subscribe(() => this.render());

    // 連線到伺服器
    try {
      await this.client.connect();
    } catch (e) {
      this.state.message = '無法連線到伺服器，請確認後端已啟動';
      this.render();
    }
  }

  private buildUI(): void {
    // 賭桌背景
    this.tableGfx = new Graphics();
    this.tableGfx.roundRect(40, 60, WIDTH - 80, HEIGHT - 120, 20);
    this.tableGfx.fill({ color: 0x1A472A, alpha: 0.4 });
    this.tableGfx.stroke({ color: 0xF0C040, width: 2, alpha: 0.3 });
    this.app.stage.addChild(this.tableGfx);

    // 頂部狀態欄
    this.balanceDisplay = new BalanceDisplay(WIDTH - 80);
    this.balanceDisplay.x = 40;
    this.balanceDisplay.y = 10;
    this.app.stage.addChild(this.balanceDisplay);

    // 閒家牌區（左）
    this.playerCards = new CardDisplay('閒 PLAYER', 0x4A9EFF);
    this.playerCards.x = WIDTH / 2 - 320;
    this.playerCards.y = 90;
    this.app.stage.addChild(this.playerCards);

    // 莊家牌區（右）
    this.bankerCards = new CardDisplay('莊 BANKER', 0xFF6B6B);
    this.bankerCards.x = WIDTH / 2 + 80;
    this.bankerCards.y = 90;
    this.app.stage.addChild(this.bankerCards);

    // VS 文字
    const vsText = new Text({
      text: 'VS',
      style: { fontFamily: 'Arial', fontSize: 36, fill: 0xF0C040, fontWeight: 'bold' },
    });
    vsText.anchor.set(0.5);
    vsText.x = WIDTH / 2;
    vsText.y = 175;
    this.app.stage.addChild(vsText);

    // 下注面板（中間）
    this.bettingPanel = new BettingPanel((zone) => {
      this.state.addBet(zone);
      this.client.placeBet(this.state.currentBets);
    });
    this.bettingPanel.x = WIDTH / 2;
    this.bettingPanel.y = 350;
    this.app.stage.addChild(this.bettingPanel);

    // 籌碼選擇器（底部）
    this.chipSelector = new ChipSelector(
      (value) => { this.state.selectedChip = value; },
      () => {
        this.state.clearBets();
        this.client.placeBet({});
      },
      () => {
        this.client.confirmBet();
        this.state.setBetConfirmed();
      },
    );
    this.chipSelector.x = WIDTH / 2;
    this.chipSelector.y = 570;
    this.app.stage.addChild(this.chipSelector);

    // 結算動畫覆蓋層（最上層）
    this.resultOverlay = new ResultOverlay(WIDTH, HEIGHT, this.app.ticker);
    this.app.stage.addChild(this.resultOverlay);

    // 說明文字
    const helpText = new Text({
      text: '選擇籌碼 → 點擊押注區下注 → 確認下注',
      style: { fontFamily: 'Arial', fontSize: 14, fill: 0x484F58 },
    });
    helpText.anchor.set(0.5);
    helpText.x = WIDTH / 2;
    helpText.y = HEIGHT - 20;
    this.app.stage.addChild(helpText);
  }

  private bindEvents(): void {
    this.client.on('PLAYER_INIT', (p) => this.state.handlePlayerInit(p));
    this.client.on('STATE_CHANGE', (p) => {
      this.state.handleStateChange(p);
      // 新一局清除牌面
      if (p.state === 'BETTING') {
        this.playerCards.clear();
        this.bankerCards.clear();
      }
    });
    this.client.on('CARD_DEALT', (p) => {
      this.state.handleCardDealt(p);
      if (p.target === 'player') {
        this.playerCards.addCard(p.card, p.hand_value);
      } else {
        this.bankerCards.addCard(p.card, p.hand_value);
      }
    });
    this.client.on('GAME_RESULT', (p) => {
      this.state.handleGameResult(p);
      this.resultOverlay.showResult(p);
    });
    this.client.on('SETTLE_RESULT', (p) => {
      this.state.handleSettleResult(p);
      this.resultOverlay.showSettle(p);
    });
    this.client.on('ERROR', (p) => this.state.handleError(p));
  }

  private render(): void {
    this.balanceDisplay.update(this.state);
    this.bettingPanel.update(this.state);
    this.chipSelector.update(this.state);
  }
}
