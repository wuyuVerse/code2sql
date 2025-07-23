"""
反向SQL生成器核心逻辑
"""
import json
import asyncio
from typing import Dict, List, Optional, Tuple
from pathlib import Path

from utils.llm_client import LLMClient
from config.data_processing.reverse_sql_generator.config import ReverseSQLConfig
from .sql_generator import SQLGenerator
from .orm_mapper import ORMMapper
from .caller_generator import CallerGenerator
from .control_flow_processor import ControlFlowProcessor
from .case_integrator import CaseIntegrator


class ReverseSQLGenerator:
    """反向SQL生成器 - 从SQL开始生成ORM和Caller代码"""
    
    def __init__(self, config: ReverseSQLConfig):
        """初始化反向生成器
        
        Args:
            config: 配置对象
        """
        self.config = config
        self.llm_client = LLMClient(config.llm_server)
        self._session = None
        
        # 初始化各个组件
        self.sql_generator = SQLGenerator(config, self.llm_client)
        self.orm_mapper = ORMMapper(config, self.llm_client)
        self.caller_generator = CallerGenerator(config, self.llm_client)
        self.control_flow_processor = ControlFlowProcessor(config, self.llm_client)
        self.case_integrator = CaseIntegrator(config)
    
    @property
    def session(self):
        """获取aiohttp session（懒加载）"""
        if self._session is None:
            import aiohttp
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def generate_complete_case(self, scenario: str, complexity: str = "simple") -> Dict:
        """生成完整的案例（SQL → ORM → Caller）
        
        Args:
            scenario: 场景类型
            complexity: 复杂度级别 (simple, medium, complex)
            
        Returns:
            完整的案例数据
        """
        print(f"开始生成反向案例: {scenario} ({complexity})")
        
        # 1. 生成完整SQL查询
        print("步骤1: 生成完整SQL查询...")
        base_sql = await self.sql_generator.generate_complete_sql(scenario, complexity)
        print(f"  - 生成基础SQL: {base_sql['query']}")
        
        # 2. 生成ORM代码
        print("步骤2: 生成ORM代码...")
        orm_code = await self.orm_mapper.sql_to_orm(base_sql)
        print(f"  - 生成ORM方法: {orm_code['method_name']}")
        
        # 3. 生成Caller代码
        print("步骤3: 生成Caller代码...")
        caller_code = await self.caller_generator.generate_caller(orm_code, scenario)
        print(f"  - 生成Caller方法: {caller_code['method_name']}")
        
        # 4. 处理控制流（如果需要）
        if complexity in ["medium", "complex"]:
            print("步骤4: 处理控制流...")
            control_flow_sqls = await self.control_flow_processor.process_control_flow(
                base_sql, orm_code, scenario, complexity
            )
            print(f"  - 生成控制流SQL: {len(control_flow_sqls)} 个")
        else:
            control_flow_sqls = []
        
        # 5. 整合完整案例
        print("步骤5: 整合完整案例...")
        complete_case = self.case_integrator.integrate_case(
            scenario=scenario,
            base_sql=base_sql,
            orm_code=orm_code,
            caller_code=caller_code,
            control_flow_sqls=control_flow_sqls,
            complexity=complexity
        )
        
        print(f"✅ 反向案例生成完成: {complete_case['case_key']}")
        return complete_case
    
    async def generate_multiple_cases(self, scenarios_and_complexities: List[Tuple[str, str]]) -> Dict:
        """批量生成多个案例
        
        Args:
            scenarios_and_complexities: [(场景, 复杂度), ...]
            
        Returns:
            所有案例的集合
        """
        print(f"开始批量生成 {len(scenarios_and_complexities)} 个反向案例...")
        
        cases = {}
        for scenario, complexity in scenarios_and_complexities:
            try:
                case = await self.generate_complete_case(scenario, complexity)
                cases.update(case)
            except Exception as e:
                print(f"❌ 生成案例失败 {scenario} ({complexity}): {e}")
                continue
        
        print(f"✅ 批量生成完成: {len(cases)} 个案例")
        return cases
    
    async def generate_if_else_case(self, scenario: str) -> Dict:
        """生成if-else结构的案例
        
        Args:
            scenario: 场景类型
            
        Returns:
            if-else案例数据
        """
        print(f"生成if-else案例: {scenario}")
        
        # 1. 生成基础SQL
        base_sql = await self.sql_generator.generate_complete_sql(scenario, "simple")
        
        # 2. 生成ORM代码
        orm_code = await self.orm_mapper.sql_to_orm(base_sql)
        
        # 3. 生成if-else控制流SQL
        if_else_sqls = await self.control_flow_processor.generate_if_else_sqls(
            base_sql, orm_code, scenario
        )
        
        # 4. 生成Caller代码
        caller_code = await self.caller_generator.generate_if_else_caller(
            orm_code, if_else_sqls, scenario
        )
        
        # 5. 整合案例
        case = self.case_integrator.integrate_if_else_case(
            scenario, base_sql, orm_code, caller_code, if_else_sqls
        )
        
        return case
    
    async def generate_switch_case(self, scenario: str) -> Dict:
        """生成switch结构的案例
        
        Args:
            scenario: 场景类型
            
        Returns:
            switch案例数据
        """
        print(f"生成switch案例: {scenario}")
        
        # 1. 生成基础SQL
        base_sql = await self.sql_generator.generate_complete_sql(scenario, "simple")
        
        # 2. 生成ORM代码
        orm_code = await self.orm_mapper.sql_to_orm(base_sql)
        
        # 3. 生成switch控制流SQL
        switch_sqls = await self.control_flow_processor.generate_switch_sqls(
            base_sql, orm_code, scenario
        )
        
        # 4. 生成Caller代码
        caller_code = await self.caller_generator.generate_switch_caller(
            orm_code, switch_sqls, scenario
        )
        
        # 5. 整合案例
        case = self.case_integrator.integrate_switch_case(
            scenario, base_sql, orm_code, caller_code, switch_sqls
        )
        
        return case
    
    async def generate_dynamic_case(self, scenario: str) -> Dict:
        """生成动态条件查询案例
        
        Args:
            scenario: 场景类型
            
        Returns:
            动态查询案例数据
        """
        print(f"生成动态查询案例: {scenario}")
        
        # 1. 生成基础SQL
        base_sql = await self.sql_generator.generate_complete_sql(scenario, "simple")
        
        # 2. 生成ORM代码
        orm_code = await self.orm_mapper.sql_to_orm(base_sql)
        
        # 3. 生成动态条件SQL变体
        dynamic_sqls = await self.control_flow_processor.generate_dynamic_sqls(
            base_sql, orm_code, scenario
        )
        
        # 4. 生成Caller代码
        caller_code = await self.caller_generator.generate_dynamic_caller(
            orm_code, dynamic_sqls, scenario
        )
        
        # 5. 整合案例
        case = self.case_integrator.integrate_dynamic_case(
            scenario, base_sql, orm_code, caller_code, dynamic_sqls
        )
        
        return case
    
    def validate_case(self, case: Dict) -> bool:
        """验证生成的案例
        
        Args:
            case: 案例数据
            
        Returns:
            验证结果
        """
        required_fields = ['scenario', 'base_sql', 'orm_code', 'caller_code']
        
        for field in required_fields:
            if field not in case:
                print(f"❌ 缺少必需字段: {field}")
                return False
        
        # 验证SQL格式
        if not self._validate_sql_format(case['base_sql']):
            print("❌ SQL格式验证失败")
            return False
        
        # 验证ORM代码格式
        if not self._validate_orm_format(case['orm_code']):
            print("❌ ORM代码格式验证失败")
            return False
        
        print("✅ 案例验证通过")
        return True
    
    def _validate_sql_format(self, sql_data: Dict) -> bool:
        """验证SQL格式"""
        required_sql_fields = ['query', 'table', 'fields', 'conditions']
        return all(field in sql_data for field in required_sql_fields)
    
    def _validate_orm_format(self, orm_data: Dict) -> bool:
        """验证ORM代码格式"""
        required_orm_fields = ['method_name', 'code', 'parameters']
        return all(field in orm_data for field in required_orm_fields) 