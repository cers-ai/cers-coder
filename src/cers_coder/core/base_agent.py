"""
智能体基类 - 所有智能体的基础实现
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from .message import Message, MessageType, create_error_message


class AgentStatus(str, Enum):
    """智能体状态枚举"""
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    STOPPED = "stopped"


class AgentCapability(str, Enum):
    """智能体能力枚举"""
    ANALYSIS = "analysis"
    DESIGN = "design"
    CODING = "coding"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    REVIEW = "review"
    MANAGEMENT = "management"
    BUILD_DEPLOY = "build_deploy"


class AgentConfig(BaseModel):
    """智能体配置"""
    name: str = Field(..., description="智能体名称")
    description: str = Field(..., description="智能体描述")
    capabilities: List[AgentCapability] = Field(default_factory=list, description="智能体能力")
    max_concurrent_tasks: int = Field(default=1, description="最大并发任务数")
    timeout: int = Field(default=300, description="任务超时时间（秒）")
    retry_attempts: int = Field(default=3, description="重试次数")
    retry_delay: int = Field(default=5, description="重试延迟（秒）")
    llm_config: Dict[str, Any] = Field(default_factory=dict, description="LLM配置")


class BaseAgent(ABC):
    """智能体基类"""
    
    def __init__(self, config: AgentConfig):
        self.id = str(uuid4())
        self.config = config
        self.status = AgentStatus.IDLE
        self.logger = logging.getLogger(f"agent.{config.name}")
        
        # 消息队列
        self._message_queue: asyncio.Queue[Message] = asyncio.Queue()
        self._running_tasks: Set[str] = set()
        
        # 状态信息
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
        self.task_count = 0
        self.error_count = 0
        
        # 事件循环
        self._stop_event = asyncio.Event()
        self._message_handler_task: Optional[asyncio.Task] = None

    @property
    def name(self) -> str:
        """获取智能体名称"""
        return self.config.name

    @property
    def is_busy(self) -> bool:
        """检查智能体是否忙碌"""
        return self.status == AgentStatus.BUSY or len(self._running_tasks) > 0

    @property
    def can_accept_task(self) -> bool:
        """检查是否可以接受新任务"""
        return (
            self.status in [AgentStatus.IDLE, AgentStatus.BUSY] and
            len(self._running_tasks) < self.config.max_concurrent_tasks
        )

    async def start(self) -> None:
        """启动智能体"""
        self.logger.info(f"启动智能体: {self.name}")
        self.status = AgentStatus.IDLE
        self._stop_event.clear()
        
        # 启动消息处理任务
        self._message_handler_task = asyncio.create_task(self._message_handler())
        
        # 执行初始化
        await self._initialize()

    async def stop(self) -> None:
        """停止智能体"""
        self.logger.info(f"停止智能体: {self.name}")
        self.status = AgentStatus.STOPPED
        self._stop_event.set()
        
        # 停止消息处理任务
        if self._message_handler_task:
            self._message_handler_task.cancel()
            try:
                await self._message_handler_task
            except asyncio.CancelledError:
                pass
        
        # 执行清理
        await self._cleanup()

    async def send_message(self, message: Message) -> None:
        """发送消息"""
        await self._message_queue.put(message)

    async def process_message(self, message: Message) -> Optional[Message]:
        """处理消息 - 子类需要实现"""
        try:
            self.last_activity = datetime.now()
            
            # 根据消息类型分发处理
            if message.type == MessageType.TASK_CREATE:
                return await self._handle_task_create(message)
            elif message.type == MessageType.TASK_UPDATE:
                return await self._handle_task_update(message)
            elif message.type == MessageType.AGENT_REQUEST:
                return await self._handle_agent_request(message)
            elif message.type == MessageType.DATA_INPUT:
                return await self._handle_data_input(message)
            else:
                return await self._handle_custom_message(message)
                
        except Exception as e:
            self.error_count += 1
            self.logger.error(f"处理消息失败: {e}", exc_info=True)
            return create_error_message(
                sender=self.name,
                error_code="MESSAGE_PROCESSING_ERROR",
                error_type=type(e).__name__,
                subject=f"处理消息失败: {message.subject}",
                content={"original_message_id": str(message.id), "error": str(e)},
                stack_trace=str(e)
            )

    @abstractmethod
    async def _handle_task_create(self, message: Message) -> Optional[Message]:
        """处理任务创建消息"""
        pass

    @abstractmethod
    async def _handle_agent_request(self, message: Message) -> Optional[Message]:
        """处理智能体请求消息"""
        pass

    async def _handle_task_update(self, message: Message) -> Optional[Message]:
        """处理任务更新消息 - 默认实现"""
        self.logger.info(f"收到任务更新: {message.subject}")
        return None

    async def _handle_data_input(self, message: Message) -> Optional[Message]:
        """处理数据输入消息 - 默认实现"""
        self.logger.info(f"收到数据输入: {message.subject}")
        return None

    async def _handle_custom_message(self, message: Message) -> Optional[Message]:
        """处理自定义消息 - 子类可以重写"""
        self.logger.warning(f"未处理的消息类型: {message.type}")
        return None

    async def _initialize(self) -> None:
        """初始化 - 子类可以重写"""
        pass

    async def _cleanup(self) -> None:
        """清理 - 子类可以重写"""
        pass

    async def _message_handler(self) -> None:
        """消息处理循环"""
        while not self._stop_event.is_set():
            try:
                # 等待消息或停止事件
                message = await asyncio.wait_for(
                    self._message_queue.get(),
                    timeout=1.0
                )
                
                # 处理消息
                response = await self.process_message(message)
                message.mark_processed()
                
                # 如果有响应消息，发送回去
                if response:
                    # 这里需要通过消息总线发送响应
                    # 具体实现依赖于消息总线的接口
                    pass
                    
            except asyncio.TimeoutError:
                # 超时是正常的，继续循环
                continue
            except Exception as e:
                self.logger.error(f"消息处理循环错误: {e}", exc_info=True)
                await asyncio.sleep(1)

    def get_status(self) -> Dict[str, Any]:
        """获取智能体状态信息"""
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "capabilities": [cap.value for cap in self.config.capabilities],
            "is_busy": self.is_busy,
            "can_accept_task": self.can_accept_task,
            "running_tasks": len(self._running_tasks),
            "max_concurrent_tasks": self.config.max_concurrent_tasks,
            "task_count": self.task_count,
            "error_count": self.error_count,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
        }

    def __str__(self) -> str:
        return f"Agent({self.name}, {self.status.value})"

    def __repr__(self) -> str:
        return f"BaseAgent(id={self.id}, name={self.name}, status={self.status.value})"
