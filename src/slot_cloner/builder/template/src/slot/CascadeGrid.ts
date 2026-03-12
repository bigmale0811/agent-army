import { Container, Graphics, Text, TextStyle } from 'pixi.js';
import { GameConfigData, CellPosition, WinResult } from '../types';
import { RNG } from '../math/RNG';

const CELL_SIZE = 100;
const CELL_GAP = 4;

/**
 * Per-symbol-type background colors for special symbols.
 * Regular symbols get a deterministic color derived from their ID hash.
 */
const SYMBOL_TYPE_COLORS: Record<string, number> = {
    wild:       0xffd700,
    scatter:    0xff4500,
    bonus:      0x9400d3,
    multiplier: 0x00ff88,
};

const REGULAR_COLORS = [
    0xe74c3c, 0x3498db, 0x2ecc71, 0xf39c12,
    0x9b59b6, 0x1abc9c, 0xe67e22, 0x34495e,
];

/**
 * CascadeGrid manages the visual slot grid.
 *
 * Responsibilities:
 *  - Render symbol cells using PixiJS Graphics + Text
 *  - Expose getSymbolGrid() for engine evaluation
 *  - Animate win highlights, cell removal, and cascade drop-fill
 */
export class CascadeGrid extends Container {
    private config: GameConfigData;
    private rng: RNG;
    private cols: number;
    private rows: number;
    // cells[col][row] — null means empty slot
    private cells: (GridCell | null)[][];
    private cellContainer: Container;

    constructor(config: GameConfigData, rng: RNG) {
        super();
        this.config = config;
        this.rng = rng;
        this.cols = config.game.grid.cols;
        this.rows = config.game.grid.rows;
        this.cells = [];
        this.cellContainer = new Container();
        this.addChild(this.cellContainer);

        this.drawBackground();

        // Initialize null grid
        for (let c = 0; c < this.cols; c++) {
            this.cells[c] = [];
            for (let r = 0; r < this.rows; r++) {
                this.cells[c][r] = null;
            }
        }
    }

    /** Draw a rounded-rect background panel behind the grid */
    private drawBackground(): void {
        const bg = new Graphics();
        const totalW = this.cols * (CELL_SIZE + CELL_GAP) - CELL_GAP + 20;
        const totalH = this.rows * (CELL_SIZE + CELL_GAP) - CELL_GAP + 20;
        bg.roundRect(-10, -10, totalW, totalH, 12);
        bg.fill({ color: 0x1a1a2e, alpha: 0.8 });
        bg.stroke({ color: 0x2d2d5e, width: 2 });
        this.addChildAt(bg, 0);
    }

    /** Fill entire grid with freshly randomized regular symbols */
    fillRandom(): void {
        this.cellContainer.removeChildren();

        const regularSymbols = this.config.symbols.filter(s => s.type === 'regular');

        for (let c = 0; c < this.cols; c++) {
            for (let r = 0; r < this.rows; r++) {
                const sym = regularSymbols[this.rng.nextInt(0, regularSymbols.length - 1)];
                this.setCell(c, r, sym.id);
            }
        }
    }

    /** Place a symbol at (col, row), replacing any existing cell visual */
    private setCell(col: number, row: number, symbolId: string): void {
        const existing = this.cells[col][row];
        if (existing) {
            this.cellContainer.removeChild(existing.container);
        }

        const cell = this.createCellVisual(col, row, symbolId);
        this.cells[col][row] = cell;
        this.cellContainer.addChild(cell.container);
    }

    /** Build the PixiJS display object for a single grid cell */
    private createCellVisual(col: number, row: number, symbolId: string): GridCell {
        const container = new Container();
        container.x = col * (CELL_SIZE + CELL_GAP);
        container.y = row * (CELL_SIZE + CELL_GAP);

        // Colored background tile
        const bg = new Graphics();
        bg.roundRect(0, 0, CELL_SIZE, CELL_SIZE, 8);
        bg.fill({ color: this.getSymbolColor(symbolId), alpha: 0.85 });
        container.addChild(bg);

        // Short symbol label (first 3 chars, uppercase)
        const symbolData = this.config.symbols.find(s => s.id === symbolId);
        const label = (symbolData?.name ?? symbolId).substring(0, 3).toUpperCase();

        const style = new TextStyle({
            fontFamily: 'Arial',
            fontSize: 18,
            fontWeight: 'bold',
            fill: 0xffffff,
            align: 'center',
        });
        const text = new Text({ text: label, style });
        text.anchor.set(0.5);
        text.x = CELL_SIZE / 2;
        text.y = CELL_SIZE / 2;
        container.addChild(text);

        return { container, symbolId, col, row };
    }

    /**
     * Determine the display color for a symbol.
     * Special types use fixed colors; regular symbols get a hash-derived color.
     */
    private getSymbolColor(symbolId: string): number {
        const symbolData = this.config.symbols.find(s => s.id === symbolId);
        if (symbolData && SYMBOL_TYPE_COLORS[symbolData.type]) {
            return SYMBOL_TYPE_COLORS[symbolData.type];
        }
        // Deterministic color from symbol ID string hash
        let hash = 0;
        for (let i = 0; i < symbolId.length; i++) {
            hash = ((hash << 5) - hash) + symbolId.charCodeAt(i);
            hash |= 0;
        }
        return REGULAR_COLORS[Math.abs(hash) % REGULAR_COLORS.length];
    }

    /**
     * Return current grid state as a 2D string array [col][row].
     * Empty slots are represented by empty string.
     */
    getSymbolGrid(): string[][] {
        const grid: string[][] = [];
        for (let c = 0; c < this.cols; c++) {
            grid[c] = [];
            for (let r = 0; r < this.rows; r++) {
                grid[c][r] = this.cells[c][r]?.symbolId ?? '';
            }
        }
        return grid;
    }

    /**
     * Scan the given positions for multiplier-type symbols and collect their values.
     * A random value from the config's multiplier.values array is assigned to each.
     */
    collectMultipliers(positions: CellPosition[]): number[] {
        const multipliers: number[] = [];
        const values = this.config.features.multiplier.values;
        for (const pos of positions) {
            const cell = this.cells[pos.col]?.[pos.row];
            if (cell) {
                const sym = this.config.symbols.find(s => s.id === cell.symbolId);
                if (sym?.type === 'multiplier') {
                    multipliers.push(values[this.rng.nextInt(0, values.length - 1)]);
                }
            }
        }
        return multipliers;
    }

    /**
     * Flash winning cells by briefly reducing their alpha.
     * Provides visual feedback before removal.
     */
    async highlightWins(wins: WinResult[]): Promise<void> {
        const positions = new Set<string>();
        for (const win of wins) {
            for (const pos of win.positions) {
                positions.add(`${pos.col},${pos.row}`);
            }
        }

        // Dim winning cells
        for (const key of positions) {
            const [col, row] = key.split(',').map(Number);
            const cell = this.cells[col]?.[row];
            if (cell) cell.container.alpha = 0.4;
        }

        await this.delay(350);

        // Restore alpha
        for (const key of positions) {
            const [col, row] = key.split(',').map(Number);
            const cell = this.cells[col]?.[row];
            if (cell) cell.container.alpha = 1;
        }
    }

    /**
     * Remove the visual objects for the given positions and null out their slots.
     */
    async removeCells(positions: CellPosition[]): Promise<void> {
        for (const pos of positions) {
            const cell = this.cells[pos.col]?.[pos.row];
            if (cell) {
                this.cellContainer.removeChild(cell.container);
                this.cells[pos.col][pos.row] = null;
            }
        }
        await this.delay(200);
    }

    /**
     * Cascade: compact symbols downward within each column to fill gaps,
     * then generate new random symbols to fill the vacated top slots.
     *
     * Column layout: row 0 = top, row (rows-1) = bottom.
     * Existing symbols sink to the bottom; new symbols appear at the top.
     */
    async cascadeDown(): Promise<void> {
        const regularSymbols = this.config.symbols.filter(s => s.type === 'regular');

        for (let c = 0; c < this.cols; c++) {
            // Gather existing (non-null) symbol IDs from top to bottom
            const existing: string[] = [];
            for (let r = 0; r < this.rows; r++) {
                if (this.cells[c][r]) {
                    existing.push(this.cells[c][r]!.symbolId);
                }
            }

            // Generate new random symbols for the vacated slots at the top
            const needed = this.rows - existing.length;
            const newSymbols: string[] = [];
            for (let i = 0; i < needed; i++) {
                newSymbols.push(
                    regularSymbols[this.rng.nextInt(0, regularSymbols.length - 1)].id
                );
            }

            // Rebuild column: new symbols fill top rows, existing symbols fill bottom rows
            const fullColumn = [...newSymbols, ...existing];
            for (let r = 0; r < this.rows; r++) {
                this.setCell(c, r, fullColumn[r]);
            }
        }

        await this.delay(300);
    }

    private delay(ms: number): Promise<void> {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}

/** Internal cell state record */
interface GridCell {
    container: Container;
    symbolId: string;
    col: number;
    row: number;
}
