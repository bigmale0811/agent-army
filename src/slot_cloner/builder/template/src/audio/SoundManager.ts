/**
 * SoundManager — 遊戲音效管理器
 *
 * 使用 Web Audio API 播放音效，不依賴外部庫。
 * 支援：
 * - 預載音效檔案（loadSound）
 * - 播放、停止、調整音量
 * - 全域靜音切換
 * - 背景音樂循環播放
 */
export class SoundManager {
    private context: AudioContext | null = null;
    private buffers: Map<string, AudioBuffer> = new Map();
    private activeSources: Map<string, AudioBufferSourceNode> = new Map();
    private gainNode: GainNode | null = null;
    private muted: boolean = false;
    private volume: number = 0.7;

    constructor() {
        this.initContext();
    }

    /** 初始化 AudioContext（需要使用者互動後才能 resume） */
    private initContext(): void {
        try {
            this.context = new AudioContext();
            this.gainNode = this.context.createGain();
            this.gainNode.connect(this.context.destination);
            this.gainNode.gain.value = this.volume;
        } catch (e) {
            console.warn('[SoundManager] Web Audio API not available:', e);
        }
    }

    /** 確保 AudioContext 已 resume（瀏覽器 autoplay policy） */
    async ensureResumed(): Promise<void> {
        if (this.context?.state === 'suspended') {
            await this.context.resume();
        }
    }

    /**
     * 預載音效檔案
     * @param name 音效名稱（用於 play 時引用）
     * @param url 音效檔案 URL
     */
    async loadSound(name: string, url: string): Promise<void> {
        if (!this.context) return;

        try {
            const response = await fetch(url);
            const arrayBuffer = await response.arrayBuffer();
            const audioBuffer = await this.context.decodeAudioData(arrayBuffer);
            this.buffers.set(name, audioBuffer);
        } catch (e) {
            console.warn(`[SoundManager] Failed to load sound "${name}":`, e);
        }
    }

    /**
     * 播放音效
     * @param name 已載入的音效名稱
     * @param loop 是否循環播放（用於背景音樂）
     * @param volumeScale 音量倍率（0~1）
     */
    play(name: string, loop: boolean = false, volumeScale: number = 1): void {
        if (!this.context || !this.gainNode || this.muted) return;

        const buffer = this.buffers.get(name);
        if (!buffer) {
            // 音效未載入時靜默失敗（遊戲不應因音效問題中斷）
            return;
        }

        // 如果同名音效正在播放，先停止
        this.stop(name);

        const source = this.context.createBufferSource();
        source.buffer = buffer;
        source.loop = loop;

        // 個別音量控制
        const individualGain = this.context.createGain();
        individualGain.gain.value = volumeScale;
        source.connect(individualGain);
        individualGain.connect(this.gainNode);

        source.start(0);
        this.activeSources.set(name, source);

        // 非循環播放結束後自動清理
        if (!loop) {
            source.onended = () => {
                this.activeSources.delete(name);
            };
        }
    }

    /** 停止特定音效 */
    stop(name: string): void {
        const source = this.activeSources.get(name);
        if (source) {
            try {
                source.stop();
            } catch {
                // 忽略已停止的 source
            }
            this.activeSources.delete(name);
        }
    }

    /** 停止所有音效 */
    stopAll(): void {
        for (const [name] of this.activeSources) {
            this.stop(name);
        }
    }

    /** 切換靜音 */
    toggleMute(): boolean {
        this.muted = !this.muted;
        if (this.gainNode) {
            this.gainNode.gain.value = this.muted ? 0 : this.volume;
        }
        return this.muted;
    }

    /** 設定音量 (0~1) */
    setVolume(value: number): void {
        this.volume = Math.max(0, Math.min(1, value));
        if (this.gainNode && !this.muted) {
            this.gainNode.gain.value = this.volume;
        }
    }

    /** 取得靜音狀態 */
    isMuted(): boolean {
        return this.muted;
    }

    /** 預定義的遊戲音效事件名稱 */
    static readonly Events = {
        SPIN: 'spin',
        WIN: 'win',
        BIG_WIN: 'big_win',
        CASCADE: 'cascade',
        FREE_SPIN_TRIGGER: 'free_spin_trigger',
        FREE_SPIN_END: 'free_spin_end',
        BUTTON_CLICK: 'button_click',
        BGM: 'bgm',
    } as const;
}
