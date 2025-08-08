// 射击器类
class Shooter {
    constructor(x, y) {
        this.x = x;
        this.y = y;
        this.angle = -Math.PI / 2; // 默认向上
        this.power = 12;
        this.currentBubble = null;
        this.nextBubble = null;
        this.trajectory = [];
        this.colors = ['#FF6B6B', '#FFB347', '#6BCF7F', '#4ECDC4', '#A8E6CF'];
        
        this.generateBubbles();
    }
    
    generateBubbles() {
        this.currentBubble = this.generateRandomBubble();
        this.nextBubble = this.generateRandomBubble();
    }
    
    generateRandomBubble() {
        const color = this.colors[Math.floor(Math.random() * this.colors.length)];
        return new Bubble(this.x, this.y - 30, color, 15);
    }
    
    // 瞄准
    aim(targetX, targetY) {
        this.angle = Math.atan2(targetY - this.y, targetX - this.x);
        
        // 限制角度范围（不能向下射击）
        const minAngle = -Math.PI * 0.8;
        const maxAngle = -Math.PI * 0.2;
        this.angle = Math.max(minAngle, Math.min(maxAngle, this.angle));
        
        // 计算轨迹预览
        this.calculateTrajectory();
    }
    
    // 计算射击轨迹
    calculateTrajectory() {
        this.trajectory = [];
        
        let x = this.x;
        let y = this.y - 30;
        let vx = Math.cos(this.angle) * this.power;
        let vy = Math.sin(this.angle) * this.power;
        
        const maxSteps = 100;
        const stepSize = 1;
        
        for (let i = 0; i < maxSteps; i++) {
            x += vx * stepSize;
            y += vy * stepSize;
            
            // 检查边界反弹
            if (x <= 15 || x >= 785) {
                vx = -vx;
                x = Math.max(15, Math.min(785, x));
            }
            
            // 如果到达顶部或碰到泡泡区域，停止计算
            if (y <= 50) {
                break;
            }
            
            this.trajectory.push({ x, y });
        }
    }
    
    // 发射泡泡
    shoot() {
        if (!this.currentBubble) return null;
        
        const bubble = this.currentBubble;
        bubble.x = this.x;
        bubble.y = this.y - 30;
        bubble.vx = Math.cos(this.angle) * this.power;
        bubble.vy = Math.sin(this.angle) * this.power;
        bubble.state = 'moving';
        
        // 切换到下一个泡泡
        this.currentBubble = this.nextBubble;
        this.nextBubble = this.generateRandomBubble();
        
        // 更新下一个泡泡预览
        this.updateNextBubblePreview();
        
        return bubble;
    }
    
    // 更新下一个泡泡预览
    updateNextBubblePreview() {
        const preview = document.getElementById('next-bubble-preview');
        if (preview && this.nextBubble) {
            preview.style.backgroundColor = this.nextBubble.color;
        }
    }
    
    // 渲染射击器
    render(ctx) {
        ctx.save();
        
        // 渲染射击器底座
        ctx.fillStyle = '#333';
        ctx.fillRect(this.x - 25, this.y - 15, 50, 30);
        
        // 渲染射击器炮管
        ctx.translate(this.x, this.y);
        ctx.rotate(this.angle);
        
        ctx.fillStyle = '#555';
        ctx.fillRect(0, -8, 40, 16);
        
        ctx.restore();
        
        // 渲染当前泡泡
        if (this.currentBubble) {
            this.currentBubble.x = this.x;
            this.currentBubble.y = this.y - 30;
            this.currentBubble.render(ctx);
        }
        
        // 渲染轨迹预览
        this.renderTrajectory(ctx);
    }
    
    // 渲染轨迹预览
    renderTrajectory(ctx) {
        if (this.trajectory.length === 0) return;
        
        ctx.save();
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.5)';
        ctx.lineWidth = 2;
        ctx.setLineDash([5, 5]);
        
        ctx.beginPath();
        ctx.moveTo(this.x, this.y - 30);
        
        for (let i = 0; i < this.trajectory.length; i += 3) {
            const point = this.trajectory[i];
            ctx.lineTo(point.x, point.y);
        }
        
        ctx.stroke();
        ctx.restore();
    }
    
    // 更新射击器
    update() {
        if (this.currentBubble) {
            this.currentBubble.x = this.x;
            this.currentBubble.y = this.y - 30;
        }
    }
    
    // 设置位置
    setPosition(x, y) {
        this.x = x;
        this.y = y;
    }
    
    // 获取当前泡泡颜色
    getCurrentBubbleColor() {
        return this.currentBubble ? this.currentBubble.color : null;
    }
    
    // 获取下一个泡泡颜色
    getNextBubbleColor() {
        return this.nextBubble ? this.nextBubble.color : null;
    }
    
    // 交换当前和下一个泡泡
    swapBubbles() {
        const temp = this.currentBubble;
        this.currentBubble = this.nextBubble;
        this.nextBubble = temp;
        
        this.updateNextBubblePreview();
    }
    
    // 重置射击器
    reset() {
        this.angle = -Math.PI / 2;
        this.trajectory = [];
        this.generateBubbles();
        this.updateNextBubblePreview();
    }
    
    // 检查是否可以射击
    canShoot() {
        return this.currentBubble !== null;
    }
    
    // 获取射击方向向量
    getShootDirection() {
        return {
            x: Math.cos(this.angle),
            y: Math.sin(this.angle)
        };
    }
    
    // 设置可用颜色
    setAvailableColors(colors) {
        this.colors = colors;
        // 重新生成泡泡以使用新颜色
        this.generateBubbles();
    }
}
