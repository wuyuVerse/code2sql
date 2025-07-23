"""
SQL生成器 - 生成完整的SQL查询
"""
import json
import random
from typing import Dict, List, Optional
from utils.llm_client import LLMClient
from config.data_processing.reverse_sql_generator.config import ReverseSQLConfig
from config.data_processing.reverse_sql_generator.prompts import SQL_GENERATION_PROMPTS


class SQLGenerator:
    """SQL生成器 - 生成完整的SQL查询"""
    
    def __init__(self, config: ReverseSQLConfig, llm_client: LLMClient):
        """初始化SQL生成器
        
        Args:
            config: 配置对象
            llm_client: LLM客户端
        """
        self.config = config
        self.llm_client = llm_client
        self._session = None
    
    @property
    def session(self):
        """获取aiohttp session（懒加载）"""
        if self._session is None:
            import aiohttp
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def generate_complete_sql(self, scenario: str, complexity: str = "simple") -> Dict:
        """生成完整的SQL查询
        
        Args:
            scenario: 场景类型
            complexity: 复杂度级别
            
        Returns:
            完整的SQL查询数据
        """
        # 获取随机变量名
        var_names = self.config.get_random_names()
        
        # 构建SQL生成提示词
        prompt = self._build_sql_generation_prompt(scenario, complexity, var_names)
        
        # 调用LLM生成SQL
        response = await self.llm_client.call_async_with_format_validation(
            self.session,
            prompt,
            validator=lambda x: self._validate_sql_response(x),
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            module="reverse_sql_generator"
        )
        
        # 解析响应
        if isinstance(response, dict) and 'valid' in response:
            if response['valid']:
                sql_data = json.loads(response.get('content', '{}'))
            else:
                raise ValueError(f"SQL生成失败: {response.get('error', '未知错误')}")
        else:
            sql_data = json.loads(str(response))
        
        # 验证SQL数据
        self._validate_sql_data(sql_data)
        
        return sql_data
    
    def _build_sql_generation_prompt(self, scenario: str, complexity: str, var_names: Dict) -> str:
        """构建SQL生成提示词
        
        Args:
            scenario: 场景类型
            complexity: 复杂度级别
            var_names: 随机变量名
            
        Returns:
            提示词字符串
        """
        # 获取场景描述
        scenario_desc = self.config.get_scenario_description(scenario)
        
        # 获取复杂度配置
        complexity_config = self._get_complexity_config(complexity)
        
        # 构建提示词
        prompt = SQL_GENERATION_PROMPTS['complete_sql'].format(
            scenario=scenario,
            scenario_desc=scenario_desc,
            complexity=complexity,
            complexity_desc=complexity_config['description'],
            min_conditions=complexity_config['min_conditions'],
            max_conditions=complexity_config['max_conditions'],
            table_name=var_names['table_examples'],
            field_examples=var_names['field_examples'],
            entity_examples=var_names['entity_examples']
        )
        
        return prompt
    
    def _get_complexity_config(self, complexity: str) -> Dict:
        """获取复杂度配置
        
        Args:
            complexity: 复杂度级别
            
        Returns:
            复杂度配置
        """
        configs = {
            "simple": {
                "description": "简单查询，包含基本的SELECT、WHERE、ORDER BY",
                "min_conditions": 1,
                "max_conditions": 3
            },
            "medium": {
                "description": "中等复杂度，包含JOIN、GROUP BY、HAVING等",
                "min_conditions": 2,
                "max_conditions": 5
            },
            "complex": {
                "description": "复杂查询，包含子查询、窗口函数、复杂条件组合",
                "min_conditions": 3,
                "max_conditions": 8
            }
        }
        
        return configs.get(complexity, configs["simple"])
    
    def _validate_sql_response(self, response: str) -> Dict:
        """验证SQL响应格式
        
        Args:
            response: LLM响应
            
        Returns:
            验证结果
        """
        try:
            data = json.loads(response)
            required_fields = ['query', 'table', 'fields', 'conditions']
            
            if not all(field in data for field in required_fields):
                return {'valid': False, 'error': '缺少必需字段'}
            
            # 验证SQL语法
            if not self._validate_sql_syntax(data['query']):
                return {'valid': False, 'error': 'SQL语法错误'}
            
            return {'valid': True, 'content': response}
            
        except json.JSONDecodeError:
            return {'valid': False, 'error': 'JSON格式错误'}
    
    def _validate_sql_syntax(self, sql: str) -> bool:
        """验证SQL语法（简单验证）
        
        Args:
            sql: SQL语句
            
        Returns:
            语法是否正确
        """
        # 简单的SQL语法验证
        sql_lower = sql.lower()
        
        # 检查基本SQL关键字
        required_keywords = ['select', 'from']
        if not all(keyword in sql_lower for keyword in required_keywords):
            return False
        
        # 检查表名
        if 'from' in sql_lower:
            from_index = sql_lower.find('from')
            after_from = sql_lower[from_index:].strip()
            if not any(char.isalnum() for char in after_from[:20]):
                return False
        
        return True
    
    def _validate_sql_data(self, sql_data: Dict):
        """验证SQL数据完整性
        
        Args:
            sql_data: SQL数据
            
        Raises:
            ValueError: 数据验证失败
        """
        required_fields = ['query', 'table', 'fields', 'conditions']
        
        for field in required_fields:
            if field not in sql_data:
                raise ValueError(f"缺少必需字段: {field}")
        
        # 验证字段类型
        if not isinstance(sql_data['fields'], list):
            raise ValueError("fields必须是列表")
        
        if not isinstance(sql_data['conditions'], list):
            raise ValueError("conditions必须是列表")
        
        # 验证SQL不为空
        if not sql_data['query'].strip():
            raise ValueError("SQL查询不能为空")
    
    async def generate_sql_variants(self, base_sql: Dict, variant_type: str) -> List[Dict]:
        """生成SQL变体
        
        Args:
            base_sql: 基础SQL
            variant_type: 变体类型 (if_else, switch, dynamic)
            
        Returns:
            SQL变体列表
        """
        var_names = self.config.get_random_names()
        
        # 构建变体生成提示词
        prompt = SQL_GENERATION_PROMPTS[f'{variant_type}_variants'].format(
            base_sql=json.dumps(base_sql, ensure_ascii=False),
            table_name=var_names['table_examples'],
            field_examples=var_names['field_examples']
        )
        
        # 调用LLM生成变体
        response = await self.llm_client.call_async_with_format_validation(
            self.session,
            prompt,
            validator=lambda x: self._validate_sql_variants_response(x),
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            module="reverse_sql_generator"
        )
        
        # 解析响应
        if isinstance(response, dict) and 'valid' in response:
            if response['valid']:
                variants = json.loads(response.get('content', '[]'))
            else:
                raise ValueError(f"SQL变体生成失败: {response.get('error', '未知错误')}")
        else:
            variants = json.loads(str(response))
        
        return variants if isinstance(variants, list) else [variants]
    
    def _validate_sql_variants_response(self, response: str) -> Dict:
        """验证SQL变体响应格式
        
        Args:
            response: LLM响应
            
        Returns:
            验证结果
        """
        try:
            data = json.loads(response)
            
            if isinstance(data, list):
                # 验证列表中的每个SQL
                for sql_variant in data:
                    if not self._validate_sql_data_structure(sql_variant):
                        return {'valid': False, 'error': 'SQL变体格式错误'}
            else:
                # 单个SQL变体
                if not self._validate_sql_data_structure(data):
                    return {'valid': False, 'error': 'SQL变体格式错误'}
            
            return {'valid': True, 'content': response}
            
        except json.JSONDecodeError:
            return {'valid': False, 'error': 'JSON格式错误'}
    
    def _validate_sql_data_structure(self, sql_data: Dict) -> bool:
        """验证SQL数据结构
        
        Args:
            sql_data: SQL数据
            
        Returns:
            结构是否正确
        """
        required_fields = ['query', 'table', 'fields', 'conditions']
        return all(field in sql_data for field in required_fields) 