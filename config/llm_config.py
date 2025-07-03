"""LLM配置文件"""
from typing import Dict, Optional
from pydantic import BaseModel
import os
import asyncio
import aiohttp
import requests
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


class ServerConfig(BaseModel):
    """服务器配置"""
    host: str
    port: int
    api_key: Optional[str] = None
    model_name: str = "default"
    base_url: Optional[str] = None
    
    @property
    def full_url(self) -> str:
        """获取完整的API URL"""
        return f"http://{self.host}:{self.port}"
    
    @property
    def chat_completions_url(self) -> str:
        """获取聊天完成API的完整URL"""
        return f"{self.full_url}/v1/chat/completions"


class LLMConfig:
    """LLM配置管理"""
    
    # 预定义的服务器配置
    SERVERS = {
        "v3": ServerConfig(
            host="43.143.249.90",  # 更新为正确的V3地址
            port=8081,
            model_name="v3",
            api_key=os.getenv("V3_API_KEY", "your-api-key-here")
        ),
        "r1": ServerConfig(
            host="111.229.79.211", 
            port=8081,
            model_name="default",
            api_key=os.getenv("R1_API_KEY", "your-api-key-here")
        )
    }
    
    @classmethod
    def get_server_config(cls, server_name: str) -> ServerConfig:
        """获取指定服务器的配置"""
        if server_name not in cls.SERVERS:
            raise ValueError(f"未知的服务器名称: {server_name}")
        return cls.SERVERS[server_name]
    
    @classmethod
    def list_servers(cls) -> list[str]:
        """列出所有可用的服务器"""
        return list(cls.SERVERS.keys())
    
    @classmethod
    def get_openai_client_config(cls, server_name: str) -> Dict[str, str]:
        """获取OpenAI客户端配置"""
        config = cls.get_server_config(server_name)
        return {
            "api_key": config.api_key or "dummy-key",
            "base_url": f"{config.full_url}/v1"
        }
    
    @classmethod
    def call_api_sync(cls, server_name: str, prompt: str, max_tokens: int = 2048) -> str:
        """同步调用API"""
        config = cls.get_server_config(server_name)
        headers = {"Content-Type": "application/json"}
        
        data = {
            "model": config.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
            "max_tokens": max_tokens,
        }
        
        try:
            response = requests.post(
                config.chat_completions_url,
                headers=headers,
                json=data,
                timeout=45
            )
            response.raise_for_status()
            result = response.json()
            return result['choices'][0]['message']['content']
        except Exception as e:
            print(f"❌ {server_name.upper()} API同步调用失败: {e}")
            return ""
    
    @classmethod
    async def call_api_async(cls, session: aiohttp.ClientSession, server_name: str, prompt: str, max_tokens: int = 2048) -> str:
        """异步调用API"""
        config = cls.get_server_config(server_name)
        headers = {"Content-Type": "application/json"}
        
        data = {
            "model": config.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
            "max_tokens": max_tokens,
        }
        
        try:
            async with session.post(
                config.chat_completions_url,
                headers=headers,
                json=data,
                timeout=aiohttp.ClientTimeout(total=45)
            ) as response:
                response.raise_for_status()
                result = await response.json()
                return result['choices'][0]['message']['content']
        except Exception as e:
            print(f"❌ {server_name.upper()} API异步调用失败: {e}")
            return "" 