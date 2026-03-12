import { GameConfigData, CellPosition, WinResult } from '../types';

/**
 * Paytable Engine — evaluates a grid and returns all winning clusters.
 *
 * Algorithm: BFS flood-fill per cell to find connected groups of the same symbol.
 * Clusters meeting the minimum size threshold qualify as wins.
 * Wild symbols are treated as matching any regular symbol during BFS traversal.
 */
export class PaytableEngine {
    private config: GameConfigData;
    private minCluster: number;

    constructor(config: GameConfigData) {
        this.config = config;
        this.minCluster = config.paytable.minClusterSize;
    }

    /**
     * Evaluate the full grid and return all qualifying winning clusters.
     * @param grid 2D array indexed as grid[col][row] of symbol IDs
     */
    evaluateGrid(grid: string[][]): WinResult[] {
        const cols = grid.length;
        const rows = grid[0]?.length ?? 0;
        // Track visited cells to avoid double-counting clusters
        const visited: boolean[][] = Array.from({ length: cols }, () => Array(rows).fill(false));
        const wins: WinResult[] = [];

        for (let c = 0; c < cols; c++) {
            for (let r = 0; r < rows; r++) {
                if (visited[c][r]) continue;
                const symbolId = grid[c][r];
                if (!symbolId) continue;

                // Scatter and bonus symbols do not form standard clusters
                const symData = this.config.symbols.find(s => s.id === symbolId);
                if (symData?.type === 'scatter' || symData?.type === 'bonus') continue;

                // BFS flood-fill to find all connected same-symbol cells
                const cluster = this.bfsCluster(grid, c, r, symbolId, visited);

                if (cluster.length >= this.minCluster) {
                    const payout = this.calculatePayout(symbolId, cluster.length);
                    if (payout > 0) {
                        wins.push({
                            symbolId,
                            positions: cluster,
                            count: cluster.length,
                            payout,
                        });
                    }
                }
            }
        }

        return wins;
    }

    /**
     * BFS flood-fill to find all orthogonally connected cells matching targetSymbol.
     * Wild symbols connect with any non-scatter, non-bonus symbol.
     */
    private bfsCluster(
        grid: string[][],
        startCol: number,
        startRow: number,
        targetSymbol: string,
        visited: boolean[][],
    ): CellPosition[] {
        const cols = grid.length;
        const rows = grid[0].length;
        const cluster: CellPosition[] = [];
        const queue: CellPosition[] = [{ col: startCol, row: startRow }];
        visited[startCol][startRow] = true;

        const wildId = this.config.features.wild.symbolId;
        const wildEnabled = this.config.features.wild.enabled;

        while (queue.length > 0) {
            const pos = queue.shift()!;
            cluster.push(pos);

            // Check all 4 orthogonal neighbors
            const neighbors: CellPosition[] = [
                { col: pos.col - 1, row: pos.row },
                { col: pos.col + 1, row: pos.row },
                { col: pos.col,     row: pos.row - 1 },
                { col: pos.col,     row: pos.row + 1 },
            ];

            for (const n of neighbors) {
                if (n.col < 0 || n.col >= cols || n.row < 0 || n.row >= rows) continue;
                if (visited[n.col][n.row]) continue;

                const nSymbol = grid[n.col][n.row];
                if (!nSymbol) continue;

                // A neighbor matches if it is the same symbol, or if either is wild
                const isMatch =
                    nSymbol === targetSymbol ||
                    (wildEnabled && nSymbol === wildId) ||
                    (wildEnabled && targetSymbol === wildId);

                if (isMatch) {
                    visited[n.col][n.row] = true;
                    queue.push(n);
                }
            }
        }

        return cluster;
    }

    /**
     * Calculate the payout multiplier for a cluster of the given size.
     * Checks both the global paytable entries and the symbol's own payouts map.
     * Returns the highest applicable multiplier found.
     */
    private calculatePayout(symbolId: string, count: number): number {
        let bestPayout = 0;

        // Check global paytable entries
        for (const entry of this.config.paytable.entries) {
            if (entry.symbolId === symbolId && count >= entry.minCount) {
                if (entry.multiplier > bestPayout) {
                    bestPayout = entry.multiplier;
                }
            }
        }

        // Also check symbol-level payout table (keyed by minimum count string)
        const sym = this.config.symbols.find(s => s.id === symbolId);
        if (sym?.payouts) {
            for (const [minStr, mult] of Object.entries(sym.payouts)) {
                const min = parseInt(minStr, 10);
                if (count >= min && mult > bestPayout) {
                    bestPayout = mult;
                }
            }
        }

        return bestPayout;
    }
}
