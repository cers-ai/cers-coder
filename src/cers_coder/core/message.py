"""
消息系统 - 智能体间通信的消息定义和处理
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class MessageType(str, Enum):
    """消息类型枚举"""
    
    # 系统消息
    SYSTEM_START = "system.start"
    SYSTEM_STOP = "system.stop"
    SYSTEM_ERROR = "system.error"
    SYSTEM_STATUS = "system.status"
    
    # 任务消息
    TASK_CREATE = "task.create"
    TASK_UPDATE = "task.update"
    TASK_COMPLETE = "task.complete"
    TASK_FAILED = "task.failed"
    
    # 智能体消息
    AGENT_REQUEST = "agent.request"
    AGENT_RESPONSE = "agent.response"
    AGENT_NOTIFICATION = "agent.notification"
    
    # 数据消息
    DATA_INPUT = "data.input"
    DATA_OUTPUT = "data.output"
    DATA_SHARE = "data.share"
    
    # 状态消息
    STATE_SAVE = "state.save"
    STATE_LOAD = "state.load"
    STATE_SYNC = "state.sync"


class MessagePriority(int, Enum):
    """消息优先级"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


class Message(BaseModel):
    """智能体间通信的消息基类"""
    
    id: UUID = Field(default_factory=uuid4, description="消息唯一标识")
    type: MessageType = Field(..., description="消息类型")
    sender: str = Field(..., description="发送者标识")
    receiver: Optional[str] = Field(None, description="接收者标识，None表示广播")
    priority: MessagePriority = Field(default=MessagePriority.NORMAL, description="消息优先级")
    
    # 消息内容
    subject: str = Field(..., description="消息主题")
    content: Dict[str, Any] = Field(default_factory=dict, description="消息内容")
    
    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    expires_at: Optional[datetime] = Field(None, description="过期时间")
    
    # 消息状态
    is_processed: bool = Field(default=False, description="是否已处理")
    processed_at: Optional[datetime] = Field(None, description="处理时间")
    
    # 关联信息
    correlation_id: Optional[UUID] = Field(None, description="关联消息ID")
    reply_to: Optional[UUID] = Field(None, description="回复消息ID")
    
    # 元数据
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")

    def mark_processed(self) -> None:
        """标记消息为已处理"""
        self.is_processed = True
        self.processed_at = datetime.now()

    def is_expired(self) -> bool:
        """检查消息是否过期"""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at

    def create_reply(
        self,
        sender: str,
        subject: str,
        content: Dict[str, Any],
        message_type: MessageType = MessageType.AGENT_RESPONSE
    ) -> "Message":
        """创建回复消息"""
        return Message(
            type=message_type,
            sender=sender,
            receiver=self.sender,
            subject=subject,
            content=content,
            reply_to=self.id,
            correlation_id=self.correlation_id or self.id
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """从字典创建消息"""
        return cls(**data)


class TaskMessage(Message):
    """任务相关消息"""
    
    task_id: str = Field(..., description="任务ID")
    task_name: str = Field(..., description="任务名称")
    task_status: Optional[str] = Field(None, description="任务状态")


class DataMessage(Message):
    """数据传输消息"""
    
    data_type: str = Field(..., description="数据类型")
    data_format: str = Field(default="json", description="数据格式")
    data_size: Optional[int] = Field(None, description="数据大小（字节）")


class ErrorMessage(Message):
    """错误消息"""
    
    error_code: str = Field(..., description="错误代码")
    error_type: str = Field(..., description="错误类型")
    stack_trace: Optional[str] = Field(None, description="堆栈跟踪")


# 消息工厂函数
def create_system_message(
    sender: str,
    subject: str,
    content: Dict[str, Any],
    message_type: MessageType = MessageType.SYSTEM_STATUS
) -> Message:
    """创建系统消息"""
    return Message(
        type=message_type,
        sender=sender,
        subject=subject,
        content=content,
        priority=MessagePriority.HIGH
    )


def create_task_message(
    sender: str,
    task_id: str,
    task_name: str,
    subject: str,
    content: Dict[str, Any],
    message_type: MessageType = MessageType.TASK_CREATE,
    task_status: Optional[str] = None
) -> TaskMessage:
    """创建任务消息"""
    return TaskMessage(
        type=message_type,
        sender=sender,
        subject=subject,
        content=content,
        task_id=task_id,
        task_name=task_name,
        task_status=task_status
    )


def create_error_message(
    sender: str,
    error_code: str,
    error_type: str,
    subject: str,
    content: Dict[str, Any],
    stack_trace: Optional[str] = None
) -> ErrorMessage:
    """创建错误消息"""
    return ErrorMessage(
        type=MessageType.SYSTEM_ERROR,
        sender=sender,
        subject=subject,
        content=content,
        error_code=error_code,
        error_type=error_type,
        stack_trace=stack_trace,
        priority=MessagePriority.URGENT
    )
