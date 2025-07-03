"""LLM配置加载器 - 从YAML文件加载配置"""
import os
import yaml
from typing import Dict, Optional, Any
from pathlib import Path
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()


class ServerConfig(BaseModel):
    """服务器配置"""
    host: str
    port: int
    model_name: str
    timeout: int = 45
    max_retries: int = 3
    api_key: Optional[str] = None
    
    @property
    def full_url(self) -> str:
        """获取完整的API URL"""
        return f"http://{self.host}:{self.port}"
    
    @property
    def chat_completions_url(self) -> str:
        """获取聊天完成API的完整URL"""
        return f"{self.full_url}/v1/chat/completions"


class LLMConfig:
    """LLM配置管理器 - 从YAML文件加载配置"""
    
    def __init__(self, config_file: str = "config/servers.yaml"):
        """初始化配置管理器
        
        Args:
            config_file: 配置文件路径
        """
        self.config_file = Path(config_file)
        self._config_data = None
        self._servers = None
        self.load_config()
    
    def load_config(self) -> None:
        """加载YAML配置文件"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self._config_data = yaml.safe_load(f)
            self._load_servers()
        except FileNotFoundError:
            raise FileNotFoundError(f"配置文件未找到: {self.config_file}")
        except yaml.YAMLError as e:
            raise ValueError(f"YAML配置文件格式错误: {e}")
    
    def _load_servers(self) -> None:
        """从配置数据加载服务器配置"""
        self._servers = {}
        
        # 检查配置数据是否已加载
        if self._config_data is None:
            raise ValueError("配置数据未加载，请先调用 load_config()")
            
        servers_config = self._config_data.get('servers', {})
        defaults = self._config_data.get('defaults', {})
        
        for server_name, server_data in servers_config.items():
            # 合并默认配置和服务器特定配置
            config = {**defaults, **server_data}
            
            # 处理API密钥
            api_key_env = config.get('api_key_env')
            api_key = None
            if api_key_env:
                api_key = os.getenv(api_key_env, config.get('default_api_key'))
            
            # 创建服务器配置对象
            self._servers[server_name] = ServerConfig(
                host=config['host'],
                port=config['port'],
                model_name=config['model_name'],
                timeout=config.get('timeout', defaults.get('timeout', 45)),
                max_retries=config.get('max_retries', defaults.get('max_retries', 3)),
                api_key=api_key
            )
    
    def get_server_config(self, server_name: str) -> ServerConfig:
        """获取指定服务器的配置
        
        Args:
            server_name: 服务器名称
            
        Returns:
            服务器配置对象
        """
        if self._servers is None:
            raise ValueError("服务器配置未初始化，请先调用 load_config()")
        
        if server_name not in self._servers:
            available = list(self._servers.keys())
            raise ValueError(f"未知的服务器名称: {server_name}，可用服务器: {available}")
        return self._servers[server_name]
    def list_servers(self) -> list[str]:
        """列出所有可用的服务器"""
        if self._servers is None:
            return []
        return list(self._servers.keys())
    
    def get_openai_client_config(self, server_name: str) -> Dict[str, str]:
        """获取OpenAI客户端配置
        Args:
            server_name: 服务器名称
            
        Returns:
            OpenAI客户端配置字典
        """
        config = self.get_server_config(server_name)
        return {
            "api_key": config.api_key or "dummy-key",
            "base_url": f"{config.full_url}/v1"
        }
    
    def get_defaults(self) -> Dict[str, Any]:
        """获取默认配置"""
        if self._config_data is None:
            return {}
        return self._config_data.get('defaults', {})
    
    def reload_config(self) -> None:
        """重新加载配置文件"""
        self.load_config()


# 全局配置实例
_global_config = None

def get_llm_config() -> LLMConfig:
    """获取全局LLM配置实例（单例模式）"""
    global _global_config
    if _global_config is None:
        _global_config = LLMConfig()
    return _global_config

def reload_llm_config() -> LLMConfig:
    """重新加载全局LLM配置"""
    global _global_config
    _global_config = None
    return get_llm_config() 