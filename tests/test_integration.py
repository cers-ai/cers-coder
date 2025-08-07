"""
集成测试
"""

import asyncio
import pytest
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from src.cers_coder.core.state_manager import StateManager
from src.cers_coder.core.workflow import WorkflowController
from src.cers_coder.core.file_parser import FileParser
from src.cers_coder.agents.pm_agent import PMAgent
from src.cers_coder.llm.ollama_client import OllamaClient


class TestSystemIntegration:
    """系统集成测试"""
    
    @pytest.fixture
    def temp_dir(self):
        """临时目录fixture"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def sample_project_files(self, temp_dir):
        """创建示例项目文件"""
        # 创建0.request.md
        request_content = """# 示例项目需求

## 🧱 项目名称
简单计算器应用

## 🎯 项目目标
开发一个支持基本数学运算的计算器应用

## 🔧 系统特性与设计原则
* **基本运算**: 支持加减乘除运算
* **用户友好**: 简洁的用户界面
* **错误处理**: 处理除零等异常情况

## 🧩 智能体构成与职责定义
| 智能体 | 职责 |
|--------|------|
| PM智能体 | 项目管理和协调 |
| 需求分析智能体 | 分析用户需求 |
| 架构设计智能体 | 设计系统架构 |
| 编码工程师智能体 | 实现核心功能 |

## 📦 项目输出要求
| 目录/文件 | 描述 |
|-----------|------|
| `out/src/` | 源代码文件 |
| `out/test/` | 测试脚本 |
| `out/docs/` | 项目文档 |
"""
        
        request_file = temp_dir / "0.request.md"
        request_file.write_text(request_content, encoding='utf-8')
        
        # 创建1.rule.md (可选)
        rule_content = """# 编码规范

## 代码风格
- 使用Python 3.12+
- 遵循PEP 8规范
- 使用类型注解

## 测试要求
- 代码覆盖率 > 80%
- 所有公共函数必须有测试
"""
        
        rule_file = temp_dir / "1.rule.md"
        rule_file.write_text(rule_content, encoding='utf-8')
        
        return temp_dir
    
    @pytest.fixture
    def mock_ollama_client(self):
        """模拟Ollama客户端"""
        client = AsyncMock(spec=OllamaClient)
        client.health_check.return_value = True
        client.generate.return_value = "模拟的LLM响应"
        client.list_models.return_value = []
        return client
    
    @pytest.fixture
    async def system_components(self, temp_dir, mock_ollama_client):
        """系统组件fixture"""
        # 创建状态管理器
        state_manager = StateManager(state_dir=str(temp_dir / "state"))
        
        # 创建工作流控制器
        workflow_controller = WorkflowController(state_manager)
        
        # 创建PM智能体
        pm_agent = PMAgent(state_manager, workflow_controller)
        
        # 注册智能体
        workflow_controller.register_agent("pm_agent", pm_agent)
        
        return {
            "state_manager": state_manager,
            "workflow_controller": workflow_controller,
            "pm_agent": pm_agent,
            "ollama_client": mock_ollama_client
        }
    
    @pytest.mark.asyncio
    async def test_file_parsing_integration(self, sample_project_files):
        """测试文件解析集成"""
        parser = FileParser(str(sample_project_files))
        
        # 解析所有文件
        parsed_files, missing_files = await parser.parse_all_files()
        
        # 验证解析结果
        assert "0.request.md" in parsed_files
        assert parsed_files["0.request.md"].exists
        assert len(missing_files) == 0  # 没有缺失必需文件
        
        # 提取需求
        requirements = await parser.extract_requirements(parsed_files)
        
        assert requirements.name == "简单计算器应用"
        assert "计算器应用" in requirements.description
        assert len(requirements.agents) >= 4
        assert len(requirements.outputs) >= 3
    
    @pytest.mark.asyncio
    async def test_state_management_integration(self, system_components):
        """测试状态管理集成"""
        state_manager = system_components["state_manager"]
        
        # 创建项目
        project = await state_manager.create_project(
            name="集成测试项目",
            description="测试状态管理集成"
        )
        
        assert project is not None
        assert project.name == "集成测试项目"
        
        # 更新项目状态
        project.update_progress(25.0)
        project.set_phase("design")
        await state_manager.save_state()
        
        # 验证状态保存
        current_state = state_manager.get_current_state()
        assert current_state.progress == 25.0
        assert current_state.current_phase == "design"
        
        # 测试项目列表
        projects = await state_manager.list_projects()
        assert len(projects) == 1
        assert projects[0]["name"] == "集成测试项目"
    
    @pytest.mark.asyncio
    async def test_workflow_integration(self, system_components):
        """测试工作流集成"""
        workflow_controller = system_components["workflow_controller"]
        
        # 创建默认工作流
        tasks = workflow_controller.create_default_workflow()
        
        assert len(tasks) > 0
        
        # 验证任务依赖关系
        task_names = [task.name for task in tasks]
        assert "解析输入文件" in task_names
        assert "需求分析" in task_names
        assert "系统架构设计" in task_names
        
        # 验证任务注册
        for task in tasks:
            assert task.id in workflow_controller.tasks
        
        # 获取工作流状态
        status = workflow_controller.get_workflow_status()
        assert "total_tasks" in status
        assert "completed_tasks" in status
        assert "progress" in status
    
    @pytest.mark.asyncio
    async def test_pm_agent_integration(self, system_components, sample_project_files):
        """测试PM智能体集成"""
        pm_agent = system_components["pm_agent"]
        state_manager = system_components["state_manager"]
        
        # 启动PM智能体
        await pm_agent.start()
        
        try:
            # 创建项目初始化消息
            from src.cers_coder.core.message import create_task_message
            
            init_message = create_task_message(
                sender="test",
                task_id="init_test",
                task_name="项目初始化测试",
                subject="初始化项目",
                content={
                    "task_type": "initialize_project",
                    "project_name": "测试项目"
                }
            )
            
            # 发送消息给PM智能体
            await pm_agent.send_message(init_message)
            
            # 等待处理
            await asyncio.sleep(0.1)
            
            # 验证项目状态
            current_state = state_manager.get_current_state()
            if current_state:
                assert current_state.name is not None
            
            # 获取项目概览
            overview = pm_agent.get_project_overview()
            assert "project_name" in overview or "error" in overview
            
        finally:
            # 停止PM智能体
            await pm_agent.stop()
    
    @pytest.mark.asyncio
    async def test_end_to_end_workflow(self, system_components, sample_project_files):
        """测试端到端工作流"""
        state_manager = system_components["state_manager"]
        workflow_controller = system_components["workflow_controller"]
        pm_agent = system_components["pm_agent"]
        
        # 1. 解析项目文件
        parser = FileParser(str(sample_project_files))
        parsed_files, missing_files = await parser.parse_all_files()
        
        assert len(missing_files) == 0
        
        # 2. 提取需求
        requirements = await parser.extract_requirements(parsed_files)
        
        assert requirements.name == "简单计算器应用"
        
        # 3. 创建项目状态
        project = await state_manager.create_project(
            name=requirements.name,
            description=requirements.description
        )
        
        # 保存需求到项目状态
        project.requirements = requirements.model_dump()
        await state_manager.save_state()
        
        # 4. 启动工作流
        await workflow_controller.start_workflow()
        
        try:
            # 5. 启动PM智能体
            await pm_agent.start()
            
            # 6. 验证系统状态
            workflow_status = workflow_controller.get_workflow_status()
            assert workflow_status["is_running"]
            
            pm_overview = pm_agent.get_project_overview()
            assert "project_name" in pm_overview or "error" in pm_overview
            
            # 7. 模拟一些工作流进度
            project.update_progress(10.0)
            await state_manager.save_state()
            
            # 验证进度更新
            updated_status = workflow_controller.get_workflow_status()
            assert "progress" in updated_status
            
        finally:
            # 清理
            await pm_agent.stop()
            await workflow_controller.stop_workflow()
    
    @pytest.mark.asyncio
    async def test_error_handling_integration(self, system_components):
        """测试错误处理集成"""
        pm_agent = system_components["pm_agent"]
        
        await pm_agent.start()
        
        try:
            # 发送无效消息
            from src.cers_coder.core.message import Message, MessageType
            
            invalid_message = Message(
                type=MessageType.TASK_CREATE,
                sender="test",
                subject="无效任务",
                content={"task_type": "invalid_task_type"}
            )
            
            # 处理消息
            response = await pm_agent.process_message(invalid_message)
            
            # 验证错误处理
            assert response is not None
            # 响应应该包含错误信息或处理结果
            
        finally:
            await pm_agent.stop()
    
    def test_configuration_integration(self, temp_dir):
        """测试配置集成"""
        # 测试环境变量配置
        import os
        
        # 设置测试环境变量
        os.environ["STATE_DIR"] = str(temp_dir / "test_state")
        os.environ["LOG_LEVEL"] = "DEBUG"
        
        # 创建状态管理器
        state_manager = StateManager()
        
        # 验证配置生效
        assert str(temp_dir / "test_state") in str(state_manager.state_dir)
        
        # 清理环境变量
        del os.environ["STATE_DIR"]
        del os.environ["LOG_LEVEL"]


class TestComponentInteraction:
    """组件交互测试"""
    
    @pytest.mark.asyncio
    async def test_message_flow(self):
        """测试消息流转"""
        from src.cers_coder.core.message import Message, MessageType
        
        # 创建消息链
        request = Message(
            type=MessageType.AGENT_REQUEST,
            sender="agent_a",
            subject="请求数据",
            content={"request": "get_status"}
        )
        
        response = request.create_reply(
            sender="agent_b",
            subject="状态数据",
            content={"status": "running"}
        )
        
        # 验证消息关联
        assert response.reply_to == request.id
        assert response.receiver == request.sender
        assert response.sender == "agent_b"
    
    @pytest.mark.asyncio
    async def test_state_synchronization(self):
        """测试状态同步"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # 创建两个状态管理器实例
            sm1 = StateManager(state_dir=temp_dir)
            sm2 = StateManager(state_dir=temp_dir)
            
            # 在第一个实例中创建项目
            project1 = await sm1.create_project("同步测试", "测试状态同步")
            project_id = project1.id
            
            # 在第二个实例中加载项目
            project2 = await sm2.load_project(project_id)
            
            assert project2 is not None
            assert project2.name == project1.name
            assert project2.id == project1.id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
