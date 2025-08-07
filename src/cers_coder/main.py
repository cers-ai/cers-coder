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
from .core.state_manager import StateManager
from .core.workflow import WorkflowController
from .llm.model_config import ModelConfigManager
from .llm.ollama_client import OllamaClient
from .utils.logger import setup_logging


class CERSCoder:
    """CERS Coder 主应用类"""
    
    def __init__(self, work_dir: str = ".", config_dir: str = "./config"):
        self.work_dir = Path(work_dir)
        self.config_dir = Path(config_dir)
        self.console = Console()
        
        # 核心组件
        self.state_manager: Optional[StateManager] = None
        self.workflow_controller: Optional[WorkflowController] = None
        self.ollama_client: Optional[OllamaClient] = None
        self.model_config_manager: Optional[ModelConfigManager] = None
        
        # 智能体
        self.pm_agent: Optional[PMAgent] = None
        self.requirement_agent: Optional[RequirementAgent] = None
        
        # 状态
        self.is_running = False

    async def initialize(self) -> bool:
        """初始化系统"""
        try:
            self.console.print(Panel.fit("🚀 初始化 CERS Coder 系统", style="bold blue"))
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console,
                transient=True,
            ) as progress:
                
                # 初始化状态管理器
                task = progress.add_task("初始化状态管理器...", total=None)
                self.state_manager = StateManager(
                    state_dir=os.getenv("STATE_DIR", "./state")
                )
                progress.update(task, description="✅ 状态管理器初始化完成")
                
                # 初始化Ollama客户端
                task = progress.add_task("连接Ollama服务...", total=None)
                ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
                self.ollama_client = OllamaClient(host=ollama_host)
                
                # 检查Ollama连接
                if not await self.ollama_client.health_check():
                    self.console.print("❌ 无法连接到Ollama服务，请确保Ollama正在运行", style="red")
                    return False
                progress.update(task, description="✅ Ollama连接成功")
                
                # 初始化模型配置管理器
                task = progress.add_task("加载模型配置...", total=None)
                self.model_config_manager = ModelConfigManager()
                progress.update(task, description="✅ 模型配置加载完成")
                
                # 初始化工作流控制器
                task = progress.add_task("初始化工作流控制器...", total=None)
                self.workflow_controller = WorkflowController(self.state_manager)
                progress.update(task, description="✅ 工作流控制器初始化完成")
                
                # 初始化智能体
                task = progress.add_task("初始化智能体...", total=None)
                await self._initialize_agents()
                progress.update(task, description="✅ 智能体初始化完成")
            
            self.console.print("🎉 系统初始化完成！", style="bold green")
            return True
            
        except Exception as e:
            self.console.print(f"❌ 系统初始化失败: {e}", style="red")
            logging.error(f"系统初始化失败: {e}", exc_info=True)
            return False

    async def _initialize_agents(self) -> None:
        """初始化智能体"""
        # 初始化PM智能体
        self.pm_agent = PMAgent(self.state_manager, self.workflow_controller)
        self.workflow_controller.register_agent("pm_agent", self.pm_agent)
        
        # 初始化需求分析智能体
        self.requirement_agent = RequirementAgent(self.ollama_client)
        self.workflow_controller.register_agent("requirement_agent", self.requirement_agent)
        
        # TODO: 初始化其他智能体

    async def start_project(self, project_name: Optional[str] = None) -> bool:
        """启动新项目"""
        try:
            self.console.print(Panel.fit("📋 开始项目开发流程", style="bold cyan"))
            
            # 检查输入文件
            file_parser = FileParser(str(self.work_dir))
            parsed_files, missing_files = await file_parser.parse_all_files()
            
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
            
            # 启动工作流
            await self.workflow_controller.start_workflow()
            
            # 启动智能体
            await self.pm_agent.start()
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

    async def _display_project_info(self, parsed_files) -> None:
        """显示项目信息"""
        table = Table(title="📁 项目文件信息")
        table.add_column("文件名", style="cyan")
        table.add_column("状态", style="green")
        table.add_column("大小", style="yellow")
        
        for filename, content in parsed_files.items():
            status = "✅ 存在" if content.exists else "❌ 缺失"
            size = f"{len(content.content)} 字符" if content.exists else "0"
            table.add_row(filename, status, size)
        
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
@click.pass_context
def start(ctx, project_name):
    """启动新项目开发"""
    app = ctx.obj['app']
    
    async def run():
        if await app.initialize():
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
            # 检查Ollama连接
            ollama_status = "✅ 连接正常" if await app.ollama_client.health_check() else "❌ 连接失败"
            
            # 获取可用模型
            models = await app.ollama_client.list_models()
            
            console.print(Panel.fit("🔍 系统状态", style="bold blue"))
            console.print(f"Ollama服务: {ollama_status}")
            console.print(f"可用模型: {len(models)} 个")
            
            if models:
                table = Table(title="📦 可用模型")
                table.add_column("模型名称", style="cyan")
                table.add_column("大小", style="yellow")
                
                for model in models[:5]:  # 只显示前5个
                    size_gb = model.size / (1024**3)
                    table.add_row(model.name, f"{size_gb:.1f} GB")
                
                console.print(table)
    
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
