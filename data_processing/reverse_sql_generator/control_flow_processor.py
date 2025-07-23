"""
控制流处理器 - 处理if-else、switch等复杂控制流
"""
import json
from typing import Dict, List, Optional
from utils.llm_client import LLMClient
from config.data_processing.reverse_sql_generator.config import ReverseSQLConfig


class ControlFlowProcessor:
    """控制流处理器 - 处理if-else、switch等复杂控制流"""
    
    def __init__(self, config: ReverseSQLConfig, llm_client: LLMClient):
        """初始化控制流处理器
        
        Args:
            config: 配置对象
            llm_client: LLM客户端
        """
        self.config = config
        self.llm_client = llm_client
        self._session = None
        
        # 初始化SQL生成器
        from .sql_generator import SQLGenerator
        self.sql_generator = SQLGenerator(config, llm_client)
    
    @property
    def session(self):
        """获取aiohttp session（懒加载）"""
        if self._session is None:
            import aiohttp
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def process_control_flow(self, base_sql: Dict, orm_code: Dict, scenario: str, complexity: str) -> List[Dict]:
        """处理控制流，生成SQL变体
        
        Args:
            base_sql: 基础SQL
            orm_code: ORM代码
            scenario: 场景类型
            complexity: 复杂度级别
            
        Returns:
            SQL变体列表
        """
        if complexity == "simple":
            return []
        
        # 根据场景类型生成不同的控制流SQL
        if "if-else" in scenario:
            return await self.generate_if_else_sqls(base_sql, orm_code, scenario)
        elif "switch" in scenario:
            return await self.generate_switch_sqls(base_sql, orm_code, scenario)
        elif "dynamic" in scenario:
            return await self.generate_dynamic_sqls(base_sql, orm_code, scenario)
        else:
            return []
    
    async def generate_if_else_sqls(self, base_sql: Dict, orm_code: Dict, scenario: str) -> List[Dict]:
        """生成if-else SQL变体
        
        Args:
            base_sql: 基础SQL
            orm_code: ORM代码
            scenario: 场景类型
            
        Returns:
            if-else SQL变体列表
        """
        # 调用SQL生成器生成if-else变体
        return await self.sql_generator.generate_sql_variants(base_sql, "if_else")
    
    async def generate_switch_sqls(self, base_sql: Dict, orm_code: Dict, scenario: str) -> List[Dict]:
        """生成switch SQL变体
        
        Args:
            base_sql: 基础SQL
            orm_code: ORM代码
            scenario: 场景类型
            
        Returns:
            switch SQL变体列表
        """
        # 调用SQL生成器生成switch变体
        return await self.sql_generator.generate_sql_variants(base_sql, "switch")
    
    async def generate_dynamic_sqls(self, base_sql: Dict, orm_code: Dict, scenario: str) -> List[Dict]:
        """生成动态条件SQL变体
        
        Args:
            base_sql: 基础SQL
            orm_code: ORM代码
            scenario: 场景类型
            
        Returns:
            动态SQL变体列表
        """
        # 调用SQL生成器生成动态变体
        return await self.sql_generator.generate_sql_variants(base_sql, "dynamic") 