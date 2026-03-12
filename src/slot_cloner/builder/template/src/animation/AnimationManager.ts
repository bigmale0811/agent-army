import { Container, Graphics, Text, TextStyle } from 'pixi.js';
import { tween, tweenFromTo, Easing } from './Tween';
import { WinResult, CellPosition } from '../types';

/**
 * AnimationManager — 遊戲動畫管理器
 *
 * 負責所有視覺動畫效果：
 * - 勝利高亮閃爍（脈衝動畫）
 * - 消除縮放淡出
 * - Cascade 掉落彈跳
 * - 大獎文字動畫
 * - 免費旋轉觸發動畫
 */
export class AnimationManager {
    private stage: Container;

    constructor(stage: Container) {
        this.stage = stage;
    }

    /**
     * 勝利格子脈衝閃爍動畫
     * @param cellContainers 勝利格子的 Container 陣列
     * @param duration 動畫持續時間（毫秒）
     */
    async pulseWinCells(cellContainers: Container[], duration: number = 600): Promise<void> {
        if (cellContainers.length === 0) return;

        // 脈衝：縮放 1.0 → 1.15 → 1.0，同時閃爍 alpha
        await tween({
            duration,
            easing: Easing.easeOutElastic,
            onUpdate: (t: number) => {
                // 兩次脈衝效果
                const pulse = Math.sin(t * Math.PI * 2) * 0.15;
                const alpha = 0.5 + Math.sin(t * Math.PI * 3) * 0.5;
                for (const c of cellContainers) {
                    c.scale.set(1 + pulse);
                    c.alpha = alpha;
                }
            },
            onComplete: () => {
                for (const c of cellContainers) {
                    c.scale.set(1);
                    c.alpha = 1;
                }
            },
        });
    }

    /**
     * 消除格子縮放淡出動畫
     * @param cellContainers 要消除的格子 Container 陣列
     */
    async shrinkAndFade(cellContainers: Container[]): Promise<void> {
        if (cellContainers.length === 0) return;

        // 同時設定 pivot 到中心以實現中心縮放
        for (const c of cellContainers) {
            c.pivot.set(50, 50); // CELL_SIZE / 2
            c.x += 50;
            c.y += 50;
        }

        await tween({
            duration: 250,
            easing: Easing.easeInQuad,
            onUpdate: (t: number) => {
                const scale = 1 - t;
                const alpha = 1 - t;
                for (const c of cellContainers) {
                    c.scale.set(scale);
                    c.alpha = alpha;
                }
            },
        });
    }

    /**
     * Cascade 掉落動畫：從上方滑入並彈跳
     * @param cellContainer 新格子的 Container
     * @param targetY 目標 Y 座標
     * @param delay 延遲毫秒（錯開掉落時機）
     */
    async dropBounce(cellContainer: Container, targetY: number, delay: number = 0): Promise<void> {
        const startY = targetY - 200; // 從上方 200px 開始掉落
        cellContainer.y = startY;
        cellContainer.alpha = 0;

        if (delay > 0) {
            await new Promise(resolve => setTimeout(resolve, delay));
        }

        cellContainer.alpha = 1;

        await tweenFromTo(startY, targetY, {
            duration: 400,
            easing: Easing.easeOutBounce,
            onUpdate: (y: number) => {
                cellContainer.y = y;
            },
        });
    }

    /**
     * 大獎文字動畫
     * @param amount 獎金金額
     * @param multiplier 乘數
     */
    async showBigWin(amount: number, multiplier: number = 1): Promise<void> {
        const overlay = new Container();

        // 半透明背景
        const bg = new Graphics();
        bg.rect(0, 0, 960, 640);
        bg.fill({ color: 0x000000, alpha: 0.6 });
        overlay.addChild(bg);

        // 大獎文字
        const winStyle = new TextStyle({
            fontFamily: 'Arial',
            fontSize: 72,
            fontWeight: 'bold',
            fill: 0xffd700,
            stroke: { color: 0x8b6914, width: 4 },
            dropShadow: {
                color: 0x000000,
                blur: 8,
                distance: 4,
                angle: Math.PI / 4,
            },
        });

        const label = multiplier > 10 ? 'MEGA WIN!' :
                      multiplier > 5  ? 'BIG WIN!' : 'NICE WIN!';

        const winText = new Text({ text: label, style: winStyle });
        winText.anchor.set(0.5);
        winText.x = 480;
        winText.y = 260;
        overlay.addChild(winText);

        // 金額文字
        const amountStyle = new TextStyle({
            fontFamily: 'Arial',
            fontSize: 48,
            fontWeight: 'bold',
            fill: 0xffffff,
        });
        const amountText = new Text({ text: `$${amount.toFixed(2)}`, style: amountStyle });
        amountText.anchor.set(0.5);
        amountText.x = 480;
        amountText.y = 350;
        overlay.addChild(amountText);

        this.stage.addChild(overlay);

        // 動畫：放大彈入 → 停留 → 淡出
        overlay.alpha = 0;
        winText.scale.set(0.1);

        await tween({
            duration: 500,
            easing: Easing.easeOutBack,
            onUpdate: (t: number) => {
                overlay.alpha = t;
                winText.scale.set(0.1 + t * 0.9);
            },
        });

        // 停留 1.5 秒
        await new Promise(resolve => setTimeout(resolve, 1500));

        // 淡出
        await tween({
            duration: 400,
            easing: Easing.easeInQuad,
            onUpdate: (t: number) => {
                overlay.alpha = 1 - t;
            },
            onComplete: () => {
                this.stage.removeChild(overlay);
                overlay.destroy({ children: true });
            },
        });
    }

    /**
     * 免費旋轉觸發動畫
     * @param spinsAwarded 獲得的免費旋轉次數
     */
    async showFreeSpinTrigger(spinsAwarded: number): Promise<void> {
        const overlay = new Container();

        const bg = new Graphics();
        bg.rect(0, 0, 960, 640);
        bg.fill({ color: 0x000033, alpha: 0.7 });
        overlay.addChild(bg);

        const style = new TextStyle({
            fontFamily: 'Arial',
            fontSize: 56,
            fontWeight: 'bold',
            fill: 0x00ffcc,
            stroke: { color: 0x006644, width: 3 },
        });

        const text = new Text({
            text: `FREE SPINS x${spinsAwarded}`,
            style,
        });
        text.anchor.set(0.5);
        text.x = 480;
        text.y = 320;
        overlay.addChild(text);

        this.stage.addChild(overlay);
        overlay.alpha = 0;
        text.scale.set(0.3);

        await tween({
            duration: 600,
            easing: Easing.easeOutBack,
            onUpdate: (t: number) => {
                overlay.alpha = t;
                text.scale.set(0.3 + t * 0.7);
            },
        });

        await new Promise(resolve => setTimeout(resolve, 1200));

        await tween({
            duration: 300,
            easing: Easing.easeInQuad,
            onUpdate: (t: number) => {
                overlay.alpha = 1 - t;
            },
            onComplete: () => {
                this.stage.removeChild(overlay);
                overlay.destroy({ children: true });
            },
        });
    }
}
