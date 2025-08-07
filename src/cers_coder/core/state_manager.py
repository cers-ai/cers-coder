"""
状态管理器 - 负责系统状态的持久化和恢复
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

import aiofiles
from pydantic import BaseModel, Field


class ProjectState(BaseModel):
    """项目状态模型"""
    
    id: str = Field(default_factory=lambda: str(uuid4()), description="项目ID")
    name: str = Field(..., description="项目名称")
    description: str = Field(default="", description="项目描述")
    
    # 状态信息
    status: str = Field(default="initialized", description="项目状态")
    current_phase: str = Field(default="analysis", description="当前阶段")
    progress: float = Field(default=0.0, description="进度百分比")
    
    # 时间信息
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")
    started_at: Optional[datetime] = Field(None, description="开始时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    
    # 配置信息
    input_files: Dict[str, str] = Field(default_factory=dict, description="输入文件内容")
    requirements: Dict[str, Any] = Field(default_factory=dict, description="需求信息")
    architecture: Dict[str, Any] = Field(default_factory=dict, description="架构信息")
    
    # 智能体状态
    agents_status: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="智能体状态")
    
    # 任务信息
    tasks: List[Dict[str, Any]] = Field(default_factory=list, description="任务列表")
    completed_tasks: List[str] = Field(default_factory=list, description="已完成任务")
    failed_tasks: List[str] = Field(default_factory=list, description="失败任务")
    
    # 输出信息
    outputs: Dict[str, Any] = Field(default_factory=dict, description="输出文件信息")
    artifacts: List[str] = Field(default_factory=list, description="生成的文件列表")
    
    # 错误信息
    errors: List[Dict[str, Any]] = Field(default_factory=list, description="错误记录")
    warnings: List[Dict[str, Any]] = Field(default_factory=list, description="警告记录")
    
    # 元数据
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")

    def update_progress(self, progress: float) -> None:
        """更新进度"""
        self.progress = max(0.0, min(100.0, progress))
        self.updated_at = datetime.now()

    def set_phase(self, phase: str) -> None:
        """设置当前阶段"""
        self.current_phase = phase
        self.updated_at = datetime.now()

    def add_error(self, error: str, details: Optional[Dict[str, Any]] = None) -> None:
        """添加错误记录"""
        self.errors.append({
            "timestamp": datetime.now().isoformat(),
            "error": error,
            "details": details or {}
        })
        self.updated_at = datetime.now()

    def add_warning(self, warning: str, details: Optional[Dict[str, Any]] = None) -> None:
        """添加警告记录"""
        self.warnings.append({
            "timestamp": datetime.now().isoformat(),
            "warning": warning,
            "details": details or {}
        })
        self.updated_at = datetime.now()


class StateManager:
    """状态管理器"""
    
    def __init__(self, state_dir: str = "./state"):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger("state_manager")
        
        # 当前项目状态
        self._current_state: Optional[ProjectState] = None
        self._state_file: Optional[Path] = None

    async def create_project(self, name: str, description: str = "") -> ProjectState:
        """创建新项目"""
        project_state = ProjectState(
            name=name,
            description=description,
            started_at=datetime.now()
        )
        
        # 设置状态文件路径
        self._state_file = self.state_dir / f"{project_state.id}.json"
        self._current_state = project_state
        
        # 保存初始状态
        await self.save_state()
        
        self.logger.info(f"创建新项目: {name} (ID: {project_state.id})")
        return project_state

    async def load_project(self, project_id: str) -> Optional[ProjectState]:
        """加载项目状态"""
        state_file = self.state_dir / f"{project_id}.json"
        
        if not state_file.exists():
            self.logger.warning(f"项目状态文件不存在: {state_file}")
            return None
        
        try:
            async with aiofiles.open(state_file, 'r', encoding='utf-8') as f:
                content = await f.read()
                data = json.loads(content)
                
            project_state = ProjectState(**data)
            self._current_state = project_state
            self._state_file = state_file
            
            self.logger.info(f"加载项目状态: {project_state.name} (ID: {project_id})")
            return project_state
            
        except Exception as e:
            self.logger.error(f"加载项目状态失败: {e}", exc_info=True)
            return None

    async def save_state(self) -> bool:
        """保存当前状态"""
        if not self._current_state or not self._state_file:
            self.logger.warning("没有当前状态或状态文件路径")
            return False
        
        try:
            # 更新时间戳
            self._current_state.updated_at = datetime.now()
            
            # 序列化状态
            data = self._current_state.model_dump(mode='json')
            
            # 写入文件
            async with aiofiles.open(self._state_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(data, indent=2, ensure_ascii=False))
            
            self.logger.debug(f"保存状态到: {self._state_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"保存状态失败: {e}", exc_info=True)
            return False

    async def create_checkpoint(self, name: str) -> bool:
        """创建检查点"""
        if not self._current_state:
            return False
        
        try:
            checkpoint_file = self.state_dir / f"{self._current_state.id}_checkpoint_{name}.json"
            data = self._current_state.model_dump(mode='json')
            
            async with aiofiles.open(checkpoint_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(data, indent=2, ensure_ascii=False))
            
            self.logger.info(f"创建检查点: {name}")
            return True
            
        except Exception as e:
            self.logger.error(f"创建检查点失败: {e}", exc_info=True)
            return False

    async def restore_checkpoint(self, name: str) -> bool:
        """恢复检查点"""
        if not self._current_state:
            return False
        
        try:
            checkpoint_file = self.state_dir / f"{self._current_state.id}_checkpoint_{name}.json"
            
            if not checkpoint_file.exists():
                self.logger.warning(f"检查点文件不存在: {checkpoint_file}")
                return False
            
            async with aiofiles.open(checkpoint_file, 'r', encoding='utf-8') as f:
                content = await f.read()
                data = json.loads(content)
            
            self._current_state = ProjectState(**data)
            await self.save_state()
            
            self.logger.info(f"恢复检查点: {name}")
            return True
            
        except Exception as e:
            self.logger.error(f"恢复检查点失败: {e}", exc_info=True)
            return False

    def get_current_state(self) -> Optional[ProjectState]:
        """获取当前状态"""
        return self._current_state

    async def update_agent_status(self, agent_name: str, status: Dict[str, Any]) -> None:
        """更新智能体状态"""
        if self._current_state:
            self._current_state.agents_status[agent_name] = status
            await self.save_state()

    async def add_task(self, task: Dict[str, Any]) -> None:
        """添加任务"""
        if self._current_state:
            self._current_state.tasks.append(task)
            await self.save_state()

    async def complete_task(self, task_id: str) -> None:
        """完成任务"""
        if self._current_state:
            self._current_state.completed_tasks.append(task_id)
            await self.save_state()

    async def fail_task(self, task_id: str) -> None:
        """任务失败"""
        if self._current_state:
            self._current_state.failed_tasks.append(task_id)
            await self.save_state()

    async def list_projects(self) -> List[Dict[str, Any]]:
        """列出所有项目"""
        projects = []
        
        for state_file in self.state_dir.glob("*.json"):
            # 跳过检查点文件
            if "_checkpoint_" in state_file.name:
                continue
                
            try:
                async with aiofiles.open(state_file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    data = json.loads(content)
                
                projects.append({
                    "id": data.get("id"),
                    "name": data.get("name"),
                    "status": data.get("status"),
                    "progress": data.get("progress", 0),
                    "created_at": data.get("created_at"),
                    "updated_at": data.get("updated_at")
                })
                
            except Exception as e:
                self.logger.warning(f"读取项目文件失败 {state_file}: {e}")
                continue
        
        return sorted(projects, key=lambda x: x.get("updated_at", ""), reverse=True)

    async def cleanup_old_states(self, days: int = 30) -> int:
        """清理旧的状态文件"""
        cutoff_time = datetime.now().timestamp() - (days * 24 * 3600)
        cleaned_count = 0
        
        for state_file in self.state_dir.glob("*.json"):
            try:
                if state_file.stat().st_mtime < cutoff_time:
                    state_file.unlink()
                    cleaned_count += 1
                    self.logger.info(f"清理旧状态文件: {state_file}")
            except Exception as e:
                self.logger.warning(f"清理文件失败 {state_file}: {e}")
        
        return cleaned_count
