/**
 * Tween — 輕量級補間動畫工具
 *
 * 使用 requestAnimationFrame 實現平滑過渡。
 * 支援常用的 easing 函數，不依賴外部庫。
 */

export type EasingFn = (t: number) => number;

/** 常用 Easing 函數 */
export const Easing = {
    linear: (t: number): number => t,
    easeOutQuad: (t: number): number => t * (2 - t),
    easeInQuad: (t: number): number => t * t,
    easeOutBounce: (t: number): number => {
        if (t < 1 / 2.75) return 7.5625 * t * t;
        if (t < 2 / 2.75) { t -= 1.5 / 2.75; return 7.5625 * t * t + 0.75; }
        if (t < 2.5 / 2.75) { t -= 2.25 / 2.75; return 7.5625 * t * t + 0.9375; }
        t -= 2.625 / 2.75;
        return 7.5625 * t * t + 0.984375;
    },
    easeOutBack: (t: number): number => {
        const c = 1.70158;
        return 1 + (c + 1) * Math.pow(t - 1, 3) + c * Math.pow(t - 1, 2);
    },
    easeOutElastic: (t: number): number => {
        if (t === 0 || t === 1) return t;
        return Math.pow(2, -10 * t) * Math.sin((t - 0.075) * (2 * Math.PI) / 0.3) + 1;
    },
} as const;

export interface TweenOptions {
    duration: number;        // 毫秒
    easing?: EasingFn;
    onUpdate: (value: number) => void;
    onComplete?: () => void;
}

/**
 * 執行一個 0→1 的補間動畫
 * @returns Promise 在動畫完成時 resolve
 */
export function tween(options: TweenOptions): Promise<void> {
    const { duration, easing = Easing.easeOutQuad, onUpdate, onComplete } = options;

    return new Promise<void>((resolve) => {
        const startTime = performance.now();

        function tick(now: number): void {
            const elapsed = now - startTime;
            const progress = Math.min(elapsed / duration, 1);
            const easedValue = easing(progress);

            onUpdate(easedValue);

            if (progress < 1) {
                requestAnimationFrame(tick);
            } else {
                onComplete?.();
                resolve();
            }
        }

        requestAnimationFrame(tick);
    });
}

/**
 * 在指定範圍之間補間
 */
export function tweenFromTo(
    from: number,
    to: number,
    options: Omit<TweenOptions, 'onUpdate'> & { onUpdate: (value: number) => void },
): Promise<void> {
    const range = to - from;
    return tween({
        ...options,
        onUpdate: (t: number) => options.onUpdate(from + range * t),
    });
}
