"""LLM客户端 - 负责实际的API调用"""
import asyncio
import aiohttp
import requests
import re
import logging
import json
from typing import Optional, Dict, Any, Callable, Union, List
from openai import OpenAI
from config.llm.llm_config import get_llm_config, ServerConfig

logger = logging.getLogger(__name__)


class FormatValidationError(Exception):
    """格式验证错误"""
    pass


class LLMClient:
    """LLM客户端 - 统一的LLM调用接口"""
    
    def __init__(self, server_name: str):
        """初始化LLM客户端
        
        Args:
            server_name: 服务器名称 (v3 或 r1)
        """
        self.server_name = server_name
        self.config_manager = get_llm_config()
        self.config = self.config_manager.get_server_config(server_name)
        self._openai_client = None
    
    @property
    def openai_client(self) -> OpenAI:
        """获取OpenAI客户端（懒加载）"""
        if self._openai_client is None:
            openai_config = self.config_manager.get_openai_client_config(self.server_name)
            self._openai_client = OpenAI(
                api_key=openai_config["api_key"],
                base_url=openai_config["base_url"]
            )
        return self._openai_client
    
    def call_sync(self, prompt: str, max_tokens: int = 2048, temperature: float = 0.0) -> str:
        """同步调用LLM API
        
        Args:
            prompt: 输入提示
            max_tokens: 最大token数
            temperature: 温度参数
            
        Returns:
            LLM的响应内容
        """
        headers = {"Content-Type": "application/json"}
        
        data = {
            "model": self.config.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        try:
            response = requests.post(
                self.config.chat_completions_url,
                headers=headers,
                json=data,
                timeout=self.config.timeout
            )
            response.raise_for_status()
            result = response.json()
            return result['choices'][0]['message']['content']
        except Exception as e:
            logger.debug(f"❌ {self.server_name.upper()} 同步API调用失败: {e}")
            return ""
    
    def _format_error_details(self, e: Exception) -> str:
        """格式化错误详情"""
        error_type = e.__class__.__name__
        error_msg = str(e)
        if isinstance(e, aiohttp.ClientError):
            if isinstance(e, aiohttp.ClientTimeout):
                return f"请求超时 ({error_type}): {error_msg}"
            elif isinstance(e, aiohttp.ClientConnectionError):
                return f"连接错误 ({error_type}): {error_msg}"
            else:
                return f"HTTP请求错误 ({error_type}): {error_msg}"
        elif isinstance(e, asyncio.TimeoutError):
            return f"异步操作超时: {error_msg}"
        else:
            return f"未知错误 ({error_type}): {error_msg}"
    

    
    async def call_async_with_format_validation(
        self, 
        session: aiohttp.ClientSession, 
        prompt: str, 
        validator: Callable[[str], Union[bool, Dict[str, Any]]],
        max_tokens: int = 2048, 
        temperature: float = 0.0,
        max_retries: Optional[int] = None, 
        retry_delay: Optional[float] = None,
        format_retry_prompt: Optional[str] = None,
        module: Optional[str] = None,
        component: Optional[str] = None
    ) -> Union[str, Dict[str, Any]]:
        """异步调用LLM API，带格式验证和重试
        
        Args:
            session: aiohttp会话
            prompt: 输入提示
            validator: 格式验证函数，返回True/False或验证结果字典
            max_tokens: 最大token数
            temperature: 温度参数
            max_retries: 最大重试次数
            retry_delay: 重试间隔（秒）
            format_retry_prompt: 格式重试提示词模板，如果为None则使用默认提示
            
        Returns:
            LLM的响应内容或验证结果
        """
        headers = {"Content-Type": "application/json"}
        
        data = {
            "model": self.config.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        # 从配置获取重试参数
        if max_retries is None or retry_delay is None:
            try:
                from config.data_processing.workflow.workflow_config import get_workflow_config
                workflow_config = get_workflow_config()
                format_config = workflow_config.get_format_validation_config(module or "", component or "")
                
                if max_retries is None:
                    max_retries = format_config.get('max_retries', 3)
                if retry_delay is None:
                    retry_delay = format_config.get('retry_delay', 1.0)
            except Exception as e:
                logger.warning(f"获取格式验证配置失败，使用默认值: {e}")
                if max_retries is None:
                    max_retries = 3
                if retry_delay is None:
                    retry_delay = 1.0
        
        # 确保参数不为None
        max_retries = max_retries or 3
        retry_delay = retry_delay or 1.0
        
        # 默认格式重试提示
        if format_retry_prompt is None:
            format_retry_prompt = """您的回答格式不正确，请严格按照要求的格式重新回答。

        原始问题：
        {prompt}

        请确保您的回答符合以下要求：
        1. 如果是JSON格式，请确保是有效的JSON
        2. 如果是特定格式，请严格按照示例格式
        3. 不要添加额外的解释或说明

        请重新回答："""
        
        for attempt in range(max_retries):
            try:
                async with session.post(
                    self.config.chat_completions_url,
                    headers=headers,
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=self.config.timeout)
                ) as response:
                    response.raise_for_status()
                    result = await response.json()
                    response_content = result['choices'][0]['message']['content']
                    
                    # 验证格式
                    validation_result = validator(response_content)
                    
                    if validation_result is True or (isinstance(validation_result, dict) and validation_result.get('valid', False)):
                        # 格式验证通过
                        return response_content if validation_result is True else validation_result
                    else:
                        # 格式验证失败，需要重试
                        if attempt < max_retries - 1:
                            logger.warning(f"❌ {self.server_name.upper()} 格式验证失败 (尝试 {attempt + 1}/{max_retries})")
                            logger.warning(f"   响应内容: {response_content[:200]}...")
                            
                            # 构建重试提示
                            retry_prompt = format_retry_prompt.format(prompt=prompt)
                            if isinstance(validation_result, dict) and 'error' in validation_result:
                                retry_prompt += f"\n\n具体错误: {validation_result['error']}"
                            
                            # 更新请求数据
                            data["messages"] = [
                                {"role": "user", "content": prompt},
                                {"role": "assistant", "content": response_content},
                                {"role": "user", "content": retry_prompt}
                            ]
                            
                            logger.warning(f"   即将重试，等待 {retry_delay * (attempt + 1):.1f} 秒...")
                            await asyncio.sleep(retry_delay * (attempt + 1))
                            continue
                        else:
                            # 最后一次尝试也失败
                            logger.error(f"❌ {self.server_name.upper()} 格式验证失败，已达到最大重试次数")
                            logger.error(f"   最终响应内容: {response_content}")
                            return response_content  # 返回最后一次的响应
                            
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                if attempt < max_retries - 1:
                    error_details = self._format_error_details(e)
                    logger.warning(f"❌ {self.server_name.upper()} 异步API调用失败 (尝试 {attempt + 1}/{max_retries})")
                    logger.warning(f"   错误详情: {error_details}")
                    await asyncio.sleep(retry_delay * (attempt + 1))
                    continue
                else:
                    error_details = self._format_error_details(e)
                    logger.error(f"❌ {self.server_name.upper()} 异步API调用失败，已达到最大重试次数")
                    logger.error(f"   错误详情: {error_details}")
                    return ""
            except Exception as e:
                error_details = self._format_error_details(e)
                logger.error(f"❌ {self.server_name.upper()} 异步API调用遇到非网络错误")
                logger.error(f"   错误详情: {error_details}")
                return ""
        
            return ""

