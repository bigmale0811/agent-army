"""RTP 模擬器 — Monte Carlo 模擬計算理論 RTP

透過大量隨機模擬 spin，計算遊戲的理論回報率 (Return to Player)。
支援 cascade 消除型遊戲的完整機制模擬。
"""
from __future__ import annotations
import logging
import random
from dataclasses import dataclass, field
from collections import defaultdict, deque

from slot_cloner.models.game import GameConfig
from slot_cloner.models.symbol import SymbolConfig
from slot_cloner.models.enums import GameType, SymbolType

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RTPResult:
    """RTP 模擬結果"""
    total_spins: int
    total_wagered: float
    total_won: float
    rtp_percent: float
    hit_rate: float  # 中獎率（有獎 spin 佔比）
    avg_cascade_depth: float  # 平均消除連鎖深度
    max_win_multiplier: float  # 最大單次贏額倍率
    free_spin_trigger_rate: float  # 免費旋轉觸發率
    symbol_hit_counts: dict[str, int] = field(default_factory=dict)


class RTPSimulator:
    """Monte Carlo RTP 模擬器

    模擬邏輯：
    1. 隨機填充 grid（含 scatter / wild / multiplier 符號）
    2. BFS 偵測消除群組
    3. 計算獎金（含 multiplier 累加）
    4. 執行 cascade 掉落 + 補充
    5. 重複直到無更多消除
    6. 偵測 scatter 觸發免費旋轉
    """

    def __init__(self, config: GameConfig, seed: int | None = None) -> None:
        self._config = config
        self._rng = random.Random(seed)
        self._cols = config.grid.cols
        self._rows = config.grid.rows

        # 建立符號權重表（regular 符號有更高的出現率）
        self._regular_symbols = [
            s for s in config.symbols if s.symbol_type == SymbolType.REGULAR
        ]
        self._all_symbol_ids = [s.id for s in config.symbols]

        # 符號出現權重：regular 10, wild 2, scatter 1, multiplier 1, bonus 1
        self._weighted_symbols: list[str] = []
        for s in config.symbols:
            weight = {
                SymbolType.REGULAR: 10,
                SymbolType.WILD: 2,
                SymbolType.SCATTER: 1,
                SymbolType.MULTIPLIER: 1,
                SymbolType.BONUS: 1,
            }.get(s.symbol_type, 5)
            self._weighted_symbols.extend([s.id] * weight)

        self._min_cluster = config.paytable.min_cluster_size
        self._wild_id = config.features.wild.symbol_id if config.features.wild.enabled else None
        self._scatter_id = config.features.scatter.symbol_id if config.features.scatter.enabled else None

    def simulate(self, num_spins: int = 100_000, bet: float = 1.0) -> RTPResult:
        """執行 Monte Carlo 模擬

        Args:
            num_spins: 模擬次數（預設 10 萬次）
            bet: 每次投注金額

        Returns:
            RTPResult 模擬結果
        """
        total_wagered = 0.0
        total_won = 0.0
        winning_spins = 0
        total_cascades = 0
        total_cascade_depth = 0
        max_win_mult = 0.0
        free_spin_triggers = 0
        symbol_hits: dict[str, int] = defaultdict(int)

        for i in range(num_spins):
            total_wagered += bet

            # 產生隨機 grid
            grid = self._random_grid()

            # 檢查 scatter
            scatter_count = self._count_scatter(grid)
            if scatter_count >= (self._config.features.scatter.trigger_count or 99):
                free_spin_triggers += 1

            # 執行 cascade 連鎖
            spin_win = 0.0
            cascade_count = 0
            multiplier_sum = 0

            while True:
                wins = self._find_clusters(grid)
                if not wins:
                    break

                cascade_count += 1

                # 計算本次 cascade 獎金
                cascade_win = 0.0
                all_removed: set[tuple[int, int]] = set()

                for sym_id, positions in wins:
                    payout = self._get_payout(sym_id, len(positions))
                    cascade_win += payout * bet
                    symbol_hits[sym_id] += 1
                    for pos in positions:
                        all_removed.add(pos)

                # 收集乘數符號
                if self._config.features.multiplier.enabled:
                    for col, row in all_removed:
                        sym_data = self._get_symbol_data(grid[col][row])
                        if sym_data and sym_data.symbol_type == SymbolType.MULTIPLIER:
                            values = list(self._config.features.multiplier.values)
                            if values:
                                multiplier_sum += self._rng.choice(values)

                effective_mult = multiplier_sum if multiplier_sum > 0 else 1
                spin_win += cascade_win * effective_mult

                # 消除並掉落
                self._remove_and_cascade(grid, all_removed)

                if cascade_count > 50:
                    break

            if spin_win > 0:
                winning_spins += 1
                win_mult = spin_win / bet
                if win_mult > max_win_mult:
                    max_win_mult = win_mult

            total_won += spin_win
            total_cascades += cascade_count
            total_cascade_depth += cascade_count

            # 進度回報
            if (i + 1) % 25000 == 0:
                logger.info(
                    "RTP 模擬進度: %d/%d (%.1f%%)",
                    i + 1, num_spins, (i + 1) / num_spins * 100,
                )

        rtp = (total_won / total_wagered * 100) if total_wagered > 0 else 0
        hit_rate = winning_spins / num_spins if num_spins > 0 else 0
        avg_cascade = total_cascade_depth / num_spins if num_spins > 0 else 0
        fs_rate = free_spin_triggers / num_spins if num_spins > 0 else 0

        result = RTPResult(
            total_spins=num_spins,
            total_wagered=total_wagered,
            total_won=total_won,
            rtp_percent=round(rtp, 4),
            hit_rate=round(hit_rate, 4),
            avg_cascade_depth=round(avg_cascade, 2),
            max_win_multiplier=round(max_win_mult, 2),
            free_spin_trigger_rate=round(fs_rate, 6),
            symbol_hit_counts=dict(symbol_hits),
        )

        logger.info(
            "RTP 模擬完成: %d spins, RTP=%.2f%%, hit_rate=%.1f%%",
            num_spins, result.rtp_percent, result.hit_rate * 100,
        )
        return result

    def _random_grid(self) -> list[list[str]]:
        """產生隨機 grid [col][row]"""
        return [
            [self._rng.choice(self._weighted_symbols) for _ in range(self._rows)]
            for _ in range(self._cols)
        ]

    def _count_scatter(self, grid: list[list[str]]) -> int:
        """計算 grid 中 scatter 符號數量"""
        if not self._scatter_id:
            return 0
        count = 0
        for col in grid:
            for sym in col:
                if sym == self._scatter_id:
                    count += 1
        return count

    def _find_clusters(self, grid: list[list[str]]) -> list[tuple[str, list[tuple[int, int]]]]:
        """BFS 搜尋所有合格的消除群組"""
        visited = [[False] * self._rows for _ in range(self._cols)]
        clusters: list[tuple[str, list[tuple[int, int]]]] = []

        for c in range(self._cols):
            for r in range(self._rows):
                if visited[c][r]:
                    continue
                sym = grid[c][r]
                if not sym:
                    continue
                sym_data = self._get_symbol_data(sym)
                if sym_data and sym_data.symbol_type in (SymbolType.SCATTER, SymbolType.BONUS):
                    continue

                cluster = self._bfs(grid, c, r, sym, visited)
                if len(cluster) >= self._min_cluster:
                    clusters.append((sym, cluster))

        return clusters

    def _bfs(
        self,
        grid: list[list[str]],
        start_c: int,
        start_r: int,
        target: str,
        visited: list[list[bool]],
    ) -> list[tuple[int, int]]:
        """BFS flood-fill（含 Wild 替代，使用 deque 確保 O(1) 取出）"""
        queue: deque[tuple[int, int]] = deque([(start_c, start_r)])
        visited[start_c][start_r] = True
        cluster: list[tuple[int, int]] = []

        while queue:
            c, r = queue.popleft()
            cluster.append((c, r))

            for nc, nr in [(c - 1, r), (c + 1, r), (c, r - 1), (c, r + 1)]:
                if 0 <= nc < self._cols and 0 <= nr < self._rows and not visited[nc][nr]:
                    n_sym = grid[nc][nr]
                    if not n_sym:
                        continue
                    match = (
                        n_sym == target
                        or (self._wild_id and n_sym == self._wild_id)
                        or (self._wild_id and target == self._wild_id)
                    )
                    if match:
                        visited[nc][nr] = True
                        queue.append((nc, nr))

        return cluster

    def _get_payout(self, symbol_id: str, count: int) -> float:
        """查詢賠率"""
        best = 0.0
        for entry in self._config.paytable.entries:
            if entry.symbol_id == symbol_id and count >= entry.min_count:
                if entry.payout_multiplier > best:
                    best = entry.payout_multiplier

        sym = self._get_symbol_data(symbol_id)
        if sym and sym.payouts:
            for min_str, mult in sym.payouts.items():
                if count >= int(min_str) and mult > best:
                    best = mult

        return best

    def _get_symbol_data(self, symbol_id: str) -> SymbolConfig | None:
        """查詢符號定義"""
        for s in self._config.symbols:
            if s.id == symbol_id:
                return s
        return None

    def _remove_and_cascade(self, grid: list[list[str]], removed: set[tuple[int, int]]) -> None:
        """消除符號並掉落填充（原地修改 grid）"""
        for c in range(self._cols):
            # 收集未被消除的符號
            remaining = [grid[c][r] for r in range(self._rows) if (c, r) not in removed]
            # 補充新符號
            needed = self._rows - len(remaining)
            new_syms = [self._rng.choice(self._weighted_symbols) for _ in range(needed)]
            # 新符號在上方，現有符號在下方
            full_col = new_syms + remaining
            for r in range(self._rows):
                grid[c][r] = full_col[r]
