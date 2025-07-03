"""LLM客户端 - 负责实际的API调用"""
import asyncio
import aiohttp
import requests
from typing import Optional, Dict, Any
from openai import OpenAI
from config.llm_config import get_llm_config, ServerConfig


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
            print(f"❌ {self.server_name.upper()} 同步API调用失败: {e}")
            return ""
    
    async def call_async(self, session: aiohttp.ClientSession, prompt: str, 
                        max_tokens: int = 2048, temperature: float = 0.0) -> str:
        """异步调用LLM API
        
        Args:
            session: aiohttp会话
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
            async with session.post(
                self.config.chat_completions_url,
                headers=headers,
                json=data,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout)
            ) as response:
                response.raise_for_status()
                result = await response.json()
                return result['choices'][0]['message']['content']
        except Exception as e:
            print(f"❌ {self.server_name.upper()} 异步API调用失败: {e}")
            return ""
    
    def call_openai(self, prompt: str, max_tokens: int = 2048, temperature: float = 0.0) -> str:
        """使用OpenAI库调用LLM API
        
        Args:
            prompt: 输入提示
            max_tokens: 最大token数
            temperature: 温度参数
            
        Returns:
            LLM的响应内容
        """
        try:
            response = self.openai_client.chat.completions.create(
                model=self.config.model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
                timeout=self.config.timeout
            )
            
            if response and hasattr(response, 'choices') and response.choices:
                content = response.choices[0].message.content
                return content if content is not None else ""
            else:
                print(f"❌ {self.server_name.upper()} OpenAI调用失败: 响应格式不正确")
                return ""
        except Exception as e:
            print(f"❌ {self.server_name.upper()} OpenAI调用失败: {str(e)}")
            return ""


class LLMClientManager:
    """LLM客户端管理器 - 方便统一管理多个客户端"""
    
    def __init__(self):
        self._clients: Dict[str, LLMClient] = {}
        self.config_manager = get_llm_config()
    
    def get_client(self, server_name: str) -> LLMClient:
        """获取LLM客户端（单例模式）"""
        if server_name not in self._clients:
            self._clients[server_name] = LLMClient(server_name)
        return self._clients[server_name]
    
    def list_available_servers(self) -> list[str]:
        """列出所有可用的服务器"""
        return self.config_manager.list_servers()
    
    async def call_all_async(self, prompt: str, max_tokens: int = 2048) -> Dict[str, str]:
        """异步调用所有可用的LLM服务器"""
        async with aiohttp.ClientSession() as session:
            tasks = []
            for server_name in self.list_available_servers():
                client = self.get_client(server_name)
                task = client.call_async(session, prompt, max_tokens)
                tasks.append((server_name, task))
            
            results = {}
            for server_name, task in tasks:
                try:
                    result = await task
                    results[server_name] = result
                except Exception as e:
                    results[server_name] = f"调用失败: {str(e)}"
            
            return results 