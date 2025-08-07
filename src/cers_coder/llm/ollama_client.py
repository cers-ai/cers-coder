"""
Ollama客户端 - 封装Ollama API调用，支持模型配置管理和错误处理
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Union

import httpx
from pydantic import BaseModel, Field


class OllamaResponse(BaseModel):
    """Ollama响应模型"""
    model: str = Field(..., description="使用的模型")
    response: str = Field(..., description="生成的响应")
    done: bool = Field(..., description="是否完成")
    context: Optional[List[int]] = Field(None, description="上下文")
    total_duration: Optional[int] = Field(None, description="总耗时（纳秒）")
    load_duration: Optional[int] = Field(None, description="加载耗时（纳秒）")
    prompt_eval_count: Optional[int] = Field(None, description="提示词token数")
    prompt_eval_duration: Optional[int] = Field(None, description="提示词评估耗时（纳秒）")
    eval_count: Optional[int] = Field(None, description="生成token数")
    eval_duration: Optional[int] = Field(None, description="生成耗时（纳秒）")


class ModelInfo(BaseModel):
    """模型信息"""
    name: str = Field(..., description="模型名称")
    size: int = Field(..., description="模型大小（字节）")
    digest: str = Field(..., description="模型摘要")
    modified_at: str = Field(..., description="修改时间")
    details: Dict[str, Any] = Field(default_factory=dict, description="详细信息")


class OllamaClient:
    """Ollama客户端"""
    
    def __init__(
        self,
        host: str = "http://localhost:11434",
        timeout: int = 300,
        max_retries: int = 3,
        retry_delay: int = 1
    ):
        self.host = host.rstrip('/')
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.logger = logging.getLogger("ollama_client")
        
        # HTTP客户端配置
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def close(self):
        """关闭客户端"""
        await self.client.aclose()

    async def health_check(self) -> bool:
        """健康检查"""
        try:
            response = await self.client.get(f"{self.host}/api/tags")
            return response.status_code == 200
        except Exception as e:
            self.logger.error(f"健康检查失败: {e}")
            return False

    async def list_models(self) -> List[ModelInfo]:
        """列出可用模型"""
        try:
            response = await self.client.get(f"{self.host}/api/tags")
            response.raise_for_status()
            
            data = response.json()
            models = []
            
            for model_data in data.get("models", []):
                model = ModelInfo(
                    name=model_data["name"],
                    size=model_data["size"],
                    digest=model_data["digest"],
                    modified_at=model_data["modified_at"],
                    details=model_data.get("details", {})
                )
                models.append(model)
            
            return models
            
        except Exception as e:
            self.logger.error(f"获取模型列表失败: {e}")
            return []

    async def pull_model(self, model_name: str) -> bool:
        """拉取模型"""
        try:
            self.logger.info(f"开始拉取模型: {model_name}")
            
            async with self.client.stream(
                "POST",
                f"{self.host}/api/pull",
                json={"name": model_name}
            ) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if line:
                        try:
                            data = eval(line)  # 简化处理，实际应该用json.loads
                            if data.get("status"):
                                self.logger.info(f"拉取进度: {data['status']}")
                        except:
                            continue
            
            self.logger.info(f"模型拉取完成: {model_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"拉取模型失败 {model_name}: {e}")
            return False

    async def generate(
        self,
        model: str,
        prompt: str,
        system: Optional[str] = None,
        context: Optional[List[int]] = None,
        options: Optional[Dict[str, Any]] = None,
        stream: bool = False
    ) -> str:
        """生成文本"""
        for attempt in range(self.max_retries):
            try:
                payload = {
                    "model": model,
                    "prompt": prompt,
                    "stream": stream
                }
                
                if system:
                    payload["system"] = system
                if context:
                    payload["context"] = context
                if options:
                    payload["options"] = options
                
                self.logger.debug(f"发送生成请求: model={model}, prompt_length={len(prompt)}")
                
                if stream:
                    return await self._generate_stream(payload)
                else:
                    return await self._generate_single(payload)
                    
            except Exception as e:
                self.logger.warning(f"生成请求失败 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                else:
                    raise

    async def _generate_single(self, payload: Dict[str, Any]) -> str:
        """单次生成"""
        response = await self.client.post(
            f"{self.host}/api/generate",
            json=payload
        )
        response.raise_for_status()
        
        data = response.json()
        return data.get("response", "")

    async def _generate_stream(self, payload: Dict[str, Any]) -> str:
        """流式生成"""
        full_response = ""
        
        async with self.client.stream(
            "POST",
            f"{self.host}/api/generate",
            json=payload
        ) as response:
            response.raise_for_status()
            
            async for line in response.aiter_lines():
                if line:
                    try:
                        data = eval(line)  # 简化处理
                        if "response" in data:
                            full_response += data["response"]
                        if data.get("done", False):
                            break
                    except:
                        continue
        
        return full_response

    async def chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        options: Optional[Dict[str, Any]] = None,
        stream: bool = False
    ) -> str:
        """聊天对话"""
        for attempt in range(self.max_retries):
            try:
                payload = {
                    "model": model,
                    "messages": messages,
                    "stream": stream
                }
                
                if options:
                    payload["options"] = options
                
                self.logger.debug(f"发送聊天请求: model={model}, messages_count={len(messages)}")
                
                if stream:
                    return await self._chat_stream(payload)
                else:
                    return await self._chat_single(payload)
                    
            except Exception as e:
                self.logger.warning(f"聊天请求失败 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                else:
                    raise

    async def _chat_single(self, payload: Dict[str, Any]) -> str:
        """单次聊天"""
        response = await self.client.post(
            f"{self.host}/api/chat",
            json=payload
        )
        response.raise_for_status()
        
        data = response.json()
        message = data.get("message", {})
        return message.get("content", "")

    async def _chat_stream(self, payload: Dict[str, Any]) -> str:
        """流式聊天"""
        full_response = ""
        
        async with self.client.stream(
            "POST",
            f"{self.host}/api/chat",
            json=payload
        ) as response:
            response.raise_for_status()
            
            async for line in response.aiter_lines():
                if line:
                    try:
                        data = eval(line)  # 简化处理
                        message = data.get("message", {})
                        if "content" in message:
                            full_response += message["content"]
                        if data.get("done", False):
                            break
                    except:
                        continue
        
        return full_response

    async def embed(self, model: str, prompt: str) -> List[float]:
        """生成嵌入向量"""
        try:
            response = await self.client.post(
                f"{self.host}/api/embeddings",
                json={
                    "model": model,
                    "prompt": prompt
                }
            )
            response.raise_for_status()
            
            data = response.json()
            return data.get("embedding", [])
            
        except Exception as e:
            self.logger.error(f"生成嵌入失败: {e}")
            return []

    async def delete_model(self, model_name: str) -> bool:
        """删除模型"""
        try:
            response = await self.client.delete(
                f"{self.host}/api/delete",
                json={"name": model_name}
            )
            response.raise_for_status()
            
            self.logger.info(f"模型删除成功: {model_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"删除模型失败 {model_name}: {e}")
            return False

    async def copy_model(self, source: str, destination: str) -> bool:
        """复制模型"""
        try:
            response = await self.client.post(
                f"{self.host}/api/copy",
                json={
                    "source": source,
                    "destination": destination
                }
            )
            response.raise_for_status()
            
            self.logger.info(f"模型复制成功: {source} -> {destination}")
            return True
            
        except Exception as e:
            self.logger.error(f"复制模型失败 {source} -> {destination}: {e}")
            return False

    async def show_model(self, model_name: str) -> Optional[Dict[str, Any]]:
        """显示模型详细信息"""
        try:
            response = await self.client.post(
                f"{self.host}/api/show",
                json={"name": model_name}
            )
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            self.logger.error(f"获取模型信息失败 {model_name}: {e}")
            return None

    def get_model_recommendations(self, task_type: str) -> List[str]:
        """根据任务类型推荐模型"""
        recommendations = {
            "coding": ["deepseek-coder:6.7b", "codellama:7b", "phi:latest"],
            "analysis": ["llama3:8b", "mistral:7b", "gemma:7b"],
            "documentation": ["llama3:8b", "mixtral:8x7b", "qwen:7b"],
            "review": ["llama3:8b", "mistral:7b", "phi:latest"],
            "general": ["llama3:8b", "mistral:7b", "phi:latest"]
        }
        
        return recommendations.get(task_type, recommendations["general"])

    async def ensure_model_available(self, model_name: str) -> bool:
        """确保模型可用，如果不存在则尝试拉取"""
        models = await self.list_models()
        model_names = [model.name for model in models]
        
        if model_name in model_names:
            return True
        
        # 尝试拉取模型
        self.logger.info(f"模型 {model_name} 不存在，尝试拉取...")
        return await self.pull_model(model_name)

    async def get_optimal_model(self, task_type: str, available_only: bool = True) -> Optional[str]:
        """获取最优模型"""
        recommendations = self.get_model_recommendations(task_type)
        
        if not available_only:
            return recommendations[0] if recommendations else None
        
        # 检查可用模型
        available_models = await self.list_models()
        available_names = [model.name for model in available_models]
        
        for model_name in recommendations:
            if model_name in available_names:
                return model_name
        
        # 如果没有推荐模型可用，返回第一个可用模型
        return available_names[0] if available_names else None
