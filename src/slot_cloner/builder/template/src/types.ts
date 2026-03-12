/** TypeScript type definitions matching game-config.json structure */

export interface GameConfigData {
    game: {
        name: string;
        displayName: string;
        type: 'cascade' | 'classic' | 'ways' | 'cluster';
        grid: { cols: number; rows: number };
        rtp: number;
        maxMultiplier: number;
        minBet: number;
        maxBet: number;
    };
    symbols: SymbolData[];
    paytable: {
        minClusterSize: number;
        entries: PaytableEntry[];
    };
    features: FeaturesData;
    assets: {
        basePath: string;
        imagesPath: string;
        audioPath: string;
        spritesPath: string;
    };
}

export interface SymbolData {
    id: string;
    name: string;
    type: 'regular' | 'wild' | 'scatter' | 'bonus' | 'multiplier';
    image: string;
    payouts: Record<string, number>;
}

export interface PaytableEntry {
    symbolId: string;
    minCount: number;
    multiplier: number;
}

export interface FeaturesData {
    wild: {
        enabled: boolean;
        symbolId: string;
        substitutesAll: boolean;
        exceptSymbols: string[];
    };
    scatter: {
        enabled: boolean;
        symbolId: string;
        triggerCount: number;
        freeSpinsAwarded: number;
    };
    cascade: {
        enabled: boolean;
        minClusterSize: number;
        fillFromTop: boolean;
    };
    multiplier: {
        enabled: boolean;
        values: number[];
        accumulateInCascade: boolean;
    };
    freeSpin: {
        enabled: boolean;
        baseSpins: number;
        retriggerEnabled: boolean;
        retriggerSpins: number;
    };
}

/** 遊戲狀態機 */
export enum GameState {
    IDLE = 'idle',
    SPINNING = 'spinning',
    CASCADING = 'cascading',
    FREE_SPIN_INTRO = 'free_spin_intro',
    FREE_SPINNING = 'free_spinning',
    WIN_DISPLAY = 'win_display',
}

/** Runtime types */
export interface CellPosition {
    col: number;
    row: number;
}

export interface SpinResult {
    grid: string[][];
    wins: WinResult[];
    totalWin: number;
    cascades: CascadeStep[];
    multiplierTotal: number;
}

export interface WinResult {
    symbolId: string;
    positions: CellPosition[];
    count: number;
    payout: number;
}

export interface CascadeStep {
    removedPositions: CellPosition[];
    newSymbols: { col: number; symbols: string[] }[];
    wins: WinResult[];
    stepWin: number;
}
