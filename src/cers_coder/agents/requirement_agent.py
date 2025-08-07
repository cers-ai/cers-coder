"""
需求分析智能体 - 负责结构化提取业务需求，生成功能模型
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ..core.base_agent import AgentCapability, AgentConfig, BaseAgent
from ..core.message import Message, MessageType
from ..core.operation_recorder import OperationRecorder, OperationType
from ..llm.ollama_client import OllamaClient


class FunctionalRequirement(BaseModel):
    """功能需求模型"""
    id: str = Field(..., description="需求ID")
    name: str = Field(..., description="需求名称")
    description: str = Field(..., description="需求描述")
    priority: str = Field(..., description="优先级：高/中/低")
    category: str = Field(..., description="需求类别")
    acceptance_criteria: List[str] = Field(default_factory=list, description="验收标准")
    dependencies: List[str] = Field(default_factory=list, description="依赖的其他需求")
    estimated_effort: str = Field(default="", description="预估工作量")


class NonFunctionalRequirement(BaseModel):
    """非功能需求模型"""
    id: str = Field(..., description="需求ID")
    name: str = Field(..., description="需求名称")
    description: str = Field(..., description="需求描述")
    category: str = Field(..., description="类别：性能/安全/可用性等")
    metrics: List[str] = Field(default_factory=list, description="度量标准")
    constraints: List[str] = Field(default_factory=list, description="约束条件")


class UseCase(BaseModel):
    """用例模型"""
    id: str = Field(..., description="用例ID")
    name: str = Field(..., description="用例名称")
    actor: str = Field(..., description="参与者")
    description: str = Field(..., description="用例描述")
    preconditions: List[str] = Field(default_factory=list, description="前置条件")
    main_flow: List[str] = Field(default_factory=list, description="主流程")
    alternative_flows: List[List[str]] = Field(default_factory=list, description="备选流程")
    postconditions: List[str] = Field(default_factory=list, description="后置条件")
    related_requirements: List[str] = Field(default_factory=list, description="相关需求")


class RequirementAnalysisResult(BaseModel):
    """需求分析结果"""
    project_overview: Dict[str, str] = Field(default_factory=dict, description="项目概览")
    functional_requirements: List[FunctionalRequirement] = Field(default_factory=list, description="功能需求")
    non_functional_requirements: List[NonFunctionalRequirement] = Field(default_factory=list, description="非功能需求")
    use_cases: List[UseCase] = Field(default_factory=list, description="用例")
    business_rules: List[str] = Field(default_factory=list, description="业务规则")
    assumptions: List[str] = Field(default_factory=list, description="假设条件")
    constraints: List[str] = Field(default_factory=list, description="约束条件")
    risks: List[str] = Field(default_factory=list, description="风险因素")
    glossary: Dict[str, str] = Field(default_factory=dict, description="术语表")


class RequirementAgent(BaseAgent):
    """需求分析智能体"""

    def __init__(self, ollama_client: OllamaClient, operation_recorder: Optional[OperationRecorder] = None):
        config = AgentConfig(
            name="需求分析智能体",
            description="负责结构化提取业务需求，生成功能模型和用例",
            capabilities=[AgentCapability.ANALYSIS],
            max_concurrent_tasks=2,
            timeout=600,
            llm_config={
                "model": "llama3:8b",
                "temperature": 0.3,
                "max_tokens": 4000
            }
        )
        super().__init__(config, operation_recorder)

        self.ollama_client = ollama_client
        self.analysis_result: Optional[RequirementAnalysisResult] = None

    async def _handle_task_create(self, message: Message) -> Optional[Message]:
        """处理任务创建消息"""
        task_type = message.content.get("task_type", "")
        
        if task_type == "analyze_requirements":
            return await self._analyze_requirements(message)
        elif task_type == "extract_functional_requirements":
            return await self._extract_functional_requirements(message)
        elif task_type == "create_use_cases":
            return await self._create_use_cases(message)
        elif task_type == "validate_requirements":
            return await self._validate_requirements(message)
        else:
            return await self._handle_generic_analysis(message)

    async def _handle_agent_request(self, message: Message) -> Optional[Message]:
        """处理智能体请求消息"""
        request_type = message.content.get("request_type", "")
        
        if request_type == "get_analysis_result":
            return await self._get_analysis_result(message)
        elif request_type == "get_requirements_summary":
            return await self._get_requirements_summary(message)
        else:
            return message.create_reply(
                sender=self.name,
                subject="未知请求类型",
                content={"error": f"未知请求类型: {request_type}"}
            )

    async def _analyze_requirements(self, message: Message) -> Optional[Message]:
        """分析需求"""
        try:
            self.logger.info("开始需求分析")
            
            # 获取输入数据
            project_data = message.content.get("project_data", {})
            input_files = message.content.get("input_files", {})
            
            # 初始化分析结果
            self.analysis_result = RequirementAnalysisResult()
            
            # 分析项目概览
            await self._analyze_project_overview(project_data, input_files)
            
            # 提取功能需求
            await self._extract_functional_requirements_from_data(input_files)
            
            # 提取非功能需求
            await self._extract_non_functional_requirements(input_files)
            
            # 生成用例
            await self._generate_use_cases()
            
            # 识别业务规则和约束
            await self._identify_business_rules_and_constraints(input_files)
            
            # 风险分析
            await self._analyze_risks(project_data)
            
            self.logger.info("需求分析完成")
            
            return message.create_reply(
                sender=self.name,
                subject="需求分析完成",
                content={
                    "analysis_result": self.analysis_result.model_dump(),
                    "summary": {
                        "functional_requirements_count": len(self.analysis_result.functional_requirements),
                        "non_functional_requirements_count": len(self.analysis_result.non_functional_requirements),
                        "use_cases_count": len(self.analysis_result.use_cases),
                        "business_rules_count": len(self.analysis_result.business_rules)
                    }
                }
            )
            
        except Exception as e:
            self.logger.error(f"需求分析失败: {e}", exc_info=True)
            return message.create_reply(
                sender=self.name,
                subject="需求分析失败",
                content={"error": str(e)}
            )

    async def _analyze_project_overview(self, project_data: Dict[str, Any], input_files: Dict[str, str]) -> None:
        """分析项目概览"""
        # 从项目数据中提取基本信息
        self.analysis_result.project_overview = {
            "name": project_data.get("name", "未知项目"),
            "description": project_data.get("description", ""),
            "domain": await self._identify_domain(input_files),
            "scope": await self._identify_scope(input_files),
            "target_users": await self._identify_target_users(input_files)
        }

    async def _identify_domain(self, input_files: Dict[str, str]) -> str:
        """识别项目领域"""
        # 使用LLM分析项目领域
        prompt = f"""
        基于以下项目文档，识别项目所属的业务领域：
        
        {self._format_input_files(input_files)}
        
        请简洁地回答项目属于哪个业务领域（如：电商、金融、教育、医疗、工具软件等）。
        """
        
        try:
            response = await self.ollama_client.generate(
                model=self.config.llm_config["model"],
                prompt=prompt,
                options={
                    "temperature": self.config.llm_config["temperature"],
                    "num_predict": 100
                }
            )
            return response.strip()
        except Exception as e:
            self.logger.warning(f"识别项目领域失败: {e}")
            return "通用软件"

    async def _identify_scope(self, input_files: Dict[str, str]) -> str:
        """识别项目范围"""
        prompt = f"""
        基于以下项目文档，总结项目的核心功能范围：
        
        {self._format_input_files(input_files)}
        
        请用1-2句话概括项目的主要功能范围。
        """
        
        try:
            response = await self.ollama_client.generate(
                model=self.config.llm_config["model"],
                prompt=prompt,
                options={
                    "temperature": self.config.llm_config["temperature"],
                    "num_predict": 200
                }
            )
            return response.strip()
        except Exception as e:
            self.logger.warning(f"识别项目范围失败: {e}")
            return "待确定"

    async def _identify_target_users(self, input_files: Dict[str, str]) -> str:
        """识别目标用户"""
        prompt = f"""
        基于以下项目文档，识别项目的目标用户群体：
        
        {self._format_input_files(input_files)}
        
        请简洁地描述项目的主要目标用户。
        """
        
        try:
            response = await self.ollama_client.generate(
                model=self.config.llm_config["model"],
                prompt=prompt,
                options={
                    "temperature": self.config.llm_config["temperature"],
                    "num_predict": 150
                }
            )
            return response.strip()
        except Exception as e:
            self.logger.warning(f"识别目标用户失败: {e}")
            return "通用用户"

    async def _extract_functional_requirements_from_data(self, input_files: Dict[str, str]) -> None:
        """从数据中提取功能需求"""
        prompt = f"""
        基于以下项目文档，提取功能需求。请以JSON格式返回，包含以下字段：
        - id: 需求唯一标识
        - name: 需求名称
        - description: 详细描述
        - priority: 优先级（高/中/低）
        - category: 需求类别
        - acceptance_criteria: 验收标准列表
        
        项目文档：
        {self._format_input_files(input_files)}
        
        请返回JSON数组格式的功能需求列表。
        """
        
        try:
            response = await self.ollama_client.generate(
                model=self.config.llm_config["model"],
                prompt=prompt,
                options={
                    "temperature": self.config.llm_config["temperature"],
                    "num_predict": 2000
                }
            )
            
            # 解析JSON响应
            requirements_data = self._parse_json_response(response)
            if requirements_data:
                for req_data in requirements_data:
                    requirement = FunctionalRequirement(**req_data)
                    self.analysis_result.functional_requirements.append(requirement)
            
        except Exception as e:
            self.logger.warning(f"提取功能需求失败: {e}")
            # 添加默认需求
            self._add_default_functional_requirements()

    async def _extract_non_functional_requirements(self, input_files: Dict[str, str]) -> None:
        """提取非功能需求"""
        prompt = f"""
        基于以下项目文档，识别非功能需求（性能、安全、可用性、可扩展性等）。
        请以JSON格式返回，包含以下字段：
        - id: 需求唯一标识
        - name: 需求名称
        - description: 详细描述
        - category: 类别（性能/安全/可用性/可扩展性等）
        - metrics: 度量标准列表
        - constraints: 约束条件列表
        
        项目文档：
        {self._format_input_files(input_files)}
        
        请返回JSON数组格式的非功能需求列表。
        """
        
        try:
            response = await self.ollama_client.generate(
                model=self.config.llm_config["model"],
                prompt=prompt,
                options={
                    "temperature": self.config.llm_config["temperature"],
                    "num_predict": 1500
                }
            )
            
            # 解析JSON响应
            requirements_data = self._parse_json_response(response)
            if requirements_data:
                for req_data in requirements_data:
                    requirement = NonFunctionalRequirement(**req_data)
                    self.analysis_result.non_functional_requirements.append(requirement)
            
        except Exception as e:
            self.logger.warning(f"提取非功能需求失败: {e}")
            # 添加默认非功能需求
            self._add_default_non_functional_requirements()

    async def _generate_use_cases(self) -> None:
        """生成用例"""
        if not self.analysis_result.functional_requirements:
            return
        
        # 基于功能需求生成用例
        for req in self.analysis_result.functional_requirements[:5]:  # 限制数量
            use_case = UseCase(
                id=f"UC_{len(self.analysis_result.use_cases) + 1:03d}",
                name=f"用例：{req.name}",
                actor="用户",
                description=f"用户通过系统{req.description}",
                preconditions=["用户已登录系统"],
                main_flow=[
                    "1. 用户访问系统",
                    f"2. 用户执行{req.name}操作",
                    "3. 系统处理请求",
                    "4. 系统返回结果"
                ],
                postconditions=["操作完成"],
                related_requirements=[req.id]
            )
            self.analysis_result.use_cases.append(use_case)

    async def _identify_business_rules_and_constraints(self, input_files: Dict[str, str]) -> None:
        """识别业务规则和约束"""
        # 从输入文件中提取业务规则
        for filename, content in input_files.items():
            if "rule" in filename.lower() or "规则" in content:
                rules = self._extract_rules_from_text(content)
                self.analysis_result.business_rules.extend(rules)
            
            if "constraint" in filename.lower() or "约束" in content or "限制" in content:
                constraints = self._extract_constraints_from_text(content)
                self.analysis_result.constraints.extend(constraints)

    async def _analyze_risks(self, project_data: Dict[str, Any]) -> None:
        """分析风险"""
        # 基于项目特点识别常见风险
        common_risks = [
            "技术复杂度风险",
            "需求变更风险",
            "资源不足风险",
            "时间压力风险",
            "集成风险"
        ]
        self.analysis_result.risks.extend(common_risks)

    def _format_input_files(self, input_files: Dict[str, str]) -> str:
        """格式化输入文件内容"""
        formatted = ""
        for filename, content in input_files.items():
            formatted += f"\n=== {filename} ===\n{content}\n"
        return formatted

    def _parse_json_response(self, response: str) -> Optional[List[Dict[str, Any]]]:
        """解析JSON响应"""
        try:
            # 尝试直接解析
            return json.loads(response)
        except json.JSONDecodeError:
            try:
                # 尝试提取JSON部分
                start = response.find('[')
                end = response.rfind(']') + 1
                if start >= 0 and end > start:
                    json_str = response[start:end]
                    return json.loads(json_str)
            except:
                pass
        
        self.logger.warning("无法解析JSON响应")
        return None

    def _extract_rules_from_text(self, text: str) -> List[str]:
        """从文本中提取规则"""
        rules = []
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if line and ('规则' in line or '必须' in line or '应该' in line):
                rules.append(line)
        return rules

    def _extract_constraints_from_text(self, text: str) -> List[str]:
        """从文本中提取约束"""
        constraints = []
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if line and ('约束' in line or '限制' in line or '不能' in line or '禁止' in line):
                constraints.append(line)
        return constraints

    def _add_default_functional_requirements(self) -> None:
        """添加默认功能需求"""
        default_req = FunctionalRequirement(
            id="FR_001",
            name="基础功能",
            description="系统应提供基础功能",
            priority="高",
            category="核心功能",
            acceptance_criteria=["功能正常运行", "用户界面友好"]
        )
        self.analysis_result.functional_requirements.append(default_req)

    def _add_default_non_functional_requirements(self) -> None:
        """添加默认非功能需求"""
        default_req = NonFunctionalRequirement(
            id="NFR_001",
            name="性能要求",
            description="系统应具备良好的性能",
            category="性能",
            metrics=["响应时间 < 2秒", "并发用户 > 100"],
            constraints=["内存使用 < 1GB"]
        )
        self.analysis_result.non_functional_requirements.append(default_req)

    async def _get_analysis_result(self, message: Message) -> Optional[Message]:
        """获取分析结果"""
        if not self.analysis_result:
            return message.create_reply(
                sender=self.name,
                subject="分析结果",
                content={"error": "尚未进行需求分析"}
            )
        
        return message.create_reply(
            sender=self.name,
            subject="分析结果",
            content={"analysis_result": self.analysis_result.model_dump()}
        )

    async def _get_requirements_summary(self, message: Message) -> Optional[Message]:
        """获取需求摘要"""
        if not self.analysis_result:
            return message.create_reply(
                sender=self.name,
                subject="需求摘要",
                content={"error": "尚未进行需求分析"}
            )
        
        summary = {
            "project_name": self.analysis_result.project_overview.get("name", "未知"),
            "functional_requirements_count": len(self.analysis_result.functional_requirements),
            "non_functional_requirements_count": len(self.analysis_result.non_functional_requirements),
            "use_cases_count": len(self.analysis_result.use_cases),
            "high_priority_requirements": [
                req.name for req in self.analysis_result.functional_requirements 
                if req.priority == "高"
            ]
        }
        
        return message.create_reply(
            sender=self.name,
            subject="需求摘要",
            content={"summary": summary}
        )
