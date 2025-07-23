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
from typing import Any

# 导入提示词模板
from config.data_processing.validation.validation_prompts import (
    ANALYSIS_PROMPT_TEMPLATE,
    VERIFICATION_PROMPT_TEMPLATE,
    FORMATTING_PROMPT_TEMPLATE
)

# Venus API 配置
os.environ['OPENAI_API_KEY'] = "jCpoXAdfcikWZBUT6F1Vsr35@3538"

# 使用导入的模板替换原有的提示词定义
CODE_ORM_MYSQL_SQL_EXTRACT = ANALYSIS_PROMPT_TEMPLATE
CODE_ORM_MYSQL_SQL_VERIFY = VERIFICATION_PROMPT_TEMPLATE
CODE_ORM_MYSQL_SQL_FORMAT = FORMATTING_PROMPT_TEMPLATE

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

async def process_json_file_async(input_file, output_file, concurrency=80):
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
        
        # 场景1：不带caller
        caller = ""
        scenario_key = f"{function_name}_no_caller"
        prompt = CODE_ORM_MYSQL_SQL_EXTRACT.format(
            function_name=function_name,
            code_value=code_value,
            caller=caller,
            code_meta_data_str=code_meta_data_str,
            sql_pattern_cnt=sql_pattern_cnt if sql_pattern_cnt is not None else ""
        )
        
        task_info = {
            'function_info': function_info,
            'caller': caller,
            'scenario_key': scenario_key,
            'prompt': prompt,
            'sql_pattern_cnt': sql_pattern_cnt
        }
        all_tasks.append(task_info)
        
        # 场景2+：每个caller
        callers = function_info.get('callers', [])
        for i, caller_info in enumerate(callers):
            caller = caller_info.get('code_value', '')
            scenario_key = f"{function_name}_caller_{i}"
            prompt = CODE_ORM_MYSQL_SQL_EXTRACT.format(
                function_name=function_name,
                code_value=code_value,
                caller=caller,
                code_meta_data_str=code_meta_data_str,
                sql_pattern_cnt=sql_pattern_cnt if sql_pattern_cnt is not None else ""
            )
            
            task_info = {
                'function_info': function_info,
                'caller': caller,
                'scenario_key': scenario_key,
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
        
        # 添加不带caller的结果
        if no_caller_task:
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

def process_json_file(input_file, output_file, concurrency=80):
    """同步版本的处理函数"""
    return asyncio.run(process_json_file_async(input_file, output_file, concurrency))

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
            base_url="http://212.64.90.3:8081/v1", 
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
            base_url="http://212.64.90.3:8081/v1", 
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
            sql_pattern_cnt=sql_pattern_cnt if sql_pattern_cnt is not None else ""
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
            base_url="http://212.64.90.3:8081/v1", 
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


if __name__ == '__main__':
    # 导入必要的库
    import argparse
    
    # 配置文件路径
    input_file = '/data/local_disk0/shawn/api_benchmark/evaluate/const_scenarios.json'
    output_file = '/data/local_disk0/shawn/api_benchmark/evaluate/const_scenarios_sql.json'
    # input_file = '/data/local_disk0/shawn/dirty_work/temp_show.json'
    # output_file = '/data/local_disk0/shawn/dirty_work/temp_show_by_caller.json'
    # 添加命令行参数支持
    parser = argparse.ArgumentParser(description='分析ORM代码有效性并生成SQL语句')
    parser.add_argument('--input', type=str, default=input_file, help='输入JSON文件路径')
    parser.add_argument('--output', type=str, default=output_file, help='输出JSON文件路径')
    parser.add_argument('--concurrency', type=int, default=100, help='并发请求数量')
    args = parser.parse_args()
    
    # 处理JSON文件
    valid_count, invalid_count = process_json_file(
        args.input, 
        args.output, 
        args.concurrency
    )
    
    print(f"统计结果: 有效ORM {valid_count}个, 无效ORM {invalid_count}个")
