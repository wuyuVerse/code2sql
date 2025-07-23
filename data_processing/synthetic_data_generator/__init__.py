"""
合成数据生成器模块

用于自动生成**合成ORM数据包**的工具，这些数据包镜像真实提取样本的结构。
"""

from .generator import SyntheticDataGenerator
from .cli import main

__all__ = ["SyntheticDataGenerator", "main"] 