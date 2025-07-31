"""
ORM映射器 - 将SQL转换为ORM代码
"""
import json
from typing import Dict, List
from utils.llm_client import LLMClient
from utils.format_validators import validate_reverse_orm_response
from config.data_processing.reverse_sql_generator.config import ReverseSQLConfig
from config.data_processing.reverse_sql_generator.prompts import ORM_MAPPING_PROMPTS
import asyncio


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
    
    async def sql_to_orm(self, base_sql: Dict) -> Dict:
        """将SQL查询转换为ORM代码
        
        Args:
            base_sql: SQL数据
            
        Returns:
            ORM代码数据
        """
        print(f"  - 开始ORM映射...")
        
        max_retries = self.config.max_retries  # 从配置获取最大重试次数
        
        for attempt in range(max_retries):
            try:
                print(f"    🔄 ORM映射尝试 {attempt + 1}/{max_retries}")
                
                # 获取随机变量名
                var_names = self.config.get_random_names()
                print(f"    - 使用变量名: {var_names}")
                
                # 构建ORM映射提示词
                prompt = ORM_MAPPING_PROMPTS['sql_to_orm'].format(
                    sql_data=json.dumps(base_sql, ensure_ascii=False),
                    method_examples=var_names['method_examples'],
                    entity_examples=var_names['entity_examples'],
                    table_examples=var_names['table_examples'],
                    field_examples=var_names['field_examples']
                )
                print(f"    - 提示词长度: {len(prompt)} 字符")
                
                # 调用LLM进行ORM映射
                response = await self.llm_client.call_async_with_format_validation(
                    self.session,
                    prompt,
                    validator=lambda x: True,  # 简单验证，总是返回True
                    max_tokens=self.config.max_tokens,
                    temperature=self.config.temperature,
                    module="reverse_sql_generator"
                )
                
                print(f"    - LLM响应类型: {type(response)}")
                
                # 解析响应
                if isinstance(response, str):
                    import re
                    # 尝试从markdown中提取JSON
                    json_match = re.search(r'```json\s*({.*?})\s*```', response, re.DOTALL)
                    if json_match:
                        json_content = json_match.group(1)
                        orm_data = json.loads(json_content)
                        print(f"    - 从markdown提取JSON成功")
                    else:
                        orm_data = json.loads(response)
                        print(f"    - 直接解析成功")
                else:
                    orm_data = json.loads(str(response))
                    print(f"    - 字符串转换后解析成功")
                
                # 验证ORM数据
                self._validate_orm_data(orm_data)
                print(f"    - 数据验证通过")
                print(f"    - ORM映射完成: {orm_data.get('method_name', '')}")
                
                return orm_data
                
            except Exception as e:
                print(f"    ❌ ORM映射尝试 {attempt + 1} 失败: {e}")
                if attempt < max_retries - 1:
                    print(f"    ⏳ 等待 1 秒后重试...")
                    await asyncio.sleep(1)
                else:
                    print(f"    ❌ ORM映射失败: 已重试 {max_retries} 次")
                    raise
    
    async def sql_to_orm_with_if_else(self, base_sql: Dict, if_else_sqls: List[Dict]) -> Dict:
        """将SQL查询转换为包含if-else逻辑的ORM代码
        
        Args:
            base_sql: 基础SQL数据
            if_else_sqls: if-else SQL变体列表
            
        Returns:
            包含if-else逻辑的ORM代码数据
        """
        print(f"  - 开始生成包含if-else逻辑的ORM...")
        
        # 获取随机变量名
        var_names = self.config.get_random_names()
        print(f"  - 使用变量名: {var_names}")
        
        # 构建包含if-else逻辑的ORM生成提示词
        prompt = ORM_MAPPING_PROMPTS['sql_to_orm_with_if_else'].format(
            sql_data=json.dumps(base_sql, ensure_ascii=False),
            if_else_sqls=json.dumps(if_else_sqls, ensure_ascii=False),
            method_examples=var_names['method_examples'],
            entity_examples=var_names['entity_examples'],
            table_examples=var_names['table_examples'],
            field_examples=var_names['field_examples']
        )
        print(f"  - 提示词长度: {len(prompt)} 字符")
        
        # 调用LLM进行ORM映射
        response = await self.llm_client.call_async_with_format_validation(
            self.session,
            prompt,
            validator=lambda x: True,  # 简单验证，总是返回True
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            module="reverse_sql_generator"
        )
        
        print(f"  - LLM响应类型: {type(response)}")
        
        # 解析响应
        if isinstance(response, str):
            import re
            # 尝试从markdown中提取JSON
            json_match = re.search(r'```json\s*({.*?})\s*```', response, re.DOTALL)
            if json_match:
                json_content = json_match.group(1)
                orm_data = json.loads(json_content)
                print(f"  - 从markdown提取JSON成功")
            else:
                orm_data = json.loads(response)
                print(f"  - 直接解析成功")
        else:
            orm_data = json.loads(str(response))
            print(f"  - 字符串转换后解析成功")
        
        # 验证ORM数据
        self._validate_orm_data(orm_data)
        print(f"  - 数据验证通过")
        print(f"  - ORM映射完成: {orm_data.get('method_name', '')}")
        
        return orm_data
    
    async def sql_to_orm_for_multi_branch_transaction(self, base_sql: Dict) -> Dict:
        """为多分支事务处理场景生成专门的ORM代码
        
        Args:
            base_sql: 基础SQL数据
            
        Returns:
            多分支事务处理ORM代码数据
        """
        print(f"  - 开始生成多分支事务处理ORM...")
        
        max_retries = self.config.max_retries  # 从配置获取最大重试次数
        
        for attempt in range(max_retries):
            try:
                print(f"    🔄 多分支事务处理ORM生成尝试 {attempt + 1}/{max_retries}")
                
                # 获取随机变量名
                var_names = self.config.get_random_names()
                print(f"    - 使用变量名: {var_names}")
                
                # 构建多分支事务处理ORM生成提示词
                prompt = ORM_MAPPING_PROMPTS['sql_to_orm_multi_branch_transaction'].format(
                    sql_data=json.dumps(base_sql, ensure_ascii=False),
                    method_examples=var_names['method_examples'],
                    entity_examples=var_names['entity_examples'],
                    table_examples=var_names['table_examples'],
                    field_examples=var_names['field_examples']
                )
                print(f"    - 提示词长度: {len(prompt)} 字符")
                
                # 调用LLM进行ORM映射
                response = await self.llm_client.call_async_with_format_validation(
                    self.session,
                    prompt,
                    validator=lambda x: True,  # 简单验证，总是返回True
                    max_tokens=self.config.max_tokens,
                    temperature=self.config.temperature,
                    module="reverse_sql_generator"
                )
                
                print(f"    - LLM响应类型: {type(response)}")
                
                # 解析响应
                if isinstance(response, str):
                    import re
                    # 尝试从markdown中提取JSON
                    json_match = re.search(r'```json\s*({.*?})\s*```', response, re.DOTALL)
                    if json_match:
                        json_content = json_match.group(1)
                        orm_data = json.loads(json_content)
                        print(f"    - 从markdown提取JSON成功")
                    else:
                        orm_data = json.loads(response)
                        print(f"    - 直接解析成功")
                else:
                    orm_data = json.loads(str(response))
                    print(f"    - 字符串转换后解析成功")
                
                # 验证ORM数据
                self._validate_orm_data(orm_data)
                print(f"    - 数据验证通过")
                print(f"    - 多分支事务处理ORM映射完成: {orm_data.get('method_name', '')}")
                
                return orm_data
                
            except Exception as e:
                print(f"    ❌ 多分支事务处理ORM生成尝试 {attempt + 1} 失败: {e}")
                if attempt < max_retries - 1:
                    print(f"    ⏳ 等待 2 秒后重试...")
                    await asyncio.sleep(2)
                else:
                    print(f"    ❌ 多分支事务处理ORM生成失败: 已重试 {max_retries} 次")
                    raise
    
    def _validate_orm_data(self, orm_data: Dict):
        """验证ORM数据格式
        
        Args:
            orm_data: ORM数据
            
        Raises:
            ValueError: 数据格式错误
        """
        # 根据提示词模板，必需的字段
        required_fields = ['method_name', 'code', 'parameters', 'return_type', 'table', 'fields', 'conditions']
        for field in required_fields:
            if field not in orm_data:
                raise ValueError(f"缺少必需字段: {field}")
        
        if not isinstance(orm_data['fields'], list):
            raise ValueError("fields必须是列表")
        
        if not isinstance(orm_data['conditions'], list):
            raise ValueError("conditions必须是列表")
        
        if not isinstance(orm_data['parameters'], list):
            raise ValueError("parameters必须是列表")
        
        if not orm_data['code'].strip():
            raise ValueError("ORM代码不能为空")
    
    async def close(self):
        """关闭会话"""
        if self._session:
            await self._session.close()
            self._session = None 