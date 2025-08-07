"""
操作记录系统 - 记录主流程和智能体的所有操作，支持复盘查看
"""

import json
import logging
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from uuid import UUID, uuid4

import aiofiles
from pydantic import BaseModel, Field


class OperationType(str, Enum):
    """操作类型枚举"""
    
    # 系统操作
    SYSTEM_START = "system.start"
    SYSTEM_STOP = "system.stop"
    SYSTEM_INIT = "system.init"
    SYSTEM_ERROR = "system.error"
    
    # 项目操作
    PROJECT_CREATE = "project.create"
    PROJECT_LOAD = "project.load"
    PROJECT_SAVE = "project.save"
    PROJECT_UPDATE = "project.update"
    
    # 智能体操作
    AGENT_START = "agent.start"
    AGENT_STOP = "agent.stop"
    AGENT_PROCESS = "agent.process"
    AGENT_GENERATE = "agent.generate"
    AGENT_ANALYZE = "agent.analyze"
    AGENT_DESIGN = "agent.design"
    AGENT_CODE = "agent.code"
    AGENT_TEST = "agent.test"
    AGENT_REVIEW = "agent.review"
    
    # 工作流操作
    WORKFLOW_START = "workflow.start"
    WORKFLOW_PAUSE = "workflow.pause"
    WORKFLOW_RESUME = "workflow.resume"
    WORKFLOW_COMPLETE = "workflow.complete"
    
    # 任务操作
    TASK_CREATE = "task.create"
    TASK_START = "task.start"
    TASK_COMPLETE = "task.complete"
    TASK_FAIL = "task.fail"
    
    # 文件操作
    FILE_READ = "file.read"
    FILE_WRITE = "file.write"
    FILE_PARSE = "file.parse"
    FILE_GENERATE = "file.generate"
    
    # LLM操作
    LLM_REQUEST = "llm.request"
    LLM_RESPONSE = "llm.response"
    LLM_ERROR = "llm.error"


class OperationStatus(str, Enum):
    """操作状态枚举"""
    STARTED = "started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OperationRecord(BaseModel):
    """操作记录模型"""
    
    id: str = Field(default_factory=lambda: str(uuid4()), description="记录ID")
    operation_type: OperationType = Field(..., description="操作类型")
    status: OperationStatus = Field(default=OperationStatus.STARTED, description="操作状态")
    
    # 操作主体信息
    actor: str = Field(..., description="操作执行者（系统/智能体名称）")
    target: Optional[str] = Field(None, description="操作目标")
    
    # 操作内容
    title: str = Field(..., description="操作标题")
    description: str = Field(default="", description="操作描述")
    input_data: Dict[str, Any] = Field(default_factory=dict, description="输入数据")
    output_data: Dict[str, Any] = Field(default_factory=dict, description="输出数据")
    
    # 时间信息
    start_time: datetime = Field(default_factory=datetime.now, description="开始时间")
    end_time: Optional[datetime] = Field(None, description="结束时间")
    duration: Optional[float] = Field(None, description="持续时间（秒）")
    
    # 关联信息
    project_id: Optional[str] = Field(None, description="项目ID")
    session_id: Optional[str] = Field(None, description="会话ID")
    parent_operation_id: Optional[str] = Field(None, description="父操作ID")
    
    # 结果信息
    success: bool = Field(default=True, description="是否成功")
    error_message: Optional[str] = Field(None, description="错误信息")
    error_details: Dict[str, Any] = Field(default_factory=dict, description="错误详情")
    
    # 元数据
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    tags: List[str] = Field(default_factory=list, description="标签")

    def complete(self, success: bool = True, output_data: Optional[Dict[str, Any]] = None, 
                error_message: Optional[str] = None) -> None:
        """完成操作记录"""
        self.end_time = datetime.now()
        self.duration = (self.end_time - self.start_time).total_seconds()
        self.success = success
        self.status = OperationStatus.COMPLETED if success else OperationStatus.FAILED
        
        if output_data:
            self.output_data.update(output_data)
        
        if error_message:
            self.error_message = error_message

    def fail(self, error_message: str, error_details: Optional[Dict[str, Any]] = None) -> None:
        """标记操作失败"""
        self.complete(success=False, error_message=error_message)
        if error_details:
            self.error_details.update(error_details)

    def add_metadata(self, key: str, value: Any) -> None:
        """添加元数据"""
        self.metadata[key] = value

    def add_tag(self, tag: str) -> None:
        """添加标签"""
        if tag not in self.tags:
            self.tags.append(tag)


class OperationRecorder:
    """操作记录器"""
    
    def __init__(self, workspace_dir: str, project_id: Optional[str] = None):
        self.workspace_dir = Path(workspace_dir)
        self.project_id = project_id
        self.session_id = str(uuid4())
        
        # 创建记录目录
        self.records_dir = self.workspace_dir / "records"
        self.records_dir.mkdir(parents=True, exist_ok=True)
        
        # 当前会话的记录文件
        self.session_file = self.records_dir / f"session_{self.session_id}.jsonl"
        
        # 内存中的记录缓存
        self.active_operations: Dict[str, OperationRecord] = {}
        
        # 日志器
        self.logger = logging.getLogger("operation_recorder")

    async def start_operation(
        self,
        operation_type: OperationType,
        actor: str,
        title: str,
        description: str = "",
        target: Optional[str] = None,
        input_data: Optional[Dict[str, Any]] = None,
        parent_operation_id: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> str:
        """开始记录操作"""
        
        record = OperationRecord(
            operation_type=operation_type,
            actor=actor,
            target=target,
            title=title,
            description=description,
            input_data=input_data or {},
            project_id=self.project_id,
            session_id=self.session_id,
            parent_operation_id=parent_operation_id,
            tags=tags or []
        )
        
        # 缓存活跃操作
        self.active_operations[record.id] = record
        
        # 写入文件
        await self._write_record(record)
        
        self.logger.debug(f"开始操作记录: {record.title} ({record.id})")
        return record.id

    async def complete_operation(
        self,
        operation_id: str,
        success: bool = True,
        output_data: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        error_details: Optional[Dict[str, Any]] = None
    ) -> None:
        """完成操作记录"""
        
        if operation_id not in self.active_operations:
            self.logger.warning(f"操作记录不存在: {operation_id}")
            return
        
        record = self.active_operations[operation_id]
        
        if success:
            record.complete(success=True, output_data=output_data)
        else:
            record.fail(error_message or "操作失败", error_details)
        
        # 更新文件
        await self._write_record(record)
        
        # 从活跃操作中移除
        del self.active_operations[operation_id]
        
        status = "成功" if success else "失败"
        self.logger.debug(f"操作记录{status}: {record.title} ({operation_id})")

    async def update_operation(
        self,
        operation_id: str,
        status: Optional[OperationStatus] = None,
        output_data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None
    ) -> None:
        """更新操作记录"""
        
        if operation_id not in self.active_operations:
            self.logger.warning(f"操作记录不存在: {operation_id}")
            return
        
        record = self.active_operations[operation_id]
        
        if status:
            record.status = status
        
        if output_data:
            record.output_data.update(output_data)
        
        if metadata:
            record.metadata.update(metadata)
        
        if tags:
            for tag in tags:
                record.add_tag(tag)
        
        # 更新文件
        await self._write_record(record)

    async def record_instant_operation(
        self,
        operation_type: OperationType,
        actor: str,
        title: str,
        description: str = "",
        target: Optional[str] = None,
        input_data: Optional[Dict[str, Any]] = None,
        output_data: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> str:
        """记录即时完成的操作"""
        
        operation_id = await self.start_operation(
            operation_type=operation_type,
            actor=actor,
            title=title,
            description=description,
            target=target,
            input_data=input_data,
            tags=tags
        )
        
        await self.complete_operation(
            operation_id=operation_id,
            success=success,
            output_data=output_data,
            error_message=error_message
        )
        
        return operation_id

    async def _write_record(self, record: OperationRecord) -> None:
        """写入记录到文件"""
        try:
            record_json = record.model_dump_json()
            async with aiofiles.open(self.session_file, 'a', encoding='utf-8') as f:
                await f.write(record_json + '\n')
        except Exception as e:
            self.logger.error(f"写入操作记录失败: {e}")

    async def get_session_records(self, session_id: Optional[str] = None) -> List[OperationRecord]:
        """获取会话记录"""
        target_session = session_id or self.session_id
        session_file = self.records_dir / f"session_{target_session}.jsonl"
        
        if not session_file.exists():
            return []
        
        records = []
        try:
            async with aiofiles.open(session_file, 'r', encoding='utf-8') as f:
                async for line in f:
                    if line.strip():
                        data = json.loads(line.strip())
                        records.append(OperationRecord(**data))
        except Exception as e:
            self.logger.error(f"读取会话记录失败: {e}")
        
        return records

    async def get_project_records(self, project_id: str) -> List[OperationRecord]:
        """获取项目的所有记录"""
        all_records = []
        
        for session_file in self.records_dir.glob("session_*.jsonl"):
            try:
                async with aiofiles.open(session_file, 'r', encoding='utf-8') as f:
                    async for line in f:
                        if line.strip():
                            data = json.loads(line.strip())
                            record = OperationRecord(**data)
                            if record.project_id == project_id:
                                all_records.append(record)
            except Exception as e:
                self.logger.error(f"读取记录文件失败 {session_file}: {e}")
        
        # 按时间排序
        all_records.sort(key=lambda x: x.start_time)
        return all_records

    async def get_agent_records(self, agent_name: str, project_id: Optional[str] = None) -> List[OperationRecord]:
        """获取特定智能体的记录"""
        if project_id:
            all_records = await self.get_project_records(project_id)
        else:
            all_records = await self.get_session_records()
        
        return [record for record in all_records if record.actor == agent_name]

    async def export_records(self, output_file: str, project_id: Optional[str] = None) -> None:
        """导出记录到文件"""
        if project_id:
            records = await self.get_project_records(project_id)
        else:
            records = await self.get_session_records()
        
        export_data = {
            "export_time": datetime.now().isoformat(),
            "project_id": project_id,
            "session_id": self.session_id,
            "total_records": len(records),
            "records": [record.model_dump() for record in records]
        }
        
        async with aiofiles.open(output_file, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(export_data, indent=2, ensure_ascii=False))

    def get_operation_stats(self, records: List[OperationRecord]) -> Dict[str, Any]:
        """获取操作统计信息"""
        if not records:
            return {}
        
        total_operations = len(records)
        successful_operations = len([r for r in records if r.success])
        failed_operations = total_operations - successful_operations
        
        # 按类型统计
        type_stats = {}
        for record in records:
            op_type = record.operation_type.value
            if op_type not in type_stats:
                type_stats[op_type] = {"count": 0, "success": 0, "failed": 0}
            type_stats[op_type]["count"] += 1
            if record.success:
                type_stats[op_type]["success"] += 1
            else:
                type_stats[op_type]["failed"] += 1
        
        # 按智能体统计
        agent_stats = {}
        for record in records:
            actor = record.actor
            if actor not in agent_stats:
                agent_stats[actor] = {"count": 0, "success": 0, "failed": 0}
            agent_stats[actor]["count"] += 1
            if record.success:
                agent_stats[actor]["success"] += 1
            else:
                agent_stats[actor]["failed"] += 1
        
        # 时间统计
        durations = [r.duration for r in records if r.duration is not None]
        avg_duration = sum(durations) / len(durations) if durations else 0
        
        return {
            "total_operations": total_operations,
            "successful_operations": successful_operations,
            "failed_operations": failed_operations,
            "success_rate": successful_operations / total_operations if total_operations > 0 else 0,
            "average_duration": avg_duration,
            "type_statistics": type_stats,
            "agent_statistics": agent_stats,
            "time_range": {
                "start": min(r.start_time for r in records).isoformat(),
                "end": max(r.end_time or r.start_time for r in records).isoformat()
            }
        }
