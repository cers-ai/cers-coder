"""
工作空间管理器 - 为每个项目创建独立的工作目录，类似Claude Code的项目管理方式
"""

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

import aiofiles
from pydantic import BaseModel, Field

from .operation_recorder import OperationRecorder, OperationType


class WorkspaceConfig(BaseModel):
    """工作空间配置"""
    id: str = Field(default_factory=lambda: str(uuid4()), description="工作空间ID")
    name: str = Field(..., description="工作空间名称")
    description: str = Field(default="", description="工作空间描述")
    
    # 路径配置
    workspace_path: str = Field(..., description="工作空间路径")
    
    # 项目信息
    project_type: str = Field(default="general", description="项目类型")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    last_accessed: datetime = Field(default_factory=datetime.now, description="最后访问时间")
    
    # 配置选项
    auto_backup: bool = Field(default=True, description="自动备份")
    max_backups: int = Field(default=10, description="最大备份数量")
    
    # 元数据
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    tags: List[str] = Field(default_factory=list, description="标签")


class WorkspaceStructure:
    """工作空间目录结构定义"""
    
    # 标准目录结构
    STANDARD_DIRS = {
        "input": "输入文件目录",
        "output": "输出文件目录", 
        "state": "状态文件目录",
        "records": "操作记录目录",
        "memory": "记忆文件目录",
        "logs": "日志文件目录",
        "temp": "临时文件目录",
        "backup": "备份文件目录"
    }
    
    # 输出子目录
    OUTPUT_SUBDIRS = {
        "src": "源代码",
        "test": "测试代码",
        "docs": "文档",
        "build": "构建产物",
        "review": "审查报告"
    }
    
    # 标准文件
    STANDARD_FILES = {
        "workspace.json": "工作空间配置文件",
        "project.json": "项目配置文件",
        "README.md": "项目说明文件"
    }


class WorkspaceManager:
    """工作空间管理器"""
    
    def __init__(self, base_workspace_dir: str = "./workspaces"):
        self.base_workspace_dir = Path(base_workspace_dir)
        self.base_workspace_dir.mkdir(parents=True, exist_ok=True)
        
        # 工作空间索引文件
        self.index_file = self.base_workspace_dir / "workspaces.json"
        
        # 当前活跃的工作空间
        self.current_workspace: Optional[WorkspaceConfig] = None
        self.current_workspace_path: Optional[Path] = None
        
        # 日志器
        self.logger = logging.getLogger("workspace_manager")
        
        # 操作记录器
        self.operation_recorder: Optional[OperationRecorder] = None

    async def create_workspace(
        self,
        name: str,
        description: str = "",
        project_type: str = "general",
        template: Optional[str] = None
    ) -> WorkspaceConfig:
        """创建新的工作空间"""
        
        # 生成工作空间ID和路径
        workspace_id = str(uuid4())
        workspace_path = self.base_workspace_dir / workspace_id
        
        # 创建工作空间配置
        config = WorkspaceConfig(
            id=workspace_id,
            name=name,
            description=description,
            workspace_path=str(workspace_path),
            project_type=project_type
        )
        
        # 创建目录结构
        await self._create_workspace_structure(workspace_path, template)
        
        # 保存工作空间配置
        await self._save_workspace_config(workspace_path, config)
        
        # 更新索引
        await self._update_workspace_index(config)
        
        self.logger.info(f"创建工作空间: {name} ({workspace_id})")
        return config

    async def _create_workspace_structure(self, workspace_path: Path, template: Optional[str] = None) -> None:
        """创建工作空间目录结构"""
        
        # 创建主目录
        workspace_path.mkdir(parents=True, exist_ok=True)
        
        # 创建标准目录
        for dir_name, description in WorkspaceStructure.STANDARD_DIRS.items():
            dir_path = workspace_path / dir_name
            dir_path.mkdir(exist_ok=True)
            
            # 创建目录说明文件
            readme_path = dir_path / ".gitkeep"
            readme_path.write_text(f"# {description}\n", encoding='utf-8')
        
        # 创建输出子目录
        output_dir = workspace_path / "output"
        for subdir_name, description in WorkspaceStructure.OUTPUT_SUBDIRS.items():
            subdir_path = output_dir / subdir_name
            subdir_path.mkdir(exist_ok=True)
            
            readme_path = subdir_path / ".gitkeep"
            readme_path.write_text(f"# {description}\n", encoding='utf-8')
        
        # 创建标准文件
        await self._create_standard_files(workspace_path, template)

    async def _create_standard_files(self, workspace_path: Path, template: Optional[str] = None) -> None:
        """创建标准文件"""
        
        # 创建README.md
        readme_content = f"""# 项目工作空间

这是一个CERS Coder项目工作空间。

## 目录结构

- `input/` - 输入文件目录（放置0.request.md等需求文件）
- `output/` - 输出文件目录
  - `src/` - 生成的源代码
  - `test/` - 生成的测试代码
  - `docs/` - 生成的文档
  - `build/` - 构建产物
  - `review/` - 审查报告
- `state/` - 项目状态文件
- `records/` - 操作记录
- `memory/` - 智能体记忆
- `logs/` - 日志文件
- `temp/` - 临时文件
- `backup/` - 备份文件

## 使用方法

1. 将项目需求文件放入 `input/` 目录
2. 在工作空间根目录运行 `cers-coder start`
3. 查看 `output/` 目录中的生成结果

创建时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        readme_path = workspace_path / "README.md"
        async with aiofiles.open(readme_path, 'w', encoding='utf-8') as f:
            await f.write(readme_content)
        
        # 如果指定了模板，复制模板文件
        if template:
            await self._apply_template(workspace_path, template)

    async def _apply_template(self, workspace_path: Path, template: str) -> None:
        """应用项目模板"""
        template_dir = Path(__file__).parent.parent / "templates" / template
        
        if template_dir.exists():
            # 复制模板文件到input目录
            input_dir = workspace_path / "input"
            for template_file in template_dir.glob("*.md"):
                target_file = input_dir / template_file.name
                shutil.copy2(template_file, target_file)
            
            self.logger.info(f"应用模板: {template}")

    async def _save_workspace_config(self, workspace_path: Path, config: WorkspaceConfig) -> None:
        """保存工作空间配置"""
        config_file = workspace_path / "workspace.json"
        config_data = config.model_dump(mode='json')
        
        async with aiofiles.open(config_file, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(config_data, indent=2, ensure_ascii=False))

    async def _update_workspace_index(self, config: WorkspaceConfig) -> None:
        """更新工作空间索引"""
        index_data = await self._load_workspace_index()
        
        index_data[config.id] = {
            "id": config.id,
            "name": config.name,
            "description": config.description,
            "workspace_path": config.workspace_path,
            "project_type": config.project_type,
            "created_at": config.created_at.isoformat(),
            "last_accessed": config.last_accessed.isoformat()
        }
        
        async with aiofiles.open(self.index_file, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(index_data, indent=2, ensure_ascii=False))

    async def _load_workspace_index(self) -> Dict[str, Any]:
        """加载工作空间索引"""
        if not self.index_file.exists():
            return {}
        
        try:
            async with aiofiles.open(self.index_file, 'r', encoding='utf-8') as f:
                content = await f.read()
                return json.loads(content)
        except Exception as e:
            self.logger.error(f"加载工作空间索引失败: {e}")
            return {}

    async def list_workspaces(self) -> List[Dict[str, Any]]:
        """列出所有工作空间"""
        index_data = await self._load_workspace_index()
        
        workspaces = []
        for workspace_info in index_data.values():
            # 检查工作空间是否仍然存在
            workspace_path = Path(workspace_info["workspace_path"])
            if workspace_path.exists():
                workspaces.append(workspace_info)
        
        # 按最后访问时间排序
        workspaces.sort(key=lambda x: x["last_accessed"], reverse=True)
        return workspaces

    async def load_workspace(self, workspace_id: str) -> Optional[WorkspaceConfig]:
        """加载工作空间"""
        index_data = await self._load_workspace_index()
        
        if workspace_id not in index_data:
            self.logger.error(f"工作空间不存在: {workspace_id}")
            return None
        
        workspace_info = index_data[workspace_id]
        workspace_path = Path(workspace_info["workspace_path"])
        
        if not workspace_path.exists():
            self.logger.error(f"工作空间目录不存在: {workspace_path}")
            return None
        
        # 加载配置文件
        config_file = workspace_path / "workspace.json"
        if not config_file.exists():
            self.logger.error(f"工作空间配置文件不存在: {config_file}")
            return None
        
        try:
            async with aiofiles.open(config_file, 'r', encoding='utf-8') as f:
                content = await f.read()
                config_data = json.loads(content)
                config = WorkspaceConfig(**config_data)
            
            # 更新最后访问时间
            config.last_accessed = datetime.now()
            await self._save_workspace_config(workspace_path, config)
            await self._update_workspace_index(config)
            
            # 设置为当前工作空间
            self.current_workspace = config
            self.current_workspace_path = workspace_path
            
            # 初始化操作记录器
            self.operation_recorder = OperationRecorder(
                workspace_dir=str(workspace_path),
                project_id=workspace_id
            )
            
            self.logger.info(f"加载工作空间: {config.name} ({workspace_id})")
            return config
            
        except Exception as e:
            self.logger.error(f"加载工作空间配置失败: {e}")
            return None

    async def delete_workspace(self, workspace_id: str, force: bool = False) -> bool:
        """删除工作空间"""
        index_data = await self._load_workspace_index()
        
        if workspace_id not in index_data:
            self.logger.error(f"工作空间不存在: {workspace_id}")
            return False
        
        workspace_info = index_data[workspace_id]
        workspace_path = Path(workspace_info["workspace_path"])
        
        try:
            # 创建备份（如果不是强制删除）
            if not force and workspace_path.exists():
                backup_name = f"deleted_{workspace_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                backup_path = self.base_workspace_dir / "deleted" / backup_name
                backup_path.parent.mkdir(exist_ok=True)
                shutil.move(str(workspace_path), str(backup_path))
                self.logger.info(f"工作空间已备份到: {backup_path}")
            else:
                # 直接删除
                if workspace_path.exists():
                    shutil.rmtree(workspace_path)
            
            # 从索引中移除
            del index_data[workspace_id]
            async with aiofiles.open(self.index_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(index_data, indent=2, ensure_ascii=False))
            
            self.logger.info(f"删除工作空间: {workspace_info['name']} ({workspace_id})")
            return True
            
        except Exception as e:
            self.logger.error(f"删除工作空间失败: {e}")
            return False

    def get_current_workspace(self) -> Optional[WorkspaceConfig]:
        """获取当前工作空间"""
        return self.current_workspace

    def get_current_workspace_path(self) -> Optional[Path]:
        """获取当前工作空间路径"""
        return self.current_workspace_path

    def get_input_dir(self) -> Optional[Path]:
        """获取输入目录"""
        if self.current_workspace_path:
            return self.current_workspace_path / "input"
        return None

    def get_output_dir(self) -> Optional[Path]:
        """获取输出目录"""
        if self.current_workspace_path:
            return self.current_workspace_path / "output"
        return None

    def get_state_dir(self) -> Optional[Path]:
        """获取状态目录"""
        if self.current_workspace_path:
            return self.current_workspace_path / "state"
        return None

    def get_logs_dir(self) -> Optional[Path]:
        """获取日志目录"""
        if self.current_workspace_path:
            return self.current_workspace_path / "logs"
        return None

    async def create_backup(self, backup_name: Optional[str] = None) -> Optional[str]:
        """创建工作空间备份"""
        if not self.current_workspace or not self.current_workspace_path:
            return None
        
        if not backup_name:
            backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        backup_dir = self.current_workspace_path / "backup"
        backup_dir.mkdir(exist_ok=True)
        
        backup_path = backup_dir / backup_name
        
        try:
            # 创建备份（排除backup目录本身）
            shutil.copytree(
                self.current_workspace_path,
                backup_path,
                ignore=shutil.ignore_patterns("backup", "temp", "*.tmp")
            )
            
            self.logger.info(f"创建备份: {backup_path}")
            return str(backup_path)
            
        except Exception as e:
            self.logger.error(f"创建备份失败: {e}")
            return None

    async def restore_backup(self, backup_name: str) -> bool:
        """恢复备份"""
        if not self.current_workspace_path:
            return False
        
        backup_path = self.current_workspace_path / "backup" / backup_name
        
        if not backup_path.exists():
            self.logger.error(f"备份不存在: {backup_path}")
            return False
        
        try:
            # 创建当前状态的备份
            current_backup = await self.create_backup("before_restore")
            
            # 恢复备份（排除backup目录）
            for item in backup_path.iterdir():
                if item.name == "backup":
                    continue
                
                target = self.current_workspace_path / item.name
                if target.exists():
                    if target.is_dir():
                        shutil.rmtree(target)
                    else:
                        target.unlink()
                
                if item.is_dir():
                    shutil.copytree(item, target)
                else:
                    shutil.copy2(item, target)
            
            self.logger.info(f"恢复备份: {backup_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"恢复备份失败: {e}")
            return False
