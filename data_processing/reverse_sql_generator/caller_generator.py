"""
Caller生成器 - 生成调用者代码
"""
import json
from typing import Dict, List
from utils.llm_client import LLMClient
from utils.format_validators import validate_reverse_caller_response
from config.data_processing.reverse_sql_generator.config import ReverseSQLConfig
from config.data_processing.reverse_sql_generator.prompts import CALLER_GENERATION_PROMPTS
import asyncio


class CallerGenerator:
    """Caller生成器 - 生成调用者代码"""
    
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
        print(f"  - 开始生成Caller...")
        
        max_retries = self.config.max_retries  # 从配置获取最大重试次数
        
        for attempt in range(max_retries):
            try:
                print(f"    🔄 Caller生成尝试 {attempt + 1}/{max_retries}")
                
                # 获取随机变量名
                var_names = self.config.get_random_names()
                print(f"    - 使用变量名: {var_names}")
                
                # 获取场景描述
                scenario_desc = self.config.get_scenario_description(scenario)
                
                # 构建基本Caller生成提示词
                prompt = CALLER_GENERATION_PROMPTS['basic_caller'].format(
                    orm_data=json.dumps(orm_code, ensure_ascii=False),
                    scenario=scenario,
                    scenario_desc=scenario_desc,
                    method_examples=var_names['method_examples'],
                    entity_examples=var_names['entity_examples'],
                    table_examples=var_names['table_examples'],
                    field_examples=var_names['field_examples']
                )
                print(f"    - 提示词长度: {len(prompt)} 字符")
                
                # 调用LLM生成Caller代码
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
                        caller_data = json.loads(json_content)
                        print(f"    - 从markdown提取JSON成功")
                    else:
                        caller_data = json.loads(response)
                        print(f"    - 直接解析成功")
                else:
                    caller_data = json.loads(str(response))
                    print(f"    - 字符串转换后解析成功")
                
                # 验证Caller数据
                self._validate_caller_data(caller_data)
                print(f"    - 数据验证通过")
                print(f"    - Caller生成完成: {caller_data.get('method_name', '')}")
                
                return caller_data
                
            except Exception as e:
                print(f"    ❌ Caller生成尝试 {attempt + 1} 失败: {e}")
                if attempt < max_retries - 1:
                    print(f"    ⏳ 等待 1 秒后重试...")
                    await asyncio.sleep(1)
                else:
                    print(f"    ❌ Caller生成失败: 已重试 {max_retries} 次")
                    raise
    
    async def generate_if_else_caller(self, orm_code: Dict, if_else_sqls: List[Dict], scenario: str) -> Dict:
        """生成if-else调用者代码
        
        Args:
            orm_code: ORM代码数据
            if_else_sqls: if-else SQL变体列表
            scenario: 场景类型
            
        Returns:
            if-else调用者代码数据
        """
        print(f"  - 开始生成if-else Caller...")
        print(f"  - SQL变体数量: {len(if_else_sqls)}")
        
        # 获取随机变量名
        var_names = self.config.get_random_names()
        print(f"  - 使用变量名: {var_names}")
        
        # 简化SQL变体数据，避免提示词过长
        simplified_sqls = []
        for i, sql_variant in enumerate(if_else_sqls):
            simplified_sql = {
                "query": sql_variant.get("query", ""),
                "branch": sql_variant.get("branch", f"branch_{i}"),
                "description": sql_variant.get("description", f"分支{i}")
            }
            simplified_sqls.append(simplified_sql)
        
        # 构建if-else Caller生成提示词
        prompt = CALLER_GENERATION_PROMPTS['if_else_caller'].format(
            orm_data=json.dumps(orm_code, ensure_ascii=False),
            if_else_sqls=json.dumps(simplified_sqls, ensure_ascii=False),
            scenario=scenario,
            method_examples=var_names['method_examples'],
            entity_examples=var_names['entity_examples'],
            table_examples=var_names['table_examples'],
            field_examples=var_names['field_examples']
        )
        print(f"  - 提示词长度: {len(prompt)} 字符")
        
        # 调用LLM生成if-else Caller代码
        print(f"  - 调用LLM ({self.config.llm_server})...")
        response = await self.llm_client.call_async_with_format_validation(
            self.session,
            prompt,
            validator=validate_reverse_caller_response,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            module="reverse_sql_generator"
        )
        
        print(f"  - LLM响应类型: {type(response)}")
        if isinstance(response, dict):
            print(f"  - 响应状态: {response.get('valid', 'unknown')}")
            if 'error' in response:
                print(f"  - 错误信息: {response['error']}")
        
        # 解析响应
        if isinstance(response, dict) and 'valid' in response:
            if response['valid']:
                caller_data = json.loads(response.get('content', '{}'))
                print(f"  - 解析成功，Caller长度: {len(str(caller_data))}")
            else:
                error_msg = response.get('error', '未知错误')
                print(f"  - 验证失败: {error_msg}")
                raise ValueError(f"if-else Caller生成失败: {error_msg}")
        else:
            print(f"  - 直接解析响应: {type(response)}")
            try:
                # 如果response是字符串，尝试解析JSON
                if isinstance(response, str):
                    # 尝试提取JSON内容（处理markdown格式）
                    import re
                    json_match = re.search(r'```json\s*({.*?})\s*```', response, re.DOTALL)
                    if json_match:
                        json_content = json_match.group(1)
                        caller_data = json.loads(json_content)
                        print(f"  - 从markdown提取JSON成功")
                    else:
                        # 尝试直接解析
                        caller_data = json.loads(response)
                        print(f"  - 直接解析成功")
                else:
                    # 如果response已经是字典，直接使用
                    caller_data = response
                    print(f"  - 使用字典响应")
            except Exception as e:
                print(f"  - 直接解析失败: {e}")
                print(f"  - 响应内容: {str(response)[:200]}...")
                raise ValueError(f"if-else Caller响应解析失败: {e}")
        
        # 验证Caller数据
        try:
            self._validate_caller_data(caller_data)
            print(f"  - 数据验证通过")
        except Exception as e:
            print(f"  - 数据验证失败: {e}")
            raise
        
        print(f"  - if-else Caller生成完成: {caller_data.get('method_name', '')}")
        return caller_data
    
    async def generate_if_else_orm_caller(self, orm_code: Dict, if_else_orm_sqls: List[Dict], scenario: str) -> Dict:
        """生成if-else+orm调用者代码
        
        Args:
            orm_code: ORM代码数据
            if_else_orm_sqls: if-else+orm SQL变体列表
            scenario: 场景类型
            
        Returns:
            if-else+orm调用者代码数据
        """
        print(f"  - 开始生成if-else+orm Caller...")
        print(f"  - SQL变体数量: {len(if_else_orm_sqls)}")
        
        # 获取随机变量名
        var_names = self.config.get_random_names()
        print(f"  - 使用变量名: {var_names}")
        
        # 简化SQL变体数据，避免提示词过长
        simplified_sqls = []
        for i, sql_variant in enumerate(if_else_orm_sqls):
            simplified_sql = {
                "query": sql_variant.get("query", ""),
                "branch": sql_variant.get("branch", f"branch_{i}"),
                "description": sql_variant.get("description", f"分支{i}")
            }
            simplified_sqls.append(simplified_sql)
        
        # 构建if-else+orm Caller生成提示词
        prompt = CALLER_GENERATION_PROMPTS['if_else_caller'].format(
            orm_data=json.dumps(orm_code, ensure_ascii=False),
            if_else_sqls=json.dumps(simplified_sqls, ensure_ascii=False),
            scenario=scenario,
            method_examples=var_names['method_examples'],
            entity_examples=var_names['entity_examples'],
            table_examples=var_names['table_examples'],
            field_examples=var_names['field_examples']
        )
        print(f"  - 提示词长度: {len(prompt)} 字符")
        
        # 调用LLM生成if-else+orm Caller代码
        print(f"  - 调用LLM ({self.config.llm_server})...")
        response = await self.llm_client.call_async_with_format_validation(
            self.session,
            prompt,
            validator=validate_reverse_caller_response,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            module="reverse_sql_generator"
        )
        
        print(f"  - LLM响应类型: {type(response)}")
        if isinstance(response, dict):
            print(f"  - 响应状态: {response.get('valid', 'unknown')}")
            if 'error' in response:
                print(f"  - 错误信息: {response['error']}")
        
        # 解析响应
        if isinstance(response, dict) and 'valid' in response:
            if response['valid']:
                caller_data = json.loads(response.get('content', '{}'))
                print(f"  - 解析成功，Caller长度: {len(str(caller_data))}")
            else:
                error_msg = response.get('error', '未知错误')
                print(f"  - 验证失败: {error_msg}")
                raise ValueError(f"if-else+orm Caller生成失败: {error_msg}")
        else:
            print(f"  - 直接解析响应: {type(response)}")
            try:
                # 如果response是字符串，尝试解析JSON
                if isinstance(response, str):
                    # 尝试提取JSON内容（处理markdown格式）
                    import re
                    json_match = re.search(r'```json\s*({.*?})\s*```', response, re.DOTALL)
                    if json_match:
                        json_content = json_match.group(1)
                        caller_data = json.loads(json_content)
                        print(f"  - 从markdown提取JSON成功")
                    else:
                        # 尝试直接解析
                        caller_data = json.loads(response)
                        print(f"  - 直接解析成功")
                else:
                    # 如果response已经是字典，直接使用
                    caller_data = response
                    print(f"  - 使用字典响应")
            except Exception as e:
                print(f"  - 直接解析失败: {e}")
                print(f"  - 响应内容: {str(response)[:200]}...")
                raise ValueError(f"if-else+orm Caller响应解析失败: {e}")
        
        # 验证Caller数据
        try:
            self._validate_caller_data(caller_data)
            print(f"  - 数据验证通过")
        except Exception as e:
            print(f"  - 数据验证失败: {e}")
            raise ValueError(f"if-else+orm Caller数据验证失败: {e}")
        
        print(f"  - if-else+orm Caller生成完成: {caller_data.get('method_name', '')}")
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
            validator=validate_reverse_caller_response,
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
            动态条件调用者代码数据
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
            validator=validate_reverse_caller_response,
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
    
    async def generate_complex_control_caller(self, orm_code: Dict, complex_sqls: List[Dict], scenario: str) -> Dict:
        """生成复杂控制流Caller代码
        
        Args:
            orm_code: ORM代码数据
            complex_sqls: 复杂控制流SQL变体列表
            scenario: 场景类型
            
        Returns:
            复杂控制流Caller代码数据
        """
        print(f"  - 开始生成复杂控制流Caller...")
        print(f"  - SQL变体数量: {len(complex_sqls)}")
        
        # 获取随机变量名
        var_names = self.config.get_random_names()
        print(f"  - 使用变量名: {var_names}")
        
        # 简化SQL变体数据，避免提示词过长
        simplified_sqls = []
        for i, sql_variant in enumerate(complex_sqls):
            simplified_sql = {
                "query": sql_variant.get("query", ""),
                "variant": sql_variant.get("variant", f"variant_{i}"),
                "description": sql_variant.get("description", f"变体{i}")
            }
            simplified_sqls.append(simplified_sql)
        
        # 构建复杂控制流Caller生成提示词
        prompt = CALLER_GENERATION_PROMPTS['complex_control_caller'].format(
            orm_data=json.dumps(orm_code, ensure_ascii=False),
            complex_sqls=json.dumps(simplified_sqls, ensure_ascii=False),
            scenario=scenario,
            method_examples=var_names['method_examples'],
            entity_examples=var_names['entity_examples'],
            table_examples=var_names['table_examples'],
            field_examples=var_names['field_examples']
        )
        print(f"  - 提示词长度: {len(prompt)} 字符")
        
        # 调用LLM生成复杂控制流Caller代码
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
                caller_data = json.loads(json_content)
                print(f"  - 从markdown提取JSON成功")
            else:
                caller_data = json.loads(response)
                print(f"  - 直接解析成功")
        else:
            caller_data = json.loads(str(response))
            print(f"  - 字符串转换后解析成功")
        
        # 验证Caller数据
        self._validate_caller_data(caller_data)
        print(f"  - 数据验证通过")
        print(f"  - 复杂控制流Caller生成完成: {caller_data.get('method_name', '')}")
        
        return caller_data
    
    async def generate_fixed_params_caller(self, orm_code: Dict, fixed_sqls: List[Dict], scenario: str) -> Dict:
        """生成固定参数Caller代码
        
        Args:
            orm_code: ORM代码数据
            fixed_sqls: 固定参数SQL变体列表
            scenario: 场景类型
            
        Returns:
            固定参数Caller代码数据
        """
        print(f"  - 开始生成固定参数Caller...")
        print(f"  - SQL变体数量: {len(fixed_sqls)}")
        
        # 获取随机变量名
        var_names = self.config.get_random_names()
        print(f"  - 使用变量名: {var_names}")
        
        # 简化SQL变体数据，避免提示词过长
        simplified_sqls = []
        for i, sql_variant in enumerate(fixed_sqls):
            simplified_sql = {
                "query": sql_variant.get("query", ""),
                "variant": sql_variant.get("variant", f"variant_{i}"),
                "description": sql_variant.get("description", f"变体{i}")
            }
            simplified_sqls.append(simplified_sql)
        
        # 构建固定参数Caller生成提示词
        prompt = CALLER_GENERATION_PROMPTS['fixed_params_caller'].format(
            orm_data=json.dumps(orm_code, ensure_ascii=False),
            fixed_sqls=json.dumps(simplified_sqls, ensure_ascii=False),
            scenario=scenario,
            method_examples=var_names['method_examples'],
            entity_examples=var_names['entity_examples'],
            table_examples=var_names['table_examples'],
            field_examples=var_names['field_examples']
        )
        print(f"  - 提示词长度: {len(prompt)} 字符")
        
        # 调用LLM生成固定参数Caller代码
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
                caller_data = json.loads(json_content)
                print(f"  - 从markdown提取JSON成功")
            else:
                caller_data = json.loads(response)
                print(f"  - 直接解析成功")
        else:
            caller_data = json.loads(str(response))
            print(f"  - 字符串转换后解析成功")
        
        # 验证Caller数据
        self._validate_caller_data(caller_data)
        print(f"  - 数据验证通过")
        print(f"  - 固定参数Caller生成完成: {caller_data.get('method_name', '')}")
        
        return caller_data
    
    async def generate_if_else_switch_mixed_caller(self, orm_code: Dict, mixed_sqls: List[Dict], scenario: str) -> Dict:
        """生成if-else+switch混合Caller代码
        
        Args:
            orm_code: ORM代码数据
            mixed_sqls: if-else+switch混合SQL变体列表
            scenario: 场景类型
            
        Returns:
            if-else+switch混合Caller代码数据
        """
        print(f"  - 开始生成if-else+switch混合Caller...")
        print(f"  - SQL变体数量: {len(mixed_sqls)}")
        
        # 获取随机变量名
        var_names = self.config.get_random_names()
        print(f"  - 使用变量名: {var_names}")
        
        # 简化SQL变体数据，避免提示词过长
        simplified_sqls = []
        for i, sql_variant in enumerate(mixed_sqls):
            simplified_sql = {
                "query": sql_variant.get("query", ""),
                "variant": sql_variant.get("variant", f"variant_{i}"),
                "description": sql_variant.get("description", f"变体{i}")
            }
            simplified_sqls.append(simplified_sql)
        
        # 构建if-else+switch混合Caller生成提示词
        prompt = CALLER_GENERATION_PROMPTS['if_else_switch_mixed_caller'].format(
            orm_data=json.dumps(orm_code, ensure_ascii=False),
            mixed_sqls=json.dumps(simplified_sqls, ensure_ascii=False),
            scenario=scenario,
            method_examples=var_names['method_examples'],
            entity_examples=var_names['entity_examples'],
            table_examples=var_names['table_examples'],
            field_examples=var_names['field_examples']
        )
        print(f"  - 提示词长度: {len(prompt)} 字符")
        
        # 调用LLM生成if-else+switch混合Caller代码
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
                caller_data = json.loads(json_content)
                print(f"  - 从markdown提取JSON成功")
            else:
                caller_data = json.loads(response)
                print(f"  - 直接解析成功")
        else:
            caller_data = json.loads(str(response))
            print(f"  - 字符串转换后解析成功")
        
        # 验证Caller数据
        self._validate_caller_data(caller_data)
        print(f"  - 数据验证通过")
        print(f"  - if-else+switch混合Caller生成完成: {caller_data.get('method_name', '')}")
        
        return caller_data
    
    async def generate_conditional_chain_caller(self, orm_code: Dict, chain_sqls: List[Dict], scenario: str) -> Dict:
        """生成条件链式Caller代码
        
        Args:
            orm_code: ORM代码数据
            chain_sqls: 条件链式SQL变体列表
            scenario: 场景类型
            
        Returns:
            条件链式Caller代码数据
        """
        print(f"  - 开始生成条件链式Caller...")
        print(f"  - SQL变体数量: {len(chain_sqls)}")
        
        # 获取随机变量名
        var_names = self.config.get_random_names()
        print(f"  - 使用变量名: {var_names}")
        
        # 简化SQL变体数据，避免提示词过长
        simplified_sqls = []
        for i, sql_variant in enumerate(chain_sqls):
            simplified_sql = {
                "query": sql_variant.get("query", ""),
                "variant": sql_variant.get("variant", f"variant_{i}"),
                "description": sql_variant.get("description", f"变体{i}")
            }
            simplified_sqls.append(simplified_sql)
        
        # 构建条件链式Caller生成提示词
        prompt = CALLER_GENERATION_PROMPTS['conditional_chain_caller'].format(
            orm_data=json.dumps(orm_code, ensure_ascii=False),
            chain_sqls=json.dumps(simplified_sqls, ensure_ascii=False),
            scenario=scenario,
            method_examples=var_names['method_examples'],
            entity_examples=var_names['entity_examples'],
            table_examples=var_names['table_examples'],
            field_examples=var_names['field_examples']
        )
        print(f"  - 提示词长度: {len(prompt)} 字符")
        
        # 调用LLM生成条件链式Caller代码
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
                caller_data = json.loads(json_content)
                print(f"  - 从markdown提取JSON成功")
            else:
                caller_data = json.loads(response)
                print(f"  - 直接解析成功")
        else:
            caller_data = json.loads(str(response))
            print(f"  - 字符串转换后解析成功")
        
        # 验证Caller数据
        self._validate_caller_data(caller_data)
        print(f"  - 数据验证通过")
        print(f"  - 条件链式Caller生成完成: {caller_data.get('method_name', '')}")
        
        return caller_data
    
    async def generate_multi_branch_transaction_caller(self, orm_code: Dict, transaction_sqls: List[Dict], scenario: str) -> Dict:
        """生成多分支事务处理Caller代码
        
        Args:
            orm_code: ORM代码数据
            transaction_sqls: 多分支事务处理SQL变体列表
            scenario: 场景类型
            
        Returns:
            多分支事务处理Caller代码数据
        """
        print(f"  - 开始生成多分支事务处理Caller...")
        print(f"  - SQL变体数量: {len(transaction_sqls)}")
        
        # 获取随机变量名
        var_names = self.config.get_random_names()
        print(f"  - 使用变量名: {var_names}")
        
        # 简化SQL变体数据，避免提示词过长
        simplified_sqls = []
        for i, sql_variant in enumerate(transaction_sqls):
            simplified_sql = {
                "query": sql_variant.get("query", ""),
                "variant": sql_variant.get("variant", f"variant_{i}"),
                "description": sql_variant.get("description", f"变体{i}")
            }
            simplified_sqls.append(simplified_sql)
        
        # 构建多分支事务处理Caller生成提示词
        prompt = CALLER_GENERATION_PROMPTS['multi_branch_transaction_caller'].format(
            orm_data=json.dumps(orm_code, ensure_ascii=False),
            transaction_sqls=json.dumps(simplified_sqls, ensure_ascii=False),
            scenario=scenario,
            method_examples=var_names['method_examples'],
            entity_examples=var_names['entity_examples'],
            table_examples=var_names['table_examples'],
            field_examples=var_names['field_examples']
        )
        print(f"  - 提示词长度: {len(prompt)} 字符")
        
        # 调用LLM生成多分支事务处理Caller代码
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
                caller_data = json.loads(json_content)
                print(f"  - 从markdown提取JSON成功")
            else:
                caller_data = json.loads(response)
                print(f"  - 直接解析成功")
        else:
            caller_data = json.loads(str(response))
            print(f"  - 字符串转换后解析成功")
        
        # 验证Caller数据
        self._validate_caller_data(caller_data)
        print(f"  - 数据验证通过")
        print(f"  - 多分支事务处理Caller生成完成: {caller_data.get('method_name', '')}")
        
        return caller_data
    
    async def generate_state_machine_branch_caller(self, orm_code: Dict, state_machine_sqls: List[Dict], scenario: str) -> Dict:
        """生成状态机式分支Caller代码
        
        Args:
            orm_code: ORM代码数据
            state_machine_sqls: 状态机式分支SQL变体列表
            scenario: 场景类型
            
        Returns:
            状态机式分支Caller代码数据
        """
        print(f"  - 开始生成状态机式分支Caller...")
        print(f"  - SQL变体数量: {len(state_machine_sqls)}")
        
        # 获取随机变量名
        var_names = self.config.get_random_names()
        print(f"  - 使用变量名: {var_names}")
        
        # 简化SQL变体数据，避免提示词过长
        simplified_sqls = []
        for i, sql_variant in enumerate(state_machine_sqls):
            simplified_sql = {
                "query": sql_variant.get("query", ""),
                "variant": sql_variant.get("variant", f"variant_{i}"),
                "description": sql_variant.get("description", f"变体{i}")
            }
            simplified_sqls.append(simplified_sql)
        
        # 构建状态机式分支Caller生成提示词
        prompt = CALLER_GENERATION_PROMPTS['state_machine_branch_caller'].format(
            orm_data=json.dumps(orm_code, ensure_ascii=False),
            state_machine_sqls=json.dumps(simplified_sqls, ensure_ascii=False),
            scenario=scenario,
            method_examples=var_names['method_examples'],
            entity_examples=var_names['entity_examples'],
            table_examples=var_names['table_examples'],
            field_examples=var_names['field_examples']
        )
        print(f"  - 提示词长度: {len(prompt)} 字符")
        
        # 调用LLM生成状态机式分支Caller代码
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
                caller_data = json.loads(json_content)
                print(f"  - 从markdown提取JSON成功")
            else:
                caller_data = json.loads(response)
                print(f"  - 直接解析成功")
        else:
            caller_data = json.loads(str(response))
            print(f"  - 字符串转换后解析成功")
        
        # 验证Caller数据
        self._validate_caller_data(caller_data)
        print(f"  - 数据验证通过")
        print(f"  - 状态机式分支Caller生成完成: {caller_data.get('method_name', '')}")
        
        return caller_data
    
    async def generate_conditional_meta_caller(self, orm_code: Dict, meta_sqls: List[Dict], scenario: str) -> Dict:
        """生成条件分支+meta Caller代码
        
        Args:
            orm_code: ORM代码数据
            meta_sqls: 条件分支+meta SQL变体列表
            scenario: 场景类型
            
        Returns:
            条件分支+meta Caller代码数据
        """
        print(f"  - 开始生成条件分支+meta Caller...")
        print(f"  - SQL变体数量: {len(meta_sqls)}")
        
        # 获取随机变量名
        var_names = self.config.get_random_names()
        print(f"  - 使用变量名: {var_names}")
        
        # 简化SQL变体数据，避免提示词过长
        simplified_sqls = []
        for i, sql_variant in enumerate(meta_sqls):
            simplified_sql = {
                "query": sql_variant.get("query", ""),
                "variant": sql_variant.get("variant", f"variant_{i}"),
                "description": sql_variant.get("description", f"变体{i}")
            }
            simplified_sqls.append(simplified_sql)
        
        # 构建条件分支+meta Caller生成提示词
        prompt = CALLER_GENERATION_PROMPTS['conditional_meta_caller'].format(
            orm_data=json.dumps(orm_code, ensure_ascii=False),
            meta_sqls=json.dumps(simplified_sqls, ensure_ascii=False),
            scenario=scenario,
            method_examples=var_names['method_examples'],
            entity_examples=var_names['entity_examples'],
            table_examples=var_names['table_examples'],
            field_examples=var_names['field_examples']
        )
        print(f"  - 提示词长度: {len(prompt)} 字符")
        
        # 调用LLM生成条件分支+meta Caller代码
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
                caller_data = json.loads(json_content)
                print(f"  - 从markdown提取JSON成功")
            else:
                caller_data = json.loads(response)
                print(f"  - 直接解析成功")
        else:
            caller_data = json.loads(str(response))
            print(f"  - 字符串转换后解析成功")
        
        # 验证Caller数据
        self._validate_caller_data(caller_data)
        print(f"  - 数据验证通过")
        print(f"  - 条件分支+meta Caller生成完成: {caller_data.get('method_name', '')}")
        
        return caller_data
    
    def _validate_caller_data(self, caller_data: Dict):
        """验证Caller数据格式
        
        Args:
            caller_data: Caller数据
            
        Raises:
            ValueError: 数据格式错误
        """
        required_fields = ['method_name', 'parameters', 'code', 'return_type']
        for field in required_fields:
            if field not in caller_data:
                raise ValueError(f"缺少必需字段: {field}")
        
        if not isinstance(caller_data['parameters'], list):
            raise ValueError("parameters必须是列表")
        
        if not caller_data['code'].strip():
            raise ValueError("Caller代码不能为空")
    
    async def close(self):
        """关闭会话"""
        if self._session:
            await self._session.close()
            self._session = None 