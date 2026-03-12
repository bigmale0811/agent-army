import { GameConfigData } from '../types';

/**
 * FreeSpinFeature — 免費旋轉系統
 *
 * 核心邏輯：
 * 1. 偵測 grid 中 scatter 符號數量 >= triggerCount → 觸發免費旋轉
 * 2. 追蹤剩餘免費旋轉次數
 * 3. 支援重新觸發（retrigger）：免費旋轉中再次達標 → 加旋轉次數
 * 4. 免費旋轉期間不扣除投注額
 */
export class FreeSpinFeature {
    private config: GameConfigData;
    private readonly enabled: boolean;
    private remainingSpins: number = 0;
    private totalAwarded: number = 0;
    private isActive: boolean = false;

    constructor(config: GameConfigData) {
        this.config = config;
        this.enabled = config.features.freeSpin.enabled &&
                       config.features.scatter.enabled;
    }

    /** 是否啟用 */
    isEnabled(): boolean {
        return this.enabled;
    }

    /** 目前是否在免費旋轉中 */
    isInFreeSpin(): boolean {
        return this.isActive;
    }

    /** 剩餘免費旋轉次數 */
    getRemainingSpins(): number {
        return this.remainingSpins;
    }

    /** 本輪累計獲得的免費旋轉次數 */
    getTotalAwarded(): number {
        return this.totalAwarded;
    }

    /**
     * 檢查 grid 是否觸發免費旋轉
     * @param grid 2D grid (col-major), grid[col][row] = symbolId
     * @returns 偵測到的 scatter 數量，0 表示未觸發
     */
    checkTrigger(grid: string[][]): number {
        if (!this.enabled) return 0;

        const scatterConfig = this.config.features.scatter;
        const scatterId = scatterConfig.symbolId;
        let scatterCount = 0;

        for (const col of grid) {
            for (const symbolId of col) {
                if (symbolId === scatterId) {
                    scatterCount++;
                }
            }
        }

        if (scatterCount >= scatterConfig.triggerCount) {
            this.trigger(scatterCount);
        }

        return scatterCount;
    }

    /**
     * 觸發免費旋轉
     * @param scatterCount Scatter 符號數量（可用於計算額外獎勵）
     */
    private trigger(scatterCount: number): void {
        const freeSpinConfig = this.config.features.freeSpin;

        if (this.isActive) {
            // 重新觸發邏輯
            if (freeSpinConfig.retriggerEnabled) {
                const extraSpins = freeSpinConfig.retriggerSpins;
                this.remainingSpins += extraSpins;
                this.totalAwarded += extraSpins;
                console.log(
                    `[FreeSpin] Retrigger! +${extraSpins} spins ` +
                    `(${scatterCount} scatters, ${this.remainingSpins} remaining)`
                );
            }
        } else {
            // 首次觸發
            const baseSpins = freeSpinConfig.baseSpins;
            this.remainingSpins = baseSpins;
            this.totalAwarded = baseSpins;
            this.isActive = true;
            console.log(
                `[FreeSpin] Triggered! ${baseSpins} free spins ` +
                `(${scatterCount} scatters detected)`
            );
        }
    }

    /**
     * 消耗一次免費旋轉（每次 spin 前呼叫）
     * @returns true 如果成功消耗，false 如果沒有剩餘
     */
    consumeSpin(): boolean {
        if (!this.isActive || this.remainingSpins <= 0) return false;

        this.remainingSpins--;
        console.log(`[FreeSpin] Spin used. ${this.remainingSpins} remaining`);

        if (this.remainingSpins <= 0) {
            this.isActive = false;
            console.log('[FreeSpin] Free spins ended!');
        }

        return true;
    }

    /** 重置所有狀態（遊戲初始化或異常恢復時使用） */
    reset(): void {
        this.remainingSpins = 0;
        this.totalAwarded = 0;
        this.isActive = false;
    }
}
