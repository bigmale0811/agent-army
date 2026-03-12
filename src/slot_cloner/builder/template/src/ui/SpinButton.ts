import { Container, Graphics, Text, TextStyle, FederatedPointerEvent } from 'pixi.js';

/**
 * SpinButton — interactive round button that emits a 'spin' event on click.
 * Supports enabled/disabled state with visual feedback.
 */
export class SpinButton extends Container {
    private bg: Graphics;
    private btnLabel: Text;
    private enabled: boolean = true;

    private static readonly COLOR_NORMAL   = 0x27ae60;
    private static readonly COLOR_HOVER    = 0x2ecc71;
    private static readonly COLOR_DISABLED = 0x555555;
    private static readonly WIDTH  = 120;
    private static readonly HEIGHT = 60;
    private static readonly RADIUS = 30;

    constructor() {
        super();

        // Button background graphics object (reused across state draws)
        this.bg = new Graphics();
        this.drawButton(SpinButton.COLOR_NORMAL);
        this.addChild(this.bg);

        // Centered label
        const style = new TextStyle({
            fontFamily: 'Arial',
            fontSize: 24,
            fontWeight: 'bold',
            fill: 0xffffff,
            letterSpacing: 1,
        });
        this.btnLabel = new Text({ text: 'SPIN', style });
        this.btnLabel.anchor.set(0.5);
        this.btnLabel.x = SpinButton.WIDTH / 2;
        this.btnLabel.y = SpinButton.HEIGHT / 2;
        this.addChild(this.btnLabel);

        // Enable pointer interactivity
        this.eventMode = 'static';
        this.cursor = 'pointer';
        this.on('pointerdown',  this.onClick.bind(this));
        this.on('pointerover',  this.onHover.bind(this));
        this.on('pointerout',   this.onOut.bind(this));
    }

    private drawButton(color: number): void {
        this.bg.clear();
        this.bg.roundRect(0, 0, SpinButton.WIDTH, SpinButton.HEIGHT, SpinButton.RADIUS);
        this.bg.fill({ color });
        this.bg.stroke({ color: 0xffffff, width: 2, alpha: 0.25 });
    }

    private onClick(_event: FederatedPointerEvent): void {
        if (!this.enabled) return;
        this.emit('spin');
    }

    private onHover(): void {
        if (this.enabled) this.drawButton(SpinButton.COLOR_HOVER);
    }

    private onOut(): void {
        if (this.enabled) this.drawButton(SpinButton.COLOR_NORMAL);
    }

    /**
     * Enable or disable the button.
     * Disabled state dims the button, changes cursor, and shows "..." label.
     */
    setEnabled(enabled: boolean): void {
        this.enabled = enabled;
        this.alpha = enabled ? 1.0 : 0.5;
        this.cursor = enabled ? 'pointer' : 'default';
        this.btnLabel.text = enabled ? 'SPIN' : '...';
        this.drawButton(enabled ? SpinButton.COLOR_NORMAL : SpinButton.COLOR_DISABLED);
    }
}
