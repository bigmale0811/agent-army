import { Application, Container } from 'pixi.js';
import { GameConfigData, GameState } from './types';
import { CascadeGrid } from './slot/CascadeGrid';
import { HUD } from './ui/HUD';
import { SpinButton } from './ui/SpinButton';
import { PaytableEngine } from './math/PaytableEngine';
import { RNG } from './math/RNG';
import { FreeSpinFeature } from './features/FreeSpinFeature';
import { MultiplierFeature } from './features/MultiplierFeature';
import { AnimationManager } from './animation/AnimationManager';
import { SoundManager } from './audio/SoundManager';

/**
 * Main Game class — 遊戲主控器
 *
 * 管理遊戲狀態、spin 生命週期、cascade 連鎖處理、
 * 免費旋轉系統、乘數累積系統。
 */
export class Game {
    private app: Application;
    private config: GameConfigData;
    private grid: CascadeGrid;
    private hud: HUD;
    private spinButton: SpinButton;
    private paytableEngine: PaytableEngine;
    private rng: RNG;
    private freeSpinFeature: FreeSpinFeature;
    private multiplierFeature: MultiplierFeature;
    private animationManager: AnimationManager;
    private soundManager: SoundManager;

    private balance: number = 10000;
    private currentBet: number = 10;
    private state: GameState = GameState.IDLE;
    private stage: Container;

    constructor(app: Application, config: GameConfigData) {
        this.app = app;
        this.config = config;
        this.rng = new RNG();
        this.paytableEngine = new PaytableEngine(config);
        this.freeSpinFeature = new FreeSpinFeature(config);
        this.multiplierFeature = new MultiplierFeature(config);
        this.stage = new Container();
        this.animationManager = new AnimationManager(this.stage);
        this.soundManager = new SoundManager();
        this.grid = new CascadeGrid(config, this.rng);
        this.hud = new HUD(this.balance, this.currentBet);
        this.spinButton = new SpinButton();
    }

    async init(): Promise<void> {
        this.app.stage.addChild(this.stage);

        // 定位各 UI 元件
        this.grid.x = 160;
        this.grid.y = 60;
        this.stage.addChild(this.grid);

        this.hud.x = 20;
        this.hud.y = 10;
        this.stage.addChild(this.hud);

        this.spinButton.x = 800;
        this.spinButton.y = 550;
        this.stage.addChild(this.spinButton);

        this.spinButton.on('spin', () => this.onSpin());
        this.grid.fillRandom();
    }

    private async onSpin(): Promise<void> {
        if (this.state !== GameState.IDLE) return;

        const isFreeSpin = this.freeSpinFeature.isInFreeSpin();

        if (isFreeSpin) {
            // 免費旋轉：不扣投注額，消耗一次免費次數
            const consumed = this.freeSpinFeature.consumeSpin();
            if (!consumed) return;
            this.state = GameState.FREE_SPINNING;
        } else {
            // 正常旋轉：檢查餘額並扣除投注額
            if (this.balance < this.currentBet) {
                console.log('Insufficient balance');
                return;
            }
            this.balance -= this.currentBet;
            this.state = GameState.SPINNING;
        }

        this.spinButton.setEnabled(false);
        this.hud.updateBalance(this.balance);
        this.hud.showWin(0);

        // 確保音效上下文已啟動（瀏覽器 autoplay policy）
        await this.soundManager.ensureResumed();
        this.soundManager.play(SoundManager.Events.SPIN);

        // 產生新的隨機 grid
        this.grid.fillRandom();

        // 檢查 scatter 觸發免費旋轉（在 cascade 之前）
        const scatterCount = this.freeSpinFeature.checkTrigger(
            this.grid.getSymbolGrid()
        );
        if (scatterCount > 0 && this.freeSpinFeature.isInFreeSpin()) {
            // 免費旋轉觸發動畫 + 音效
            this.soundManager.play(SoundManager.Events.FREE_SPIN_TRIGGER);
            await this.animationManager.showFreeSpinTrigger(
                this.freeSpinFeature.getTotalAwarded()
            );
            this.hud.showFreeSpin(
                this.freeSpinFeature.getRemainingSpins(),
                this.freeSpinFeature.getTotalAwarded()
            );
        }

        // 重置乘數系統（每次 spin 開始）
        this.multiplierFeature.reset();

        // 執行 cascade 連鎖處理
        const totalWin = await this.processCascadeChain();

        // 結算獎金
        if (totalWin > 0) {
            this.balance += totalWin;
            this.hud.showWin(totalWin);

            // 大獎動畫（根據乘數等級觸發）
            const multiplier = this.multiplierFeature.getEffectiveMultiplier();
            if (totalWin >= this.currentBet * 20) {
                this.soundManager.play(SoundManager.Events.BIG_WIN);
                await this.animationManager.showBigWin(totalWin, multiplier);
            } else {
                this.soundManager.play(SoundManager.Events.WIN);
            }
        }

        this.hud.updateBalance(this.balance);

        // 更新免費旋轉 HUD
        if (this.freeSpinFeature.isInFreeSpin()) {
            this.hud.showFreeSpin(
                this.freeSpinFeature.getRemainingSpins(),
                this.freeSpinFeature.getTotalAwarded()
            );
        } else {
            this.hud.hideFreeSpin();
        }

        this.state = GameState.IDLE;
        this.spinButton.setEnabled(true);
    }

    /**
     * 處理 cascade 連鎖直到無更多勝利
     * @returns 本次 spin 的總獎金
     */
    private async processCascadeChain(): Promise<number> {
        let totalWin = 0;
        let cascadeCount = 0;

        this.state = GameState.CASCADING;

        while (true) {
            const wins = this.paytableEngine.evaluateGrid(
                this.grid.getSymbolGrid()
            );
            if (wins.length === 0) break;
            cascadeCount++;

            // 收集所有要移除的位置，計算原始獎金
            let cascadeWin = 0;
            const allRemovedPositions: Set<string> = new Set();

            for (const win of wins) {
                cascadeWin += win.payout * this.currentBet;
                for (const pos of win.positions) {
                    allRemovedPositions.add(`${pos.col},${pos.row}`);
                }
            }

            // 乘數系統：從被移除的格子中收集乘數值
            const removedList = [...allRemovedPositions].map(s => {
                const [col, row] = s.split(',').map(Number);
                return { col, row };
            });

            this.multiplierFeature.collectFromRemovedCells(
                removedList,
                this.grid.getSymbolGrid()
            );
            const effectiveMultiplier = this.multiplierFeature.getEffectiveMultiplier();
            totalWin += cascadeWin * effectiveMultiplier;

            // 視覺效果：高亮 → 移除 → 下落
            await this.grid.highlightWins(wins);
            await this.grid.removeCells(removedList);
            await this.grid.cascadeDown();

            // 安全閥：防止無限迴圈
            if (cascadeCount > 50) break;
        }

        return totalWin;
    }
}
