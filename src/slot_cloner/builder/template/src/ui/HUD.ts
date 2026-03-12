import { Container, Text, TextStyle } from 'pixi.js';

/**
 * HUD (Head-Up Display) — shows balance, current bet, and last win amount.
 * Positioned at the top of the screen.
 */
export class HUD extends Container {
    private balanceText: Text;
    private betText: Text;
    private winText: Text;
    private freeSpinText: Text | null = null;

    constructor(balance: number, bet: number) {
        super();

        const labelStyle = new TextStyle({
            fontFamily: 'Arial',
            fontSize: 14,
            fill: 0xaaaacc,
            letterSpacing: 2,
        });

        const valueStyle = new TextStyle({
            fontFamily: 'Arial',
            fontSize: 22,
            fontWeight: 'bold',
            fill: 0xffd700,
        });

        // --- Balance column ---
        const balLabel = new Text({ text: 'BALANCE', style: labelStyle });
        balLabel.x = 0;
        balLabel.y = 0;
        this.addChild(balLabel);

        this.balanceText = new Text({ text: `$${balance.toFixed(2)}`, style: valueStyle });
        this.balanceText.x = 0;
        this.balanceText.y = 18;
        this.addChild(this.balanceText);

        // --- Bet column ---
        const betLabel = new Text({ text: 'BET', style: labelStyle });
        betLabel.x = 220;
        betLabel.y = 0;
        this.addChild(betLabel);

        this.betText = new Text({ text: `$${bet.toFixed(2)}`, style: valueStyle });
        this.betText.x = 220;
        this.betText.y = 18;
        this.addChild(this.betText);

        // --- Win column ---
        const winLabel = new Text({ text: 'WIN', style: labelStyle });
        winLabel.x = 440;
        winLabel.y = 0;
        this.addChild(winLabel);

        this.winText = new Text({ text: '$0.00', style: valueStyle });
        this.winText.x = 440;
        this.winText.y = 18;
        this.addChild(this.winText);
    }

    /** Update displayed balance amount */
    updateBalance(amount: number): void {
        this.balanceText.text = `$${amount.toFixed(2)}`;
    }

    /** Update displayed bet amount */
    updateBet(amount: number): void {
        this.betText.text = `$${amount.toFixed(2)}`;
    }

    /**
     * Show win amount with a brief color flash.
     * Pass 0 to reset the win display.
     */
    showWin(amount: number): void {
        this.winText.text = `$${amount.toFixed(2)}`;
        if (amount > 0) {
            // Flash orange then return to gold
            this.winText.style.fill = 0xff6600;
            setTimeout(() => {
                this.winText.style.fill = 0xffd700;
            }, 1200);
        }
    }

    /** 顯示免費旋轉剩餘次數 */
    showFreeSpin(remaining: number, total: number): void {
        if (!this.freeSpinText) {
            const style = new TextStyle({
                fontFamily: 'Arial',
                fontSize: 20,
                fontWeight: 'bold',
                fill: 0x00ffcc,
            });
            this.freeSpinText = new Text({ text: '', style });
            this.freeSpinText.x = 660;
            this.freeSpinText.y = 18;
            this.addChild(this.freeSpinText);
        }
        this.freeSpinText.text = `FREE: ${remaining}/${total}`;
        this.freeSpinText.visible = true;
    }

    /** 隱藏免費旋轉顯示 */
    hideFreeSpin(): void {
        if (this.freeSpinText) {
            this.freeSpinText.visible = false;
        }
    }
}
