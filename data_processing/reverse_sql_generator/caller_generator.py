"""
Caller生成器 - 根据ORM代码生成调用者代码
"""
import json
from typing import Dict, List, Optional
from utils.llm_client import LLMClient
from config.data_processing.reverse_sql_generator.config import ReverseSQLConfig
from config.data_processing.reverse_sql_generator.prompts import CALLER_GENERATION_PROMPTS


class CallerGenerator:
    """Caller生成器 - 根据ORM代码生成调用者代码"""
    
    def __init__(self, config: ReverseSQLConfig, llm_client: LLMClient):
        """初始化Caller生成器
        
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
    
    async def generate_caller(self, orm_code: Dict, scenario: str) -> Dict:
        """生成基本调用者代码
        
        Args:
            orm_code: ORM代码数据
            scenario: 场景类型
            
        Returns:
            调用者代码数据
        """
        # 获取随机变量名
        var_names = self.config.get_random_names()
        scenario_desc = self.config.get_scenario_description(scenario)
        
        # 构建Caller生成提示词
        prompt = CALLER_GENERATION_PROMPTS['basic_caller'].format(
            orm_data=json.dumps(orm_code, ensure_ascii=False),
            scenario=scenario,
            scenario_desc=scenario_desc,
            method_examples=var_names['method_examples'],
            entity_examples=var_names['entity_examples'],
            table_examples=var_names['table_examples'],
            field_examples=var_names['field_examples']
        )
        
        # 调用LLM生成Caller代码
        response = await self.llm_client.call_async_with_format_validation(
            self.session,
            prompt,
            validator=lambda x: self._validate_caller_response(x),
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            module="reverse_sql_generator"
        )
        
        # 解析响应
        if isinstance(response, dict) and 'valid' in response:
            if response['valid']:
                caller_data = json.loads(response.get('content', '{}'))
            else:
                raise ValueError(f"Caller生成失败: {response.get('error', '未知错误')}")
        else:
            caller_data = json.loads(str(response))
        
        # 验证Caller数据
        self._validate_caller_data(caller_data)
        
        return caller_data
    
    async def generate_if_else_caller(self, orm_code: Dict, if_else_sqls: List[Dict], scenario: str) -> Dict:
        """生成if-else调用者代码
        
        Args:
            orm_code: ORM代码数据
            if_else_sqls: if-else SQL变体列表
            scenario: 场景类型
            
        Returns:
            if-else调用者代码数据
        """
        # 获取随机变量名
        var_names = self.config.get_random_names()
        
        # 构建if-else Caller生成提示词
        prompt = CALLER_GENERATION_PROMPTS['if_else_caller'].format(
            orm_data=json.dumps(orm_code, ensure_ascii=False),
            if_else_sqls=json.dumps(if_else_sqls, ensure_ascii=False),
            scenario=scenario,
            method_examples=var_names['method_examples'],
            entity_examples=var_names['entity_examples'],
            table_examples=var_names['table_examples'],
            field_examples=var_names['field_examples']
        )
        
        # 调用LLM生成if-else Caller代码
        response = await self.llm_client.call_async_with_format_validation(
            self.session,
            prompt,
            validator=lambda x: self._validate_caller_response(x),
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            module="reverse_sql_generator"
        )
        
        # 解析响应
        if isinstance(response, dict) and 'valid' in response:
            if response['valid']:
                caller_data = json.loads(response.get('content', '{}'))
            else:
                raise ValueError(f"if-else Caller生成失败: {response.get('error', '未知错误')}")
        else:
            caller_data = json.loads(str(response))
        
        # 验证Caller数据
        self._validate_caller_data(caller_data)
        
        return caller_data
    
    async def generate_switch_caller(self, orm_code: Dict, switch_sqls: List[Dict], scenario: str) -> Dict:
        """生成switch调用者代码
        
        Args:
            orm_code: ORM代码数据
            switch_sqls: switch SQL变体列表
            scenario: 场景类型
            
        Returns:
            switch调用者代码数据
        """
        # 获取随机变量名
        var_names = self.config.get_random_names()
        
        # 构建switch Caller生成提示词
        prompt = CALLER_GENERATION_PROMPTS['switch_caller'].format(
            orm_data=json.dumps(orm_code, ensure_ascii=False),
            switch_sqls=json.dumps(switch_sqls, ensure_ascii=False),
            scenario=scenario,
            method_examples=var_names['method_examples'],
            entity_examples=var_names['entity_examples'],
            table_examples=var_names['table_examples'],
            field_examples=var_names['field_examples']
        )
        
        # 调用LLM生成switch Caller代码
        response = await self.llm_client.call_async_with_format_validation(
            self.session,
            prompt,
            validator=lambda x: self._validate_caller_response(x),
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            module="reverse_sql_generator"
        )
        
        # 解析响应
        if isinstance(response, dict) and 'valid' in response:
            if response['valid']:
                caller_data = json.loads(response.get('content', '{}'))
            else:
                raise ValueError(f"switch Caller生成失败: {response.get('error', '未知错误')}")
        else:
            caller_data = json.loads(str(response))
        
        # 验证Caller数据
        self._validate_caller_data(caller_data)
        
        return caller_data
    
    async def generate_dynamic_caller(self, orm_code: Dict, dynamic_sqls: List[Dict], scenario: str) -> Dict:
        """生成动态条件调用者代码
        
        Args:
            orm_code: ORM代码数据
            dynamic_sqls: 动态SQL变体列表
            scenario: 场景类型
            
        Returns:
            动态调用者代码数据
        """
        # 获取随机变量名
        var_names = self.config.get_random_names()
        
        # 构建动态Caller生成提示词
        prompt = CALLER_GENERATION_PROMPTS['dynamic_caller'].format(
            orm_data=json.dumps(orm_code, ensure_ascii=False),
            dynamic_sqls=json.dumps(dynamic_sqls, ensure_ascii=False),
            scenario=scenario,
            method_examples=var_names['method_examples'],
            entity_examples=var_names['entity_examples'],
            table_examples=var_names['table_examples'],
            field_examples=var_names['field_examples']
        )
        
        # 调用LLM生成动态Caller代码
        response = await self.llm_client.call_async_with_format_validation(
            self.session,
            prompt,
            validator=lambda x: self._validate_caller_response(x),
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            module="reverse_sql_generator"
        )
        
        # 解析响应
        if isinstance(response, dict) and 'valid' in response:
            if response['valid']:
                caller_data = json.loads(response.get('content', '{}'))
            else:
                raise ValueError(f"动态Caller生成失败: {response.get('error', '未知错误')}")
        else:
            caller_data = json.loads(str(response))
        
        # 验证Caller数据
        self._validate_caller_data(caller_data)
        
        return caller_data
    
    def _validate_caller_response(self, response: str) -> Dict:
        """验证Caller响应格式
        
        Args:
            response: LLM响应
            
        Returns:
            验证结果
        """
        try:
            data = json.loads(response)
            required_fields = ['method_name', 'code', 'parameters', 'return_type']
            
            if not all(field in data for field in required_fields):
                return {'valid': False, 'error': '缺少必需字段'}
            
            # 验证代码格式
            if not self._validate_caller_code(data['code']):
                return {'valid': False, 'error': 'Caller代码格式错误'}
            
            return {'valid': True, 'content': response}
            
        except json.JSONDecodeError:
            return {'valid': False, 'error': 'JSON格式错误'}
    
    def _validate_caller_code(self, code: str) -> bool:
        """验证Caller代码格式（简单验证）
        
        Args:
            code: Caller代码
            
        Returns:
            格式是否正确
        """
        # 简单的Caller代码验证
        code_lower = code.lower()
        
        # 检查基本Go语法
        required_keywords = ['func', 'return']
        if not all(keyword in code_lower for keyword in required_keywords):
            return False
        
        # 检查调用相关关键字
        call_keywords = ['call', 'invoke', 'method', 'function']
        if not any(keyword in code_lower for keyword in call_keywords):
            return False
        
        return True
    
    def _validate_caller_data(self, caller_data: Dict):
        """验证Caller数据完整性
        
        Args:
            caller_data: Caller数据
            
        Raises:
            ValueError: 数据验证失败
        """
        required_fields = ['method_name', 'code', 'parameters', 'return_type']
        
        for field in required_fields:
            if field not in caller_data:
                raise ValueError(f"缺少必需字段: {field}")
        
        # 验证参数类型
        if not isinstance(caller_data['parameters'], list):
            raise ValueError("parameters必须是列表")
        
        # 验证代码不为空
        if not caller_data['code'].strip():
            raise ValueError("Caller代码不能为空") 