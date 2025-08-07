"""
服务管理器 - 管理系统各个组件的生命周期，提供优雅降级机制
"""

import asyncio
import logging
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass

from rich.console import Console
from rich.panel import Panel
from rich.table import Table


class ServiceStatus(str, Enum):
    """服务状态"""
    UNKNOWN = "unknown"
    STARTING = "starting"
    RUNNING = "running"
    DEGRADED = "degraded"  # 降级运行
    STOPPED = "stopped"
    FAILED = "failed"


class ServiceLevel(str, Enum):
    """服务级别"""
    CORE = "core"        # 核心服务，必须运行
    ENHANCED = "enhanced"  # 增强服务，可选
    OPTIONAL = "optional"  # 可选服务


@dataclass
class ServiceInfo:
    """服务信息"""
    name: str
    level: ServiceLevel
    status: ServiceStatus = ServiceStatus.UNKNOWN
    error_message: Optional[str] = None
    dependencies: List[str] = None
    health_check: Optional[callable] = None
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


class ServiceManager:
    """服务管理器"""
    
    def __init__(self):
        self.console = Console()
        self.logger = logging.getLogger("service_manager")
        
        # 服务注册表
        self.services: Dict[str, ServiceInfo] = {}
        self.service_instances: Dict[str, Any] = {}
        
        # 系统状态
        self.system_status = ServiceStatus.UNKNOWN
        self.failed_services: Set[str] = set()
        self.degraded_services: Set[str] = set()

    def register_service(
        self,
        name: str,
        level: ServiceLevel,
        dependencies: Optional[List[str]] = None,
        health_check: Optional[callable] = None
    ) -> None:
        """注册服务"""
        self.services[name] = ServiceInfo(
            name=name,
            level=level,
            dependencies=dependencies or [],
            health_check=health_check
        )
        self.logger.debug(f"注册服务: {name} ({level.value})")

    async def start_all_services(self) -> bool:
        """启动所有服务"""
        self.console.print(Panel.fit("🚀 启动系统服务", style="bold blue"))
        
        # 按依赖顺序启动服务
        start_order = self._get_start_order()
        
        for service_name in start_order:
            await self._start_service(service_name)
        
        # 评估系统状态
        self._evaluate_system_status()
        
        # 显示启动结果
        self._display_startup_summary()
        
        return self.system_status in [ServiceStatus.RUNNING, ServiceStatus.DEGRADED]

    async def _start_service(self, service_name: str) -> bool:
        """启动单个服务"""
        service = self.services.get(service_name)
        if not service:
            self.logger.error(f"服务不存在: {service_name}")
            return False
        
        try:
            service.status = ServiceStatus.STARTING
            self.console.print(f"启动服务: {service_name}...", end="")
            
            # 检查依赖
            for dep in service.dependencies:
                dep_service = self.services.get(dep)
                if not dep_service or dep_service.status != ServiceStatus.RUNNING:
                    if service.level == ServiceLevel.CORE:
                        raise Exception(f"核心服务依赖失败: {dep}")
                    else:
                        service.status = ServiceStatus.DEGRADED
                        self.degraded_services.add(service_name)
                        self.console.print(" ⚠️  降级运行", style="yellow")
                        return True
            
            # 启动服务
            success = await self._initialize_service(service_name)
            
            if success:
                service.status = ServiceStatus.RUNNING
                self.console.print(" ✅", style="green")
                return True
            else:
                raise Exception("服务初始化失败")
                
        except Exception as e:
            service.status = ServiceStatus.FAILED
            service.error_message = str(e)
            self.failed_services.add(service_name)
            
            if service.level == ServiceLevel.CORE:
                self.console.print(f" ❌ {e}", style="red")
                return False
            else:
                self.console.print(f" ⚠️  跳过 ({e})", style="yellow")
                return True

    async def _initialize_service(self, service_name: str) -> bool:
        """初始化具体服务"""
        try:
            if service_name == "workspace_manager":
                from ..core.workspace_manager import WorkspaceManager
                self.service_instances[service_name] = WorkspaceManager()
                return True
                
            elif service_name == "ollama_client":
                from ..llm.ollama_client import OllamaClient
                import os
                client = OllamaClient(host=os.getenv("OLLAMA_HOST", "http://localhost:11434"))
                # 健康检查
                if await client.health_check():
                    self.service_instances[service_name] = client
                    return True
                else:
                    return False
                    
            elif service_name == "model_config_manager":
                from ..llm.model_config import ModelConfigManager
                self.service_instances[service_name] = ModelConfigManager()
                return True
                
            elif service_name == "state_manager":
                from ..core.state_manager import StateManager
                import os
                state_dir = os.getenv("STATE_DIR", "./state")
                # 确保目录存在
                import pathlib
                pathlib.Path(state_dir).mkdir(parents=True, exist_ok=True)
                self.service_instances[service_name] = StateManager(state_dir=state_dir)
                return True
                
            elif service_name == "workflow_controller":
                from ..core.workflow import WorkflowController
                state_manager = self.service_instances.get("state_manager")
                if state_manager:
                    self.service_instances[service_name] = WorkflowController(state_manager)
                    return True
                return False
                
            else:
                self.logger.warning(f"未知服务: {service_name}")
                return False
                
        except Exception as e:
            self.logger.error(f"初始化服务失败 {service_name}: {e}")
            return False

    def _get_start_order(self) -> List[str]:
        """获取服务启动顺序（拓扑排序）"""
        # 简化的拓扑排序
        visited = set()
        order = []
        
        def visit(service_name: str):
            if service_name in visited:
                return
            visited.add(service_name)
            
            service = self.services.get(service_name)
            if service:
                for dep in service.dependencies:
                    if dep in self.services:
                        visit(dep)
                order.append(service_name)
        
        # 按服务级别排序，核心服务优先
        core_services = [name for name, service in self.services.items() 
                        if service.level == ServiceLevel.CORE]
        enhanced_services = [name for name, service in self.services.items() 
                           if service.level == ServiceLevel.ENHANCED]
        optional_services = [name for name, service in self.services.items() 
                           if service.level == ServiceLevel.OPTIONAL]
        
        for service_name in core_services + enhanced_services + optional_services:
            visit(service_name)
        
        return order

    def _evaluate_system_status(self) -> None:
        """评估系统状态"""
        core_services = [name for name, service in self.services.items() 
                        if service.level == ServiceLevel.CORE]
        
        # 检查核心服务
        core_failed = any(name in self.failed_services for name in core_services)
        
        if core_failed:
            self.system_status = ServiceStatus.FAILED
        elif self.failed_services or self.degraded_services:
            self.system_status = ServiceStatus.DEGRADED
        else:
            self.system_status = ServiceStatus.RUNNING

    def _display_startup_summary(self) -> None:
        """显示启动摘要"""
        table = Table(title="🔧 系统服务状态")
        table.add_column("服务名称", style="cyan")
        table.add_column("级别", style="blue")
        table.add_column("状态", style="green")
        table.add_column("说明", style="yellow")
        
        for name, service in self.services.items():
            status_icon = {
                ServiceStatus.RUNNING: "✅ 运行中",
                ServiceStatus.DEGRADED: "⚠️  降级",
                ServiceStatus.FAILED: "❌ 失败",
                ServiceStatus.STOPPED: "⏹️  停止"
            }.get(service.status, "❓ 未知")
            
            description = service.error_message if service.error_message else "正常"
            
            table.add_row(
                name,
                service.level.value,
                status_icon,
                description[:50] + "..." if len(description) > 50 else description
            )
        
        self.console.print(table)
        
        # 系统状态摘要
        if self.system_status == ServiceStatus.RUNNING:
            self.console.print("🎉 系统启动成功，所有功能可用！", style="bold green")
        elif self.system_status == ServiceStatus.DEGRADED:
            self.console.print("⚠️  系统以降级模式运行，部分功能受限", style="bold yellow")
            self.console.print("💡 建议检查失败的服务并修复", style="yellow")
        else:
            self.console.print("❌ 系统启动失败，核心功能不可用", style="bold red")

    def get_service(self, service_name: str) -> Optional[Any]:
        """获取服务实例"""
        return self.service_instances.get(service_name)

    def is_service_available(self, service_name: str) -> bool:
        """检查服务是否可用"""
        service = self.services.get(service_name)
        return service and service.status == ServiceStatus.RUNNING

    def get_system_status(self) -> ServiceStatus:
        """获取系统状态"""
        return self.system_status

    async def health_check(self) -> Dict[str, Any]:
        """系统健康检查"""
        health_info = {
            "system_status": self.system_status.value,
            "services": {},
            "recommendations": []
        }
        
        for name, service in self.services.items():
            service_health = {
                "status": service.status.value,
                "level": service.level.value,
                "error": service.error_message
            }
            
            # 执行健康检查
            if service.health_check and service.status == ServiceStatus.RUNNING:
                try:
                    service_health["health_check"] = await service.health_check()
                except Exception as e:
                    service_health["health_check"] = f"检查失败: {e}"
            
            health_info["services"][name] = service_health
        
        # 生成建议
        if self.failed_services and "ollama_client" in self.failed_services:
            health_info["recommendations"].append(
                "Ollama服务不可用，请启动Ollama服务以使用AI功能"
            )
        
        if self.system_status == ServiceStatus.DEGRADED:
            health_info["recommendations"].append(
                "系统运行在降级模式，建议修复失败的服务"
            )
        
        return health_info

    async def stop_all_services(self) -> None:
        """停止所有服务"""
        self.console.print("🛑 停止系统服务...")
        
        for name, service in self.services.items():
            if service.status == ServiceStatus.RUNNING:
                service.status = ServiceStatus.STOPPED
                # 这里可以添加具体的停止逻辑
        
        self.service_instances.clear()
        self.system_status = ServiceStatus.STOPPED
