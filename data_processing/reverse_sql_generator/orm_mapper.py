"""
ORM映射器 - 将SQL转换为ORM代码
"""
import json
from typing import Dict, Optional
from utils.llm_client import LLMClient
from config.data_processing.reverse_sql_generator.config import ReverseSQLConfig
from config.data_processing.reverse_sql_generator.prompts import ORM_MAPPING_PROMPTS


class ORMMapper:
    """ORM映射器 - 将SQL转换为ORM代码"""
    
    def __init__(self, config: ReverseSQLConfig, llm_client: LLMClient):
        """初始化ORM映射器
        
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
    
    async def sql_to_orm(self, sql_data: Dict) -> Dict:
        """将SQL查询转换为ORM代码
        
        Args:
            sql_data: SQL查询数据
            
        Returns:
            ORM代码数据
        """
        # 获取随机变量名
        var_names = self.config.get_random_names()
        
        # 构建ORM映射提示词
        prompt = ORM_MAPPING_PROMPTS['sql_to_orm'].format(
            sql_data=json.dumps(sql_data, ensure_ascii=False),
            method_examples=var_names['method_examples'],
            entity_examples=var_names['entity_examples'],
            table_examples=var_names['table_examples'],
            field_examples=var_names['field_examples']
        )
        
        # 调用LLM生成ORM代码
        response = await self.llm_client.call_async_with_format_validation(
            self.session,
            prompt,
            validator=lambda x: self._validate_orm_response(x),
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            module="reverse_sql_generator"
        )
        
        # 解析响应
        if isinstance(response, dict) and 'valid' in response:
            if response['valid']:
                orm_data = json.loads(response.get('content', '{}'))
            else:
                raise ValueError(f"ORM映射失败: {response.get('error', '未知错误')}")
        else:
            orm_data = json.loads(str(response))
        
        # 验证ORM数据
        self._validate_orm_data(orm_data)
        
        return orm_data
    
    def _validate_orm_response(self, response: str) -> Dict:
        """验证ORM响应格式
        
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
            if not self._validate_orm_code(data['code']):
                return {'valid': False, 'error': 'ORM代码格式错误'}
            
            return {'valid': True, 'content': response}
            
        except json.JSONDecodeError:
            return {'valid': False, 'error': 'JSON格式错误'}
    
    def _validate_orm_code(self, code: str) -> bool:
        """验证ORM代码格式（简单验证）
        
        Args:
            code: ORM代码
            
        Returns:
            格式是否正确
        """
        # 简单的ORM代码验证
        code_lower = code.lower()
        
        # 检查基本Go语法
        required_keywords = ['func', 'return']
        if not all(keyword in code_lower for keyword in required_keywords):
            return False
        
        # 检查GORM相关关键字
        gorm_keywords = ['gorm', 'db', 'table', 'where', 'find']
        if not any(keyword in code_lower for keyword in gorm_keywords):
            return False
        
        return True
    
    def _validate_orm_data(self, orm_data: Dict):
        """验证ORM数据完整性
        
        Args:
            orm_data: ORM数据
            
        Raises:
            ValueError: 数据验证失败
        """
        required_fields = ['method_name', 'code', 'parameters', 'return_type']
        
        for field in required_fields:
            if field not in orm_data:
                raise ValueError(f"缺少必需字段: {field}")
        
        # 验证参数类型
        if not isinstance(orm_data['parameters'], list):
            raise ValueError("parameters必须是列表")
        
        # 验证代码不为空
        if not orm_data['code'].strip():
            raise ValueError("ORM代码不能为空") 