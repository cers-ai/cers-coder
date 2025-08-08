// 泡泡类
class Bubble {
    constructor(x, y, color, radius = 20) {
        this.x = x;
        this.y = y;
        this.originalX = x;
        this.originalY = y;
        this.color = color;
        this.radius = radius;
        this.vx = 0;
        this.vy = 0;
        this.state = 'static'; // static, moving, falling, exploding
        this.animationFrame = 0;
        this.glowIntensity = 0;
        this.gridRow = -1;
        this.gridCol = -1;
    }
    
    update() {
        switch (this.state) {
            case 'moving':
                this.x += this.vx;
                this.y += this.vy;
                break;
                
            case 'falling':
                this.vy += 0.5; // 重力加速度
                this.x += this.vx * 0.98; // 空气阻力
                this.y += this.vy;
                
                // 旋转效果
                this.rotation = (this.rotation || 0) + 0.1;
                break;
                
            case 'exploding':
                this.animationFrame++;
                this.glowIntensity = Math.sin(this.animationFrame * 0.3) * 0.5 + 0.5;
                
                if (this.animationFrame > 20) {
                    this.state = 'destroyed';
                }
                break;
                
            case 'static':
                // 轻微的呼吸动画
                this.glowIntensity = Math.sin(Date.now() * 0.002) * 0.1 + 0.1;
                break;
        }
    }
    
    render(ctx) {
        if (this.state === 'destroyed') return;
        
        ctx.save();
        
        // 应用变换
        ctx.translate(this.x, this.y);
        if (this.rotation) {
            ctx.rotate(this.rotation);
        }
        
        // 爆炸效果
        if (this.state === 'exploding') {
            const scale = 1 + (this.animationFrame / 20) * 0.5;
            const alpha = 1 - (this.animationFrame / 20);
            ctx.globalAlpha = alpha;
            ctx.scale(scale, scale);
        }
        
        // 发光效果
        if (this.glowIntensity > 0) {
            ctx.shadowColor = this.color;
            ctx.shadowBlur = this.glowIntensity * 20;
        }
        
        // 绘制主体
        ctx.beginPath();
        ctx.arc(0, 0, this.radius, 0, Math.PI * 2);
        ctx.fillStyle = this.color;
        ctx.fill();
        
        // 绘制高光
        const gradient = ctx.createRadialGradient(-5, -5, 0, -5, -5, this.radius * 0.7);
        gradient.addColorStop(0, 'rgba(255, 255, 255, 0.8)');
        gradient.addColorStop(1, 'rgba(255, 255, 255, 0)');
        
        ctx.beginPath();
        ctx.arc(0, 0, this.radius, 0, Math.PI * 2);
        ctx.fillStyle = gradient;
        ctx.fill();
        
        // 绘制边框
        ctx.beginPath();
        ctx.arc(0, 0, this.radius, 0, Math.PI * 2);
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.3)';
        ctx.lineWidth = 2;
        ctx.stroke();
        
        ctx.restore();
    }
    
    // 检查与另一个泡泡的碰撞
    collidesWith(other) {
        const dx = this.x - other.x;
        const dy = this.y - other.y;
        const distance = Math.sqrt(dx * dx + dy * dy);
        return distance < (this.radius + other.radius);
    }
    
    // 获取距离
    distanceTo(other) {
        const dx = this.x - other.x;
        const dy = this.y - other.y;
        return Math.sqrt(dx * dx + dy * dy);
    }
    
    // 设置网格位置
    setGridPosition(row, col) {
        this.gridRow = row;
        this.gridCol = col;
    }
    
    // 开始爆炸动画
    explode() {
        this.state = 'exploding';
        this.animationFrame = 0;
    }
    
    // 开始掉落
    fall() {
        this.state = 'falling';
        this.vx = (Math.random() - 0.5) * 2;
        this.vy = Math.random() * 2;
    }
    
    // 停止移动并固定位置
    stop() {
        this.state = 'static';
        this.vx = 0;
        this.vy = 0;
    }
    
    // 检查是否在画布边界内
    isInBounds(canvasWidth, canvasHeight) {
        return this.x >= this.radius && 
               this.x <= canvasWidth - this.radius &&
               this.y >= this.radius && 
               this.y <= canvasHeight - this.radius;
    }
    
    // 边界反弹
    bounceOffWalls(canvasWidth, canvasHeight) {
        if (this.x <= this.radius || this.x >= canvasWidth - this.radius) {
            this.vx = -this.vx;
            this.x = Math.max(this.radius, Math.min(canvasWidth - this.radius, this.x));
        }
        
        if (this.y <= this.radius) {
            this.vy = -this.vy;
            this.y = this.radius;
        }
    }
    
    // 克隆泡泡
    clone() {
        const bubble = new Bubble(this.x, this.y, this.color, this.radius);
        bubble.vx = this.vx;
        bubble.vy = this.vy;
        bubble.state = this.state;
        return bubble;
    }
    
    // 获取颜色的RGB值
    getColorRGB() {
        const colors = {
            '#FF6B6B': [255, 107, 107],
            '#FFB347': [255, 179, 71],
            '#FFD93D': [255, 217, 61],
            '#6BCF7F': [107, 207, 127],
            '#4ECDC4': [78, 205, 196],
            '#A8E6CF': [168, 230, 207],
            '#FFB3BA': [255, 179, 186]
        };
        return colors[this.color] || [255, 255, 255];
    }
    
    // 检查是否已销毁
    isDestroyed() {
        return this.state === 'destroyed';
    }
    
    // 检查是否正在移动
    isMoving() {
        return this.state === 'moving';
    }
    
    // 检查是否正在掉落
    isFalling() {
        return this.state === 'falling';
    }
    
    // 检查是否正在爆炸
    isExploding() {
        return this.state === 'exploding';
    }
    
    // 重置泡泡状态
    reset() {
        this.x = this.originalX;
        this.y = this.originalY;
        this.vx = 0;
        this.vy = 0;
        this.state = 'static';
        this.animationFrame = 0;
        this.glowIntensity = 0;
        this.rotation = 0;
    }
}
