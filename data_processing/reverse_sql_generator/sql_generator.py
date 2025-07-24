"""
SQL生成器 - 生成完整的SQL查询
"""
import json
import random
from typing import Dict, List, Optional
from utils.llm_client import LLMClient
from utils.format_validators import validate_reverse_sql_response, validate_reverse_sql_variants_response
from config.data_processing.reverse_sql_generator.config import ReverseSQLConfig
from config.data_processing.reverse_sql_generator.prompts import SQL_GENERATION_PROMPTS
import asyncio


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
            SQL查询数据
        """
        print(f"  - 开始生成SQL: {scenario} ({complexity})")
        
        max_retries = self.config.max_retries  # 从配置获取最大重试次数
        
        for attempt in range(max_retries):
            try:
                print(f"    🔄 SQL生成尝试 {attempt + 1}/{max_retries}")
                
                # 获取随机变量名
                var_names = self.config.get_random_names()
                print(f"    - 使用变量名: {var_names}")
                
                # 构建SQL生成提示词
                prompt = SQL_GENERATION_PROMPTS['complete_sql'].format(
                    scenario=scenario,
                    complexity=complexity,
                    table_examples=var_names['table_examples'],
                    field_examples=var_names['field_examples']
                )
                print(f"    - 提示词长度: {len(prompt)} 字符")
                
                # 调用LLM生成SQL
                response = self.llm_client.call_sync(
                    prompt,
                    max_tokens=self.config.max_tokens,
                    temperature=self.config.temperature
                )
                
                print(f"    - LLM响应类型: {type(response)}")
                
                # 解析响应
                if isinstance(response, str):
                    import re
                    # 尝试从markdown中提取JSON
                    json_match = re.search(r'```json\s*({.*?})\s*```', response, re.DOTALL)
                    if json_match:
                        json_content = json_match.group(1)
                        sql_data = json.loads(json_content)
                        print(f"    - 从markdown提取JSON成功")
                    else:
                        sql_data = json.loads(response)
                        print(f"    - 直接解析成功")
                else:
                    sql_data = json.loads(str(response))
                    print(f"    - 字符串转换后解析成功")
                
                # 验证SQL数据
                self._validate_sql_data(sql_data)
                print(f"    - 数据验证通过")
                print(f"    - SQL生成完成: {sql_data.get('query', '')[:50]}...")
                
                return sql_data
                
            except Exception as e:
                print(f"    ❌ SQL生成尝试 {attempt + 1} 失败: {e}")
                if attempt < max_retries - 1:
                    print(f"    ⏳ 等待 1 秒后重试...")
                    await asyncio.sleep(1)
                else:
                    print(f"    ❌ SQL生成失败: 已重试 {max_retries} 次")
                    raise
    
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
        
        # 验证SQL语法
        if not self._validate_sql_syntax(sql_data['query']):
            raise ValueError("SQL语法错误")
    
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
    
    async def close(self):
        """关闭会话"""
        if self._session:
            await self._session.close()
            self._session = None
    
    async def generate_sql_variants(self, base_sql: Dict, variant_type: str, scenario: str = None, complexity: str = "simple") -> List[Dict]:
        """生成SQL变体
        
        Args:
            base_sql: 基础SQL数据
            variant_type: 变体类型 (if_else, switch, dynamic)
            scenario: 场景类型（用于确定变体数量）
            complexity: 复杂度级别（用于确定变体数量）
            
        Returns:
            SQL变体列表
        """
        print(f"  - 开始生成{variant_type} SQL变体...")
        
        max_retries = self.config.max_retries  # 从配置获取最大重试次数
        
        for attempt in range(max_retries):
            try:
                print(f"    🔄 SQL变体生成尝试 {attempt + 1}/{max_retries}")
                
                # 获取随机变量名
                var_names = self.config.get_random_names()
                print(f"    - 使用变量名: {var_names}")
                
                # 获取动态变体数量
                variants_count = self.config.get_sql_variants_count(scenario or variant_type, complexity)
                print(f"    - 目标变体数量: {variants_count}")
                
                # 构建SQL变体生成提示词
                prompt = self._build_sql_variants_prompt(base_sql, variant_type, var_names, variants_count)
                print(f"    - 提示词长度: {len(prompt)} 字符")
                
                # 调用LLM生成SQL变体（不使用格式验证）
                print(f"    - 调用LLM生成{variant_type}变体...")
                response = self.llm_client.call_sync(
                    prompt,
                    max_tokens=self.config.max_tokens,
                    temperature=self.config.temperature
                )
                
                print(f"    - LLM响应类型: {type(response)}")
                print(f"    - LLM响应长度: {len(str(response))} 字符")
                
                # 解析响应
                sql_variants = []
                if isinstance(response, str):
                    import re
                    # 尝试从markdown中提取JSON
                    json_match = re.search(r'```json\s*(\[.*?\])\s*```', response, re.DOTALL)
                    if json_match:
                        json_content = json_match.group(1)
                        print(f"    - 从markdown提取JSON成功")
                        try:
                            sql_variants = json.loads(json_content)
                            print(f"    - JSON解析成功")
                        except json.JSONDecodeError as e:
                            print(f"    - JSON解析失败: {e}")
                            # 尝试直接解析
                            try:
                                sql_variants = json.loads(response)
                                print(f"    - 直接解析成功")
                            except json.JSONDecodeError:
                                print(f"    - 所有解析方法都失败")
                                raise ValueError(f"无法解析LLM响应: {response[:200]}...")
                    else:
                        # 尝试直接解析
                        try:
                            sql_variants = json.loads(response)
                            print(f"    - 直接解析成功")
                        except json.JSONDecodeError as e:
                            print(f"    - 直接解析失败: {e}")
                            raise ValueError(f"无法解析LLM响应: {response[:200]}...")
                else:
                    try:
                        sql_variants = json.loads(str(response))
                        print(f"    - 字符串转换后解析成功")
                    except json.JSONDecodeError as e:
                        print(f"    - 字符串转换后解析失败: {e}")
                        raise ValueError(f"无法解析LLM响应: {str(response)[:200]}...")
                
                print(f"    - 生成 {len(sql_variants)} 个{variant_type}变体")
                
                # 验证SQL变体数据
                for i, sql_variant in enumerate(sql_variants):
                    try:
                        self._validate_sql_data(sql_variant)
                        print(f"    - 变体 {i+1} 验证通过")
                    except Exception as e:
                        print(f"    - 变体 {i+1} 验证失败: {e}")
                        raise
                
                return sql_variants
                
            except Exception as e:
                print(f"    ❌ SQL变体生成尝试 {attempt + 1} 失败: {e}")
                if attempt < max_retries - 1:
                    print(f"    ⏳ 等待 2 秒后重试...")
                    await asyncio.sleep(2)
                else:
                    print(f"    ❌ SQL变体生成失败: 已重试 {max_retries} 次")
                    raise
    
    def _build_sql_variants_prompt(self, base_sql: Dict, variant_type: str, var_names: Dict, variants_count: int) -> str:
        """构建SQL变体生成提示词
        
        Args:
            base_sql: 基础SQL数据
            variant_type: 变体类型
            var_names: 随机变量名
            variants_count: 目标变体数量
            
        Returns:
            提示词字符串
        """
        # 获取变体类型对应的提示词模板
        # 将variant_type转换为提示词模板中的键名格式
        template_key = f"{variant_type}_variants"
        prompt_template = SQL_GENERATION_PROMPTS.get(template_key)
        if not prompt_template:
            raise ValueError(f"不支持的变体类型: {variant_type}，模板键: {template_key}")
        
        # 构建提示词
        prompt = prompt_template.format(
            base_sql=json.dumps(base_sql, ensure_ascii=False),
            table_name=var_names['table_examples'],
            field_examples=var_names['field_examples'],
            variants_count=variants_count
        )
        
        return prompt 