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
        if scenario == "if-else+caller":
            return await self.generate_if_else_sqls(base_sql, orm_code, scenario)
        elif scenario == "if-else+orm":
            return await self.generate_if_else_orm_sqls(base_sql, orm_code, scenario)
        elif scenario == "switch":
            return await self.generate_switch_sqls(base_sql, orm_code, scenario)
        elif scenario == "dynamic_query":
            return await self.generate_dynamic_sqls(base_sql, orm_code, scenario)
        elif scenario == "complex_control":
            return await self.generate_complex_control_sqls(base_sql, orm_code, scenario)
        elif scenario == "fixed_params":
            return await self.generate_fixed_params_sqls(base_sql, orm_code, scenario)
        elif scenario == "if-else+switch_mixed":
            return await self.generate_if_else_switch_mixed_sqls(base_sql, orm_code, scenario)
        elif scenario == "conditional_chain":
            return await self.generate_conditional_chain_sqls(base_sql, orm_code, scenario)
        elif scenario == "multi_branch_transaction":
            return await self.generate_multi_branch_transaction_sqls(base_sql, orm_code, scenario)
        elif scenario == "state_machine_branch":
            return await self.generate_state_machine_branch_sqls(base_sql, orm_code, scenario)
        elif scenario == "conditional_meta":
            return await self.generate_conditional_meta_sqls(base_sql, orm_code, scenario)
        else:
            print(f"警告: 未识别的场景类型: {scenario}")
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
        return await self.sql_generator.generate_sql_variants(base_sql, "if_else", scenario, "medium")
    
    async def generate_if_else_orm_sqls(self, base_sql: Dict, orm_code: Dict, scenario: str) -> List[Dict]:
        """生成if-else+orm SQL变体
        
        Args:
            base_sql: 基础SQL
            orm_code: ORM代码
            scenario: 场景类型
            
        Returns:
            if-else+orm SQL变体列表
        """
        # 调用SQL生成器生成if-else+orm变体
        return await self.sql_generator.generate_sql_variants(base_sql, "if_else_orm", scenario, "medium")
    
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
        return await self.sql_generator.generate_sql_variants(base_sql, "switch", scenario, "medium")
    
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
        return await self.sql_generator.generate_sql_variants(base_sql, "dynamic", scenario, "medium")
    
    async def generate_complex_control_sqls(self, base_sql: Dict, orm_code: Dict, scenario: str) -> List[Dict]:
        """生成复杂控制流SQL变体（多层嵌套）
        
        Args:
            base_sql: 基础SQL
            orm_code: ORM代码
            scenario: 场景类型
            
        Returns:
            复杂控制流SQL变体列表
        """
        # 调用SQL生成器生成复杂控制流变体
        return await self.sql_generator.generate_sql_variants(base_sql, "complex_control", scenario, "complex")
    
    async def generate_fixed_params_sqls(self, base_sql: Dict, orm_code: Dict, scenario: str) -> List[Dict]:
        """生成固定参数SQL变体（包含固定参数和动态参数的不同组合）
        
        Args:
            base_sql: 基础SQL
            orm_code: ORM代码
            scenario: 场景类型
            
        Returns:
            固定参数SQL变体列表
        """
        # 调用SQL生成器生成固定参数变体
        return await self.sql_generator.generate_sql_variants(base_sql, "fixed_params", scenario, "simple")
    
    async def generate_if_else_switch_mixed_sqls(self, base_sql: Dict, orm_code: Dict, scenario: str) -> List[Dict]:
        """生成if-else+switch混合SQL变体
        
        Args:
            base_sql: 基础SQL
            orm_code: ORM代码
            scenario: 场景类型
            
        Returns:
            if-else+switch混合SQL变体列表
        """
        # 调用SQL生成器生成if-else+switch混合变体
        return await self.sql_generator.generate_sql_variants(base_sql, "if_else_switch_mixed", scenario, "complex")
    
    async def generate_conditional_chain_sqls(self, base_sql: Dict, orm_code: Dict, scenario: str) -> List[Dict]:
        """生成条件链式查询SQL变体
        
        Args:
            base_sql: 基础SQL
            orm_code: ORM代码
            scenario: 场景类型
            
        Returns:
            条件链式查询SQL变体列表
        """
        # 调用SQL生成器生成条件链式查询变体
        return await self.sql_generator.generate_sql_variants(base_sql, "conditional_chain", scenario, "medium")
    
    async def generate_multi_branch_transaction_sqls(self, base_sql: Dict, orm_code: Dict, scenario: str) -> List[Dict]:
        """生成多分支事务处理SQL变体
        
        Args:
            base_sql: 基础SQL
            orm_code: ORM代码
            scenario: 场景类型
            
        Returns:
            多分支事务处理SQL变体列表
        """
        # 调用SQL生成器生成多分支事务处理变体
        return await self.sql_generator.generate_sql_variants(base_sql, "multi_branch_transaction", scenario, "complex")
    
    async def generate_state_machine_branch_sqls(self, base_sql: Dict, orm_code: Dict, scenario: str) -> List[Dict]:
        """生成状态机式分支SQL变体
        
        Args:
            base_sql: 基础SQL
            orm_code: ORM代码
            scenario: 场景类型
            
        Returns:
            状态机式分支SQL变体列表
        """
        # 调用SQL生成器生成状态机式分支变体
        return await self.sql_generator.generate_sql_variants(base_sql, "state_machine_branch", scenario, "complex")
    
    async def generate_conditional_meta_sqls(self, base_sql: Dict, orm_code: Dict, scenario: str) -> List[Dict]:
        """生成条件分支+meta SQL变体
        
        Args:
            base_sql: 基础SQL
            orm_code: ORM代码
            scenario: 场景类型
            
        Returns:
            条件分支+meta SQL变体列表
        """
        # 调用SQL生成器生成条件分支+meta变体
        return await self.sql_generator.generate_sql_variants(base_sql, "conditional_meta", scenario, "medium")
    
    async def close(self):
        """关闭会话"""
        if self._session:
            await self._session.close()
            self._session = None 