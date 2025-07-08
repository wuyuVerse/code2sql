"""
LLM配置模块
包含LLM服务器配置、提示词模板等
"""

from .llm_config import get_llm_config, ServerConfig
from .prompts import *

__all__ = ['get_llm_config', 'ServerConfig'] 