"""
CERS Coder 主程序入口
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Optional

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from .agents.pm_agent import PMAgent
from .agents.requirement_agent import RequirementAgent
from .core.file_parser import FileParser
from .core.operation_recorder import OperationRecorder, OperationType
from .core.service_manager import ServiceManager, ServiceLevel, ServiceStatus
from .core.state_manager import StateManager
from .core.workflow import WorkflowController
from .core.workspace_manager import WorkspaceManager
from .llm.model_config import ModelConfigManager
from .llm.ollama_client import OllamaClient
from .utils.logger import setup_logging


class CERSCoder:
    """CERS Coder 主应用类"""

    def __init__(self, work_dir: str = ".", config_dir: str = "./config"):
        self.work_dir = Path(work_dir)
        self.config_dir = Path(config_dir)
        self.console = Console()

        # 服务管理器
        self.service_manager = ServiceManager()

        # 状态
        self.is_running = False
        self.current_workspace_id: Optional[str] = None

    async def initialize(self) -> bool:
        """初始化系统"""
        try:
            # 注册服务
            self._register_services()

            # 启动服务
            success = await self.service_manager.start_all_services()

            if success:
                # 初始化智能体（如果相关服务可用）
                await self._initialize_agents()

            return success

        except Exception as e:
            self.console.print(f"❌ 系统初始化失败: {e}", style="red")
            logging.error(f"系统初始化失败: {e}", exc_info=True)
            return False

    def _register_services(self) -> None:
        """注册系统服务"""
        # 核心服务（必须运行）
        self.service_manager.register_service(
            "workspace_manager",
            ServiceLevel.CORE
        )

        self.service_manager.register_service(
            "state_manager",
            ServiceLevel.ENHANCED  # 改为ENHANCED，因为不是所有功能都需要它
        )

        # 增强服务（可选，但影响功能）
        self.service_manager.register_service(
            "ollama_client",
            ServiceLevel.ENHANCED
        )

        self.service_manager.register_service(
            "model_config_manager",
            ServiceLevel.ENHANCED
            # 移除ollama_client依赖，让它可以独立运行
        )

        self.service_manager.register_service(
            "workflow_controller",
            ServiceLevel.ENHANCED,
            dependencies=["state_manager"]
        )

    async def _initialize_agents(self) -> None:
        """初始化智能体"""
        # 获取服务实例
        state_manager = self.service_manager.get_service("state_manager")
        workflow_controller = self.service_manager.get_service("workflow_controller")
        ollama_client = self.service_manager.get_service("ollama_client")
        model_config_manager = self.service_manager.get_service("model_config_manager")

        # 只有在相关服务可用时才初始化智能体
        if state_manager and workflow_controller:
            # 初始化PM智能体
            pm_agent = PMAgent(state_manager, workflow_controller)
            workflow_controller.register_agent("pm_agent", pm_agent)

            # 如果Ollama可用，检查模型并初始化AI智能体
            if ollama_client and model_config_manager:
                try:
                    # 检查模型状态
                    model_status = await model_config_manager.check_and_suggest_models(ollama_client)

                    if model_status["status"] == "success":
                        if model_status["missing_models"]:
                            self.console.print("⚠️  部分配置的模型不可用:", style="yellow")
                            for model in model_status["missing_models"][:3]:
                                self.console.print(f"  • {model}", style="yellow")
                                # 显示建议
                                if model in model_status["suggestions"]:
                                    suggestions = model_status["suggestions"][model]
                                    self.console.print(f"    💡 建议: {suggestions[0]}", style="cyan")

                            if len(model_status["missing_models"]) > 3:
                                self.console.print(f"  ... 还有 {len(model_status['missing_models']) - 3} 个模型缺失")

                            self.console.print("💡 使用 'cers-coder models --check-missing --suggest' 查看详情")

                        # 如果有可用模型，初始化需求分析智能体
                        if model_status["available_models"]:
                            requirement_agent = RequirementAgent(ollama_client)
                            workflow_controller.register_agent("requirement_agent", requirement_agent)
                            self.console.print(f"✅ AI智能体已初始化 (可用模型: {len(model_status['available_models'])}个)")
                        else:
                            self.console.print("⚠️  没有可用模型，跳过AI智能体初始化", style="yellow")
                            self.console.print("💡 请先下载模型: ollama pull llama3:8b", style="cyan")
                    else:
                        self.console.print(f"⚠️  模型检查失败: {model_status['message']}", style="yellow")

                except Exception as e:
                    self.console.print(f"⚠️  模型检查异常: {e}", style="yellow")
                    # 仍然尝试初始化，但不检查模型
                    requirement_agent = RequirementAgent(ollama_client)
                    workflow_controller.register_agent("requirement_agent", requirement_agent)
            else:
                self.console.print("⚠️  Ollama不可用，跳过AI智能体初始化", style="yellow")
                self.console.print("💡 启动Ollama: ollama serve", style="cyan")

    def get_workspace_manager(self) -> Optional[WorkspaceManager]:
        """获取工作空间管理器"""
        return self.service_manager.get_service("workspace_manager")

    def get_ollama_client(self) -> Optional[OllamaClient]:
        """获取Ollama客户端"""
        return self.service_manager.get_service("ollama_client")

    def is_ai_available(self) -> bool:
        """检查AI功能是否可用"""
        return self.service_manager.is_service_available("ollama_client")

    async def start_project(self, project_name: Optional[str] = None) -> bool:
        """启动新项目"""
        try:
            workspace_manager = self.get_workspace_manager()

            # 初始化操作记录器
            if workspace_manager and workspace_manager.get_current_workspace():
                workspace_path = workspace_manager.get_current_workspace_path()
                operation_recorder = OperationRecorder(
                    workspace_dir=str(workspace_path),
                    project_id=self.current_workspace_id
                )

                # 记录项目启动操作
                await operation_recorder.start_operation(
                    operation_type=OperationType.PROJECT_CREATE,
                    actor="system",
                    title="启动项目开发",
                    description=f"在工作空间中启动项目: {project_name or '未命名项目'}",
                    input_data={"project_name": project_name, "workspace_id": self.current_workspace_id}
                )

            self.console.print(Panel.fit("📋 开始项目开发流程", style="bold cyan"))

            # 确定工作目录
            if workspace_manager and workspace_manager.get_current_workspace():
                work_dir = workspace_manager.get_input_dir()
                self.console.print(f"📁 工作空间: {workspace_manager.get_current_workspace().name}")
            else:
                work_dir = self.work_dir
                self.console.print(f"📁 工作目录: {work_dir}")

            # 检查输入文件
            file_parser = FileParser(str(work_dir))
            try:
                parsed_files, missing_files = await file_parser.parse_all_files()
                self.console.print(f"DEBUG: 解析完成，文件数: {len(parsed_files)}")
            except Exception as e:
                self.console.print(f"DEBUG: 解析文件时出错: {e}")
                self.console.print(f"DEBUG: 工作目录: {work_dir}")
                raise

            if missing_files:
                self.console.print("❌ 缺少必需的输入文件:", style="red")
                for file in missing_files:
                    self.console.print(f"  - {file}", style="red")
                return False

            # 显示项目信息
            await self._display_project_info(parsed_files)

            # 确认开始
            if not click.confirm("是否开始项目开发？"):
                self.console.print("项目开发已取消", style="yellow")
                return False
            
            # 启动工作流（如果可用）
            workflow_controller = self.service_manager.get_service("workflow_controller")
            if workflow_controller:
                await workflow_controller.start_workflow()
            else:
                self.console.print("⚠️  工作流控制器不可用，跳过工作流启动", style="yellow")

            # 启动智能体（如果可用）
            # 在降级模式下，我们可以手动创建基础的项目结构
            if not self.is_ai_available():
                self.console.print("🔧 AI不可用，创建基础项目结构...", style="cyan")
                await self._create_basic_project_structure(parsed_files)
            else:
                # 正常的AI辅助开发流程
                pass
            await self.requirement_agent.start()
            
            # 发送项目初始化任务给PM智能体
            from .core.message import create_task_message
            init_message = create_task_message(
                sender="main",
                task_id="init_project",
                task_name="项目初始化",
                subject="初始化项目",
                content={
                    "task_type": "initialize_project",
                    "project_name": project_name,
                    "work_dir": str(self.work_dir)
                }
            )
            await self.pm_agent.send_message(init_message)
            
            self.is_running = True
            self.console.print("🚀 项目开发已启动！", style="bold green")
            
            # 监控进度
            await self._monitor_progress()
            
            return True

        except Exception as e:
            self.console.print(f"❌ 启动项目失败: {e}", style="red")
            logging.error(f"启动项目失败: {e}", exc_info=True)
            return False

    async def _create_basic_project_structure(self, parsed_files):
        """在AI不可用时创建基础项目结构"""
        try:
            workspace_manager = self.get_workspace_manager()
            if not workspace_manager:
                self.console.print("❌ 工作空间管理器不可用", style="red")
                return

            output_dir = workspace_manager.get_output_dir()

            # 创建基础目录结构
            directories = [
                "src",
                "src/css",
                "src/js",
                "src/js/game",
                "src/js/ui",
                "src/js/audio",
                "src/assets",
                "src/assets/images",
                "src/assets/sounds",
                "src/assets/data",
                "test",
                "docs",
                "build"
            ]

            for dir_name in directories:
                dir_path = output_dir / dir_name
                dir_path.mkdir(parents=True, exist_ok=True)
                self.console.print(f"📁 创建目录: {dir_name}")

            # 创建基础HTML文件
            html_content = self._generate_basic_html()
            (output_dir / "src" / "index.html").write_text(html_content, encoding='utf-8')
            self.console.print("📄 创建文件: src/index.html")

            # 创建基础CSS文件
            css_content = self._generate_basic_css()
            (output_dir / "src" / "css" / "main.css").write_text(css_content, encoding='utf-8')
            self.console.print("📄 创建文件: src/css/main.css")

            # 创建基础JavaScript文件
            js_content = self._generate_basic_js()
            (output_dir / "src" / "js" / "main.js").write_text(js_content, encoding='utf-8')
            self.console.print("📄 创建文件: src/js/main.js")

            # 创建README文件
            readme_content = self._generate_readme(parsed_files)
            (output_dir / "README.md").write_text(readme_content, encoding='utf-8')
            self.console.print("📄 创建文件: README.md")

            self.console.print("✅ 基础项目结构创建完成！", style="green")
            self.console.print(f"📁 项目位置: {output_dir}")
            self.console.print("💡 你可以在此基础上继续开发游戏")

        except Exception as e:
            self.console.print(f"❌ 创建项目结构失败: {e}", style="red")
            logging.error(f"创建项目结构失败: {e}", exc_info=True)

    def _generate_basic_html(self):
        """生成基础HTML文件"""
        return '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>泡泡射击游戏</title>
    <link rel="stylesheet" href="css/main.css">
</head>
<body>
    <div class="game-container">
        <!-- 主菜单 -->
        <div id="main-menu" class="menu-screen">
            <h1 class="game-title">🫧 泡泡射击</h1>
            <div class="menu-buttons">
                <button class="btn btn-primary" id="start-game">开始游戏</button>
                <button class="btn btn-secondary" id="settings">设置</button>
                <button class="btn btn-secondary" id="help">帮助</button>
            </div>
            <div class="high-score">
                <p>最高分: <span id="high-score-value">0</span></p>
            </div>
        </div>

        <!-- 游戏界面 -->
        <div id="game-screen" class="game-screen hidden">
            <div class="game-header">
                <div class="score-info">
                    <span>分数: <span id="current-score">0</span></span>
                    <span>关卡: <span id="current-level">1</span></span>
                </div>
                <div class="game-controls">
                    <button class="btn btn-small" id="pause-btn">⏸️</button>
                    <button class="btn btn-small" id="restart-btn">🔄</button>
                </div>
            </div>

            <canvas id="game-canvas" width="800" height="600"></canvas>

            <div class="game-footer">
                <div class="next-bubble">
                    <span>下一个:</span>
                    <div id="next-bubble-preview"></div>
                </div>
            </div>
        </div>
    </div>

    <script src="js/main.js"></script>
</body>
</html>'''

    def _generate_basic_css(self):
        """生成基础CSS文件"""
        return '''/* 泡泡射击游戏样式 */
:root {
    --primary-color: #667eea;
    --secondary-color: #764ba2;
    --accent-color: #ff6b6b;
    --text-color: #333;
    --bg-gradient: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
}

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: 'Arial', sans-serif;
    background: var(--bg-gradient);
    min-height: 100vh;
    display: flex;
    justify-content: center;
    align-items: center;
}

.game-container {
    width: 100%;
    max-width: 900px;
    margin: 0 auto;
    padding: 20px;
}

.menu-screen {
    background: rgba(255, 255, 255, 0.95);
    border-radius: 20px;
    padding: 40px;
    text-align: center;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
}

.game-title {
    font-size: 3rem;
    color: var(--primary-color);
    margin-bottom: 30px;
    text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.1);
}

.menu-buttons {
    margin: 20px 0;
}

.btn {
    padding: 12px 24px;
    border: none;
    border-radius: 25px;
    font-size: 1.1rem;
    cursor: pointer;
    transition: all 0.3s ease;
    margin: 8px;
    min-width: 150px;
}

.btn-primary {
    background: var(--accent-color);
    color: white;
}

.btn-primary:hover {
    background: #ff5252;
    transform: translateY(-2px);
    box-shadow: 0 5px 15px rgba(255, 107, 107, 0.4);
}

.btn-secondary {
    background: var(--primary-color);
    color: white;
}

.btn-secondary:hover {
    background: #5a6fd8;
    transform: translateY(-2px);
}

.btn-small {
    padding: 8px 16px;
    font-size: 0.9rem;
    min-width: auto;
}

.game-screen {
    background: rgba(255, 255, 255, 0.95);
    border-radius: 20px;
    padding: 20px;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
}

.game-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
    padding: 10px;
    background: rgba(102, 126, 234, 0.1);
    border-radius: 10px;
}

.score-info span {
    margin-right: 20px;
    font-weight: bold;
    color: var(--text-color);
}

#game-canvas {
    border: 3px solid var(--primary-color);
    border-radius: 10px;
    background: linear-gradient(to bottom, #87ceeb, #e0f6ff);
    display: block;
    margin: 0 auto;
    cursor: crosshair;
}

.game-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 20px;
    padding: 10px;
}

.next-bubble {
    display: flex;
    align-items: center;
    gap: 10px;
}

#next-bubble-preview {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    background: #ff6b6b;
    border: 2px solid white;
    box-shadow: 0 2px 5px rgba(0, 0, 0, 0.2);
}

.hidden {
    display: none;
}

.high-score {
    margin-top: 20px;
    font-size: 1.2rem;
    color: var(--text-color);
}

/* 响应式设计 */
@media (max-width: 768px) {
    .game-container {
        padding: 10px;
    }

    .game-title {
        font-size: 2rem;
    }

    .btn {
        min-width: 120px;
        font-size: 1rem;
    }

    #game-canvas {
        width: 100%;
        height: auto;
    }

    .game-header {
        flex-direction: column;
        gap: 10px;
    }
}'''

    def _generate_basic_js(self):
        """生成基础JavaScript文件"""
        return '''// 泡泡射击游戏主文件
class BubbleGame {
    constructor() {
        this.canvas = document.getElementById('game-canvas');
        this.ctx = this.canvas.getContext('2d');
        this.gameState = 'menu'; // menu, playing, paused, gameover
        this.score = 0;
        this.level = 1;
        this.highScore = localStorage.getItem('bubbleGameHighScore') || 0;

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
        // 初始化关卡 - 这里是基础实现
        this.bubbles = [];
        this.createInitialBubbles();
    }

    createInitialBubbles() {
        // 创建初始泡泡布局
        const colors = ['#FF6B6B', '#FFB347', '#6BCF7F', '#4ECDC4', '#A8E6CF'];
        const rows = 5;
        const cols = 8;

        for (let row = 0; row < rows; row++) {
            for (let col = 0; col < cols; col++) {
                if (Math.random() > 0.3) { // 70%概率放置泡泡
                    const x = col * 50 + (row % 2) * 25 + 50;
                    const y = row * 43 + 50;
                    const color = colors[Math.floor(Math.random() * colors.length)];

                    this.bubbles.push({
                        x: x,
                        y: y,
                        color: color,
                        radius: 20
                    });
                }
            }
        }
    }

    handleClick(e) {
        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        // 简单的点击射击实现
        this.shootAt(x, y);
    }

    shootAt(targetX, targetY) {
        // 基础射击逻辑
        console.log(`射击目标: (${targetX}, ${targetY})`);
        // TODO: 实现完整的射击逻辑
    }

    shoot() {
        // 空格键射击
        console.log('射击!');
        // TODO: 实现射击逻辑
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

        // 游戏逻辑更新
        // TODO: 实现完整的游戏逻辑
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

        // 渲染泡泡
        this.renderBubbles();

        // 渲染射击器
        this.renderShooter();
    }

    renderBubbles() {
        for (const bubble of this.bubbles) {
            this.ctx.save();

            // 绘制泡泡主体
            this.ctx.beginPath();
            this.ctx.arc(bubble.x, bubble.y, bubble.radius, 0, Math.PI * 2);
            this.ctx.fillStyle = bubble.color;
            this.ctx.fill();

            // 绘制高光
            this.ctx.beginPath();
            this.ctx.arc(bubble.x - 5, bubble.y - 5, bubble.radius * 0.3, 0, Math.PI * 2);
            this.ctx.fillStyle = 'rgba(255, 255, 255, 0.6)';
            this.ctx.fill();

            // 绘制边框
            this.ctx.beginPath();
            this.ctx.arc(bubble.x, bubble.y, bubble.radius, 0, Math.PI * 2);
            this.ctx.strokeStyle = 'rgba(255, 255, 255, 0.8)';
            this.ctx.lineWidth = 2;
            this.ctx.stroke();

            this.ctx.restore();
        }
    }

    renderShooter() {
        // 渲染射击器
        const shooterX = this.canvas.width / 2;
        const shooterY = this.canvas.height - 30;

        this.ctx.save();
        this.ctx.fillStyle = '#333';
        this.ctx.fillRect(shooterX - 20, shooterY - 10, 40, 20);

        // 渲染当前泡泡
        this.ctx.beginPath();
        this.ctx.arc(shooterX, shooterY - 20, 15, 0, Math.PI * 2);
        this.ctx.fillStyle = '#FF6B6B';
        this.ctx.fill();
        this.ctx.strokeStyle = 'white';
        this.ctx.lineWidth = 2;
        this.ctx.stroke();

        this.ctx.restore();
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
});'''

    def _generate_readme(self, parsed_files):
        """生成README文件"""
        project_name = "泡泡射击游戏"

        # 从需求文件中提取项目信息
        request_content = ""
        if parsed_files and 'request' in parsed_files:
            request_content = parsed_files['request'].content[:500] + "..."

        return f'''# {project_name}

## 项目简介

{request_content}

## 项目结构

```
src/
├── index.html          # 主页面
├── css/
│   └── main.css        # 主样式文件
├── js/
│   └── main.js         # 主JavaScript文件
├── assets/
│   ├── images/         # 图片资源
│   ├── sounds/         # 音效文件
│   └── data/           # 关卡数据
test/                   # 测试文件
docs/                   # 文档
build/                  # 构建文件
```

## 快速开始

1. 打开 `src/index.html` 文件
2. 在浏览器中运行游戏
3. 点击"开始游戏"按钮开始游戏

## 游戏特性

- 🎮 经典泡泡射击玩法
- 🎨 现代化界面设计
- 📱 响应式设计，支持移动设备
- 🔊 音效支持（待实现）
- 🏆 分数系统和最高分记录

## 开发状态

这是一个基础版本，包含了：
- ✅ 基础界面和菜单
- ✅ 游戏画布和渲染系统
- ✅ 基础的泡泡显示
- ⏳ 射击逻辑（待完善）
- ⏳ 碰撞检测（待实现）
- ⏳ 消除算法（待实现）
- ⏳ 音效系统（待实现）

## 技术栈

- HTML5 Canvas
- CSS3
- JavaScript (ES6+)
- 本地存储 (localStorage)

## 开发计划

1. **第一阶段**: 完善射击和碰撞检测
2. **第二阶段**: 实现泡泡消除逻辑
3. **第三阶段**: 添加音效和特效
4. **第四阶段**: 关卡系统和难度调节
5. **第五阶段**: 性能优化和测试

## 贡献

欢迎提交 Issue 和 Pull Request！

## 许可证

MIT License

---

*此项目由 CERS Coder 智能体系统生成*'''

    async def _display_project_info(self, parsed_files) -> None:
        """显示项目信息"""
        table = Table(title="📁 项目文件信息")
        table.add_column("文件名", style="cyan")
        table.add_column("状态", style="green")
        table.add_column("大小", style="yellow")

        try:
            for filename, content in parsed_files.items():
                status = "✅ 存在" if content.exists else "❌ 缺失"
                if content.exists and hasattr(content, 'content'):
                    if isinstance(content.content, str):
                        size = f"{len(content.content)} 字符"
                    else:
                        # 调试信息
                        self.console.print(f"DEBUG: content.content type: {type(content.content)}")
                        self.console.print(f"DEBUG: content.content value: {content.content}")
                        size = f"类型错误: {type(content.content)}"
                else:
                    size = "0"
                table.add_row(filename, status, size)
        except Exception as e:
            self.console.print(f"DEBUG: 显示项目信息时出错: {e}")
            self.console.print(f"DEBUG: parsed_files type: {type(parsed_files)}")
            self.console.print(f"DEBUG: parsed_files keys: {list(parsed_files.keys()) if hasattr(parsed_files, 'keys') else 'No keys'}")
            raise

        self.console.print(table)

    async def _monitor_progress(self) -> None:
        """监控项目进度"""
        self.console.print("\n📊 开始监控项目进度...")
        
        try:
            while self.is_running:
                # 获取工作流状态
                status = self.workflow_controller.get_workflow_status()
                
                # 显示进度
                progress_bar = f"进度: {status['progress']:.1f}% "
                progress_bar += f"({status['completed_tasks']}/{status['total_tasks']} 任务完成)"
                
                self.console.print(f"\r{progress_bar}", end="")
                
                # 检查是否完成
                if status['progress'] >= 100:
                    self.console.print("\n🎉 项目开发完成！", style="bold green")
                    break
                
                # 检查是否有失败任务
                if status['failed_tasks'] > 0:
                    self.console.print(f"\n⚠️  有 {status['failed_tasks']} 个任务失败", style="yellow")
                
                await asyncio.sleep(5)  # 每5秒更新一次
                
        except KeyboardInterrupt:
            self.console.print("\n⏸️  用户中断，正在停止...", style="yellow")
            await self.stop()

    async def stop(self) -> None:
        """停止系统"""
        self.console.print("🛑 正在停止系统...")
        
        self.is_running = False
        
        # 停止工作流
        if self.workflow_controller:
            await self.workflow_controller.stop_workflow()
        
        # 停止智能体
        if self.pm_agent:
            await self.pm_agent.stop()
        if self.requirement_agent:
            await self.requirement_agent.stop()
        
        # 关闭Ollama客户端
        if self.ollama_client:
            await self.ollama_client.close()
        
        self.console.print("✅ 系统已停止", style="green")

    async def resume_project(self, project_id: str) -> bool:
        """恢复项目"""
        try:
            self.console.print(f"🔄 恢复项目: {project_id}")
            
            # 加载项目状态
            project_state = await self.state_manager.load_project(project_id)
            if not project_state:
                self.console.print("❌ 项目状态不存在", style="red")
                return False
            
            self.console.print(f"✅ 项目状态已加载: {project_state.name}")
            
            # 启动工作流
            await self.workflow_controller.start_workflow()
            
            # 启动智能体
            await self.pm_agent.start()
            await self.requirement_agent.start()
            
            self.is_running = True
            
            # 监控进度
            await self._monitor_progress()
            
            return True
            
        except Exception as e:
            self.console.print(f"❌ 恢复项目失败: {e}", style="red")
            logging.error(f"恢复项目失败: {e}", exc_info=True)
            return False

    async def list_projects(self) -> None:
        """列出所有项目"""
        projects = await self.state_manager.list_projects()
        
        if not projects:
            self.console.print("📭 没有找到任何项目", style="yellow")
            return
        
        table = Table(title="📋 项目列表")
        table.add_column("ID", style="cyan")
        table.add_column("名称", style="green")
        table.add_column("状态", style="yellow")
        table.add_column("进度", style="blue")
        table.add_column("更新时间", style="magenta")
        
        for project in projects:
            table.add_row(
                project["id"][:8] + "...",
                project["name"],
                project["status"],
                f"{project['progress']:.1f}%",
                project["updated_at"][:19]
            )
        
        self.console.print(table)


# CLI命令
@click.group()
@click.option('--work-dir', default='.', help='工作目录')
@click.option('--verbose', is_flag=True, help='详细输出')
@click.option('--log-level', default='INFO', help='日志级别')
@click.pass_context
def cli(ctx, work_dir, verbose, log_level):
    """CERS Coder - 极简智能开发代理系统"""
    # 加载环境变量
    load_dotenv()
    
    # 设置日志
    setup_logging(level=log_level, verbose=verbose)
    
    # 创建应用实例
    ctx.ensure_object(dict)
    ctx.obj['app'] = CERSCoder(work_dir=work_dir)


@cli.command()
@click.option('--project-name', help='项目名称')
@click.option('--workspace-id', help='指定工作空间ID')
@click.option('--create-workspace', is_flag=True, help='自动创建工作空间')
@click.pass_context
def start(ctx, project_name, workspace_id, create_workspace):
    """启动项目开发"""
    app = ctx.obj['app']

    async def run():
        if await app.initialize():
            # 处理工作空间
            workspace_manager = app.get_workspace_manager()
            if workspace_id:
                # 加载指定的工作空间
                if not workspace_manager:
                    app.console.print("❌ 工作空间管理器不可用", style="red")
                    return
                workspace = await workspace_manager.load_workspace(workspace_id)
                if not workspace:
                    app.console.print(f"❌ 工作空间不存在: {workspace_id}", style="red")
                    return
                app.current_workspace_id = workspace_id
            elif create_workspace:
                # 创建新的工作空间
                if not workspace_manager:
                    app.console.print("❌ 工作空间管理器不可用", style="red")
                    return
                workspace_name = project_name or "新项目"
                workspace = await workspace_manager.create_workspace(
                    name=workspace_name,
                    description=f"自动创建的工作空间: {workspace_name}"
                )
                app.current_workspace_id = workspace.id
                app.console.print(f"✅ 已创建工作空间: {workspace_name}")
            else:
                # 检查当前目录是否有输入文件，如果没有则提示创建工作空间
                input_files = list(Path(".").glob("*.request.md")) + list(Path(".").glob("0.request.md"))
                if not input_files:
                    app.console.print("❌ 当前目录没有找到输入文件", style="red")
                    app.console.print("💡 建议使用以下方式之一：", style="yellow")
                    app.console.print("   1. cers-coder start --create-workspace --project-name '项目名称'")
                    app.console.print("   2. cers-coder workspace create '项目名称'")
                    app.console.print("   3. 在当前目录创建 0.request.md 文件")
                    return

            await app.start_project(project_name)

    asyncio.run(run())


@cli.command()
@click.argument('project_id')
@click.pass_context
def resume(ctx, project_id):
    """恢复项目开发"""
    app = ctx.obj['app']
    
    async def run():
        if await app.initialize():
            await app.resume_project(project_id)
    
    asyncio.run(run())


@cli.command()
@click.pass_context
def list(ctx):
    """列出所有项目"""
    app = ctx.obj['app']
    
    async def run():
        if await app.initialize():
            await app.list_projects()
    
    asyncio.run(run())


@cli.command()
@click.pass_context
def status(ctx):
    """显示系统状态"""
    app = ctx.obj['app']
    console = Console()

    async def run():
        if await app.initialize():
            # 获取系统健康状态
            health_info = await app.service_manager.health_check()

            console.print(Panel.fit("🔍 系统状态", style="bold blue"))
            console.print(f"系统状态: {health_info['system_status']}")

            # 获取工作空间信息
            workspace_manager = app.get_workspace_manager()
            if workspace_manager:
                workspaces = await workspace_manager.list_workspaces()
                current_workspace = workspace_manager.get_current_workspace()
                console.print(f"工作空间数量: {len(workspaces)} 个")

                if current_workspace:
                    console.print(f"当前工作空间: {current_workspace.name}")

            # 获取Ollama和模型信息
            ollama_client = app.get_ollama_client()
            model_config_manager = app.service_manager.get_service("model_config_manager")

            if ollama_client and model_config_manager:
                try:
                    models = await ollama_client.list_models()
                    console.print(f"可用模型: {len(models)} 个")

                    # 检查模型状态
                    model_status = await model_config_manager.check_and_suggest_models(ollama_client)
                    if model_status["status"] == "success" and model_status["missing_models"]:
                        console.print(f"缺失模型: {len(model_status['missing_models'])} 个", style="yellow")

                    if models:
                        table = Table(title="📦 可用模型")
                        table.add_column("模型名称", style="cyan")
                        table.add_column("大小", style="yellow")
                        table.add_column("状态", style="green")

                        for model in models[:5]:  # 只显示前5个
                            size_gb = model.size / (1024**3)
                            # 检查是否是配置的模型
                            status = "✅ 已配置" if model.name in [m for mapping in model_config_manager.agent_mappings.values()
                                                                for m in [mapping.primary_model] + mapping.fallback_models] else "📦 可用"
                            table.add_row(model.name, f"{size_gb:.1f} GB", status)

                        console.print(table)

                        if len(models) > 5:
                            console.print(f"... 还有 {len(models) - 5} 个模型")

                except Exception as e:
                    console.print(f"获取模型信息失败: {e}", style="red")
            elif ollama_client:
                console.print("模型配置管理器不可用", style="yellow")
            else:
                console.print("Ollama服务不可用", style="yellow")
                console.print("💡 启动命令: ollama serve", style="cyan")

            # 显示建议
            if health_info.get('recommendations'):
                console.print("\n💡 建议:")
                for rec in health_info['recommendations']:
                    console.print(f"  • {rec}", style="yellow")

    asyncio.run(run())


@cli.group()
def workspace():
    """工作空间管理命令"""
    pass


@workspace.command()
@click.argument('name')
@click.option('--description', default='', help='工作空间描述')
@click.option('--type', 'project_type', default='general', help='项目类型')
@click.option('--template', help='使用模板')
@click.pass_context
def create(ctx, name, description, project_type, template):
    """创建新的工作空间"""
    app = ctx.obj['app']

    async def run():
        if await app.initialize():
            workspace_manager = app.get_workspace_manager()
            if workspace_manager:
                workspace = await workspace_manager.create_workspace(
                    name=name,
                    description=description,
                    project_type=project_type,
                    template=template
                )

                app.console.print(f"✅ 工作空间创建成功: {name}")
                app.console.print(f"📁 路径: {workspace.workspace_path}")
                app.console.print(f"🆔 ID: {workspace.id}")
            else:
                app.console.print("❌ 工作空间管理器不可用", style="red")

    asyncio.run(run())


@workspace.command()
@click.pass_context
def list(ctx):
    """列出所有工作空间"""
    app = ctx.obj['app']

    async def run():
        if await app.initialize():
            workspace_manager = app.get_workspace_manager()
            if not workspace_manager:
                app.console.print("❌ 工作空间管理器不可用", style="red")
                return

            workspaces = await workspace_manager.list_workspaces()

            if not workspaces:
                app.console.print("📭 没有找到任何工作空间", style="yellow")
                return

            table = Table(title="📋 工作空间列表")
            table.add_column("名称", style="green")
            table.add_column("ID", style="cyan")
            table.add_column("类型", style="blue")
            table.add_column("创建时间", style="magenta")
            table.add_column("最后访问", style="yellow")

            for workspace in workspaces:
                table.add_row(
                    workspace["name"],
                    workspace["id"][:8] + "...",
                    workspace["project_type"],
                    workspace["created_at"][:19],
                    workspace["last_accessed"][:19]
                )

            app.console.print(table)

    asyncio.run(run())


@workspace.command()
@click.argument('workspace_id')
@click.pass_context
def switch(ctx, workspace_id):
    """切换到指定工作空间"""
    app = ctx.obj['app']

    async def run():
        if await app.initialize():
            workspace_manager = app.get_workspace_manager()
            if not workspace_manager:
                app.console.print("❌ 工作空间管理器不可用", style="red")
                return

            workspace = await workspace_manager.load_workspace(workspace_id)

            if workspace:
                app.current_workspace_id = workspace_id
                app.console.print(f"✅ 已切换到工作空间: {workspace.name}")
                app.console.print(f"📁 路径: {workspace.workspace_path}")
            else:
                app.console.print(f"❌ 工作空间不存在: {workspace_id}", style="red")

    asyncio.run(run())


@workspace.command()
@click.argument('workspace_id')
@click.option('--force', is_flag=True, help='强制删除，不创建备份')
@click.pass_context
def delete(ctx, workspace_id, force):
    """删除工作空间"""
    app = ctx.obj['app']

    async def run():
        if await app.initialize():
            workspace_manager = app.get_workspace_manager()
            if not workspace_manager:
                app.console.print("❌ 工作空间管理器不可用", style="red")
                return

            # 确认删除
            workspaces = await workspace_manager.list_workspaces()
            workspace_info = next((w for w in workspaces if w["id"] == workspace_id), None)

            if not workspace_info:
                app.console.print(f"❌ 工作空间不存在: {workspace_id}", style="red")
                return

            if not click.confirm(f"确定要删除工作空间 '{workspace_info['name']}' 吗？"):
                app.console.print("取消删除", style="yellow")
                return

            success = await workspace_manager.delete_workspace(workspace_id, force)

            if success:
                app.console.print(f"✅ 工作空间已删除: {workspace_info['name']}")
                if not force:
                    app.console.print("💾 已创建备份")
            else:
                app.console.print("❌ 删除失败", style="red")

    asyncio.run(run())


@cli.group()
def records():
    """操作记录管理命令"""
    pass


@records.command()
@click.option('--workspace-id', help='指定工作空间ID')
@click.option('--agent', help='指定智能体名称')
@click.option('--limit', default=50, help='显示记录数量限制')
@click.pass_context
def show(ctx, workspace_id, agent, limit):
    """显示操作记录"""
    app = ctx.obj['app']

    async def run():
        if await app.initialize():
            # 确定工作空间
            if workspace_id:
                workspace = await app.workspace_manager.load_workspace(workspace_id)
                if not workspace:
                    app.console.print(f"❌ 工作空间不存在: {workspace_id}", style="red")
                    return
            elif not app.workspace_manager.get_current_workspace():
                app.console.print("❌ 请指定工作空间ID或切换到工作空间", style="red")
                return

            # 获取操作记录
            workspace_path = app.workspace_manager.get_current_workspace_path()
            recorder = OperationRecorder(str(workspace_path), workspace_id or app.current_workspace_id)

            if agent:
                records_list = await recorder.get_agent_records(agent, workspace_id or app.current_workspace_id)
            else:
                records_list = await recorder.get_session_records()

            if not records_list:
                app.console.print("📭 没有找到操作记录", style="yellow")
                return

            # 限制显示数量
            records_list = records_list[-limit:]

            # 显示记录
            table = Table(title="📋 操作记录")
            table.add_column("时间", style="cyan")
            table.add_column("操作者", style="green")
            table.add_column("操作类型", style="blue")
            table.add_column("标题", style="yellow")
            table.add_column("状态", style="magenta")
            table.add_column("耗时", style="red")

            for record in records_list:
                status_icon = "✅" if record.success else "❌"
                duration = f"{record.duration:.2f}s" if record.duration else "N/A"

                table.add_row(
                    record.start_time.strftime("%H:%M:%S"),
                    record.actor,
                    record.operation_type.value,
                    record.title[:30] + "..." if len(record.title) > 30 else record.title,
                    f"{status_icon} {record.status.value}",
                    duration
                )

            app.console.print(table)

            # 显示统计信息
            stats = recorder.get_operation_stats(records_list)
            if stats:
                app.console.print(f"\n📊 统计信息:")
                app.console.print(f"总操作数: {stats['total_operations']}")
                app.console.print(f"成功率: {stats['success_rate']:.1%}")
                app.console.print(f"平均耗时: {stats['average_duration']:.2f}s")

    asyncio.run(run())


@records.command('export')
@click.option('--workspace-id', help='指定工作空间ID')
@click.option('--output', help='输出文件路径')
@click.pass_context
def export_records(ctx, workspace_id, output):
    """导出操作记录"""
    app = ctx.obj['app']

    async def run():
        if await app.initialize():
            # 确定工作空间
            if workspace_id:
                workspace = await app.workspace_manager.load_workspace(workspace_id)
                if not workspace:
                    app.console.print(f"❌ 工作空间不存在: {workspace_id}", style="red")
                    return
            elif not app.workspace_manager.get_current_workspace():
                app.console.print("❌ 请指定工作空间ID或切换到工作空间", style="red")
                return

            # 生成输出文件名
            if not output:
                workspace_manager = app.get_workspace_manager()
                if workspace_manager and workspace_manager.get_current_workspace():
                    workspace_name = workspace_manager.get_current_workspace().name
                else:
                    workspace_name = "unknown"
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output = f"records_{workspace_name}_{timestamp}.json"

            # 导出记录
            workspace_path = app.workspace_manager.get_current_workspace_path()
            recorder = OperationRecorder(str(workspace_path), workspace_id or app.current_workspace_id)

            await recorder.export_records(output, workspace_id or app.current_workspace_id)

            app.console.print(f"✅ 操作记录已导出到: {output}")

    asyncio.run(run())


@cli.command()
@click.pass_context
def diagnose(ctx):
    """系统诊断和修复建议"""
    app = ctx.obj['app']

    async def run():
        app.console.print(Panel.fit("🔧 系统诊断", style="bold blue"))

        if await app.initialize():
            try:
                health_info = await app.service_manager.health_check()
            except Exception as e:
                app.console.print(f"❌ 获取健康信息失败: {e}", style="red")
                return

            # 显示详细的服务状态
            table = Table(title="📋 服务诊断报告")
            table.add_column("服务", style="cyan")
            table.add_column("状态", style="green")
            table.add_column("级别", style="blue")
            table.add_column("问题", style="red")
            table.add_column("建议", style="yellow")

            services = health_info.get('services', {})
            if not services:
                app.console.print("❌ 无法获取服务信息", style="red")
                return

            for service_name, service_info in services.items():
                status = service_info['status']
                level = service_info['level']
                error = service_info.get('error', '')

                # 生成修复建议
                suggestion = ""
                if status == "failed":
                    if service_name == "ollama_client":
                        suggestion = "启动Ollama服务: ollama serve"
                    elif service_name == "workspace_manager":
                        suggestion = "检查目录权限"
                    else:
                        suggestion = "检查配置和依赖"
                elif status == "degraded":
                    suggestion = "检查依赖服务"
                else:
                    suggestion = "正常"

                status_icon = {
                    "running": "✅ 正常",
                    "degraded": "⚠️  降级",
                    "failed": "❌ 失败",
                    "stopped": "⏹️  停止"
                }.get(status, "❓ 未知")

                table.add_row(
                    service_name,
                    status_icon,
                    level,
                    error[:30] + "..." if len(error) > 30 else error,
                    suggestion
                )

            app.console.print(table)

            # 显示系统建议
            if health_info.get('recommendations'):
                app.console.print("\n🔧 修复建议:")
                for i, rec in enumerate(health_info['recommendations'], 1):
                    app.console.print(f"  {i}. {rec}")

            # 显示系统信息
            app.console.print(f"\n📊 系统信息:")
            app.console.print(f"  • 系统状态: {health_info['system_status']}")
            app.console.print(f"  • AI功能: {'可用' if app.is_ai_available() else '不可用'}")

            workspace_manager = app.get_workspace_manager()
            if workspace_manager:
                try:
                    workspaces = await workspace_manager.list_workspaces()
                    app.console.print(f"  • 工作空间: {len(workspaces)} 个")
                except Exception as e:
                    app.console.print(f"  • 工作空间: 获取失败 ({e})")
            else:
                app.console.print(f"  • 工作空间: 管理器不可用")
        else:
            app.console.print("❌ 系统初始化失败，无法进行诊断", style="red")

    asyncio.run(run())


@cli.command()
@click.option('--check-missing', is_flag=True, help='检查缺失的模型')
@click.option('--suggest', is_flag=True, help='提供模型建议')
@click.pass_context
def models(ctx, check_missing, suggest):
    """模型管理和检查"""
    app = ctx.obj['app']

    async def run():
        if await app.initialize():
            ollama_client = app.get_ollama_client()
            model_config_manager = app.service_manager.get_service("model_config_manager")

            if not model_config_manager:
                app.console.print("❌ 模型配置管理器不可用", style="red")
                return

            app.console.print(Panel.fit("🤖 模型状态检查", style="bold blue"))

            if not ollama_client:
                app.console.print("⚠️  Ollama服务不可用，无法检查模型状态", style="yellow")
                app.console.print("\n💡 启动Ollama服务:")
                app.console.print("   ollama serve")
                return

            # 检查模型状态
            model_status = await model_config_manager.check_and_suggest_models(ollama_client)

            if model_status["status"] == "error":
                app.console.print(f"❌ {model_status['message']}", style="red")
                return

            # 显示基本信息
            app.console.print(f"📊 模型统计:")
            app.console.print(f"  • 已配置模型: {model_status['total_configured']} 个")
            app.console.print(f"  • 可用模型: {model_status['total_available']} 个")
            app.console.print(f"  • 缺失模型: {len(model_status['missing_models'])} 个")

            # 显示可用模型
            if model_status["available_models"]:
                table = Table(title="✅ 可用模型")
                table.add_column("模型名称", style="green")
                table.add_column("状态", style="cyan")

                for model in model_status["available_models"]:
                    table.add_row(model, "✅ 已安装")

                app.console.print(table)

            # 显示缺失模型和建议
            if check_missing and model_status["missing_models"]:
                app.console.print("\n❌ 缺失的配置模型:")
                for model in model_status["missing_models"]:
                    app.console.print(f"  • {model}", style="red")

                    # 显示建议
                    if suggest and model in model_status["suggestions"]:
                        suggestions = model_status["suggestions"][model]
                        app.console.print(f"    💡 建议替代: {', '.join(suggestions)}", style="yellow")
                        app.console.print(f"    📥 下载命令: ollama pull {suggestions[0]}", style="cyan")

            # 显示下载建议
            if model_status["missing_models"]:
                app.console.print("\n📥 下载缺失模型:")
                for model in model_status["missing_models"][:3]:  # 只显示前3个
                    app.console.print(f"  ollama pull {model}")

                if len(model_status["missing_models"]) > 3:
                    app.console.print(f"  ... 还有 {len(model_status['missing_models']) - 3} 个模型")
        else:
            app.console.print("❌ 系统初始化失败", style="red")

    asyncio.run(run())


def main():
    """主入口函数"""
    try:
        cli()
    except KeyboardInterrupt:
        console = Console()
        console.print("\n👋 再见！", style="bold yellow")
        sys.exit(0)
    except Exception as e:
        console = Console()
        console.print(f"❌ 程序异常退出: {e}", style="red")
        sys.exit(1)


if __name__ == "__main__":
    main()
