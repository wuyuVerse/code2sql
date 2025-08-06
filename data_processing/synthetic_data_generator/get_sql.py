import json
import os
import asyncio
import openai
import argparse
import re
from tqdm import tqdm
import time
import base64
from mimetypes import guess_type
import random
from typing import Any, Dict, List
import aiohttp # Added for call_async_with_format_validation

# 导入提示词模板
from config.data_processing.validation.validation_prompts import (
    ANALYSIS_PROMPT_TEMPLATE,
    VERIFICATION_PROMPT_TEMPLATE,
    FORMATTING_PROMPT_TEMPLATE,
    CONDITION_FIELD_MAPPING_PROMPT_TEMPLATE
)

# Venus API 配置
os.environ['OPENAI_API_KEY'] = "jCpoXAdfcikWZBUT6F1Vsr35@3538"

# 使用导入的模板替换原有的提示词定义
CODE_ORM_MYSQL_SQL_EXTRACT = ANALYSIS_PROMPT_TEMPLATE
CODE_ORM_MYSQL_SQL_VERIFY = VERIFICATION_PROMPT_TEMPLATE
CODE_ORM_MYSQL_SQL_FORMAT = FORMATTING_PROMPT_TEMPLATE
CODE_ORM_MYSQL_SQL_CONDITION_FIELD_MAPPING = CONDITION_FIELD_MAPPING_PROMPT_TEMPLATE

# =====================================================
# 📝 场景特定 SQL 生成规则
# =====================================================
# 部分 with_* 场景对生成的 SQL 有特殊要求，例如需要自动
# 添加 LIMIT、ORDER BY 或生成 COUNT 查询等。为了避免在
# 多处手动拼接规则，这里集中维护一个映射表，在构建 prompt
# 时统一附加相应说明。

SCENARIO_SQL_RULES = {
    # with_first → LIMIT 1
    'with_first': (
        "\n# ⚠️ 规则提醒:\n"
        "- 当 ORM 使用 First() 方法时，生成的 SQL 必须自动添加 `LIMIT 1`。\n"
        "- 请确保 SELECT 语句末尾包含 `LIMIT 1`。\n"
    ),

    # with_take → LIMIT 1
    'with_take': (
        "\n# ⚠️ 规则提醒:\n"
        "- 当 ORM 使用 Take() 方法时，生成的 SQL 必须自动添加 `LIMIT 1`。\n"
        "- 请确保 SELECT 语句末尾包含 `LIMIT 1`。\n"
    ),

    # with_last → LIMIT 1 + ORDER BY 主键 DESC
    'with_last': (
        "\n# ⚠️ 规则提醒:\n"
        "- 当 ORM 使用 Last() 方法时，生成的 SQL 必须自动添加 `LIMIT 1`，并且添加 `ORDER BY <primary_key> DESC`。\n"
        "- 如果无法识别主键名称，可以使用 `ORDER BY id DESC` 作为默认。\n"
    ),

    # with_find_no_limit → 不添加 LIMIT
    'with_find_no_limit': (
        "\n# ⚠️ 规则提醒:\n"
        "- 当 ORM 使用 Find() 方法且场景为 with_find_no_limit 时，生成的 SQL 不应包含任何 `LIMIT` 子句。\n"
    ),

    # with_count → SELECT COUNT(*)
    'with_count': (
        "\n# ⚠️ 规则提醒:\n"
        "- 当 ORM 使用 Count() 方法时，生成的 SQL 必须为 `SELECT COUNT(*) ...` 形式，用于统计记录数量。\n"
    ),
}

# 添加指数退避重试机制
async def retry_with_exponential_backoff(func, max_retries=10, base_delay=1.0, max_delay=60.0, backoff_factor=2.0, jitter=True):
    """
    带指数退避的重试机制
    
    Args:
        func: 要重试的异步函数
        max_retries: 最大重试次数
        base_delay: 基础延迟时间（秒）
        max_delay: 最大延迟时间（秒）
        backoff_factor: 退避因子
        jitter: 是否添加随机抖动
    """
    last_exception = None
    
    for attempt in range(max_retries + 1):  # 包括第一次尝试
        try:
            return await func()
        except Exception as e:
            last_exception = e
            
            if attempt == max_retries:
                # 最后一次重试失败，抛出异常
                break
            
            # 计算延迟时间
            delay = min(base_delay * (backoff_factor ** attempt), max_delay)
            
            # 添加随机抖动以避免惊群效应
            if jitter:
                delay = delay * (0.5 + random.random() * 0.5)
            
            print(f"第 {attempt + 1} 次尝试失败，{delay:.2f}秒后重试: {str(e)[:100]}")
            await asyncio.sleep(delay)
    
    # 如果所有重试都失败，抛出最后一个异常
    if last_exception is not None:
        raise last_exception
    else:
        raise Exception("所有重试都失败，但没有捕获到具体异常")

# 互斥条件场景专用SQL生成函数
async def generate_mutual_exclusive_sql(orm_code: str, llm_client, semaphore=None) -> Dict:
    """
    为mutual_exclusive_conditions场景生成SQL
    
    Args:
        orm_code: ORM代码
        llm_client: LLM客户端
        semaphore: 信号量（用于并发控制）
        
    Returns:
        包含SQL变体的字典
    """
    from config.data_processing.synthetic_data_generator.prompts import PROMPT_SQL_MUTUAL_EXCLUSIVE
    
    prompt = PROMPT_SQL_MUTUAL_EXCLUSIVE.format(
        orm_code=orm_code
    )
    
    if semaphore:
        async with semaphore:
            response = await llm_client.call_async(prompt)
    else:
        response = await llm_client.call_async(prompt)
    
    # 清理响应
    response = response.replace("```json", "").replace("```", "")
    
    try:
        sql_data = json.loads(response)
        return sql_data
    except json.JSONDecodeError as e:
        print(f"解析mutual_exclusive_conditions SQL响应失败: {e}")
        print(f"响应内容: {response[:200]}...")
        raise ValueError(f"mutual_exclusive_conditions SQL生成失败: {e}")

# 互斥条件场景SQL分析函数
async def analyze_mutual_exclusive_sql(orm_code: str, function_name: str = "", caller: str = "", code_meta_data: str = "", llm_client=None, semaphore=None) -> List[Dict]:
    """
    分析mutual_exclusive_conditions场景的ORM代码，生成SQL语句
    
    Args:
        orm_code: ORM代码
        function_name: 函数名称
        caller: 调用者信息
        code_meta_data: 元数据信息
        llm_client: LLM客户端
        semaphore: 信号量
        
    Returns:
        SQL分析结果列表
    """
    if not llm_client:
        from utils.llm_client import LLMClient
        llm_client = LLMClient("v3")
    
    print(f"分析mutual_exclusive_conditions SQL: {function_name}")
    print(f"代码长度: {len(orm_code)} 字符")
    
    # 使用标准的分析提示词模板
    from config.data_processing.validation.validation_prompts import ANALYSIS_PROMPT_TEMPLATE
    
    prompt = ANALYSIS_PROMPT_TEMPLATE.format(
        function_name=function_name,
        code_value=orm_code,
        caller=caller,
        code_meta_data_str=code_meta_data,
        sql_pattern_cnt=1  # mutual_exclusive_conditions场景通常生成1个SQL模式
    )
    
    # 创建简单的验证函数 - 对于mutual_exclusive_conditions场景使用宽松验证
    def validate_json_response(response: str) -> bool:
        # 对于mutual_exclusive_conditions场景，使用宽松验证
        # 只要响应不为空就认为格式正确
        if response and response.strip():
            return True
        return False
    
    if semaphore:
        async with semaphore:
            async with aiohttp.ClientSession() as session:
                response = await llm_client.call_async_with_format_validation(
                    session=session,
                    prompt=prompt,
                    validator=validate_json_response,
                    max_tokens=4096,
                    temperature=0.0
                )
    else:
        async with aiohttp.ClientSession() as session:
            response = await llm_client.call_async_with_format_validation(
                session=session,
                prompt=prompt,
                validator=validate_json_response,
                max_tokens=4096,
                temperature=0.0
            )
    
    # 处理LLM响应 - 支持分析报告格式和JSON格式
    def parse_llm_response(response_text: str) -> dict:
        """解析LLM响应，支持分析报告格式和JSON格式"""
        # 首先尝试提取JSON格式
        json_content = extract_json_from_response(response_text)
        if json_content:
            parsed_json = clean_and_parse_json(json_content)
            if parsed_json:
                return parsed_json
        
        # 如果JSON解析失败，尝试解析分析报告格式
        return parse_analysis_report(response_text)
    
    def extract_json_from_response(response_text: str) -> str:
        """从响应中提取JSON内容，支持多种格式"""
        # 清理响应
        cleaned_response = response_text.replace("```json", "").replace("```", "").strip()
        
        # 方法1：查找JSON开始位置
        json_start = cleaned_response.find('{')
        if json_start == -1:
            json_start = cleaned_response.find('[')
        
        if json_start == -1:
            # 如果没有找到JSON标记，尝试查找其他可能的JSON内容
            # 查找包含SQL语句的部分
            sql_markers = ['"sql":', '"type":', '"variants":']
            for marker in sql_markers:
                marker_pos = cleaned_response.find(marker)
                if marker_pos != -1:
                    # 向前查找最近的{或[
                    for i in range(marker_pos, -1, -1):
                        if cleaned_response[i] in '{[':
                            json_start = i
                            break
                    if json_start != -1:
                        break
        
        if json_start == -1:
            return None
        
        # 提取JSON部分
        json_content = cleaned_response[json_start:]
        
        # 尝试找到完整的JSON对象
        brace_count = 0
        bracket_count = 0
        json_end = 0
        in_string = False
        escape_next = False
        
        for i, char in enumerate(json_content):
            if escape_next:
                escape_next = False
                continue
            
            if char == '\\':
                escape_next = True
                continue
            
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
            
            if not in_string:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                elif char == '[':
                    bracket_count += 1
                elif char == ']':
                    bracket_count -= 1
                
                # 检查是否找到完整的JSON
                if (brace_count == 0 and bracket_count == 0) or (brace_count == 0 and bracket_count > 0):
                    json_end = i + 1
                    break
        
        if json_end > 0:
            json_content = json_content[:json_end]
        
        return json_content
    
    def clean_and_parse_json(json_content: str) -> dict:
        """清理并解析JSON内容"""
        if not json_content:
            return None
        
        # 尝试直接解析
        try:
            return json.loads(json_content)
        except json.JSONDecodeError:
            pass
        
        # 清理JSON内容
        cleaned_json = json_content.strip()
        
        # 移除可能的空对象前缀
        if cleaned_json.startswith('{}'):
            cleaned_json = cleaned_json[2:].strip()
        
        # 移除可能的空数组前缀
        if cleaned_json.startswith('[]'):
            cleaned_json = cleaned_json[2:].strip()
        
        # 尝试解析清理后的JSON
        try:
            return json.loads(cleaned_json)
        except json.JSONDecodeError:
            pass
        
        # 尝试修复常见的JSON格式问题
        # 1. 修复缺少引号的键名
        import re
        # 匹配没有引号的键名: {key: value} -> {"key": value}
        cleaned_json = re.sub(r'(\s*)(\w+)(\s*):', r'\1"\2"\3:', cleaned_json)
        
        try:
            return json.loads(cleaned_json)
        except json.JSONDecodeError:
            pass
        
        # 2. 尝试提取数组内容
        array_start = cleaned_json.find('[')
        array_end = cleaned_json.rfind(']')
        if array_start != -1 and array_end != -1 and array_end > array_start:
            try:
                return json.loads(cleaned_json[array_start:array_end+1])
            except json.JSONDecodeError:
                pass
        
        # 3. 尝试提取对象内容
        obj_start = cleaned_json.find('{')
        obj_end = cleaned_json.rfind('}')
        if obj_start != -1 and obj_end != -1 and obj_end > obj_start:
            try:
                return json.loads(cleaned_json[obj_start:obj_end+1])
            except json.JSONDecodeError:
                pass
        
        return None
    
    def parse_analysis_report(report_text: str) -> dict:
        """解析分析报告格式的响应"""
        # 检查是否是边界条件情况
        if "NO SQL GENERATE" in report_text.upper() or "不能生成SQL" in report_text:
            # 提取无法生成SQL的原因
            reason = extract_reason_from_report(report_text)
            return [{
                "type": "NO_SQL_GENERATE",
                "variants": [{
                    "scenario": reason,
                    "sql": ""
                }]
            }]
        
        if "LACK INFORMATION" in report_text.upper() or "信息缺失" in report_text:
            # 提取缺失信息和推测的SQL
            reason, sql = extract_lack_info_from_report(report_text)
            return [{
                "type": "LACK_INFORMATION",
                "variants": [{
                    "scenario": reason,
                    "sql": sql
                }]
            }]
        
        # 尝试从分析报告中提取SQL语句
        sql_statements = extract_sql_from_report(report_text)
        if sql_statements:
            return sql_statements
        
        # 如果无法解析，返回默认的无法生成SQL结果
        return [{
            "type": "NO_SQL_GENERATE",
            "variants": [{
                "scenario": "无法解析LLM响应",
                "sql": ""
            }]
        }]
    
    def extract_reason_from_report(report_text: str) -> str:
        """从报告中提取无法生成SQL的原因"""
        # 查找常见的原因标记
        markers = [
            "不能生成SQL的原因：",
            "无法生成SQL的原因：",
            "原因：",
            "NO SQL GENERATE:",
            "LACK INFORMATION:"
        ]
        
        for marker in markers:
            if marker in report_text:
                start = report_text.find(marker) + len(marker)
                end = report_text.find('\n', start)
                if end == -1:
                    end = len(report_text)
                return report_text[start:end].strip()
        
        return "代码不会生成SQL"
    
    def extract_lack_info_from_report(report_text: str) -> tuple:
        """从报告中提取缺失信息和推测的SQL"""
        # 查找缺失信息描述
        reason = "信息缺失"
        sql = ""
        
        # 查找推测的SQL
        sql_markers = ["推测的SQL语句：", "推测SQL：", "SQL：", "生成的SQL："]
        for marker in sql_markers:
            if marker in report_text:
                start = report_text.find(marker) + len(marker)
                end = report_text.find('\n', start)
                if end == -1:
                    end = len(report_text)
                sql = report_text[start:end].strip()
                break
        
        return reason, sql
    
    def extract_sql_from_report(report_text: str) -> list:
        """从分析报告中提取SQL语句"""
        sql_list = []
        
        # 查找SQL语句的模式
        import re
        
        # 查找SELECT语句
        select_pattern = r'SELECT\s+.*?;'
        select_matches = re.findall(select_pattern, report_text, re.IGNORECASE | re.DOTALL)
        
        # 查找INSERT语句
        insert_pattern = r'INSERT\s+.*?;'
        insert_matches = re.findall(insert_pattern, report_text, re.IGNORECASE | re.DOTALL)
        
        # 查找UPDATE语句
        update_pattern = r'UPDATE\s+.*?;'
        update_matches = re.findall(update_pattern, report_text, re.IGNORECASE | re.DOTALL)
        
        # 查找DELETE语句
        delete_pattern = r'DELETE\s+.*?;'
        delete_matches = re.findall(delete_pattern, report_text, re.IGNORECASE | re.DOTALL)
        
        # 合并所有SQL语句
        all_sql = select_matches + insert_matches + update_matches + delete_matches
        
        if all_sql:
            # 清理SQL语句
            cleaned_sql = []
            for sql in all_sql:
                sql = sql.strip()
                if sql and not sql.startswith('--'):
                    cleaned_sql.append(sql)
            
            if cleaned_sql:
                return cleaned_sql
        
        return None
    
    # 解析LLM响应
    sql_analysis = parse_llm_response(response)
    
    if sql_analysis is None:
        print(f"无法解析LLM响应")
        print(f"响应内容: {response[:200]}...")
        raise ValueError(f"mutual_exclusive_conditions SQL分析失败: 无法解析响应")
    
    print(f"SQL分析结果类型: {type(sql_analysis)}")
    print(f"SQL分析结果长度: {len(str(sql_analysis))} 字符")
    return sql_analysis

# 互斥条件场景SQL验证函数
async def verify_mutual_exclusive_sql(sql_analysis: List[Dict], orm_code: str, function_name: str = "", caller: str = "", code_meta_data: str = "", llm_client=None, semaphore=None) -> List[Dict]:
    """
    验证mutual_exclusive_conditions场景的SQL分析结果
    
    Args:
        sql_analysis: SQL分析结果
        orm_code: ORM代码
        function_name: 函数名称
        caller: 调用者信息
        code_meta_data: 元数据信息
        llm_client: LLM客户端
        semaphore: 信号量
        
    Returns:
        验证后的SQL分析结果
    """
    if not llm_client:
        from utils.llm_client import LLMClient
        llm_client = LLMClient("v3")
    
    print(f"验证SQL分析结果: {function_name}")
    print(f"SQL分析结果类型: {type(sql_analysis)}")
    print(f"SQL分析结果长度: {len(str(sql_analysis))} 字符")
    
    # 使用标准的验证提示词模板
    from config.data_processing.validation.validation_prompts import VERIFICATION_PROMPT_TEMPLATE
    
    # 将sql_analysis转换为字符串格式
    sql_statement = json.dumps(sql_analysis, ensure_ascii=False, indent=2)
    
    prompt = VERIFICATION_PROMPT_TEMPLATE.format(
        function_definition=orm_code,
        caller=caller,
        code_chain=code_meta_data,
        sql_statement=sql_statement,
        sql_pattern_cnt=1  # mutual_exclusive_conditions场景通常生成1个SQL模式
    )
    
    # 创建简单的验证函数 - 对于mutual_exclusive_conditions场景使用宽松验证
    def validate_json_response(response: str) -> bool:
        # 对于mutual_exclusive_conditions场景，使用宽松验证
        # 只要响应不为空就认为格式正确
        if response and response.strip():
            return True
        return False
    
    if semaphore:
        async with semaphore:
            async with aiohttp.ClientSession() as session:
                response = await llm_client.call_async_with_format_validation(
                    session=session,
                    prompt=prompt,
                    validator=validate_json_response,
                    max_tokens=2048,
                    temperature=0.0
                )
    else:
        async with aiohttp.ClientSession() as session:
            response = await llm_client.call_async_with_format_validation(
                session=session,
                prompt=prompt,
                validator=validate_json_response,
                max_tokens=2048,
                temperature=0.0
            )
    
    # 处理LLM响应 - 支持分析报告格式和JSON格式
    def parse_llm_response(response_text: str) -> dict:
        """解析LLM响应，支持分析报告格式和JSON格式"""
        # 首先尝试提取JSON格式
        json_content = extract_json_from_response(response_text)
        if json_content:
            parsed_json = clean_and_parse_json(json_content)
            if parsed_json:
                return parsed_json
        
        # 如果JSON解析失败，尝试解析分析报告格式
        return parse_analysis_report(response_text)
    
    def extract_json_from_response(response_text: str) -> str:
        """从响应中提取JSON内容，支持多种格式"""
        # 清理响应
        cleaned_response = response_text.replace("```json", "").replace("```", "").strip()
        
        # 方法1：查找JSON开始位置
        json_start = cleaned_response.find('{')
        if json_start == -1:
            json_start = cleaned_response.find('[')
        
        if json_start == -1:
            # 如果没有找到JSON标记，尝试查找其他可能的JSON内容
            # 查找包含SQL语句的部分
            sql_markers = ['"sql":', '"type":', '"variants":']
            for marker in sql_markers:
                marker_pos = cleaned_response.find(marker)
                if marker_pos != -1:
                    # 向前查找最近的{或[
                    for i in range(marker_pos, -1, -1):
                        if cleaned_response[i] in '{[':
                            json_start = i
                            break
                    if json_start != -1:
                        break
        
        if json_start == -1:
            return None
        
        # 提取JSON部分
        json_content = cleaned_response[json_start:]
        
        # 尝试找到完整的JSON对象
        brace_count = 0
        bracket_count = 0
        json_end = 0
        in_string = False
        escape_next = False
        
        for i, char in enumerate(json_content):
            if escape_next:
                escape_next = False
                continue
            
            if char == '\\':
                escape_next = True
                continue
            
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
            
            if not in_string:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                elif char == '[':
                    bracket_count += 1
                elif char == ']':
                    bracket_count -= 1
                
                # 检查是否找到完整的JSON
                if (brace_count == 0 and bracket_count == 0) or (brace_count == 0 and bracket_count > 0):
                    json_end = i + 1
                    break
        
        if json_end > 0:
            json_content = json_content[:json_end]
        
        return json_content
    
    def clean_and_parse_json(json_content: str) -> dict:
        """清理并解析JSON内容"""
        if not json_content:
            return None
        
        # 尝试直接解析
        try:
            return json.loads(json_content)
        except json.JSONDecodeError:
            pass
        
        # 清理JSON内容
        cleaned_json = json_content.strip()
        
        # 移除可能的空对象前缀
        if cleaned_json.startswith('{}'):
            cleaned_json = cleaned_json[2:].strip()
        
        # 移除可能的空数组前缀
        if cleaned_json.startswith('[]'):
            cleaned_json = cleaned_json[2:].strip()
        
        # 尝试解析清理后的JSON
        try:
            return json.loads(cleaned_json)
        except json.JSONDecodeError:
            pass
        
        # 尝试修复常见的JSON格式问题
        # 1. 修复缺少引号的键名
        import re
        # 匹配没有引号的键名: {key: value} -> {"key": value}
        cleaned_json = re.sub(r'(\s*)(\w+)(\s*):', r'\1"\2"\3:', cleaned_json)
        
        try:
            return json.loads(cleaned_json)
        except json.JSONDecodeError:
            pass
        
        # 2. 尝试提取数组内容
        array_start = cleaned_json.find('[')
        array_end = cleaned_json.rfind(']')
        if array_start != -1 and array_end != -1 and array_end > array_start:
            try:
                return json.loads(cleaned_json[array_start:array_end+1])
            except json.JSONDecodeError:
                pass
        
        # 3. 尝试提取对象内容
        obj_start = cleaned_json.find('{')
        obj_end = cleaned_json.rfind('}')
        if obj_start != -1 and obj_end != -1 and obj_end > obj_start:
            try:
                return json.loads(cleaned_json[obj_start:obj_end+1])
            except json.JSONDecodeError:
                pass
        
        return None
    
    def parse_analysis_report(report_text: str) -> dict:
        """解析分析报告格式的响应"""
        # 检查是否是边界条件情况
        if "NO SQL GENERATE" in report_text.upper() or "不能生成SQL" in report_text:
            # 提取无法生成SQL的原因
            reason = extract_reason_from_report(report_text)
            return [{
                "type": "NO_SQL_GENERATE",
                "variants": [{
                    "scenario": reason,
                    "sql": ""
                }]
            }]
        
        if "LACK INFORMATION" in report_text.upper() or "信息缺失" in report_text:
            # 提取缺失信息和推测的SQL
            reason, sql = extract_lack_info_from_report(report_text)
            return [{
                "type": "LACK_INFORMATION",
                "variants": [{
                    "scenario": reason,
                    "sql": sql
                }]
            }]
        
        # 尝试从分析报告中提取SQL语句
        sql_statements = extract_sql_from_report(report_text)
        if sql_statements:
            return sql_statements
        
        # 如果无法解析，返回默认的无法生成SQL结果
        return [{
            "type": "NO_SQL_GENERATE",
            "variants": [{
                "scenario": "无法解析LLM响应",
                "sql": ""
            }]
        }]
    
    def extract_reason_from_report(report_text: str) -> str:
        """从报告中提取无法生成SQL的原因"""
        # 查找常见的原因标记
        markers = [
            "不能生成SQL的原因：",
            "无法生成SQL的原因：",
            "原因：",
            "NO SQL GENERATE:",
            "LACK INFORMATION:"
        ]
        
        for marker in markers:
            if marker in report_text:
                start = report_text.find(marker) + len(marker)
                end = report_text.find('\n', start)
                if end == -1:
                    end = len(report_text)
                return report_text[start:end].strip()
        
        return "代码不会生成SQL"
    
    def extract_lack_info_from_report(report_text: str) -> tuple:
        """从报告中提取缺失信息和推测的SQL"""
        # 查找缺失信息描述
        reason = "信息缺失"
        sql = ""
        
        # 查找推测的SQL
        sql_markers = ["推测的SQL语句：", "推测SQL：", "SQL：", "生成的SQL："]
        for marker in sql_markers:
            if marker in report_text:
                start = report_text.find(marker) + len(marker)
                end = report_text.find('\n', start)
                if end == -1:
                    end = len(report_text)
                sql = report_text[start:end].strip()
                break
        
        return reason, sql
    
    def extract_sql_from_report(report_text: str) -> list:
        """从分析报告中提取SQL语句"""
        sql_list = []
        
        # 查找SQL语句的模式
        import re
        
        # 查找SELECT语句
        select_pattern = r'SELECT\s+.*?;'
        select_matches = re.findall(select_pattern, report_text, re.IGNORECASE | re.DOTALL)
        
        # 查找INSERT语句
        insert_pattern = r'INSERT\s+.*?;'
        insert_matches = re.findall(insert_pattern, report_text, re.IGNORECASE | re.DOTALL)
        
        # 查找UPDATE语句
        update_pattern = r'UPDATE\s+.*?;'
        update_matches = re.findall(update_pattern, report_text, re.IGNORECASE | re.DOTALL)
        
        # 查找DELETE语句
        delete_pattern = r'DELETE\s+.*?;'
        delete_matches = re.findall(delete_pattern, report_text, re.IGNORECASE | re.DOTALL)
        
        # 合并所有SQL语句
        all_sql = select_matches + insert_matches + update_matches + delete_matches
        
        if all_sql:
            # 清理SQL语句
            cleaned_sql = []
            for sql in all_sql:
                sql = sql.strip()
                if sql and not sql.startswith('--'):
                    cleaned_sql.append(sql)
            
            if cleaned_sql:
                return cleaned_sql
        
        return None
    
    # 解析LLM响应
    verified_sql_analysis = parse_llm_response(response)
    
    if verified_sql_analysis is None:
        print(f"无法解析LLM响应")
        print(f"响应内容: {response[:200]}...")
        raise ValueError(f"mutual_exclusive_conditions SQL验证失败: 无法解析响应")
    
    print(f"验证后SQL分析结果类型: {type(verified_sql_analysis)}")
    print(f"验证后SQL分析结果长度: {len(str(verified_sql_analysis))} 字符")
    return verified_sql_analysis

# 保存中间结果的函数
def save_intermediate_results(results, output_file, stage_name):
    """保存中间结果到文件"""
    intermediate_file = f"{output_file}.{stage_name}.tmp"
    try:
        with open(intermediate_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"已保存 {stage_name} 阶段的中间结果到 {intermediate_file}")
    except Exception as e:
        print(f"保存 {stage_name} 阶段中间结果失败: {e}")

# 加载中间结果的函数
def load_intermediate_results(output_file, stage_name):
    """加载中间结果"""
    intermediate_file = f"{output_file}.{stage_name}.tmp"
    if os.path.exists(intermediate_file):
        try:
            with open(intermediate_file, 'r', encoding='utf-8') as f:
                results = json.load(f)
            print(f"找到 {stage_name} 阶段的中间结果，加载了 {len(results)} 个任务")
            return results
        except Exception as e:
            print(f"加载 {stage_name} 阶段中间结果失败: {e}")
    return None

async def process_json_file_async(input_file, output_file, concurrency=10):
    """处理JSON文件并将结果保存到单个文件中，包含SQL语句"""
    # 验证输入文件
    if not validate_input_file(input_file):
        print("输入文件验证失败，终止处理")
        return 0, 0
    
    # 读取输入文件
    with open(input_file, 'r', encoding='utf-8') as file:
        data = json.load(file)
    
    # 创建信号量控制并发请求数
    semaphore = asyncio.Semaphore(concurrency)
    
    # 准备所有函数信息
    all_functions = []
    if isinstance(data, dict):
        # 检查是否是synthetic_scenarios.json格式（包含scenario字段）
        sample_key = next(iter(data.keys())) if data else None
        is_synthetic_format = sample_key and isinstance(data[sample_key], dict) and 'scenario' in data[sample_key]
        
        if is_synthetic_format:
            print("检测到synthetic_scenarios.json格式，进行格式适配")
            # 处理synthetic_scenarios.json格式
            for synthetic_key, function_info in data.items():
                # 提取真正的函数名，优先使用code_key，如果没有则使用synthetic_key
                function_name = function_info.get('code_key', synthetic_key)
                
                # 创建适配后的函数信息
                adapted_function_info = {
                    'function_name': function_name,
                    'synthetic_key': synthetic_key,  # 保留原始键
                    'scenario': function_info.get('scenario', ''),
                    'code_value': function_info.get('code_value', ''),
                    'code_meta_data': function_info.get('code_meta_data', []),
                    'sql_pattern_cnt': function_info.get('sql_pattern_cnt', None),
                    'callers': function_info.get('callers', []),
                    'callees': function_info.get('callees', []),
                    'is_valid': True
                }
                all_functions.append(adapted_function_info)
                print(f"已适配函数: {function_name} (场景: {adapted_function_info['scenario']})")
        else:
            # 原来的处理方式
            for function_name_or_path, function_info in data.items():
                # 确保function_info包含function_name
                function_info['function_name'] = function_name_or_path
                # 默认所有函数都是有效的，跳过验证阶段
                function_info['is_valid'] = True
                all_functions.append(function_info)
    elif isinstance(data, list):
        # 如果是列表类型，直接将列表项添加到all_functions
        for i, function_info in enumerate(data):
            # 确保每个项是字典类型
            if not isinstance(function_info, dict):
                print(f"警告: 索引 {i} 处的元素不是字典类型，跳过")
                continue
            # 如果没有function_name字段，使用索引作为函数名
            if 'function_name' not in function_info:
                function_info['function_name'] = f"function_{i}"
            # 默认所有函数都是有效的
            function_info['is_valid'] = True
            all_functions.append(function_info)
    
    valid_count = len(all_functions)
    invalid_count = 0

    # 为每个ORM代码块准备所有需要处理的场景（不带caller + 每个caller）
    all_tasks = []
    
    for function_info in all_functions:
        function_name = function_info['function_name']
        print(f"准备处理函数: {function_name}")
        
        # 提取所需信息
        code_value = function_info.get('code_value', '')
        
        # 如果code_value为空，尝试从其他字段获取代码内容
        if not code_value:
            code_value = function_info.get('orm_code', '')
        
        # 如果仍然为空，跳过这个函数
        if not code_value:
            print(f"警告: 函数 {function_name} 缺少代码内容，跳过处理")
            invalid_count += 1
            continue
            
        code_meta_data = function_info.get('code_meta_data', [])
        code_meta_data_str = ""
        for meta in code_meta_data:
            meta_code = meta.get('code_value', '')
            if meta_code:
                code_meta_data_str += meta_code + "\n"
        sql_pattern_cnt = function_info.get('sql_pattern_cnt', None)
        
        # 识别ORM场景并选择合适的提示词模板
        scenario_type, prompt_template = identify_orm_scenario(function_info)
        print(f"函数 {function_name} 识别为场景: {scenario_type}")
        
        # 检查是否是必须带caller的场景
        scenario = function_info.get('scenario', '')
        is_mutual_exclusive = scenario == 'mutual_exclusive_conditions'
        is_table_name_from_caller = scenario == 'table_name_from_caller'
        requires_caller = is_mutual_exclusive or is_table_name_from_caller
        
        # 对于必须带caller的场景，不创建不带caller的任务
        if not requires_caller:
            # 场景1：不带caller
            caller = ""
            scenario_key = f"{function_name}_no_caller"
            prompt = prompt_template.format(
                function_name=function_name,
                code_value=code_value,  # 使用code_value参数名
                caller=caller,
                code_meta_data_str=code_meta_data_str,
                sql_pattern_cnt=sql_pattern_cnt if sql_pattern_cnt is not None else ""
            )
            
            # 如果是特殊 with_* 场景，附加 SQL 生成规则
            scenario_key_lower = scenario.lower() if scenario else ""
            if scenario_key_lower in SCENARIO_SQL_RULES:
                prompt += SCENARIO_SQL_RULES[scenario_key_lower]
            
            task_info = {
                'function_info': function_info,
                'caller': caller,
                'scenario_key': scenario_key,
                'scenario_type': scenario_type,
                'prompt': prompt,
                'sql_pattern_cnt': sql_pattern_cnt
            }
            all_tasks.append(task_info)
        else:
            if is_mutual_exclusive:
                print(f"mutual_exclusive_conditions场景 {function_name} 跳过不带caller的任务")
            elif is_table_name_from_caller:
                print(f"table_name_from_caller场景 {function_name} 跳过不带caller的任务")
        
        # 场景2+：每个caller
        callers = function_info.get('callers', [])
        for i, caller_info in enumerate(callers):
            caller = caller_info.get('code_value', '')
            scenario_key = f"{function_name}_caller_{i}"
            prompt = prompt_template.format(
                function_name=function_name,
                code_value=code_value,  # 使用code_value参数名
                caller=caller,
                code_meta_data_str=code_meta_data_str,
                sql_pattern_cnt=sql_pattern_cnt if sql_pattern_cnt is not None else ""
            )
            
            # 如果是特殊 with_* 场景，附加 SQL 生成规则
            scenario_key_lower = scenario.lower() if scenario else ""
            if scenario_key_lower in SCENARIO_SQL_RULES:
                prompt += SCENARIO_SQL_RULES[scenario_key_lower]
            
            task_info = {
                'function_info': function_info,
                'caller': caller,
                'scenario_key': scenario_key,
                'scenario_type': scenario_type,
                'prompt': prompt,
                'sql_pattern_cnt': sql_pattern_cnt
            }
            all_tasks.append(task_info)

    print(f"总共准备了 {len(all_tasks)} 个处理任务")

    # 尝试加载第一阶段的中间结果
    stage1_results = load_intermediate_results(output_file, "stage1_sql_generation")
    
    if stage1_results is None:
        # 第一阶段：生成SQL语句
        print("开始第一阶段：生成SQL语句")
        initial_tasks = []
        task_map = {}
        
        for task_info in all_tasks:
            # 检查是否是mutual_exclusive_conditions场景
            if task_info['scenario_type'] == 'mutual_exclusive_conditions':
                print(f"检测到mutual_exclusive_conditions场景，使用专用处理函数")
                # 使用专用的mutual_exclusive_conditions处理函数
                task = asyncio.create_task(
                    process_mutual_exclusive_task(task_info, semaphore)
                )
            else:
                # 使用标准的SQL生成流程
                task = asyncio.create_task(send_request_async(task_info['prompt'], semaphore))
            
            initial_tasks.append(task)
            task_map[task] = task_info
        
        # 并发等待所有初始任务完成
        if initial_tasks:
            print(f"等待所有 {len(initial_tasks)} 个SQL生成任务完成...")
            initial_results = await asyncio.gather(*initial_tasks, return_exceptions=True)
        else:
            initial_results = []
        
        # 保存第一阶段结果
        for i, sql_statement in enumerate(initial_results):
            if i >= len(initial_tasks):
                continue
                
            task = initial_tasks[i]
            task_info = task_map[task]
            
            # 检查是否有异常
            if isinstance(sql_statement, Exception):
                task_info['sql_statement'] = f"请求失败: {str(sql_statement)}"
            else:
                task_info['sql_statement'] = sql_statement
        
        # 保存第一阶段的中间结果
        stage1_results = all_tasks.copy()
        save_intermediate_results(stage1_results, output_file, "stage1_sql_generation")
    else:
        # 使用加载的中间结果
        all_tasks = stage1_results
        print(f"使用加载的第一阶段中间结果，共 {len(all_tasks)} 个任务")

    # 尝试加载第二阶段的中间结果
    stage2_results = load_intermediate_results(output_file, "stage2_sql_verification")
    
    if stage2_results is None:
        # 第二阶段：验证SQL语句
        print("开始第二阶段：验证SQL语句")
        verify_tasks = []
        verify_map = {}
        
        for task_info in all_tasks:
            sql_statement = task_info.get('sql_statement', '')
            
            # 检查是否有有效的SQL语句需要验证
            if not sql_statement or sql_statement.startswith("请求失败"):
                print(f"跳过验证任务 {task_info.get('scenario_key', 'unknown')}，因为SQL生成失败")
                task_info['verified_sql'] = sql_statement
                continue
            else:
                print(f"SQL生成任务 {task_info.get('scenario_key', 'unknown')} 完成，开始验证")
            
            # 创建验证任务
            verify_task = asyncio.create_task(
                verify_sql_async(
                    sql_statement, 
                    function_definition=task_info['function_info'].get('code_value', ''),
                    code_meta_data=task_info['function_info'].get('code_meta_data', []),
                    caller=task_info['caller'],
                    semaphore=semaphore,
                    sql_pattern_cnt=task_info['sql_pattern_cnt']
                )
            )
            verify_tasks.append(verify_task)
            verify_map[verify_task] = {
                'task_info': task_info,
                'original_sql': sql_statement
            }
        
        # 并发等待所有验证任务完成
        if verify_tasks:
            print(f"等待所有 {len(verify_tasks)} 个验证任务完成...")
            verify_results = await asyncio.gather(*verify_tasks, return_exceptions=True)
        else:
            verify_results = []
        
        # 保存第二阶段结果
        for i, verified_sql in enumerate(verify_results):
            if i >= len(verify_tasks):
                continue
                
            task = verify_tasks[i]
            task_data = verify_map[task]
            task_info = task_data['task_info']
            
            # 检查是否有异常
            if isinstance(verified_sql, Exception):
                task_info['verified_sql'] = task_data['original_sql']
            else:
                task_info['verified_sql'] = verified_sql
        
        # 保存第二阶段的中间结果
        stage2_results = all_tasks.copy()
        save_intermediate_results(stage2_results, output_file, "stage2_sql_verification")
    else:
        # 使用加载的中间结果
        all_tasks = stage2_results
        print(f"使用加载的第二阶段中间结果，共 {len(all_tasks)} 个任务")

    # 尝试加载第三阶段的中间结果
    stage3_results = load_intermediate_results(output_file, "stage3_sql_formatting")
    
    if stage3_results is None:
        # 第三阶段：格式化SQL语句
        print("开始第三阶段：格式化SQL语句")
        format_tasks = []
        format_map = {}
        
        for task_info in all_tasks:
            verified_sql = task_info.get('verified_sql', '')
            
            # 检查是否有有效的SQL语句需要格式化
            if not verified_sql or verified_sql.startswith("请求失败"):
                print(f"跳过格式化任务 {task_info.get('scenario_key', 'unknown')}，因为验证失败")
                # 使用原始SQL或提取SQL语句
                if 'sql_statement' in task_info:
                    sql_list = extract_sql_statements(task_info['sql_statement'])
                else:
                    sql_list = []
                task_info['sql_statement_list'] = sql_list
                continue
            else:
                print(f"验证任务 {task_info.get('scenario_key', 'unknown')} 完成，开始格式化")
            
            # 创建格式化任务
            format_task = asyncio.create_task(format_sql_async(verified_sql, semaphore))
            format_tasks.append(format_task)
            format_map[format_task] = {
                'task_info': task_info,
                'verified_sql': verified_sql
            }
        
        # 并发等待所有格式化任务完成
        if format_tasks:
            print(f"等待所有 {len(format_tasks)} 个格式化任务完成...")
            format_results = await asyncio.gather(*format_tasks, return_exceptions=True)
        else:
            format_results = []

        # 保存第三阶段结果
        for i, sql_list in enumerate(format_results):
            if i >= len(format_tasks):
                continue
                
            task = format_tasks[i]
            task_data = format_map[task]
            task_info = task_data['task_info']
            
            # 检查是否有异常
            if isinstance(sql_list, Exception):
                print(f"格式化任务 {task_info.get('scenario_key', 'unknown')} 失败: {sql_list}")
                verified_sql = task_data['verified_sql']
                sql_list = extract_sql_statements(verified_sql)
            else:
                print(f"格式化任务 {task_info.get('scenario_key', 'unknown')} 完成")
            
            # 如果sql_list仍然是格式不正确的字符串，尝试修复
            if isinstance(sql_list, str):
                sql_list = fix_malformed_json_array(sql_list)
            
            # 验证SQL语句完整性
            sql_list = validate_sql_completeness(sql_list)
            
            # 将SQL语句列表添加到任务信息中
            task_info['sql_statement_list'] = sql_list
            
            # 添加SQL类型分类
            sql_types = []
            for sql in sql_list:
                sql_types.append(classify_sql(sql))
            task_info['sql_types'] = sql_types

        # 保存第三阶段的中间结果
        stage3_results = all_tasks.copy()
        save_intermediate_results(stage3_results, output_file, "stage3_sql_formatting")
    else:
        # 使用加载的中间结果
        all_tasks = stage3_results
        print(f"使用加载的第三阶段中间结果，共 {len(all_tasks)} 个任务")

    # 处理失败的任务
    for task_info in all_tasks:
        if 'sql_statement_list' not in task_info:
            # 这些是由于初始请求失败而跳过验证的任务
            if 'sql_statement' in task_info:
                task_info['sql_statement_list'] = [task_info['sql_statement']]
                task_info['sql_types'] = [classify_sql(task_info['sql_statement'])]
            else:
                task_info['sql_statement_list'] = []
                task_info['sql_types'] = []
        
        # 验证SQL语句数量是否与预期一致
        sql_pattern_cnt = task_info.get('sql_pattern_cnt')
        if sql_pattern_cnt is not None:
            task_info['sql_length_match'] = (len(task_info['sql_statement_list']) == sql_pattern_cnt)
        else:
            task_info['sql_length_match'] = True

    # 重新组织结果为要求的格式
    print("重新组织结果为要求的格式")
    final_results = []
    
    # 按函数分组
    function_groups = {}
    for task_info in all_tasks:
        function_name = task_info['function_info']['function_name']
        if function_name not in function_groups:
            function_groups[function_name] = []
        function_groups[function_name].append(task_info)
    
    # 为每个函数生成结果
    for function_name, tasks in function_groups.items():
        function_info = tasks[0]['function_info']  # 获取函数信息
        
        # 找到不带caller的结果
        no_caller_task = None
        caller_tasks = []
        
        for task in tasks:
            if task['caller'] == "":
                no_caller_task = task
            else:
                caller_tasks.append(task)
        
        # 检查是否是必须带caller的场景
        scenario = function_info.get('scenario', '')
        is_mutual_exclusive = scenario == 'mutual_exclusive_conditions'
        is_table_name_from_caller = scenario == 'table_name_from_caller'
        requires_caller = is_mutual_exclusive or is_table_name_from_caller
        
        # 对于必须带caller的场景，不允许空的caller
        if no_caller_task and not requires_caller:
            result_entry = {
                'function_name': function_name,
                'orm_code': function_info.get('code_value', ''),
                'caller': "",
                'sql_statement_list': no_caller_task.get('sql_statement_list', []),
                'sql_types': no_caller_task.get('sql_types', []),
                'sql_length_match': no_caller_task.get('sql_length_match', True),
                'code_meta_data': function_info.get('code_meta_data', []),
                'sql_pattern_cnt': function_info.get('sql_pattern_cnt', None)
            }
            final_results.append(result_entry)
        elif no_caller_task and requires_caller:
            if is_mutual_exclusive:
                print(f"警告: mutual_exclusive_conditions场景 {function_name} 没有caller，跳过该结果")
            elif is_table_name_from_caller:
                print(f"警告: table_name_from_caller场景 {function_name} 没有caller，跳过该结果")
        
        # 添加每个caller的结果
        for task in caller_tasks:
            result_entry = {
                'function_name': function_name,
                'orm_code': function_info.get('code_value', ''),
                'caller': task['caller'],
                'sql_statement_list': task.get('sql_statement_list', []),
                'sql_types': task.get('sql_types', []),
                'sql_length_match': task.get('sql_length_match', True),
                'code_meta_data': function_info.get('code_meta_data', []),
                'sql_pattern_cnt': function_info.get('sql_pattern_cnt', None)
            }
            final_results.append(result_entry)
    
    # 将结果写入输出文件
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(final_results, f, ensure_ascii=False, indent=2)
    
    print(f"处理完成，已将结果保存到 {output_file}")
    print(f"总共生成了 {len(final_results)} 个结果条目")
    
    # 清理中间文件
    for stage in ["stage1_sql_generation", "stage2_sql_verification", "stage3_sql_formatting"]:
        intermediate_file = f"{output_file}.{stage}.tmp"
        if os.path.exists(intermediate_file):
            try:
                os.remove(intermediate_file)
                print(f"已清理中间文件: {intermediate_file}")
            except Exception as e:
                print(f"清理中间文件失败 {intermediate_file}: {e}")
    
    # 统计SQL类型
    sql_type_counts = {"SELECT": 0, "INSERT": 0, "UPDATE": 0, "DELETE": 0, "OTHER": 0}
    for result in final_results:
        for sql_type in result.get('sql_types', []):
            if sql_type in sql_type_counts:
                sql_type_counts[sql_type] += 1
    
    print(f"SQL类型统计: {sql_type_counts}")
    
    return valid_count, invalid_count

def process_json_file(input_file, output_file, concurrency=10):
    """同步版本的处理函数"""
    return asyncio.run(process_json_file_async(input_file, output_file, concurrency))

# 添加场景识别函数
def identify_orm_scenario(function_info):
    """
    识别ORM代码的场景类型，选择合适的提示词模板
    
    Args:
        function_info: 函数信息字典
        
    Returns:
        tuple: (场景类型, 提示词模板)
    """
    code_value = function_info.get('code_value', '')
    scenario = function_info.get('scenario', '')
    
    # 检查是否是mutual_exclusive_conditions场景
    if scenario == 'mutual_exclusive_conditions':
        return 'mutual_exclusive_conditions', CODE_ORM_MYSQL_SQL_EXTRACT
    
    # 检查是否是table_name_from_caller场景
    if scenario == 'table_name_from_caller':
        return 'table_name_from_caller', CODE_ORM_MYSQL_SQL_EXTRACT
    
    # 检查是否是condition_field_mapping场景
    if scenario == 'condition_field_mapping':
        return 'condition_field_mapping', CODE_ORM_MYSQL_SQL_CONDITION_FIELD_MAPPING
    
    # 检查代码中是否包含条件字段映射的特征
    # condition_mapping_patterns = [
    #     r'if\s+\w+\s*==\s*["\'](\w+)["\']\s*{',  # if field == "value" {
    #     r'switch\s+\w+\s*{',  # switch field {
    #     r'case\s+["\'](\w+)["\']:',  # case "value":
    #     r'filter\[["\'](\w+)["\']\]',  # filter["field"]
    #     r'Where\(["\'](\w+)\s*=\s*\?["\']',  # Where("field = ?")
    # ]
    
    # for pattern in condition_mapping_patterns:
    #     if re.search(pattern, code_value, re.IGNORECASE):
    #         # 进一步检查是否包含字段映射逻辑
    #         mapping_indicators = [
    #             'location_id', 'topic_id', 'area_id', 'author_id',  # 常见映射字段
    #             'cluster_id', 'type_id', 'category_id', 'region_id',  # 更多映射字段
    #             'BillingAddress', 'Subject', 'Zone', 'Publisher',  # 映射键名
    #         ]
            
    #         for indicator in mapping_indicators:
    #             if indicator in code_value:
    #                 return 'condition_field_mapping', CODE_ORM_MYSQL_SQL_CONDITION_FIELD_MAPPING
    
    # 默认使用标准提示词
    return 'standard', CODE_ORM_MYSQL_SQL_EXTRACT

# 添加输入验证
def validate_input_file(input_file):
    try:
        with open(input_file, 'r', encoding='utf-8') as file:
            data = json.load(file)
        
        # 验证必要字段
        if isinstance(data, dict):
            # 如果是字典类型，按原来的方式处理
            for function_name, function_info in data.items():
                if 'code_value' not in function_info:
                    print(f"警告: {function_name} 缺少 code_value 字段")
        elif isinstance(data, list):
            # 如果是列表类型，检查每个元素是否包含必要字段
            for i, function_info in enumerate(data):
                if not isinstance(function_info, dict):
                    print(f"警告: 索引 {i} 处的元素不是字典类型")
                    continue
                if 'code_value' not in function_info:
                    print(f"警告: 索引 {i} 处的元素缺少 code_value 字段")
        else:
            print(f"警告: 输入文件格式不是字典或列表类型，而是 {type(data)}")
            return False
            
        return True
    except Exception as e:
        print(f"输入文件验证失败: {e}")
        return False

# 添加SQL分类功能
def classify_sql(sql_statement):
    # 检查是否是字典类型（处理参数依赖的SQL变体）
    if isinstance(sql_statement, dict):
        # 如果是参数依赖的SQL，返回特殊类型
        if "type" in sql_statement and sql_statement["type"] == "param_dependent":
            return "PARAM_DEPENDENT"
        # 尝试从字典中获取第一个SQL语句进行分类
        if "sql" in sql_statement and isinstance(sql_statement["sql"], str):
            sql_lower = sql_statement["sql"].lower().strip()
        elif "variants" in sql_statement and len(sql_statement["variants"]) > 0:
            # 使用第一个变体的SQL进行分类
            first_variant = sql_statement["variants"][0]
            if "sql" in first_variant and isinstance(first_variant["sql"], str):
                sql_lower = first_variant["sql"].lower().strip()
            else:
                return "OTHER"
        else:
            return "OTHER"
    elif isinstance(sql_statement, str):
        # 原始的字符串处理逻辑
        sql_lower = sql_statement.lower().strip()
    else:
        # 处理其他类型
        return "OTHER"
    
    # 分类逻辑
    if sql_lower.startswith("select"):
        return "SELECT"
    elif sql_lower.startswith("insert"):
        return "INSERT"
    elif sql_lower.startswith("update"):
        return "UPDATE"
    elif sql_lower.startswith("delete"):
        return "DELETE"
    else:
        return "OTHER"

# 添加缺失的函数
async def send_request_async(question, semaphore):
    async with semaphore:
        client = openai.AsyncClient(
            base_url="http://10.0.0.31:8081/v1", 
            api_key="EMPTY"
        )
        
        async def make_request():
            response = await client.chat.completions.create(
                model="default",
                messages=[
                    {"role": "system", "content": ""},
                    {"role": "user", "content": question},
                ],
                temperature=0.7,
                max_tokens=8096,
            )
            return response.choices[0].message.content
        
        try:
            return await retry_with_exponential_backoff(make_request)
        except Exception as e:
            print(f"请求最终失败: {question[:50]}... 错误: {e}")
            return f"请求失败: {question[:50]}..."

async def verify_sql_async(sql_statement, function_definition=None, code_meta_data=None, caller=None, semaphore=None, sql_pattern_cnt=None):
    if semaphore is None:
        # 如果没有提供信号量，创建一个临时的
        semaphore = asyncio.Semaphore(1)
    
    async with semaphore:
        client = openai.AsyncClient(
            base_url="http://10.0.0.31:8081/v1", 
            api_key="EMPTY"
        )
        
        # 构建提示词，使用CODE_ORM_MYSQL_SQL_VERIFY模板
        code_chain = ""
        if code_meta_data and len(code_meta_data) > 0:
            for meta in code_meta_data:
                if isinstance(meta, str):
                    code_chain += f"{meta}\n"
                elif isinstance(meta, dict) and 'code_value' in meta:
                    code_chain += f"{meta.get('code_value', '')}\n"
        
        prompt = CODE_ORM_MYSQL_SQL_VERIFY.format(
            function_definition=function_definition if function_definition else "",
            caller=caller if caller else "",
            code_chain=code_chain,
            sql_statement=sql_statement,
            sql_pattern_cnt=sql_pattern_cnt if sql_pattern_cnt is not None else "",
            code_value=function_definition if function_definition else ""  # 添加code_value参数
        )
        
        async def make_verify_request():
            response = await client.chat.completions.create(
                model="default",
                messages=[
                    {"role": "system", "content": "你是一个SQL专家，擅长分析和修正SQL语句。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=8096,
            )
            return response.choices[0].message.content
        
        try:
            result = await retry_with_exponential_backoff(make_verify_request)
            
            # 验证并重新生成（如果需要）
            validated_result = await validate_and_regenerate_sql(
                result,
                function_definition=function_definition,
                code_meta_data=code_meta_data,
                caller=caller,
                sql_pattern_cnt=sql_pattern_cnt,
                semaphore=semaphore
            )
            
            return validated_result
            
        except Exception as e:
            print(f"验证SQL最终失败，返回原始SQL: {str(e)[:100]}")
            return sql_statement

async def format_sql_async(sql_statement, semaphore):
    async with semaphore:
        client = openai.AsyncClient(
            base_url="http://10.0.0.31:8081/v1", 
            api_key="EMPTY"
        )
        
        # 构建提示词，使用CODE_ORM_MYSQL_SQL_FORMAT模板
        prompt = CODE_ORM_MYSQL_SQL_FORMAT.format(
            sql_statement=sql_statement
        )
        
        async def make_format_request():
            response = await client.chat.completions.create(
                model="default",
                messages=[
                    {"role": "system", "content": "你是一个SQL格式化专家，擅长将SQL语句转换为标准JSON格式。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=8096,
            )
            
            # 尝试解析响应为JSON数组
            formatted_response = response.choices[0].message.content
            if formatted_response is None:
                formatted_response = ""
            formatted_response = formatted_response.strip()
            try:
                # 检查是否包含```json标记
                if "```json" in formatted_response:
                    # 提取json部分
                    match = re.search(r'```json\s*([\s\S]*?)```', formatted_response)
                    if match:
                        json_content = match.group(1).strip()
                        # 解析提取出的json内容
                        sql_list = json.loads(json_content)
                        return sql_list
                
                # 检查是否已经是JSON数组格式
                if formatted_response.startswith('[') and formatted_response.endswith(']'):
                    sql_list = json.loads(formatted_response)
                    return sql_list
                else:
                    # 尝试分割SQL语句
                    sql_statements = [stmt.strip() for stmt in formatted_response.split(';') if stmt.strip()]
                    sql_statements = [f"{stmt};" for stmt in sql_statements]
                    # 移除最后一个语句末尾多余的分号
                    if sql_statements and sql_statements[-1].endswith(';;'):
                        sql_statements[-1] = sql_statements[-1][:-1]
                    return sql_statements
            except json.JSONDecodeError:
                # 如果不是有效的JSON，尝试分割SQL语句
                sql_statements = [stmt.strip() for stmt in formatted_response.split(';') if stmt.strip()]
                sql_statements = [f"{stmt};" for stmt in sql_statements]
                # 移除最后一个语句末尾多余的分号
                if sql_statements and sql_statements[-1].endswith(';;'):
                    sql_statements[-1] = sql_statements[-1][:-1]
                return sql_statements
        
        try:
            result = await retry_with_exponential_backoff(make_format_request)
            
            # 验证并重新生成（如果需要）
            validated_result = await validate_and_regenerate_sql(
                result,
                semaphore=semaphore
            )
            
            return validated_result
            
        except Exception as e:
            print(f"格式化SQL最终失败，尝试简单分割: {str(e)[:100]}")
            sql_statements = [stmt.strip() for stmt in sql_statement.split(';') if stmt.strip()]
            sql_statements = [f"{stmt};" for stmt in sql_statements]
            # 移除最后一个语句末尾多余的分号
            if sql_statements and sql_statements[-1].endswith(';;'):
                sql_statements[-1] = sql_statements[-1][:-1]
            return sql_statements

# 添加新的函数用于验证SQL语句完整性
def validate_sql_completeness(sql_list):
    """验证SQL语句是否完整，没有省略号或类似的占位符"""
    validated_list = []
    
    # 尝试修复不正确的JSON格式
    if isinstance(sql_list, str):
        sql_list = fix_malformed_json_array(sql_list)
    
    # 如果仍然是字符串，转换为列表
    if isinstance(sql_list, str):
        sql_list = [sql_list]
    
    for item in sql_list:
        if isinstance(item, str):
            # 检查字符串中是否有省略号或[其他字段]类型的占位符
            if "..." in item or "[其他" in item or "其他]" in item:
                # 尝试修复或标记为不完整
                print(f"发现不完整SQL语句: {item}")
                # 这里可以添加修复逻辑或直接标记
                validated_list.append(f"不完整SQL语句: {item}")
            else:
                validated_list.append(item)
        elif isinstance(item, dict) and "variants" in item:
            # 检查每个变体
            fixed_variants = []
            for variant in item.get("variants", []):
                sql = variant.get("sql", "")
                if "..." in sql or "[其他" in sql or "其他]" in sql:
                    print(f"发现不完整SQL变体: {sql}")
                    # 这里可以添加修复逻辑或直接标记
                    variant["sql"] = f"不完整SQL语句: {sql}"
                fixed_variants.append(variant)
            
            item["variants"] = fixed_variants
            validated_list.append(item)
        else:
            validated_list.append(item)
    
    return validated_list

def fix_malformed_json_array(json_str):
    """修复格式不正确的JSON数组字符串"""
    # 如果是字符串内的JSON数组，尝试提取并解析
    try:
        # 尝试直接解析
        return json.loads(json_str)
    except json.JSONDecodeError:
        # 如果解析失败，尝试修复常见问题
        
        # 检查是否是引号内的JSON字符串（如示例中的情况）
        if json_str.startswith('"[') and json_str.endswith(']"'):
            # 移除外层引号并转义内部引号
            inner_json = json_str[1:-1].replace('\\"', '"')
            try:
                return json.loads(inner_json)
            except json.JSONDecodeError:
                pass
        
        # 检查是否有多余的转义字符
        cleaned = json_str.replace('\\n', '\n').replace('\\"', '"')
        if cleaned != json_str:
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                pass
        
        # 更彻底的修复尝试 - 提取所有可能的SQL语句
        return extract_sql_statements(json_str)

def extract_sql_statements(text):
    """从文本中提取SQL语句"""
    # 这个函数尝试从文本中提取SQL语句，适用于LLM返回了带有说明的文本而不是纯JSON
    
    # 尝试提取param_dependent格式的SQL
    param_dependent_matches = re.findall(r'{\s*"type"\s*:\s*"param_dependent"[^}]*"variants"\s*:\s*\[.*?\]\s*}', text, re.DOTALL)
    
    # 一般性SQL语句提取
    # 查找以SELECT、INSERT、UPDATE、DELETE等开头，以分号结尾的语句
    sql_matches = re.findall(r'(?:SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP)[\s\S]*?;', text, re.IGNORECASE)
    
    # 合并结果
    result = []
    
    # 添加param_dependent类型
    for match in param_dependent_matches:
        try:
            # 尝试将提取的内容解析为JSON
            parsed = json.loads(match)
            result.append(parsed)
        except json.JSONDecodeError:
            # 如果解析失败，将其作为字符串添加
            result.append(match)
    
    # 添加常规SQL语句
    for match in sql_matches:
        # 检查是否已经作为param_dependent的一部分添加
        already_added = False
        for item in result:
            if isinstance(item, dict) and 'variants' in item:
                for variant in item['variants']:
                    if match in variant.get('sql', ''):
                        already_added = True
                        break
        
        if not already_added:
            result.append(match)
    
    # 如果没有找到任何SQL语句，将原始文本分割为语句
    if not result:
        statements = [stmt.strip() for stmt in text.split(';') if stmt.strip()]
        statements = [f"{stmt};" for stmt in statements if not stmt.startswith('{') and not stmt.startswith('[')]
        result.extend(statements)
    
    return result

# 添加函数用于比较两个SQL语句是否重复
def compare_sql_statements(sql1, sql2):
    """比较两个SQL语句是否实质上相同"""
    # 如果两个语句完全相同
    if sql1 == sql2:
        return True
    
    # 如果一个是字符串，一个是字典，它们不相同
    if (isinstance(sql1, str) and isinstance(sql2, dict)) or \
       (isinstance(sql1, dict) and isinstance(sql2, str)):
        return False
    
    # 如果都是字符串，进行简化比较
    if isinstance(sql1, str) and isinstance(sql2, str):
        # 移除空格、换行和分号进行比较
        simplified1 = re.sub(r'\s+', ' ', sql1).strip().rstrip(';').lower()
        simplified2 = re.sub(r'\s+', ' ', sql2).strip().rstrip(';').lower()
        return simplified1 == simplified2
    
    # 如果都是字典（变体SQL）
    if isinstance(sql1, dict) and isinstance(sql2, dict):
        # 如果类型不同
        if sql1.get('type') != sql2.get('type'):
            return False
        
        # 比较变体数量
        variants1 = sql1.get('variants', [])
        variants2 = sql2.get('variants', [])
        
        if len(variants1) != len(variants2):
            return False
        
        # 简单检查：检查是否有相同数量的变体具有相同的SQL
        sql_set1 = set()
        for variant in variants1:
            if 'sql' in variant:
                simplified = re.sub(r'\s+', ' ', variant['sql']).strip().rstrip(';').lower()
                sql_set1.add(simplified)
        
        sql_set2 = set()
        for variant in variants2:
            if 'sql' in variant:
                simplified = re.sub(r'\s+', ' ', variant['sql']).strip().rstrip(';').lower()
                sql_set2.add(simplified)
        
        # 如果两个集合有重叠，认为它们可能是相同的SQL
        return len(sql_set1.intersection(sql_set2)) > 0
    
    return False


# 导入验证函数
from utils.response_parser import validate_sql_output_format


async def validate_and_regenerate_sql(sql_output: Any, 
                                    function_definition: str = None,
                                    code_meta_data: str = None,
                                    caller: str = None,
                                    sql_pattern_cnt: int = None,
                                    semaphore: asyncio.Semaphore = None,
                                    max_retries: int = 3) -> Any:
    """
    验证SQL输出格式，如果不符合要求则重新生成
    
    Args:
        sql_output: 要验证的SQL输出
        function_definition: 函数定义
        code_meta_data: 代码元数据
        caller: 调用者信息
        sql_pattern_cnt: SQL模式数量
        semaphore: 信号量
        max_retries: 最大重试次数
        
    Returns:
        验证通过或重新生成后的SQL输出
    """
    # 验证输出格式
    is_valid, error_msg = validate_sql_output_format(sql_output)
    
    if is_valid:
        print(f"✅ SQL输出格式验证通过")
        return sql_output
    
    print(f"❌ SQL输出格式验证失败: {error_msg}")
    print(f"🔄 开始重新生成SQL...")
    
    # 重新生成SQL
    for attempt in range(max_retries):
        try:
            print(f"🔄 第 {attempt + 1} 次重新生成尝试...")
            
            # 重新调用SQL生成
            new_sql_output = await verify_sql_async(
                sql_output,
                function_definition=function_definition,
                code_meta_data=code_meta_data,
                caller=caller,
                semaphore=semaphore,
                sql_pattern_cnt=sql_pattern_cnt
            )
            
            # 验证新生成的输出
            new_is_valid, new_error_msg = validate_sql_output_format(new_sql_output)
            
            if new_is_valid:
                print(f"✅ 重新生成成功，格式验证通过")
                return new_sql_output
            else:
                print(f"❌ 重新生成后格式仍不正确: {new_error_msg}")
                
        except Exception as e:
            print(f"❌ 重新生成失败 (尝试 {attempt + 1}): {e}")
    
    # 如果所有重试都失败，返回原始输出并记录警告
    print(f"⚠️ 所有重新生成尝试都失败，返回原始输出")
    return sql_output

# 处理mutual_exclusive_conditions场景的专用函数
async def process_mutual_exclusive_task(task_info, semaphore):
    """
    处理mutual_exclusive_conditions场景的SQL生成任务
    
    Args:
        task_info: 任务信息
        semaphore: 信号量
        
    Returns:
        SQL分析结果
    """
    try:
        from utils.llm_client import LLMClient
        
        # 创建LLM客户端
        llm_client = LLMClient("v3")
        
        # 提取任务信息
        function_info = task_info['function_info']
        function_name = function_info.get('function_name', '')
        code_value = function_info.get('code_value', '')
        caller = task_info['caller']
        code_meta_data = function_info.get('code_meta_data', [])
        
        # 格式化元数据
        code_meta_data_str = ""
        for meta in code_meta_data:
            meta_code = meta.get('code_value', '')
            if meta_code:
                code_meta_data_str += meta_code + "\n"
        
        # 格式化调用者信息
        caller_str = caller if caller else ""
        
        print(f"处理mutual_exclusive_conditions任务: {function_name}")
        print(f"代码长度: {len(code_value)} 字符")
        print(f"调用者长度: {len(caller_str)} 字符")
        
        # 使用信号量控制并发
        if semaphore:
            async with semaphore:
                # 使用专用的mutual_exclusive_conditions分析函数
                sql_analysis = await analyze_mutual_exclusive_sql(
                    orm_code=code_value,
                    function_name=function_name,
                    caller=caller_str,
                    code_meta_data=code_meta_data_str,
                    llm_client=llm_client,
                    semaphore=None  # 这里不需要再传递信号量，因为已经在外部控制了
                )
                
                # 验证SQL分析结果
                verified_sql = await verify_mutual_exclusive_sql(
                    sql_analysis=sql_analysis,
                    orm_code=code_value,
                    function_name=function_name,
                    caller=caller_str,
                    code_meta_data=code_meta_data_str,
                    llm_client=llm_client,
                    semaphore=None  # 这里不需要再传递信号量，因为已经在外部控制了
                )
        else:
            # 使用专用的mutual_exclusive_conditions分析函数
            sql_analysis = await analyze_mutual_exclusive_sql(
                orm_code=code_value,
                function_name=function_name,
                caller=caller_str,
                code_meta_data=code_meta_data_str,
                llm_client=llm_client,
                semaphore=None
            )
            
            # 验证SQL分析结果
            verified_sql = await verify_mutual_exclusive_sql(
                sql_analysis=sql_analysis,
                orm_code=code_value,
                function_name=function_name,
                caller=caller_str,
                code_meta_data=code_meta_data_str,
                llm_client=llm_client,
                semaphore=None
            )
        
        # 返回验证后的SQL结果
        # 将字典格式转换为字符串格式，以兼容工作流期望的格式
        if isinstance(verified_sql, dict):
            import json
            return json.dumps(verified_sql, ensure_ascii=False, indent=2)
        elif isinstance(verified_sql, list):
            import json
            return json.dumps(verified_sql, ensure_ascii=False, indent=2)
        else:
            return str(verified_sql)
        
    except Exception as e:
        print(f"处理mutual_exclusive_conditions任务失败: {e}")
        import traceback
        traceback.print_exc()
        return f"mutual_exclusive_conditions处理失败: {str(e)}"


if __name__ == '__main__':
    # 导入必要的库
    import argparse
    
    # 配置文件路径
    input_file = '/data/cloud_disk_1/home/wuyu/code2sql/const_scenarios.json'
    output_file = '/data/cloud_disk_1/home/wuyu/code2sql/const_scenarios_sql.json'
    # input_file = '/data/local_disk0/shawn/dirty_work/temp_show.json'
    # output_file = '/data/local_disk0/shawn/dirty_work/temp_show_by_caller.json'
    # 添加命令行参数支持
    parser = argparse.ArgumentParser(description='分析ORM代码有效性并生成SQL语句')
    parser.add_argument('--input', type=str, default=input_file, help='输入JSON文件路径')
    parser.add_argument('--output', type=str, default=output_file, help='输出JSON文件路径')
    parser.add_argument('--concurrency', type=int, default=10, help='并发请求数量')
    args = parser.parse_args()
    
    # 处理JSON文件
    valid_count, invalid_count = process_json_file(
        args.input, 
        args.output, 
        args.concurrency
    )
    
    print(f"统计结果: 有效ORM {valid_count}个, 无效ORM {invalid_count}个")
