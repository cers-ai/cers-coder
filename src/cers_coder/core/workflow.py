"""
工作流控制器 - 管理开发流程的执行顺序和智能体协调
"""

import asyncio
import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4

from pydantic import BaseModel, Field

from .base_agent import BaseAgent
from .message import Message, MessageType, create_task_message
from .state_manager import StateManager


class WorkflowPhase(str, Enum):
    """工作流阶段枚举"""
    INITIALIZATION = "initialization"
    REQUIREMENT_ANALYSIS = "requirement_analysis"
    ARCHITECTURE_DESIGN = "architecture_design"
    CODING = "coding"
    TESTING = "testing"
    BUILD_DEPLOY = "build_deploy"
    DOCUMENTATION = "documentation"
    REVIEW = "review"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskDefinition(BaseModel):
    """任务定义"""
    id: str = Field(default_factory=lambda: str(uuid4()), description="任务ID")
    name: str = Field(..., description="任务名称")
    description: str = Field(..., description="任务描述")
    phase: WorkflowPhase = Field(..., description="所属阶段")
    agent_type: str = Field(..., description="负责的智能体类型")
    dependencies: List[str] = Field(default_factory=list, description="依赖的任务ID")
    inputs: Dict[str, Any] = Field(default_factory=dict, description="输入数据")
    outputs: Dict[str, Any] = Field(default_factory=dict, description="输出数据")
    priority: int = Field(default=1, description="优先级")
    timeout: int = Field(default=300, description="超时时间（秒）")
    retry_count: int = Field(default=0, description="重试次数")
    max_retries: int = Field(default=3, description="最大重试次数")
    status: str = Field(default="pending", description="任务状态")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    started_at: Optional[datetime] = Field(None, description="开始时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    error_message: Optional[str] = Field(None, description="错误信息")


class WorkflowController:
    """工作流控制器"""
    
    def __init__(self, state_manager: StateManager):
        self.state_manager = state_manager
        self.logger = logging.getLogger("workflow_controller")
        
        # 智能体注册表
        self.agents: Dict[str, BaseAgent] = {}
        
        # 任务管理
        self.tasks: Dict[str, TaskDefinition] = {}
        self.task_queue: asyncio.Queue[str] = asyncio.Queue()
        self.running_tasks: Set[str] = set()
        
        # 工作流状态
        self.current_phase = WorkflowPhase.INITIALIZATION
        self.is_running = False
        self.is_paused = False
        
        # 事件
        self._stop_event = asyncio.Event()
        self._pause_event = asyncio.Event()
        
        # 任务执行器
        self._task_executor: Optional[asyncio.Task] = None

    def register_agent(self, agent_type: str, agent: BaseAgent) -> None:
        """注册智能体"""
        self.agents[agent_type] = agent
        self.logger.info(f"注册智能体: {agent_type} -> {agent.name}")

    def create_default_workflow(self) -> List[TaskDefinition]:
        """创建默认工作流"""
        tasks = [
            # 需求分析阶段
            TaskDefinition(
                name="解析输入文件",
                description="解析项目输入文件，提取需求信息",
                phase=WorkflowPhase.REQUIREMENT_ANALYSIS,
                agent_type="requirement_agent",
                priority=1
            ),
            TaskDefinition(
                name="需求分析",
                description="分析业务需求，生成功能模型",
                phase=WorkflowPhase.REQUIREMENT_ANALYSIS,
                agent_type="requirement_agent",
                dependencies=["解析输入文件"],
                priority=2
            ),
            
            # 架构设计阶段
            TaskDefinition(
                name="系统架构设计",
                description="设计系统架构，定义模块和接口",
                phase=WorkflowPhase.ARCHITECTURE_DESIGN,
                agent_type="architecture_agent",
                dependencies=["需求分析"],
                priority=1
            ),
            TaskDefinition(
                name="技术选型",
                description="选择技术栈和工具",
                phase=WorkflowPhase.ARCHITECTURE_DESIGN,
                agent_type="architecture_agent",
                dependencies=["系统架构设计"],
                priority=2
            ),
            
            # 编码阶段
            TaskDefinition(
                name="核心模块开发",
                description="开发核心业务模块",
                phase=WorkflowPhase.CODING,
                agent_type="coding_agent",
                dependencies=["技术选型"],
                priority=1
            ),
            TaskDefinition(
                name="接口实现",
                description="实现系统接口",
                phase=WorkflowPhase.CODING,
                agent_type="coding_agent",
                dependencies=["核心模块开发"],
                priority=2
            ),
            
            # 测试阶段
            TaskDefinition(
                name="单元测试",
                description="编写和执行单元测试",
                phase=WorkflowPhase.TESTING,
                agent_type="testing_agent",
                dependencies=["接口实现"],
                priority=1
            ),
            TaskDefinition(
                name="集成测试",
                description="执行集成测试",
                phase=WorkflowPhase.TESTING,
                agent_type="testing_agent",
                dependencies=["单元测试"],
                priority=2
            ),
            
            # 构建部署阶段
            TaskDefinition(
                name="构建配置",
                description="生成构建脚本和配置",
                phase=WorkflowPhase.BUILD_DEPLOY,
                agent_type="build_agent",
                dependencies=["集成测试"],
                priority=1
            ),
            
            # 文档生成阶段
            TaskDefinition(
                name="API文档生成",
                description="生成API接口文档",
                phase=WorkflowPhase.DOCUMENTATION,
                agent_type="documentation_agent",
                dependencies=["构建配置"],
                priority=1
            ),
            TaskDefinition(
                name="用户文档生成",
                description="生成用户使用文档",
                phase=WorkflowPhase.DOCUMENTATION,
                agent_type="documentation_agent",
                dependencies=["API文档生成"],
                priority=2
            ),
            
            # 审查阶段
            TaskDefinition(
                name="代码审查",
                description="审查代码质量和一致性",
                phase=WorkflowPhase.REVIEW,
                agent_type="review_agent",
                dependencies=["用户文档生成"],
                priority=1
            ),
            TaskDefinition(
                name="最终验证",
                description="最终验证项目完整性",
                phase=WorkflowPhase.REVIEW,
                agent_type="review_agent",
                dependencies=["代码审查"],
                priority=2
            )
        ]
        
        # 为任务分配ID并注册
        for task in tasks:
            task.id = task.name  # 使用名称作为ID，简化依赖关系
            self.tasks[task.id] = task
        
        return tasks

    async def start_workflow(self) -> None:
        """启动工作流"""
        if self.is_running:
            self.logger.warning("工作流已在运行中")
            return
        
        self.logger.info("启动工作流")
        self.is_running = True
        self.is_paused = False
        self._stop_event.clear()
        self._pause_event.clear()
        
        # 启动所有智能体
        for agent in self.agents.values():
            await agent.start()
        
        # 创建默认工作流（如果没有任务）
        if not self.tasks:
            self.create_default_workflow()
        
        # 启动任务执行器
        self._task_executor = asyncio.create_task(self._task_execution_loop())
        
        # 将准备就绪的任务加入队列
        await self._enqueue_ready_tasks()

    async def stop_workflow(self) -> None:
        """停止工作流"""
        if not self.is_running:
            return
        
        self.logger.info("停止工作流")
        self.is_running = False
        self._stop_event.set()
        
        # 停止任务执行器
        if self._task_executor:
            self._task_executor.cancel()
            try:
                await self._task_executor
            except asyncio.CancelledError:
                pass
        
        # 停止所有智能体
        for agent in self.agents.values():
            await agent.stop()

    async def pause_workflow(self) -> None:
        """暂停工作流"""
        if not self.is_running or self.is_paused:
            return
        
        self.logger.info("暂停工作流")
        self.is_paused = True
        self._pause_event.set()

    async def resume_workflow(self) -> None:
        """恢复工作流"""
        if not self.is_running or not self.is_paused:
            return
        
        self.logger.info("恢复工作流")
        self.is_paused = False
        self._pause_event.clear()

    async def _task_execution_loop(self) -> None:
        """任务执行循环"""
        while not self._stop_event.is_set():
            try:
                # 检查是否暂停
                if self.is_paused:
                    await self._pause_event.wait()
                    continue
                
                # 获取下一个任务
                try:
                    task_id = await asyncio.wait_for(
                        self.task_queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                # 执行任务
                await self._execute_task(task_id)
                
            except Exception as e:
                self.logger.error(f"任务执行循环错误: {e}", exc_info=True)
                await asyncio.sleep(1)

    async def _execute_task(self, task_id: str) -> None:
        """执行单个任务"""
        task = self.tasks.get(task_id)
        if not task:
            self.logger.error(f"任务不存在: {task_id}")
            return
        
        agent = self.agents.get(task.agent_type)
        if not agent:
            self.logger.error(f"智能体不存在: {task.agent_type}")
            task.status = "failed"
            task.error_message = f"智能体不存在: {task.agent_type}"
            return
        
        try:
            self.logger.info(f"开始执行任务: {task.name}")
            task.status = "running"
            task.started_at = datetime.now()
            self.running_tasks.add(task_id)
            
            # 创建任务消息
            message = create_task_message(
                sender="workflow_controller",
                task_id=task.id,
                task_name=task.name,
                subject=f"执行任务: {task.name}",
                content={
                    "description": task.description,
                    "inputs": task.inputs,
                    "timeout": task.timeout
                }
            )
            
            # 发送任务给智能体
            await agent.send_message(message)
            
            # 等待任务完成（这里简化处理，实际需要更复杂的状态跟踪）
            await asyncio.sleep(1)  # 模拟任务执行时间
            
            # 标记任务完成
            task.status = "completed"
            task.completed_at = datetime.now()
            self.running_tasks.discard(task_id)
            
            self.logger.info(f"任务完成: {task.name}")
            
            # 检查并加入新的就绪任务
            await self._enqueue_ready_tasks()
            
        except Exception as e:
            self.logger.error(f"执行任务失败 {task.name}: {e}", exc_info=True)
            task.status = "failed"
            task.error_message = str(e)
            task.completed_at = datetime.now()
            self.running_tasks.discard(task_id)
            
            # 检查是否需要重试
            if task.retry_count < task.max_retries:
                task.retry_count += 1
                task.status = "pending"
                await self.task_queue.put(task_id)
                self.logger.info(f"任务重试 {task.name} (第{task.retry_count}次)")

    async def _enqueue_ready_tasks(self) -> None:
        """将准备就绪的任务加入队列"""
        for task in self.tasks.values():
            if task.status == "pending" and self._is_task_ready(task):
                await self.task_queue.put(task.id)
                task.status = "queued"

    def _is_task_ready(self, task: TaskDefinition) -> bool:
        """检查任务是否准备就绪"""
        # 检查依赖任务是否都已完成
        for dep_id in task.dependencies:
            dep_task = self.tasks.get(dep_id)
            if not dep_task or dep_task.status != "completed":
                return False
        return True

    def get_workflow_status(self) -> Dict[str, Any]:
        """获取工作流状态"""
        total_tasks = len(self.tasks)
        completed_tasks = len([t for t in self.tasks.values() if t.status == "completed"])
        failed_tasks = len([t for t in self.tasks.values() if t.status == "failed"])
        
        return {
            "is_running": self.is_running,
            "is_paused": self.is_paused,
            "current_phase": self.current_phase.value,
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "failed_tasks": failed_tasks,
            "running_tasks": len(self.running_tasks),
            "progress": (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0,
            "agents": {name: agent.get_status() for name, agent in self.agents.items()}
        }
