"""
合成数据生成器配置模块

提供合成数据生成器的配置管理和prompt模板
"""

from .config import SyntheticDataConfig
from .prompts import PROMPT_ORM, PROMPT_CALLER, PROMPT_META

__all__ = [
    'SyntheticDataConfig',
    'PROMPT_ORM',
    'PROMPT_CALLER', 
    'PROMPT_META'
] 