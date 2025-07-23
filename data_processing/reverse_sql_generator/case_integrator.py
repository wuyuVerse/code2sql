"""
案例整合器 - 整合完整的案例数据
"""
import json
import uuid
from typing import Dict, List, Optional
from config.data_processing.reverse_sql_generator.config import ReverseSQLConfig


class CaseIntegrator:
    """案例整合器 - 整合完整的案例数据"""
    
    def __init__(self, config: ReverseSQLConfig):
        """初始化案例整合器
        
        Args:
            config: 配置对象
        """
        self.config = config
    
    def integrate_case(self, scenario: str, base_sql: Dict, orm_code: Dict, 
                      caller_code: Dict, control_flow_sqls: List[Dict], 
                      complexity: str) -> Dict:
        """整合完整案例
        
        Args:
            scenario: 场景类型
            base_sql: 基础SQL
            orm_code: ORM代码
            caller_code: Caller代码
            control_flow_sqls: 控制流SQL变体
            complexity: 复杂度级别
            
        Returns:
            完整的案例数据
        """
        # 生成案例键
        case_key = self._generate_case_key(scenario, orm_code)
        
        # 构建完整案例
        case = {
            case_key: {
                "scenario": scenario,
                "complexity": complexity,
                "base_sql": base_sql,
                "orm_code": orm_code,
                "caller_code": caller_code,
                "control_flow_sqls": control_flow_sqls,
                "metadata": {
                    "generated_at": self._get_timestamp(),
                    "version": "1.0",
                    "generator": "reverse_sql_generator"
                }
            }
        }
        
        return case
    
    def integrate_if_else_case(self, scenario: str, base_sql: Dict, orm_code: Dict,
                             caller_code: Dict, if_else_sqls: List[Dict]) -> Dict:
        """整合if-else案例
        
        Args:
            scenario: 场景类型
            base_sql: 基础SQL
            orm_code: ORM代码
            caller_code: Caller代码
            if_else_sqls: if-else SQL变体
            
        Returns:
            if-else案例数据
        """
        case_key = self._generate_case_key(scenario, orm_code)
        
        case = {
            case_key: {
                "scenario": scenario,
                "type": "if-else",
                "base_sql": base_sql,
                "orm_code": orm_code,
                "caller_code": caller_code,
                "control_flow_sqls": if_else_sqls,
                "metadata": {
                    "generated_at": self._get_timestamp(),
                    "version": "1.0",
                    "generator": "reverse_sql_generator"
                }
            }
        }
        
        return case
    
    def integrate_switch_case(self, scenario: str, base_sql: Dict, orm_code: Dict,
                            caller_code: Dict, switch_sqls: List[Dict]) -> Dict:
        """整合switch案例
        
        Args:
            scenario: 场景类型
            base_sql: 基础SQL
            orm_code: ORM代码
            caller_code: Caller代码
            switch_sqls: switch SQL变体
            
        Returns:
            switch案例数据
        """
        case_key = self._generate_case_key(scenario, orm_code)
        
        case = {
            case_key: {
                "scenario": scenario,
                "type": "switch",
                "base_sql": base_sql,
                "orm_code": orm_code,
                "caller_code": caller_code,
                "control_flow_sqls": switch_sqls,
                "metadata": {
                    "generated_at": self._get_timestamp(),
                    "version": "1.0",
                    "generator": "reverse_sql_generator"
                }
            }
        }
        
        return case
    
    def integrate_dynamic_case(self, scenario: str, base_sql: Dict, orm_code: Dict,
                             caller_code: Dict, dynamic_sqls: List[Dict]) -> Dict:
        """整合动态查询案例
        
        Args:
            scenario: 场景类型
            base_sql: 基础SQL
            orm_code: ORM代码
            caller_code: Caller代码
            dynamic_sqls: 动态SQL变体
            
        Returns:
            动态查询案例数据
        """
        case_key = self._generate_case_key(scenario, orm_code)
        
        case = {
            case_key: {
                "scenario": scenario,
                "type": "dynamic",
                "base_sql": base_sql,
                "orm_code": orm_code,
                "caller_code": caller_code,
                "control_flow_sqls": dynamic_sqls,
                "metadata": {
                    "generated_at": self._get_timestamp(),
                    "version": "1.0",
                    "generator": "reverse_sql_generator"
                }
            }
        }
        
        return case
    
    def _generate_case_key(self, scenario: str, orm_code: Dict) -> str:
        """生成案例键
        
        Args:
            scenario: 场景类型
            orm_code: ORM代码
            
        Returns:
            案例键
        """
        method_name = orm_code.get('method_name', 'UnknownMethod')
        scenario_clean = scenario.replace('+', '_').replace(' ', '_').replace('(', '').replace(')', '')
        
        return f"reverse_{scenario_clean}_{method_name}"
    
    def _get_timestamp(self) -> str:
        """获取当前时间戳
        
        Returns:
            时间戳字符串
        """
        from datetime import datetime
        return datetime.now().isoformat() 