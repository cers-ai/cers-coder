"""
PM智能体 - 项目管理智能体，负责任务分解、进度控制和智能体协调
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..core.base_agent import AgentCapability, AgentConfig, BaseAgent
from ..core.file_parser import FileParser, ProjectRequirements
from ..core.message import Message, MessageType, create_task_message
from ..core.operation_recorder import OperationRecorder, OperationType
from ..core.state_manager import StateManager
from ..core.workflow import TaskDefinition, WorkflowController, WorkflowPhase


class PMAgent(BaseAgent):
    """项目管理智能体"""

    def __init__(self, state_manager: StateManager, workflow_controller: WorkflowController,
                 operation_recorder: Optional[OperationRecorder] = None):
        config = AgentConfig(
            name="PM智能体",
            description="项目管理智能体，负责任务分解、进度控制和智能体协调",
            capabilities=[AgentCapability.MANAGEMENT],
            max_concurrent_tasks=5,
            timeout=600
        )
        super().__init__(config, operation_recorder)

        self.state_manager = state_manager
        self.workflow_controller = workflow_controller
        self.file_parser = FileParser()

        # PM状态
        self.project_requirements: Optional[ProjectRequirements] = None
        self.current_phase = WorkflowPhase.INITIALIZATION
        self.task_progress: Dict[str, float] = {}

    async def _initialize(self) -> None:
        """初始化PM智能体"""
        self.logger.info("PM智能体初始化")
        await self._load_project_state()

    async def _load_project_state(self) -> None:
        """加载项目状态"""
        current_state = self.state_manager.get_current_state()
        if current_state:
            self.logger.info(f"加载现有项目状态: {current_state.name}")
            # 从状态中恢复需求信息
            if current_state.requirements:
                self.project_requirements = ProjectRequirements(**current_state.requirements)
        else:
            self.logger.info("没有现有项目状态，将创建新项目")

    async def _handle_task_create(self, message: Message) -> Optional[Message]:
        """处理任务创建消息"""
        task_type = message.content.get("task_type", "")
        
        if task_type == "initialize_project":
            return await self._handle_initialize_project(message)
        elif task_type == "parse_requirements":
            return await self._handle_parse_requirements(message)
        elif task_type == "create_workflow":
            return await self._handle_create_workflow(message)
        elif task_type == "monitor_progress":
            return await self._handle_monitor_progress(message)
        else:
            return await self._handle_generic_task(message)

    async def _handle_agent_request(self, message: Message) -> Optional[Message]:
        """处理智能体请求消息"""
        request_type = message.content.get("request_type", "")
        
        if request_type == "get_requirements":
            return await self._handle_get_requirements(message)
        elif request_type == "report_progress":
            return await self._handle_report_progress(message)
        elif request_type == "request_approval":
            return await self._handle_request_approval(message)
        else:
            return message.create_reply(
                sender=self.name,
                subject="未知请求类型",
                content={"error": f"未知请求类型: {request_type}"}
            )

    async def _handle_initialize_project(self, message: Message) -> Optional[Message]:
        """处理项目初始化"""
        try:
            self.logger.info("开始项目初始化")
            
            # 解析输入文件
            parsed_files, missing_files = await self.file_parser.parse_all_files()
            
            if missing_files:
                error_msg = f"缺少必需文件: {', '.join(missing_files)}"
                self.logger.error(error_msg)
                return message.create_reply(
                    sender=self.name,
                    subject="项目初始化失败",
                    content={"error": error_msg, "missing_files": missing_files}
                )
            
            # 提取项目需求
            self.project_requirements = await self.file_parser.extract_requirements(parsed_files)
            
            # 验证需求完整性
            validation_issues = self.file_parser.validate_requirements(self.project_requirements)
            if validation_issues:
                self.logger.warning(f"需求验证发现问题: {validation_issues}")
            
            # 创建项目状态
            project_state = await self.state_manager.create_project(
                name=self.project_requirements.name,
                description=self.project_requirements.description
            )
            
            # 保存需求信息到状态
            project_state.requirements = self.project_requirements.model_dump()
            project_state.input_files = {
                filename: content.content 
                for filename, content in parsed_files.items() 
                if content.exists
            }
            await self.state_manager.save_state()
            
            self.logger.info(f"项目初始化完成: {self.project_requirements.name}")
            
            return message.create_reply(
                sender=self.name,
                subject="项目初始化完成",
                content={
                    "project_name": self.project_requirements.name,
                    "project_id": project_state.id,
                    "requirements": self.project_requirements.model_dump(),
                    "validation_issues": validation_issues
                }
            )
            
        except Exception as e:
            self.logger.error(f"项目初始化失败: {e}", exc_info=True)
            return message.create_reply(
                sender=self.name,
                subject="项目初始化失败",
                content={"error": str(e)}
            )

    async def _handle_parse_requirements(self, message: Message) -> Optional[Message]:
        """处理需求解析"""
        if not self.project_requirements:
            return message.create_reply(
                sender=self.name,
                subject="需求解析失败",
                content={"error": "项目未初始化"}
            )
        
        # 分析需求并生成任务计划
        task_plan = await self._create_task_plan()
        
        return message.create_reply(
            sender=self.name,
            subject="需求解析完成",
            content={
                "requirements": self.project_requirements.model_dump(),
                "task_plan": task_plan
            }
        )

    async def _handle_create_workflow(self, message: Message) -> Optional[Message]:
        """处理工作流创建"""
        try:
            # 创建工作流任务
            tasks = await self._create_detailed_workflow()
            
            # 将任务添加到工作流控制器
            for task in tasks:
                self.workflow_controller.tasks[task.id] = task
            
            self.logger.info(f"创建工作流，包含 {len(tasks)} 个任务")
            
            return message.create_reply(
                sender=self.name,
                subject="工作流创建完成",
                content={
                    "task_count": len(tasks),
                    "phases": list(set(task.phase.value for task in tasks)),
                    "tasks": [
                        {
                            "id": task.id,
                            "name": task.name,
                            "phase": task.phase.value,
                            "agent_type": task.agent_type
                        }
                        for task in tasks
                    ]
                }
            )
            
        except Exception as e:
            self.logger.error(f"创建工作流失败: {e}", exc_info=True)
            return message.create_reply(
                sender=self.name,
                subject="工作流创建失败",
                content={"error": str(e)}
            )

    async def _handle_monitor_progress(self, message: Message) -> Optional[Message]:
        """处理进度监控"""
        workflow_status = self.workflow_controller.get_workflow_status()
        
        # 更新项目状态
        current_state = self.state_manager.get_current_state()
        if current_state:
            current_state.update_progress(workflow_status["progress"])
            await self.state_manager.save_state()
        
        return message.create_reply(
            sender=self.name,
            subject="进度报告",
            content=workflow_status
        )

    async def _handle_get_requirements(self, message: Message) -> Optional[Message]:
        """处理获取需求请求"""
        if not self.project_requirements:
            return message.create_reply(
                sender=self.name,
                subject="需求信息",
                content={"error": "项目需求未加载"}
            )
        
        return message.create_reply(
            sender=self.name,
            subject="需求信息",
            content={"requirements": self.project_requirements.model_dump()}
        )

    async def _handle_report_progress(self, message: Message) -> Optional[Message]:
        """处理进度报告"""
        agent_name = message.sender
        progress_data = message.content.get("progress", {})
        
        # 更新任务进度
        task_id = progress_data.get("task_id")
        progress = progress_data.get("progress", 0)
        
        if task_id:
            self.task_progress[task_id] = progress
            self.logger.info(f"更新任务进度: {task_id} -> {progress}%")
        
        # 更新智能体状态
        await self.state_manager.update_agent_status(agent_name, progress_data)
        
        return message.create_reply(
            sender=self.name,
            subject="进度已记录",
            content={"status": "acknowledged"}
        )

    async def _handle_request_approval(self, message: Message) -> Optional[Message]:
        """处理审批请求"""
        approval_type = message.content.get("approval_type", "")
        details = message.content.get("details", {})
        
        # 简化的自动审批逻辑
        approved = await self._evaluate_approval_request(approval_type, details)
        
        return message.create_reply(
            sender=self.name,
            subject="审批结果",
            content={
                "approved": approved,
                "approval_type": approval_type,
                "reason": "自动审批" if approved else "需要人工审核"
            }
        )

    async def _handle_generic_task(self, message: Message) -> Optional[Message]:
        """处理通用任务"""
        self.logger.info(f"处理通用任务: {message.subject}")
        
        # 记录任务
        task_info = {
            "id": str(message.id),
            "name": message.subject,
            "description": message.content.get("description", ""),
            "sender": message.sender,
            "created_at": datetime.now().isoformat()
        }
        
        current_state = self.state_manager.get_current_state()
        if current_state:
            await self.state_manager.add_task(task_info)
        
        return message.create_reply(
            sender=self.name,
            subject="任务已接收",
            content={"task_id": str(message.id), "status": "acknowledged"}
        )

    async def _create_task_plan(self) -> Dict[str, Any]:
        """创建任务计划"""
        if not self.project_requirements:
            return {}
        
        plan = {
            "phases": [],
            "estimated_duration": "待评估",
            "key_milestones": [],
            "risk_factors": []
        }
        
        # 根据需求分析创建阶段计划
        phases = [
            {"name": "需求分析", "duration": "1-2天", "deliverables": ["需求文档", "功能模型"]},
            {"name": "架构设计", "duration": "2-3天", "deliverables": ["架构图", "接口定义"]},
            {"name": "代码开发", "duration": "5-10天", "deliverables": ["源代码", "单元测试"]},
            {"name": "测试验证", "duration": "2-3天", "deliverables": ["测试报告", "bug修复"]},
            {"name": "构建部署", "duration": "1-2天", "deliverables": ["构建脚本", "部署配置"]},
            {"name": "文档生成", "duration": "1-2天", "deliverables": ["API文档", "用户手册"]},
            {"name": "最终审查", "duration": "1天", "deliverables": ["审查报告", "优化建议"]}
        ]
        
        plan["phases"] = phases
        plan["estimated_duration"] = "13-23天"
        
        return plan

    async def _create_detailed_workflow(self) -> List[TaskDefinition]:
        """创建详细的工作流任务"""
        tasks = []
        
        if not self.project_requirements:
            return self.workflow_controller.create_default_workflow()
        
        # 根据项目需求定制任务
        # 这里可以根据具体需求动态生成任务
        base_tasks = self.workflow_controller.create_default_workflow()
        
        # 可以根据项目特点调整任务
        for task in base_tasks:
            # 根据项目需求调整任务参数
            if self.project_requirements.name:
                task.inputs["project_name"] = self.project_requirements.name
            if self.project_requirements.description:
                task.inputs["project_description"] = self.project_requirements.description
            
            tasks.append(task)
        
        return tasks

    async def _evaluate_approval_request(self, approval_type: str, details: Dict[str, Any]) -> bool:
        """评估审批请求"""
        # 简化的审批逻辑
        if approval_type == "architecture_change":
            # 架构变更需要更严格的审批
            return False
        elif approval_type == "code_review":
            # 代码审查通常自动通过
            return True
        elif approval_type == "deployment":
            # 部署需要检查测试结果
            test_passed = details.get("test_passed", False)
            return test_passed
        else:
            # 默认需要人工审核
            return False

    def get_project_overview(self) -> Dict[str, Any]:
        """获取项目概览"""
        if not self.project_requirements:
            return {"error": "项目未初始化"}
        
        current_state = self.state_manager.get_current_state()
        workflow_status = self.workflow_controller.get_workflow_status()
        
        return {
            "project_name": self.project_requirements.name,
            "project_description": self.project_requirements.description,
            "current_phase": self.current_phase.value,
            "progress": workflow_status.get("progress", 0),
            "total_tasks": workflow_status.get("total_tasks", 0),
            "completed_tasks": workflow_status.get("completed_tasks", 0),
            "running_tasks": workflow_status.get("running_tasks", 0),
            "agents_count": len(self.workflow_controller.agents),
            "last_updated": current_state.updated_at.isoformat() if current_state else None
        }
