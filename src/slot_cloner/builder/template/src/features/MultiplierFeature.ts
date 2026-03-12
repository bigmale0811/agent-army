import { GameConfigData, CellPosition } from '../types';

/**
 * MultiplierFeature — 乘數系統
 *
 * 管理消除連鎖中的乘數累積邏輯：
 * - 從被消除的格子中收集乘數型符號的乘數值
 * - 支援消除連鎖累加模式（accumulateInCascade）
 * - 每次 spin 開始時重置
 */
export class MultiplierFeature {
    private config: GameConfigData;
    private accumulatedMultiplier: number = 0;
    private readonly enabled: boolean;

    constructor(config: GameConfigData) {
        this.config = config;
        this.enabled = config.features.multiplier.enabled;
    }

    /** 每次 spin 開始時重置乘數 */
    reset(): void {
        this.accumulatedMultiplier = 0;
    }

    /** 是否啟用 */
    isEnabled(): boolean {
        return this.enabled;
    }

    /**
     * 從被移除的格子中收集乘數值並累加
     * @param removedPositions 被消除的位置
     * @param grid 當前 grid 狀態 (col-major)
     * @returns 本次 cascade 收集到的乘數值陣列
     */
    collectFromRemovedCells(
        removedPositions: CellPosition[],
        grid: string[][],
    ): number[] {
        if (!this.enabled) return [];

        const multiplierValues = this.config.features.multiplier.values;
        const collected: number[] = [];

        for (const pos of removedPositions) {
            const symbolId = grid[pos.col]?.[pos.row];
            if (!symbolId) continue;

            const symData = this.config.symbols.find(s => s.id === symbolId);
            if (symData?.type === 'multiplier' && multiplierValues.length > 0) {
                // 隨機選取一個乘數值（實際遊戲可能由伺服器決定）
                const value = multiplierValues[Math.floor(Math.random() * multiplierValues.length)];
                collected.push(value);
            }
        }

        // 累加模式：乘數值在整個 spin 的 cascade 鏈中持續累加
        if (this.config.features.multiplier.accumulateInCascade) {
            this.accumulatedMultiplier += collected.reduce((a, b) => a + b, 0);
        } else {
            // 非累加模式：只用當前 cascade 的乘數
            this.accumulatedMultiplier = collected.reduce((a, b) => a + b, 0);
        }

        return collected;
    }

    /**
     * 取得當前有效乘數
     * @returns 有效乘數值，最小為 1
     */
    getEffectiveMultiplier(): number {
        return this.accumulatedMultiplier > 0 ? this.accumulatedMultiplier : 1;
    }

    /** 取得累積的原始乘數值（可為 0） */
    getAccumulatedMultiplier(): number {
        return this.accumulatedMultiplier;
    }
}
