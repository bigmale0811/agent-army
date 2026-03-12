/**
 * Cryptographically secure RNG using crypto.getRandomValues.
 * Avoids Math.random() which is not cryptographically secure.
 */
export class RNG {
    /**
     * Generate a random integer between min and max (inclusive).
     * Uses modulo reduction — suitable for small ranges.
     */
    nextInt(min: number, max: number): number {
        const range = max - min + 1;
        const array = new Uint32Array(1);
        crypto.getRandomValues(array);
        return min + (array[0] % range);
    }

    /**
     * Generate a random float between 0 (inclusive) and 1 (exclusive).
     */
    nextFloat(): number {
        const array = new Uint32Array(1);
        crypto.getRandomValues(array);
        return array[0] / (0xFFFFFFFF + 1);
    }

    /**
     * Shuffle an array in place using the Fisher-Yates algorithm.
     * Returns the same array reference after shuffling.
     */
    shuffle<T>(arr: T[]): T[] {
        for (let i = arr.length - 1; i > 0; i--) {
            const j = this.nextInt(0, i);
            [arr[i], arr[j]] = [arr[j], arr[i]];
        }
        return arr;
    }

    /**
     * Pick a random element from an array.
     */
    pick<T>(arr: readonly T[]): T {
        return arr[this.nextInt(0, arr.length - 1)];
    }
}
