import { Application } from 'pixi.js';
import { Game } from './Game';
import { GameConfigData } from './types';

async function bootstrap(): Promise<void> {
    // Load game config from JSON file
    const response = await fetch('./game-config.json');
    const config: GameConfigData = await response.json();

    // Create PixiJS v8 Application
    const app = new Application();
    await app.init({
        width: 960,
        height: 640,
        backgroundColor: 0x0d0d1a,
        antialias: true,
        resolution: window.devicePixelRatio || 1,
        autoDensity: true,
    });

    // Mount canvas to DOM
    const container = document.getElementById('game-container');
    if (container) {
        container.appendChild(app.canvas);
    }

    // Initialize and start the game
    const game = new Game(app, config);
    await game.init();
}

bootstrap().catch(console.error);
