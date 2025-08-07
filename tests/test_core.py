"""
核心组件测试
"""

import asyncio
import pytest
from datetime import datetime
from pathlib import Path
import tempfile
import json

from src.cers_coder.core.message import Message, MessageType, MessagePriority
from src.cers_coder.core.state_manager import StateManager, ProjectState
from src.cers_coder.core.file_parser import FileParser


class TestMessage:
    """消息系统测试"""
    
    def test_message_creation(self):
        """测试消息创建"""
        message = Message(
            type=MessageType.TASK_CREATE,
            sender="test_sender",
            subject="测试消息",
            content={"key": "value"}
        )
        
        assert message.type == MessageType.TASK_CREATE
        assert message.sender == "test_sender"
        assert message.subject == "测试消息"
        assert message.content["key"] == "value"
        assert message.priority == MessagePriority.NORMAL
        assert not message.is_processed
    
    def test_message_reply(self):
        """测试消息回复"""
        original = Message(
            type=MessageType.AGENT_REQUEST,
            sender="agent_a",
            subject="请求",
            content={"request": "data"}
        )
        
        reply = original.create_reply(
            sender="agent_b",
            subject="回复",
            content={"response": "data"}
        )
        
        assert reply.type == MessageType.AGENT_RESPONSE
        assert reply.sender == "agent_b"
        assert reply.receiver == "agent_a"
        assert reply.reply_to == original.id
    
    def test_message_processing(self):
        """测试消息处理标记"""
        message = Message(
            type=MessageType.SYSTEM_STATUS,
            sender="system",
            subject="状态",
            content={}
        )
        
        assert not message.is_processed
        assert message.processed_at is None
        
        message.mark_processed()
        
        assert message.is_processed
        assert message.processed_at is not None
    
    def test_message_serialization(self):
        """测试消息序列化"""
        message = Message(
            type=MessageType.DATA_INPUT,
            sender="test",
            subject="数据",
            content={"data": [1, 2, 3]}
        )
        
        # 转换为字典
        data = message.to_dict()
        assert isinstance(data, dict)
        assert data["type"] == MessageType.DATA_INPUT
        assert data["sender"] == "test"
        
        # 从字典创建
        new_message = Message.from_dict(data)
        assert new_message.type == message.type
        assert new_message.sender == message.sender
        assert new_message.content == message.content


class TestStateManager:
    """状态管理器测试"""
    
    @pytest.fixture
    def temp_dir(self):
        """临时目录fixture"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.fixture
    def state_manager(self, temp_dir):
        """状态管理器fixture"""
        return StateManager(state_dir=temp_dir)
    
    @pytest.mark.asyncio
    async def test_create_project(self, state_manager):
        """测试项目创建"""
        project = await state_manager.create_project(
            name="测试项目",
            description="这是一个测试项目"
        )
        
        assert project.name == "测试项目"
        assert project.description == "这是一个测试项目"
        assert project.status == "initialized"
        assert project.progress == 0.0
        assert project.started_at is not None
    
    @pytest.mark.asyncio
    async def test_save_and_load_project(self, state_manager):
        """测试项目保存和加载"""
        # 创建项目
        original_project = await state_manager.create_project(
            name="保存测试项目",
            description="测试保存和加载功能"
        )
        
        # 修改项目状态
        original_project.update_progress(50.0)
        original_project.set_phase("coding")
        await state_manager.save_state()
        
        # 加载项目
        loaded_project = await state_manager.load_project(original_project.id)
        
        assert loaded_project is not None
        assert loaded_project.name == original_project.name
        assert loaded_project.progress == 50.0
        assert loaded_project.current_phase == "coding"
    
    @pytest.mark.asyncio
    async def test_checkpoint_operations(self, state_manager):
        """测试检查点操作"""
        # 创建项目
        project = await state_manager.create_project(
            name="检查点测试",
            description="测试检查点功能"
        )
        
        # 修改状态
        project.update_progress(30.0)
        await state_manager.save_state()
        
        # 创建检查点
        success = await state_manager.create_checkpoint("milestone_1")
        assert success
        
        # 继续修改状态
        project.update_progress(60.0)
        await state_manager.save_state()
        
        # 恢复检查点
        success = await state_manager.restore_checkpoint("milestone_1")
        assert success
        
        # 验证状态已恢复
        current_state = state_manager.get_current_state()
        assert current_state.progress == 30.0
    
    @pytest.mark.asyncio
    async def test_list_projects(self, state_manager):
        """测试项目列表"""
        # 创建多个项目
        await state_manager.create_project("项目1", "描述1")
        await state_manager.create_project("项目2", "描述2")
        
        # 获取项目列表
        projects = await state_manager.list_projects()
        
        assert len(projects) == 2
        project_names = [p["name"] for p in projects]
        assert "项目1" in project_names
        assert "项目2" in project_names


class TestFileParser:
    """文件解析器测试"""
    
    @pytest.fixture
    def temp_dir(self):
        """临时目录fixture"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def sample_request_file(self, temp_dir):
        """示例请求文件"""
        content = """# 测试项目需求

## 🧱 项目名称
测试智能助手

## 🎯 项目目标
开发一个简单的智能助手应用

## 🔧 系统特性与设计原则
* **智能对话**: 支持自然语言交互
* **任务管理**: 创建、编辑、删除任务

## 🧩 智能体构成与职责定义
| 智能体 | 职责 |
|--------|------|
| PM智能体 | 项目管理 |
| 需求分析智能体 | 需求分析 |

## 📦 项目输出要求
| 目录/文件 | 描述 |
|-----------|------|
| `out/src/` | 源代码 |
| `out/test/` | 测试代码 |
"""
        
        file_path = temp_dir / "0.request.md"
        file_path.write_text(content, encoding='utf-8')
        return file_path
    
    @pytest.mark.asyncio
    async def test_parse_markdown_file(self, temp_dir, sample_request_file):
        """测试Markdown文件解析"""
        parser = FileParser(str(temp_dir))
        content = await parser._parse_markdown_file(sample_request_file)
        
        assert content.filename == "0.request.md"
        assert content.exists
        assert len(content.sections) > 0
        assert "项目名称" in content.sections or "🧱 项目名称" in content.sections
        assert len(content.tables) >= 2  # 智能体表格和输出要求表格
    
    @pytest.mark.asyncio
    async def test_parse_all_files(self, temp_dir, sample_request_file):
        """测试解析所有文件"""
        parser = FileParser(str(temp_dir))
        parsed_files, missing_files = await parser.parse_all_files()
        
        # 应该找到0.request.md文件
        assert "0.request.md" in parsed_files
        assert parsed_files["0.request.md"].exists
        
        # 其他可选文件应该标记为缺失但不在missing_files中
        assert "1.rule.md" in parsed_files
        assert not parsed_files["1.rule.md"].exists
        assert "1.rule.md" not in missing_files  # 因为是可选的
    
    @pytest.mark.asyncio
    async def test_extract_requirements(self, temp_dir, sample_request_file):
        """测试需求提取"""
        parser = FileParser(str(temp_dir))
        parsed_files, _ = await parser.parse_all_files()
        
        requirements = await parser.extract_requirements(parsed_files)
        
        assert requirements.name == "测试智能助手"
        assert "智能助手应用" in requirements.description
        assert len(requirements.features) > 0
        assert len(requirements.agents) >= 2
        assert len(requirements.outputs) >= 2
    
    def test_extract_sections(self):
        """测试章节提取"""
        parser = FileParser()
        content = """# 标题1
内容1

## 标题2
内容2

### 标题3
内容3
"""
        
        sections = parser._extract_sections(content)
        
        assert "标题1" in sections
        assert "标题2" in sections
        assert "标题3" in sections
        assert "内容1" in sections["标题1"]
        assert "内容2" in sections["标题2"]
    
    def test_extract_tables(self):
        """测试表格提取"""
        parser = FileParser()
        content = """
| 列1 | 列2 | 列3 |
|-----|-----|-----|
| 值1 | 值2 | 值3 |
| 值4 | 值5 | 值6 |
"""
        
        tables = parser._extract_tables(content)
        
        assert len(tables) == 1
        table = tables[0]
        assert table["headers"] == ["列1", "列2", "列3"]
        assert len(table["rows"]) == 2
        assert table["rows"][0]["列1"] == "值1"
    
    def test_extract_lists(self):
        """测试列表提取"""
        parser = FileParser()
        content = """
* 项目1
* 项目2
* 项目3

1. 步骤1
2. 步骤2
3. 步骤3

- 选项A
- 选项B
"""
        
        lists = parser._extract_lists(content)
        
        assert len(lists) == 3
        assert "项目1" in lists[0]
        assert "步骤1" in lists[1]
        assert "选项A" in lists[2]


class TestProjectState:
    """项目状态测试"""
    
    def test_project_state_creation(self):
        """测试项目状态创建"""
        state = ProjectState(
            name="测试项目",
            description="测试描述"
        )
        
        assert state.name == "测试项目"
        assert state.description == "测试描述"
        assert state.status == "initialized"
        assert state.progress == 0.0
        assert state.current_phase == "analysis"
    
    def test_progress_update(self):
        """测试进度更新"""
        state = ProjectState(name="测试", description="测试")
        original_time = state.updated_at
        
        state.update_progress(50.5)
        
        assert state.progress == 50.5
        assert state.updated_at > original_time
    
    def test_phase_setting(self):
        """测试阶段设置"""
        state = ProjectState(name="测试", description="测试")
        original_time = state.updated_at
        
        state.set_phase("coding")
        
        assert state.current_phase == "coding"
        assert state.updated_at > original_time
    
    def test_error_logging(self):
        """测试错误记录"""
        state = ProjectState(name="测试", description="测试")
        
        state.add_error("测试错误", {"detail": "错误详情"})
        
        assert len(state.errors) == 1
        error = state.errors[0]
        assert error["error"] == "测试错误"
        assert error["details"]["detail"] == "错误详情"
    
    def test_warning_logging(self):
        """测试警告记录"""
        state = ProjectState(name="测试", description="测试")
        
        state.add_warning("测试警告", {"detail": "警告详情"})
        
        assert len(state.warnings) == 1
        warning = state.warnings[0]
        assert warning["warning"] == "测试警告"
        assert warning["details"]["detail"] == "警告详情"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
