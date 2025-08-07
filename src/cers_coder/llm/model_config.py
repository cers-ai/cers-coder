"""
模型配置管理 - 管理不同智能体的模型配置和参数
"""

import logging
import os
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ModelConfig(BaseModel):
    """模型配置"""
    name: str = Field(..., description="模型名称")
    alias: str = Field(..., description="模型别名")
    description: str = Field(default="", description="模型描述")
    
    # 生成参数
    temperature: float = Field(default=0.7, description="温度参数")
    top_p: float = Field(default=0.9, description="Top-p参数")
    top_k: int = Field(default=40, description="Top-k参数")
    max_tokens: int = Field(default=2048, description="最大token数")
    
    # 性能参数
    num_ctx: int = Field(default=4096, description="上下文长度")
    num_predict: int = Field(default=2048, description="预测token数")
    repeat_penalty: float = Field(default=1.1, description="重复惩罚")
    
    # 适用场景
    suitable_tasks: List[str] = Field(default_factory=list, description="适用任务类型")
    performance_level: str = Field(default="medium", description="性能级别：low/medium/high")
    
    # 资源需求
    min_memory_gb: float = Field(default=4.0, description="最小内存需求（GB）")
    recommended_memory_gb: float = Field(default=8.0, description="推荐内存（GB）")


class AgentModelMapping(BaseModel):
    """智能体模型映射"""
    agent_type: str = Field(..., description="智能体类型")
    primary_model: str = Field(..., description="主要模型")
    fallback_models: List[str] = Field(default_factory=list, description="备用模型")
    custom_config: Dict[str, Any] = Field(default_factory=dict, description="自定义配置")


class ModelConfigManager:
    """模型配置管理器"""
    
    def __init__(self, config_file: Optional[str] = None):
        self.logger = logging.getLogger("model_config_manager")
        self.config_file = config_file
        
        # 预定义模型配置
        self.model_configs = self._load_default_configs()
        
        # 智能体模型映射
        self.agent_mappings = self._load_default_mappings()
        
        # 从环境变量或配置文件加载自定义配置
        self._load_custom_configs()

    def _load_default_configs(self) -> Dict[str, ModelConfig]:
        """加载默认模型配置"""
        configs = {}
        
        # Llama3 系列
        configs["llama3:8b"] = ModelConfig(
            name="llama3:8b",
            alias="llama3-8b",
            description="Meta Llama 3 8B 参数模型，平衡性能和资源消耗",
            temperature=0.7,
            top_p=0.9,
            max_tokens=2048,
            suitable_tasks=["analysis", "documentation", "general"],
            performance_level="medium",
            min_memory_gb=6.0,
            recommended_memory_gb=8.0
        )
        
        configs["llama3:70b"] = ModelConfig(
            name="llama3:70b",
            alias="llama3-70b",
            description="Meta Llama 3 70B 参数模型，高性能但资源需求大",
            temperature=0.7,
            top_p=0.9,
            max_tokens=4096,
            suitable_tasks=["analysis", "review", "complex_reasoning"],
            performance_level="high",
            min_memory_gb=40.0,
            recommended_memory_gb=64.0
        )
        
        # DeepSeek Coder 系列
        configs["deepseek-coder:6.7b"] = ModelConfig(
            name="deepseek-coder:6.7b",
            alias="deepseek-coder",
            description="DeepSeek Coder 6.7B，专门用于代码生成",
            temperature=0.3,
            top_p=0.95,
            max_tokens=4096,
            suitable_tasks=["coding", "code_review"],
            performance_level="medium",
            min_memory_gb=5.0,
            recommended_memory_gb=8.0
        )
        
        # CodeLlama 系列
        configs["codellama:7b"] = ModelConfig(
            name="codellama:7b",
            alias="codellama",
            description="Meta Code Llama 7B，代码生成和理解",
            temperature=0.2,
            top_p=0.95,
            max_tokens=4096,
            suitable_tasks=["coding", "code_analysis"],
            performance_level="medium",
            min_memory_gb=5.0,
            recommended_memory_gb=8.0
        )
        
        # Mistral 系列
        configs["mistral:7b"] = ModelConfig(
            name="mistral:7b",
            alias="mistral",
            description="Mistral 7B，高效的通用模型",
            temperature=0.7,
            top_p=0.9,
            max_tokens=2048,
            suitable_tasks=["analysis", "documentation", "general"],
            performance_level="medium",
            min_memory_gb=5.0,
            recommended_memory_gb=8.0
        )
        
        # Phi 系列
        configs["phi:latest"] = ModelConfig(
            name="phi:latest",
            alias="phi",
            description="Microsoft Phi，小型但高效的模型",
            temperature=0.7,
            top_p=0.9,
            max_tokens=2048,
            suitable_tasks=["general", "quick_analysis"],
            performance_level="low",
            min_memory_gb=2.0,
            recommended_memory_gb=4.0
        )
        
        # Gemma 系列
        configs["gemma:7b"] = ModelConfig(
            name="gemma:7b",
            alias="gemma",
            description="Google Gemma 7B，开源高性能模型",
            temperature=0.7,
            top_p=0.9,
            max_tokens=2048,
            suitable_tasks=["analysis", "documentation"],
            performance_level="medium",
            min_memory_gb=5.0,
            recommended_memory_gb=8.0
        )
        
        return configs

    def _load_default_mappings(self) -> Dict[str, AgentModelMapping]:
        """加载默认智能体模型映射"""
        mappings = {}
        
        mappings["pm_agent"] = AgentModelMapping(
            agent_type="pm_agent",
            primary_model="llama3:8b",
            fallback_models=["mistral:7b", "phi:latest"],
            custom_config={"temperature": 0.5}
        )
        
        mappings["requirement_agent"] = AgentModelMapping(
            agent_type="requirement_agent",
            primary_model="llama3:8b",
            fallback_models=["mistral:7b", "gemma:7b"],
            custom_config={"temperature": 0.3, "max_tokens": 4000}
        )
        
        mappings["architecture_agent"] = AgentModelMapping(
            agent_type="architecture_agent",
            primary_model="llama3:8b",
            fallback_models=["mistral:7b", "deepseek-coder:6.7b"],
            custom_config={"temperature": 0.4}
        )
        
        mappings["coding_agent"] = AgentModelMapping(
            agent_type="coding_agent",
            primary_model="deepseek-coder:6.7b",
            fallback_models=["codellama:7b", "llama3:8b"],
            custom_config={"temperature": 0.2, "max_tokens": 4096}
        )
        
        mappings["testing_agent"] = AgentModelMapping(
            agent_type="testing_agent",
            primary_model="deepseek-coder:6.7b",
            fallback_models=["codellama:7b", "llama3:8b"],
            custom_config={"temperature": 0.3}
        )
        
        mappings["build_agent"] = AgentModelMapping(
            agent_type="build_agent",
            primary_model="llama3:8b",
            fallback_models=["mistral:7b", "phi:latest"],
            custom_config={"temperature": 0.4}
        )
        
        mappings["documentation_agent"] = AgentModelMapping(
            agent_type="documentation_agent",
            primary_model="llama3:8b",
            fallback_models=["mistral:7b", "gemma:7b"],
            custom_config={"temperature": 0.6, "max_tokens": 3000}
        )
        
        mappings["review_agent"] = AgentModelMapping(
            agent_type="review_agent",
            primary_model="llama3:8b",
            fallback_models=["mistral:7b", "deepseek-coder:6.7b"],
            custom_config={"temperature": 0.4}
        )
        
        return mappings

    def _load_custom_configs(self) -> None:
        """加载自定义配置"""
        # 从环境变量加载
        default_model = os.getenv("OLLAMA_DEFAULT_MODEL")
        if default_model:
            self.logger.info(f"使用环境变量指定的默认模型: {default_model}")
            # 更新所有映射的主要模型
            for mapping in self.agent_mappings.values():
                if default_model in self.model_configs:
                    mapping.primary_model = default_model

    def get_model_config(self, model_name: str) -> Optional[ModelConfig]:
        """获取模型配置"""
        return self.model_configs.get(model_name)

    def get_agent_model_config(self, agent_type: str) -> Optional[Dict[str, Any]]:
        """获取智能体的模型配置"""
        mapping = self.agent_mappings.get(agent_type)
        if not mapping:
            return None
        
        model_config = self.model_configs.get(mapping.primary_model)
        if not model_config:
            return None
        
        # 合并基础配置和自定义配置
        config = model_config.model_dump()
        config.update(mapping.custom_config)
        
        return config

    def get_fallback_models(self, agent_type: str) -> List[str]:
        """获取智能体的备用模型列表"""
        mapping = self.agent_mappings.get(agent_type)
        if not mapping:
            return []
        
        return [mapping.primary_model] + mapping.fallback_models

    def recommend_model_for_task(self, task_type: str, memory_limit_gb: Optional[float] = None) -> Optional[str]:
        """为任务类型推荐模型"""
        suitable_models = []
        
        for model_name, config in self.model_configs.items():
            if task_type in config.suitable_tasks:
                if memory_limit_gb is None or config.min_memory_gb <= memory_limit_gb:
                    suitable_models.append((model_name, config))
        
        if not suitable_models:
            return None
        
        # 按性能级别排序，优先推荐高性能模型
        performance_order = {"high": 3, "medium": 2, "low": 1}
        suitable_models.sort(
            key=lambda x: performance_order.get(x[1].performance_level, 0),
            reverse=True
        )
        
        return suitable_models[0][0]

    def validate_model_requirements(self, model_name: str, available_memory_gb: float) -> bool:
        """验证模型资源需求"""
        config = self.model_configs.get(model_name)
        if not config:
            return False
        
        return available_memory_gb >= config.min_memory_gb

    def get_model_options(self, model_name: str, custom_options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """获取模型的Ollama选项"""
        config = self.model_configs.get(model_name)
        if not config:
            return custom_options or {}
        
        options = {
            "temperature": config.temperature,
            "top_p": config.top_p,
            "top_k": config.top_k,
            "num_ctx": config.num_ctx,
            "num_predict": config.num_predict,
            "repeat_penalty": config.repeat_penalty
        }
        
        # 合并自定义选项
        if custom_options:
            options.update(custom_options)
        
        return options

    def list_models_by_task(self, task_type: str) -> List[str]:
        """列出适用于特定任务的所有模型"""
        models = []
        for model_name, config in self.model_configs.items():
            if task_type in config.suitable_tasks:
                models.append(model_name)
        return models

    def get_performance_tier_models(self, tier: str) -> List[str]:
        """获取特定性能级别的模型"""
        models = []
        for model_name, config in self.model_configs.items():
            if config.performance_level == tier:
                models.append(model_name)
        return models

    def add_custom_model_config(self, config: ModelConfig) -> None:
        """添加自定义模型配置"""
        self.model_configs[config.name] = config
        self.logger.info(f"添加自定义模型配置: {config.name}")

    def update_agent_mapping(self, agent_type: str, mapping: AgentModelMapping) -> None:
        """更新智能体模型映射"""
        self.agent_mappings[agent_type] = mapping
        self.logger.info(f"更新智能体模型映射: {agent_type}")

    def get_system_recommendations(self, available_memory_gb: float) -> Dict[str, List[str]]:
        """根据系统资源获取推荐配置"""
        recommendations = {
            "high_performance": [],
            "balanced": [],
            "resource_efficient": []
        }
        
        for model_name, config in self.model_configs.items():
            if config.min_memory_gb <= available_memory_gb:
                if config.performance_level == "high":
                    recommendations["high_performance"].append(model_name)
                elif config.performance_level == "medium":
                    recommendations["balanced"].append(model_name)
                else:
                    recommendations["resource_efficient"].append(model_name)
        
        return recommendations
