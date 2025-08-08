// 泡泡网格系统
class BubbleGrid {
    constructor(rows = 10, cols = 16) {
        this.rows = rows;
        this.cols = cols;
        this.grid = [];
        this.bubbleRadius = 20;
        this.hexOffsetX = this.bubbleRadius * 2;
        this.hexOffsetY = this.bubbleRadius * Math.sqrt(3);
        this.startX = 50;
        this.startY = 50;
        
        this.initGrid();
    }
    
    initGrid() {
        this.grid = [];
        for (let row = 0; row < this.rows; row++) {
            this.grid[row] = [];
            for (let col = 0; col < this.cols; col++) {
                this.grid[row][col] = null;
            }
        }
    }
    
    // 六边形网格布局计算位置
    getPosition(row, col) {
        const x = this.startX + col * this.hexOffsetX + (row % 2) * this.bubbleRadius;
        const y = this.startY + row * this.hexOffsetY;
        return { x, y };
    }
    
    // 根据像素坐标获取网格位置
    getGridPosition(x, y) {
        // 简化的网格位置计算
        const row = Math.round((y - this.startY) / this.hexOffsetY);
        const offsetX = (row % 2) * this.bubbleRadius;
        const col = Math.round((x - this.startX - offsetX) / this.hexOffsetX);
        
        return { row, col };
    }
    
    // 添加泡泡到网格
    addBubble(row, col, bubble) {
        if (this.isValidPosition(row, col)) {
            const pos = this.getPosition(row, col);
            bubble.x = pos.x;
            bubble.y = pos.y;
            bubble.setGridPosition(row, col);
            bubble.stop();
            this.grid[row][col] = bubble;
            return true;
        }
        return false;
    }
    
    // 移除泡泡
    removeBubble(row, col) {
        if (this.isValidPosition(row, col)) {
            const bubble = this.grid[row][col];
            this.grid[row][col] = null;
            return bubble;
        }
        return null;
    }
    
    // 获取泡泡
    getBubble(row, col) {
        if (this.isValidPosition(row, col)) {
            return this.grid[row][col];
        }
        return null;
    }
    
    // 检查位置是否有效
    isValidPosition(row, col) {
        return row >= 0 && row < this.rows && col >= 0 && col < this.cols;
    }
    
    // 获取相邻位置（六边形网格）
    getNeighbors(row, col) {
        const neighbors = [];
        const isEvenRow = row % 2 === 0;
        
        // 六边形的6个相邻位置
        const offsets = isEvenRow ? [
            [-1, -1], [-1, 0],  // 上左，上右
            [0, -1],  [0, 1],   // 左，右
            [1, -1],  [1, 0]    // 下左，下右
        ] : [
            [-1, 0],  [-1, 1],  // 上左，上右
            [0, -1],  [0, 1],   // 左，右
            [1, 0],   [1, 1]    // 下左，下右
        ];
        
        for (const [dRow, dCol] of offsets) {
            const newRow = row + dRow;
            const newCol = col + dCol;
            if (this.isValidPosition(newRow, newCol)) {
                neighbors.push([newRow, newCol]);
            }
        }
        
        return neighbors;
    }
    
    // 查找连通的相同颜色泡泡
    findConnectedBubbles(row, col, color, visited = new Set()) {
        const key = `${row},${col}`;
        if (visited.has(key)) return [];
        
        const bubble = this.getBubble(row, col);
        if (!bubble || bubble.color !== color) return [];
        
        visited.add(key);
        let connected = [{ row, col, bubble }];
        
        // 检查相邻位置
        const neighbors = this.getNeighbors(row, col);
        for (const [nRow, nCol] of neighbors) {
            connected = connected.concat(
                this.findConnectedBubbles(nRow, nCol, color, visited)
            );
        }
        
        return connected;
    }
    
    // 查找最近的空位置
    findNearestEmptyPosition(x, y) {
        const gridPos = this.getGridPosition(x, y);
        let { row, col } = gridPos;
        
        // 确保在有效范围内
        row = Math.max(0, Math.min(this.rows - 1, row));
        col = Math.max(0, Math.min(this.cols - 1, col));
        
        // 如果当前位置为空，直接返回
        if (!this.getBubble(row, col)) {
            return { row, col };
        }
        
        // 向上查找空位置
        for (let r = row; r >= 0; r--) {
            if (!this.getBubble(r, col)) {
                return { row: r, col };
            }
        }
        
        // 如果没找到，返回顶部位置
        return { row: 0, col };
    }
    
    // 检查游戏是否结束（泡泡到达底部）
    isGameOver() {
        const bottomRow = this.rows - 1;
        for (let col = 0; col < this.cols; col++) {
            if (this.getBubble(bottomRow, col)) {
                return true;
            }
        }
        return false;
    }
    
    // 检查是否获胜（没有泡泡）
    isWin() {
        for (let row = 0; row < this.rows; row++) {
            for (let col = 0; col < this.cols; col++) {
                if (this.getBubble(row, col)) {
                    return false;
                }
            }
        }
        return true;
    }
    
    // 获取所有泡泡
    getAllBubbles() {
        const bubbles = [];
        for (let row = 0; row < this.rows; row++) {
            for (let col = 0; col < this.cols; col++) {
                const bubble = this.getBubble(row, col);
                if (bubble) {
                    bubbles.push(bubble);
                }
            }
        }
        return bubbles;
    }
    
    // 渲染网格
    render(ctx) {
        for (let row = 0; row < this.rows; row++) {
            for (let col = 0; col < this.cols; col++) {
                const bubble = this.getBubble(row, col);
                if (bubble) {
                    bubble.render(ctx);
                }
            }
        }
    }
    
    // 更新网格
    update() {
        for (let row = 0; row < this.rows; row++) {
            for (let col = 0; col < this.cols; col++) {
                const bubble = this.getBubble(row, col);
                if (bubble) {
                    bubble.update();
                }
            }
        }
    }
    
    // 清空网格
    clear() {
        this.initGrid();
    }
    
    // 创建初始关卡
    createLevel(levelData) {
        this.clear();
        
        if (levelData && levelData.bubbles) {
            for (let row = 0; row < levelData.bubbles.length; row++) {
                const rowData = levelData.bubbles[row];
                for (let col = 0; col < rowData.length; col++) {
                    const color = rowData[col];
                    if (color) {
                        const pos = this.getPosition(row, col);
                        const bubble = new Bubble(pos.x, pos.y, color);
                        this.addBubble(row, col, bubble);
                    }
                }
            }
        }
    }
    
    // 获取网格边界
    getBounds() {
        return {
            left: this.startX - this.bubbleRadius,
            right: this.startX + this.cols * this.hexOffsetX + this.bubbleRadius,
            top: this.startY - this.bubbleRadius,
            bottom: this.startY + this.rows * this.hexOffsetY + this.bubbleRadius
        };
    }
}
