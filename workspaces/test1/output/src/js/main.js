// 泡泡射击游戏主文件
class BubbleGame {
    constructor() {
        this.canvas = document.getElementById('game-canvas');
        this.ctx = this.canvas.getContext('2d');
        this.gameState = 'menu'; // menu, playing, paused, gameover
        this.score = 0;
        this.level = 1;
        this.highScore = localStorage.getItem('bubbleGameHighScore') || 0;

        // 游戏对象
        this.bubbleGrid = new BubbleGrid(10, 16);
        this.shooter = new Shooter(400, 550);
        this.movingBubbles = [];

        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.updateHighScore();
        this.gameLoop();
    }
    
    setupEventListeners() {
        // 菜单按钮事件
        document.getElementById('start-game').addEventListener('click', () => {
            this.startGame();
        });
        
        document.getElementById('pause-btn').addEventListener('click', () => {
            this.togglePause();
        });
        
        document.getElementById('restart-btn').addEventListener('click', () => {
            this.restartGame();
        });
        
        // 游戏控制事件
        this.canvas.addEventListener('mousemove', (e) => {
            if (this.gameState === 'playing') {
                this.handleMouseMove(e);
            }
        });

        this.canvas.addEventListener('click', (e) => {
            if (this.gameState === 'playing') {
                this.handleClick(e);
            }
        });
        
        // 键盘事件
        document.addEventListener('keydown', (e) => {
            if (e.code === 'Space' && this.gameState === 'playing') {
                e.preventDefault();
                this.shoot();
            }
        });
    }
    
    startGame() {
        this.gameState = 'playing';
        this.score = 0;
        this.level = 1;
        this.updateScore();
        this.showGameScreen();
        this.initLevel();
    }
    
    showGameScreen() {
        document.getElementById('main-menu').classList.add('hidden');
        document.getElementById('game-screen').classList.remove('hidden');
    }
    
    showMainMenu() {
        document.getElementById('main-menu').classList.remove('hidden');
        document.getElementById('game-screen').classList.add('hidden');
    }
    
    initLevel() {
        // 初始化关卡
        this.movingBubbles = [];
        this.createInitialBubbles();
        this.shooter.reset();
    }

    createInitialBubbles() {
        // 创建初始泡泡布局
        const colors = ['#FF6B6B', '#FFB347', '#6BCF7F', '#4ECDC4', '#A8E6CF'];
        const levelData = {
            bubbles: []
        };

        // 生成5行泡泡
        for (let row = 0; row < 5; row++) {
            const rowData = [];
            const colCount = 16 - (row % 2); // 奇数行少一个

            for (let col = 0; col < colCount; col++) {
                if (Math.random() > 0.2) { // 80%概率放置泡泡
                    const color = colors[Math.floor(Math.random() * colors.length)];
                    rowData.push(color);
                } else {
                    rowData.push(null);
                }
            }
            levelData.bubbles.push(rowData);
        }

        this.bubbleGrid.createLevel(levelData);
    }
    
    handleMouseMove(e) {
        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        // 只瞄准，不射击
        this.shooter.aim(x, y);
    }

    handleClick(e) {
        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        // 瞄准并射击
        this.shooter.aim(x, y);
        this.shoot();
    }

    shootAt(targetX, targetY) {
        this.shooter.aim(targetX, targetY);
        this.shoot();
    }

    shoot() {
        if (this.shooter.canShoot()) {
            const bubble = this.shooter.shoot();
            if (bubble) {
                this.movingBubbles.push(bubble);
            }
        }
    }
    
    togglePause() {
        if (this.gameState === 'playing') {
            this.gameState = 'paused';
        } else if (this.gameState === 'paused') {
            this.gameState = 'playing';
        }
    }
    
    restartGame() {
        this.startGame();
    }
    
    updateScore() {
        document.getElementById('current-score').textContent = this.score;
        document.getElementById('current-level').textContent = this.level;
        
        if (this.score > this.highScore) {
            this.highScore = this.score;
            localStorage.setItem('bubbleGameHighScore', this.highScore);
            this.updateHighScore();
        }
    }
    
    updateHighScore() {
        document.getElementById('high-score-value').textContent = this.highScore;
    }
    
    gameLoop() {
        this.update();
        this.render();
        requestAnimationFrame(() => this.gameLoop());
    }
    
    update() {
        if (this.gameState !== 'playing') return;

        // 更新射击器
        this.shooter.update();

        // 更新网格中的泡泡
        this.bubbleGrid.update();

        // 更新移动的泡泡
        this.updateMovingBubbles();

        // 检查游戏状态
        this.checkGameState();
    }

    updateMovingBubbles() {
        for (let i = this.movingBubbles.length - 1; i >= 0; i--) {
            const bubble = this.movingBubbles[i];
            bubble.update();

            // 检查边界碰撞
            bubble.bounceOffWalls(this.canvas.width, this.canvas.height);

            // 检查与网格泡泡的碰撞
            if (this.checkBubbleCollision(bubble)) {
                this.movingBubbles.splice(i, 1);
                continue;
            }

            // 检查是否到达顶部
            if (bubble.y <= 50) {
                this.attachBubbleToGrid(bubble);
                this.movingBubbles.splice(i, 1);
            }
        }
    }

    checkBubbleCollision(movingBubble) {
        const allBubbles = this.bubbleGrid.getAllBubbles();

        for (const staticBubble of allBubbles) {
            if (movingBubble.collidesWith(staticBubble)) {
                this.attachBubbleToGrid(movingBubble);
                return true;
            }
        }

        return false;
    }

    attachBubbleToGrid(bubble) {
        // 找到最近的空位置
        const gridPos = this.bubbleGrid.findNearestEmptyPosition(bubble.x, bubble.y);

        // 将泡泡添加到网格
        if (this.bubbleGrid.addBubble(gridPos.row, gridPos.col, bubble)) {
            // 检查消除
            this.checkElimination(gridPos.row, gridPos.col);
        }
    }

    checkElimination(row, col) {
        const bubble = this.bubbleGrid.getBubble(row, col);
        if (!bubble) return;

        // 查找连通的相同颜色泡泡
        const connected = this.bubbleGrid.findConnectedBubbles(row, col, bubble.color);

        if (connected.length >= 3) {
            // 消除泡泡
            let eliminatedCount = 0;
            for (const item of connected) {
                const eliminatedBubble = this.bubbleGrid.removeBubble(item.row, item.col);
                if (eliminatedBubble) {
                    eliminatedBubble.explode();
                    eliminatedCount++;
                }
            }

            // 更新分数
            this.score += eliminatedCount * 10;
            this.updateScore();

            // 检查掉落的泡泡
            this.checkFallingBubbles();
        }
    }

    checkFallingBubbles() {
        // 简化的掉落检测 - 这里可以实现更复杂的连通性检测
        // 暂时跳过，保持游戏简单
    }

    checkGameState() {
        // 检查胜利条件
        if (this.bubbleGrid.isWin()) {
            this.gameState = 'win';
            this.level++;
            setTimeout(() => {
                this.initLevel();
                this.gameState = 'playing';
            }, 2000);
        }

        // 检查失败条件
        if (this.bubbleGrid.isGameOver()) {
            this.gameState = 'gameover';
            setTimeout(() => {
                this.showMainMenu();
            }, 2000);
        }
    }
    
    render() {
        // 清空画布
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        if (this.gameState === 'playing' || this.gameState === 'paused') {
            this.renderGame();
        }
        
        if (this.gameState === 'paused') {
            this.renderPauseOverlay();
        }
    }
    
    renderGame() {
        // 渲染背景
        const gradient = this.ctx.createLinearGradient(0, 0, 0, this.canvas.height);
        gradient.addColorStop(0, '#87ceeb');
        gradient.addColorStop(1, '#e0f6ff');
        this.ctx.fillStyle = gradient;
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

        // 渲染网格泡泡
        this.bubbleGrid.render(this.ctx);

        // 渲染移动的泡泡
        for (const bubble of this.movingBubbles) {
            bubble.render(this.ctx);
        }

        // 渲染射击器
        this.shooter.render(this.ctx);

        // 渲染游戏状态
        this.renderGameStatus();
    }

    renderGameStatus() {
        if (this.gameState === 'win') {
            this.ctx.save();
            this.ctx.fillStyle = 'rgba(0, 255, 0, 0.8)';
            this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

            this.ctx.fillStyle = 'white';
            this.ctx.font = '48px Arial';
            this.ctx.textAlign = 'center';
            this.ctx.fillText('关卡完成!', this.canvas.width / 2, this.canvas.height / 2);
            this.ctx.restore();
        } else if (this.gameState === 'gameover') {
            this.ctx.save();
            this.ctx.fillStyle = 'rgba(255, 0, 0, 0.8)';
            this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

            this.ctx.fillStyle = 'white';
            this.ctx.font = '48px Arial';
            this.ctx.textAlign = 'center';
            this.ctx.fillText('游戏结束', this.canvas.width / 2, this.canvas.height / 2);
            this.ctx.restore();
        }
    }
    
    renderPauseOverlay() {
        this.ctx.save();
        this.ctx.fillStyle = 'rgba(0, 0, 0, 0.5)';
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
        
        this.ctx.fillStyle = 'white';
        this.ctx.font = '48px Arial';
        this.ctx.textAlign = 'center';
        this.ctx.fillText('暂停', this.canvas.width / 2, this.canvas.height / 2);
        
        this.ctx.restore();
    }
}

// 启动游戏
window.addEventListener('load', () => {
    new BubbleGame();
});
