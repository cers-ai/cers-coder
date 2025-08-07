"""
文件解析器 - 解析标准输入文件（0.request.md等）
"""

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import aiofiles
from pydantic import BaseModel, Field


class InputFileSpec(BaseModel):
    """输入文件规范"""
    filename: str = Field(..., description="文件名")
    required: bool = Field(..., description="是否必需")
    description: str = Field(..., description="文件描述")


class ParsedContent(BaseModel):
    """解析后的内容"""
    filename: str = Field(..., description="文件名")
    exists: bool = Field(..., description="文件是否存在")
    content: str = Field(default="", description="文件内容")
    sections: Dict[str, str] = Field(default_factory=dict, description="章节内容")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    tables: List[Dict[str, Any]] = Field(default_factory=list, description="表格数据")
    lists: List[List[str]] = Field(default_factory=list, description="列表数据")


class ProjectRequirements(BaseModel):
    """项目需求"""
    name: str = Field(..., description="项目名称")
    description: str = Field(..., description="项目描述")
    goals: List[str] = Field(default_factory=list, description="项目目标")
    features: List[str] = Field(default_factory=list, description="系统特性")
    constraints: List[str] = Field(default_factory=list, description="限制条件")
    
    # 智能体配置
    agents: List[Dict[str, str]] = Field(default_factory=list, description="智能体配置")
    workflow: List[Dict[str, str]] = Field(default_factory=list, description="工作流程")
    
    # 输出要求
    outputs: Dict[str, str] = Field(default_factory=dict, description="输出要求")
    
    # 技术要求
    tech_stack: List[str] = Field(default_factory=list, description="技术栈")
    dependencies: List[str] = Field(default_factory=list, description="依赖库")
    
    # 其他配置
    rules: List[str] = Field(default_factory=list, description="编码规则")
    assets: Dict[str, str] = Field(default_factory=dict, description="已有资产")
    environment: Dict[str, str] = Field(default_factory=dict, description="环境配置")


class FileParser:
    """文件解析器"""
    
    # 标准输入文件规范
    STANDARD_FILES = [
        InputFileSpec(filename="0.request.md", required=True, description="功能需求、目标、输出范围"),
        InputFileSpec(filename="1.rule.md", required=False, description="编码风格、命名规范、模块划分约束等规则"),
        InputFileSpec(filename="2.mcp.md", required=False, description="自定义开发流程与智能体间通信协议"),
        InputFileSpec(filename="3.assets.md", required=False, description="已有资产：接口说明、已有模型、已有代码等"),
        InputFileSpec(filename="4.env.md", required=False, description="运行平台、语言环境、依赖库要求等"),
    ]
    
    def __init__(self, project_dir: str = "."):
        self.project_dir = Path(project_dir)
        self.logger = logging.getLogger("file_parser")

    async def parse_all_files(self) -> Tuple[Dict[str, ParsedContent], List[str]]:
        """解析所有标准输入文件"""
        parsed_files = {}
        missing_required = []
        
        for file_spec in self.STANDARD_FILES:
            file_path = self.project_dir / file_spec.filename
            
            if file_path.exists():
                try:
                    content = await self._parse_markdown_file(file_path)
                    parsed_files[file_spec.filename] = content
                    self.logger.info(f"成功解析文件: {file_spec.filename}")
                except Exception as e:
                    self.logger.error(f"解析文件失败 {file_spec.filename}: {e}")
                    parsed_files[file_spec.filename] = ParsedContent(
                        filename=file_spec.filename,
                        exists=False
                    )
            else:
                if file_spec.required:
                    missing_required.append(file_spec.filename)
                    self.logger.error(f"必需文件缺失: {file_spec.filename}")
                else:
                    self.logger.info(f"可选文件不存在: {file_spec.filename}")
                
                parsed_files[file_spec.filename] = ParsedContent(
                    filename=file_spec.filename,
                    exists=False
                )
        
        return parsed_files, missing_required

    async def _parse_markdown_file(self, file_path: Path) -> ParsedContent:
        """解析Markdown文件"""
        async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
            content = await f.read()
        
        # 解析章节
        sections = self._extract_sections(content)
        
        # 解析表格
        tables = self._extract_tables(content)
        
        # 解析列表
        lists = self._extract_lists(content)
        
        # 提取元数据
        metadata = self._extract_metadata(content, sections)
        
        return ParsedContent(
            filename=file_path.name,
            exists=True,
            content=content,
            sections=sections,
            metadata=metadata,
            tables=tables,
            lists=lists
        )

    def _extract_sections(self, content: str) -> Dict[str, str]:
        """提取Markdown章节"""
        sections = {}
        current_section = None
        current_content = []
        
        for line in content.split('\n'):
            # 检查是否是标题行
            if line.startswith('#'):
                # 保存上一个章节
                if current_section:
                    sections[current_section] = '\n'.join(current_content).strip()
                
                # 开始新章节
                current_section = line.strip('#').strip()
                current_content = []
            else:
                if current_section:
                    current_content.append(line)
        
        # 保存最后一个章节
        if current_section:
            sections[current_section] = '\n'.join(current_content).strip()
        
        return sections

    def _extract_tables(self, content: str) -> List[Dict[str, Any]]:
        """提取Markdown表格"""
        tables = []
        lines = content.split('\n')
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # 检查是否是表格行
            if '|' in line and line.startswith('|') and line.endswith('|'):
                # 找到表格开始
                table_lines = []
                while i < len(lines) and '|' in lines[i]:
                    table_lines.append(lines[i].strip())
                    i += 1
                
                if len(table_lines) >= 2:  # 至少有标题行和分隔行
                    table = self._parse_table(table_lines)
                    if table:
                        tables.append(table)
                continue
            
            i += 1
        
        return tables

    def _parse_table(self, table_lines: List[str]) -> Optional[Dict[str, Any]]:
        """解析单个表格"""
        if len(table_lines) < 2:
            return None
        
        # 解析标题行
        header_line = table_lines[0]
        headers = [cell.strip() for cell in header_line.split('|')[1:-1]]
        
        # 跳过分隔行
        data_lines = table_lines[2:]
        
        rows = []
        for line in data_lines:
            cells = [cell.strip() for cell in line.split('|')[1:-1]]
            if len(cells) == len(headers):
                row = dict(zip(headers, cells))
                rows.append(row)
        
        return {
            "headers": headers,
            "rows": rows,
            "row_count": len(rows)
        }

    def _extract_lists(self, content: str) -> List[List[str]]:
        """提取Markdown列表"""
        lists = []
        current_list = []
        
        for line in content.split('\n'):
            line = line.strip()
            
            # 检查是否是列表项
            if line.startswith('*') or line.startswith('-') or re.match(r'^\d+\.', line):
                # 提取列表项内容
                if line.startswith('*') or line.startswith('-'):
                    item = line[1:].strip()
                else:
                    item = re.sub(r'^\d+\.\s*', '', line)
                
                current_list.append(item)
            else:
                # 如果不是列表项且当前有列表，保存当前列表
                if current_list:
                    lists.append(current_list)
                    current_list = []
        
        # 保存最后一个列表
        if current_list:
            lists.append(current_list)
        
        return lists

    def _extract_metadata(self, content: str, sections: Dict[str, str]) -> Dict[str, Any]:
        """提取元数据"""
        metadata = {}
        
        # 从内容中提取关键信息
        if "项目名称" in sections:
            metadata["project_name"] = sections["项目名称"].strip()
        elif "🧱 项目名称" in sections:
            metadata["project_name"] = sections["🧱 项目名称"].strip()
        
        if "项目目标" in sections:
            metadata["project_goals"] = sections["项目目标"].strip()
        elif "🎯 项目目标" in sections:
            metadata["project_goals"] = sections["🎯 项目目标"].strip()
        
        # 提取技术栈信息
        tech_keywords = ["python", "docker", "ollama", "llm", "智能体", "agent"]
        mentioned_tech = []
        content_lower = content.lower()
        for keyword in tech_keywords:
            if keyword in content_lower:
                mentioned_tech.append(keyword)
        metadata["mentioned_technologies"] = mentioned_tech
        
        return metadata

    async def extract_requirements(self, parsed_files: Dict[str, ParsedContent]) -> ProjectRequirements:
        """从解析的文件中提取项目需求"""
        requirements = ProjectRequirements(
            name="未知项目",
            description="无描述"
        )
        
        # 从0.request.md提取主要需求
        request_file = parsed_files.get("0.request.md")
        if request_file and request_file.exists:
            await self._extract_from_request_file(request_file, requirements)
        
        # 从1.rule.md提取编码规则
        rule_file = parsed_files.get("1.rule.md")
        if rule_file and rule_file.exists:
            await self._extract_from_rule_file(rule_file, requirements)
        
        # 从3.assets.md提取已有资产
        assets_file = parsed_files.get("3.assets.md")
        if assets_file and assets_file.exists:
            await self._extract_from_assets_file(assets_file, requirements)
        
        # 从4.env.md提取环境配置
        env_file = parsed_files.get("4.env.md")
        if env_file and env_file.exists:
            await self._extract_from_env_file(env_file, requirements)
        
        return requirements

    async def _extract_from_request_file(self, file_content: ParsedContent, requirements: ProjectRequirements) -> None:
        """从request文件提取需求"""
        sections = file_content.sections
        
        # 提取项目名称
        for key in ["项目名称", "🧱 项目名称"]:
            if key in sections:
                requirements.name = sections[key].strip()
                break
        
        # 提取项目目标
        for key in ["项目目标", "🎯 项目目标"]:
            if key in sections:
                requirements.description = sections[key].strip()
                break
        
        # 提取系统特性
        for key in ["系统特性与设计原则", "🔧 系统特性与设计原则"]:
            if key in sections:
                features_text = sections[key]
                # 提取以*开头的特性列表
                features = re.findall(r'\*\s*\*\*([^*]+)\*\*[：:]\s*([^\n]+)', features_text)
                for feature_name, feature_desc in features:
                    requirements.features.append(f"{feature_name}: {feature_desc}")
                break
        
        # 提取智能体信息
        for key in ["智能体构成与职责定义", "🧩 智能体构成与职责定义"]:
            if key in sections:
                # 从表格中提取智能体信息
                for table in file_content.tables:
                    if "智能体" in table.get("headers", []) or "职责" in table.get("headers", []):
                        for row in table["rows"]:
                            agent_info = {}
                            for header, value in row.items():
                                agent_info[header] = value
                            requirements.agents.append(agent_info)
                break
        
        # 提取输出要求
        for key in ["项目输出要求", "📦 项目输出要求"]:
            if key in sections:
                # 从表格中提取输出要求
                for table in file_content.tables:
                    if "目录/文件" in table.get("headers", []) or "描述" in table.get("headers", []):
                        for row in table["rows"]:
                            if "目录/文件" in row and "描述" in row:
                                requirements.outputs[row["目录/文件"]] = row["描述"]
                break

    async def _extract_from_rule_file(self, file_content: ParsedContent, requirements: ProjectRequirements) -> None:
        """从rule文件提取编码规则"""
        # 将所有章节内容作为规则添加
        for section_name, section_content in file_content.sections.items():
            if section_content.strip():
                requirements.rules.append(f"{section_name}: {section_content.strip()}")

    async def _extract_from_assets_file(self, file_content: ParsedContent, requirements: ProjectRequirements) -> None:
        """从assets文件提取已有资产"""
        for section_name, section_content in file_content.sections.items():
            if section_content.strip():
                requirements.assets[section_name] = section_content.strip()

    async def _extract_from_env_file(self, file_content: ParsedContent, requirements: ProjectRequirements) -> None:
        """从env文件提取环境配置"""
        for section_name, section_content in file_content.sections.items():
            if section_content.strip():
                requirements.environment[section_name] = section_content.strip()

    def validate_requirements(self, requirements: ProjectRequirements) -> List[str]:
        """验证需求完整性"""
        issues = []
        
        if not requirements.name or requirements.name == "未知项目":
            issues.append("缺少项目名称")
        
        if not requirements.description or requirements.description == "无描述":
            issues.append("缺少项目描述")
        
        if not requirements.agents:
            issues.append("缺少智能体配置")
        
        if not requirements.outputs:
            issues.append("缺少输出要求")
        
        return issues
