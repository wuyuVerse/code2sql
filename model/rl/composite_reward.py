import json
import re
from typing import Dict, Any, List, Tuple, Optional
import os
import requests
import time
import hashlib
import asyncio
import openai
from concurrent.futures import ThreadPoolExecutor
MAX_WORKERS = 32

# ============================= 异步API调用函数 =============================

async def async_call_v3_api(client, prompt: str, max_tokens: int = 2048) -> str:
    """异步调用V3 API（优化版：使用共享客户端提升并发性能）"""
    try:
        response = await client.chat.completions.create(
            model="v3",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"❌ V3 API异步调用失败: {e}")
        return ""

# ============================= 框架适配的主奖励函数 =============================

def format_and_llm_reward(data_source: dict, solution_str: str, ground_truth: str, extra_info: Optional[dict] = None) -> float:
    """
    新版三维度合并评估：expect步骤覆盖、关键步骤覆盖、指令正确性
    支持异步高并发评估，自动记录评分结果
    
    Args:
        data_source: 数据源信息（框架要求，但此处不使用）
        solution_str: 模型响应文本
        ground_truth: 期望的排查步骤文本（expect数据）
        extra_info: 额外信息（可选）
        
    Returns:
        最终奖励分数 (0.0-1.0)
    """
    
    # 获取白名单文件路径，优先从extra_info获取，否则使用默认路径
    if extra_info and 'whitelist_path' in extra_info:
        whitelist_path = extra_info['whitelist_path']
    else:
        whitelist_path = "/data/local_disk3/zuowei/verl-main/examples/reinforce_plus_plus_trainer/mysql_variables_cynos.txt"
    
    # 获取日志目录配置
    log_dir = extra_info.get('log_dir', '/data/local_disk3/zuowei/verl-main/reward_logs') if extra_info else '/data/local_disk3/zuowei/verl-main/reward_logs'
    
    try:
        # 使用异步评估（高并发，使用共享openai客户端）
        expect_score, key_steps_score, instruction_score = asyncio.run(
            async_evaluate_all_dimensions(solution_str, ground_truth, whitelist_path, log_dir)
        )
        
        # 计算综合分数
        WEIGHT_EXPECT = 0.30      # 30%
        WEIGHT_KEY_STEPS = 0.30   # 30% 
        WEIGHT_INSTRUCTION = 0.40  # 40%
        
        final_score = (expect_score * WEIGHT_EXPECT) + \
                      (key_steps_score * WEIGHT_KEY_STEPS) + \
                      (instruction_score * WEIGHT_INSTRUCTION)
        final_score = round(final_score, 2)
        
        # 确保分数在有效范围内
        final_score = max(0.0, min(1.0, final_score))
        
        # 简洁的评估结果输出（批量友好）
        print(f"[评估] 得分: {final_score} | expect: {expect_score:.2f} | 关键步骤: {key_steps_score:.2f} | 指令: {instruction_score:.2f}")
        
        return final_score
        
    except Exception as e:
        print(f"[错误] 奖励评估失败: {e}")
        return 0.0

# ============================= expect步骤覆盖度评估部分 =============================

def call_v3_for_expect_coverage(answer_steps: str, expect_steps: str) -> dict:
    """使用V3大模型评估expect步骤覆盖度"""
    api_url = os.getenv("V3_API_URL", "http://43.143.249.90:8081/v1/chat/completions")
    headers = {"Content-Type": "application/json"}

    prompt = f"""
你是一位顶级的MySQL数据库专家。你的任务是评估answer中的排查步骤对expect中所有关键排查步骤的覆盖程度。

**评分标准**：
- 1.0-0.9分：answer中完全覆盖expect所有关键排查步骤无遗漏，步骤逻辑完整
- 0.8-0.7分：覆盖expect大部分关键步骤（高于80%），但可能有轻微遗漏（如缺少一个重要检查点）不影响整体方向
- 0.6-0.5分：覆盖expect部分关键步骤（只覆盖50-80%），排查可能不全面
- 0.4-0.3分：expect中的关键步骤覆盖不全（只覆盖30-50%），较多遗漏，影响问题诊断
- 0.2-0.1分：只覆盖expect中少数关键步骤（低于30%），无法支持有效排查
- 0.0分：无关键步骤覆盖，或步骤完全无关

**Expect关键步骤**：
```
{expect_steps}
```

**Answer排查步骤**：
```
{answer_steps}
```

**输出格式要求**：
你必须返回一个单一的、格式完好的JSON对象，包含以下字段：
```json
{{
  "coverage_score": 0.85,
  "covered_steps": ["步骤1描述", "步骤2描述"],
  "missing_steps": ["缺失步骤1", "缺失步骤2"],
  "coverage_analysis": "详细的覆盖度分析说明"
}}
```

请严格遵守此格式，不要返回任何额外的文本或解释。
"""

    default_result = {
        "coverage_score": 0.0,
        "covered_steps": [],
        "missing_steps": [],
        "coverage_analysis": "V3评估失败",
        "error": None
    }

    data = {
        "model": "v3",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "max_tokens": 2048,
    }

    try:
        response = requests.post(api_url, headers=headers, json=data, timeout=60)
        response.raise_for_status()
        result_text = response.json()['choices'][0]['message']['content']
        
        json_start = result_text.find('{')
        json_end = result_text.rfind('}')
        if json_start != -1 and json_end != -1:
            json_str = result_text[json_start:json_end+1]
            parsed_json = json.loads(json_str)
            
            for key, default_value in default_result.items():
                if key not in parsed_json:
                    parsed_json[key] = default_value
            return parsed_json
        
        default_result["error"] = f"Response was not a valid JSON object: {result_text}"
        return default_result

    except Exception as e:
        default_result["error"] = f"V3 API call failed: {e}"
        return default_result

def evaluate_expect_coverage(answer_text: str, expect_text: str) -> Tuple[float, dict]:
    """评估expect步骤覆盖度"""
    if not expect_text or not expect_text.strip():
        # 如果没有expect数据，返回满分
        return 1.0, {
            "coverage_score": 1.0,
            "covered_steps": [],
            "missing_steps": [],
            "coverage_analysis": "无expect数据，默认满分",
            "note": "No expect data provided"
        }
    
    result = call_v3_for_expect_coverage(answer_text, expect_text)
    coverage_score = result.get("coverage_score", 0.0)
    return coverage_score, result

# ============================= 关键步骤覆盖度评估部分（大模型版本） =============================

def call_v3_for_key_steps_coverage(answer_steps: str) -> dict:
    """使用V3大模型评估关键步骤覆盖度"""
    api_url = os.getenv("V3_API_URL", "http://43.143.249.90:8081/v1/chat/completions")
    headers = {"Content-Type": "application/json"}

    # 定义关键步骤检查标准
    key_steps_requirements = """
**关键步骤覆盖标准**：
1. **性能相关问题**（需要覆盖>=5条）：
   - 执行计划分析：EXPLAIN FORMAT=JSON [query]
   - 实际执行分析：EXPLAIN ANALYZE [query]
   - 优化器跟踪：SET optimizer_trace="enabled=on"; [query]; SELECT * FROM information_schema.optimizer_trace;
   - 统计信息检查：SELECT last_updated FROM mysql.innodb_table_stats WHERE table_name='[table]'
   - 指定连接顺序验证：SELECT /*+ STRAIGHT_JOIN */ ...
   - 制定索引验证：SELECT /*+ FORCE INDEX([index_name]) */ ...

2. **Crash类问题**（需要覆盖>=2条）：
   - 堆栈获取：gdb -q /usr/sbin/mysqld core.[pid] -ex 'thread apply all bt full' --batch > stack.txt
   - 堆栈分析，从过往案例中匹配堆栈
   - Signal解析：检查错误日志，根据signal [number]执行对应操作：grep "Assertion failure" /var/log/mysql/error.log

3. **复制类问题**（需要覆盖>=2条）：
   - 复制状态检查：SHOW SLAVE STATUS\G
   - GTID完整性验证：SELECT GTID_SUBSET(@@gtid_executed, @@gtid_purged)
   - 检查并行复制是否开启检测：SELECT THREAD_ID FROM performance_schema.threads WHERE NAME LIKE '%parallel%'

4. **硬件问题类**（需要覆盖>=1条）：
   - 磁盘健康检查：smartctl -x /dev/sda | grep Reallocated_Sector_Ct
   - IO性能测试：fio --name=randwrite --ioengine=libaio --rw=randwrite --bs=4k --numjobs=16 --size=1G --runtime=60
   - 内存错误检测：dmesg -T | grep -iE "out of memory|killed process"

5. **内存相关类**（需要覆盖>=1条）：
   - 内存错误检测：dmesg -T | grep -iE "out of memory|killed process"
   - 检查错误日志是否包含OOM提示

6. **锁相关类**（需要覆盖>=2条）：
   - 锁等待分析：SELECT * FROM sys.innodb_lock_waits
   - 检查持锁情况：SHOW ENGINE INNODB STATUS
   - 检查死锁日志记录：SET GLOBAL innodb_print_all_deadlocks=ON

7. **复制延迟类**：
   - 实时延迟监控：pt-heartbeat --monitor --databases [dbname] -h slave_host
   - 延迟复现测试：pt-slave-delay --delay 1m --interval 15s --run-time 10m slave_host

8. **网络问题类**（必须包含）：
   - 抓包测试
"""

    prompt = f"""
你是一位顶级的MySQL数据库专家。你的任务是分析下面的排查步骤文本，判断其属于哪类问题，并评估是否充分覆盖了该类问题的关键排查步骤。

{key_steps_requirements}

**评分标准**：
- 1.0-0.9分：完全覆盖所有关键排查步骤（如错误日志检查、参数验证、性能监控等）无遗漏，步骤逻辑完整
- 0.8-0.7分：覆盖大部分关键步骤（高于阈值），但可能有轻微遗漏（如缺少一个重要检查点），但包含较多对expect以外的符合标准的步骤，不影响整体方向
- 0.6-0.5分：覆盖部分关键步骤，但缺少一些重要步骤（如只覆盖50-70%），排查可能不全面
- 0.4-0.3分：关键步骤覆盖不全（如只覆盖30-50%），较多遗漏，影响问题诊断
- 0.2-0.1分：只覆盖少数关键步骤（如仅1-2个），无法支持有效排查
- 0.0分：无关键步骤覆盖，或步骤完全无关

**待分析的排查步骤**：
```
{answer_steps}
```

**输出格式要求**：
你必须返回一个单一的、格式完好的JSON对象，包含以下字段：
```json
{{
  "problem_category": "识别的问题类别",
  "required_steps_count": 5,
  "covered_steps_count": 4,
  "coverage_score": 0.8,
  "covered_key_steps": ["已覆盖的关键步骤1", "已覆盖的关键步骤2"],
  "missing_key_steps": ["缺失的关键步骤1"],
  "coverage_analysis": "详细的覆盖度分析说明"
}}
```

请严格遵守此格式，不要返回任何额外的文本或解释。
"""

    default_result = {
        "problem_category": "未分类",
        "required_steps_count": 0,
        "covered_steps_count": 0,
        "coverage_score": 0.0,
        "covered_key_steps": [],
        "missing_key_steps": [],
        "coverage_analysis": "V3评估失败",
        "error": None
    }

    data = {
        "model": "v3",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "max_tokens": 2048,
    }

    try:
        response = requests.post(api_url, headers=headers, json=data, timeout=60)
        response.raise_for_status()
        result_text = response.json()['choices'][0]['message']['content']
        
        json_start = result_text.find('{')
        json_end = result_text.rfind('}')
        if json_start != -1 and json_end != -1:
            json_str = result_text[json_start:json_end+1]
            parsed_json = json.loads(json_str)
            
            for key, default_value in default_result.items():
                if key not in parsed_json:
                    parsed_json[key] = default_value
            return parsed_json
        
        default_result["error"] = f"Response was not a valid JSON object: {result_text}"
        return default_result

    except Exception as e:
        default_result["error"] = f"V3 API call failed: {e}"
        return default_result

def evaluate_key_steps_coverage_v3(answer_text: str) -> Tuple[float, dict]:
    """使用V3大模型评估关键步骤覆盖度"""
    result = call_v3_for_key_steps_coverage(answer_text)
    coverage_score = result.get("coverage_score", 0.0)
    return coverage_score, result

# ============================= 指令正确性评估部分 =============================

def call_v3_for_instruction_evaluation(text_to_analyze: str) -> dict:
    """使用V3大模型评估指令正确性"""
    api_url = os.getenv("V3_API_URL", "http://43.143.249.90:8081/v1/chat/completions")
    headers = {"Content-Type": "application/json"}

    prompt = f"""
你是一位顶级的数据库诊断专家和评审员。你的任务是基于"指令正确性"这个核心维度，对下面提供的数据库问题排查建议进行全面的分析，并以一个严格的 JSON 格式返回结果。

你的分析需要覆盖以下几个方面：

1.  **可配置系统参数提取**:
    - 任务：从文本中提取所有可通过 `my.cnf` 或 `SET` 命令修改的**系统参数**。
    - 关键点：必须是**可配置的参数**，而不是只读的状态变量（如 `Slave_IO_Running`）或 Schema 字段。
    - 输出字段：`configurable_parameters` (一个字符串列表)

2.  **风险操作识别**:
    - **可容忍风险 (Tolerable Risk)**:
        - 定义：会改变数据库状态或短暂影响性能，但通常是必要的维护操作。
        - 例子：更新统计信息 (`ANALYZE TABLE`)、检查或修复表 (`CHECK TABLE`, `REPAIR TABLE`)。
        - 输出字段：`tolerable_risks` (一个对象列表，每个对象包含 `operation` 和 `reason` 字段)
    - **明显风险 (Significant Risk)**:
        - 定义：会造成数据库卡顿、长时间锁定或服务中断的操作。
        - 例子：重启数据库服务 (任何形式的 `restart`, `shutdown` 指令)、在超大表上执行无在线工具的 `ALTER TABLE`。
        - 输出字段：`significant_risks` (一个对象列表，每个对象包含 `operation` 和 `reason` 字段)

**关键的排除规则 (非常重要)**:
- **绝对不是风险**: 任何**只读**的、用于监控和诊断的查询指令，都**不属于**任何风险类别。
- **具体例子**:
  - 所有 `SHOW ...` 命令 (如 `SHOW SLAVE STATUS`, `SHOW VARIABLES`)。
  - 所有从 `information_schema` 或 `performance_schema` 中 `SELECT` 数据的查询。
- 如果一个操作属于此类，请直接忽略，不要将其放入 `tolerable_risks` 或 `significant_risks` 列表中。

**输出格式要求**:
你必须严格按照以下 JSON 结构返回你的分析结果。不要添加任何额外的解释、Markdown 标记或注释。你的输出必须是一个合法的 JSON 对象。

```json
{{
  "configurable_parameters": ["param1", "param2"],
  "tolerable_risks": [
    {{"operation": "找到的操作或指令", "reason": "为什么这是可容忍风险"}}
  ],
  "significant_risks": [
    {{"operation": "找到的操作或指令", "reason": "为什么这是明显风险"}}
  ]
}}
```

---
**待分析的排查建议文本**:
```
{text_to_analyze}
```
---

现在，请开始分析并返回 JSON 结果。
"""
    default_result = {
        "configurable_parameters": [],
        "tolerable_risks": [],
        "significant_risks": [],
        "error": None
    }

    data = {
        "model": "v3",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "max_tokens": 2048,
    }

    try:
        response = requests.post(api_url, headers=headers, json=data, timeout=60)
        response.raise_for_status()
        result_text = response.json()['choices'][0]['message']['content']
        
        json_start = result_text.find('{')
        json_end = result_text.rfind('}')
        if json_start != -1 and json_end != -1:
            json_str = result_text[json_start:json_end+1]
            parsed_json = json.loads(json_str)
            
            for key, default_value in default_result.items():
                if key not in parsed_json:
                    parsed_json[key] = default_value
            return parsed_json
        
        default_result["error"] = f"Response was not a valid JSON object: {result_text}"
        return default_result

    except Exception as e:
        default_result["error"] = f"V3 API call failed: {e}"
        return default_result

def extract_sql_from_response(text: str) -> List[str]:
    """从响应中提取SQL语句"""
    found_sqls = set()

    inline_code_regex = re.compile(r'`([^`]+)`')
    block_code_regex = re.compile(r'```(?:sql)?\n(.*?)```', re.DOTALL)
    
    SQL_KEYWORDS = (
        'SELECT', 'SHOW', 'EXPLAIN', 'SET', 'ANALYZE',
        'CREATE', 'ALTER', 'DROP', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE',
        'DESCRIBE', 'USE'
    )

    # 从单反引号中提取
    for match in inline_code_regex.finditer(text):
        potential_sql = match.group(1).strip()
        is_command = len(potential_sql.split()) > 1
        if is_command and potential_sql.upper().startswith(SQL_KEYWORDS):
            found_sqls.add(potential_sql)
    
    # 从三反引号代码块中提取
    for match in block_code_regex.finditer(text):
        block_content = match.group(1).strip()
        statements_in_block = block_content.split(';')
        for stmt in statements_in_block:
            stmt = stmt.strip()
            if stmt and stmt.upper().startswith(SQL_KEYWORDS):
                found_sqls.add(stmt)

    # 清洗结果
    cleaned_sqls = set()
    for sql in found_sqls:
        if '[' in sql and ']' in sql:
            continue

        cleaned_sql = sql.strip()
        
        is_cleaning = True
        while is_cleaning:
            is_cleaning = False
            if cleaned_sql.endswith(';'):
                cleaned_sql = cleaned_sql[:-1].strip()
                is_cleaning = True
            if cleaned_sql.endswith('\\G'):
                cleaned_sql = cleaned_sql[:-2].strip()
                is_cleaning = True
        
        if cleaned_sql:
            cleaned_sqls.add(cleaned_sql)
    
    return list(cleaned_sqls)

def validate_sql_simple(sql: str) -> Tuple[bool, Optional[str]]:
    """简单的SQL语法验证（避免sqlglot依赖）"""
    # 简单的语法检查
    sql = sql.strip()
    if not sql:
        return False, "Empty SQL"
    
    # 检查基本的SQL关键字
    sql_upper = sql.upper()
    valid_starts = ('SELECT', 'SHOW', 'EXPLAIN', 'SET', 'ANALYZE', 'CREATE', 'ALTER', 'DROP', 'INSERT', 'UPDATE', 'DELETE', 'DESCRIBE', 'USE')
    
    if not sql_upper.startswith(valid_starts):
        return False, f"SQL does not start with valid keyword: {sql[:20]}..."
    
    # 检查基本的括号匹配
    open_parens = sql.count('(')
    close_parens = sql.count(')')
    if open_parens != close_parens:
        return False, f"Mismatched parentheses: {open_parens} open, {close_parens} close"
    
    # 检查基本的引号匹配
    single_quotes = sql.count("'")
    if single_quotes % 2 != 0:
        return False, "Mismatched single quotes"
    
    return True, None

def validate_all_sqls(sqls: List[str]) -> dict:
    """验证SQL列表"""
    valid_sqls = []
    invalid_sqls_details = []
    
    for sql in sqls:
        is_valid, error_message = validate_sql_simple(sql)
        if is_valid:
            valid_sqls.append(sql)
        else:
            invalid_sqls_details.append({"sql": sql, "error": error_message})

    total_sql = len(sqls)
    valid_count = len(valid_sqls)
    score = (valid_count / total_sql) if total_sql > 0 else 1.0

    return {
        "score": score,
        "total_sql": total_sql,
        "valid_count": valid_count,
        "invalid_count": len(invalid_sqls_details),
        "valid_sqls": valid_sqls,
        "invalid_sqls_details": invalid_sqls_details,
    }

def validate_parameters(extracted_params: List[str], whitelist_path: str) -> Tuple[float, dict]:
    """验证参数列表"""
    try:
        with open(whitelist_path, 'r', encoding='utf-8') as f:
            whitelist = {
                line.strip().split('\t')[0].lower()
                for line in f.readlines()[1:] if line.strip()
            }
    except FileNotFoundError:
        # 如果白名单文件不存在，返回满分
        return 1.0, {"error": "Whitelist file not found", "score": 1.0}

    if not extracted_params:
        return 1.0, {
            'score': 1.0, 'valid_count': 0, 'invalid_count': 0, 
            'total_extracted': 0, 'valid': [], 'invalid': []
        }

    valid_params = []
    invalid_params = []
    for param in extracted_params:
        if param.lower() in whitelist:
            valid_params.append(param)
        else:
            invalid_params.append(param)

    score = len(valid_params) / len(extracted_params)

    details = {
        'score': score,
        'valid_count': len(valid_params),
        'invalid_count': len(invalid_params),
        'total_extracted': len(extracted_params),
        'valid': sorted(valid_params),
        'invalid': sorted(invalid_params)
    }
    return score, details

def calculate_instruction_score(sql_syntax_details: dict, param_accuracy_details: dict, risk_details: dict) -> Tuple[float, dict]:
    """计算指令正确性分数（改进版：避免对空内容给满分）"""
    sql_syntax_score = sql_syntax_details.get("score", 1.0)
    param_accuracy_score = param_accuracy_details.get("score", 1.0)
    
    WEIGHT_SQL_SYNTAX = 0.6
    WEIGHT_PARAM_ACCURACY = 0.4
    PENALTY_TOLERABLE_RISK = 0.1
    PENALTY_SIGNIFICANT_RISK = 0.3

    num_tolerable_risks = len(risk_details.get("tolerable_risks", []))
    num_significant_risks = len(risk_details.get("significant_risks", []))
    
    total_penalty = (num_tolerable_risks * PENALTY_TOLERABLE_RISK) + \
                    (num_significant_risks * PENALTY_SIGNIFICANT_RISK)
    
    base_score = (sql_syntax_score * WEIGHT_SQL_SYNTAX) + \
                 (param_accuracy_score * WEIGHT_PARAM_ACCURACY)
                 
    final_score = base_score - total_penalty
    final_score = max(0.0, min(1.0, final_score))
    final_score = round(final_score, 2)

    score_details = {
        "instruction_score": final_score,
        "base_score": base_score,
        "total_penalty": total_penalty,
        "components": {
            "sql_syntax_score": sql_syntax_score,
            "param_accuracy_score": param_accuracy_score,
            "tolerable_risks_found": num_tolerable_risks,
            "significant_risks_found": num_significant_risks,
        }
    }
    return final_score, score_details

def evaluate_instruction_correctness(response_text: str, whitelist_path: str) -> dict:
    """评估指令正确性"""
    # 提取和验证SQL语法
    extracted_sqls = extract_sql_from_response(response_text)
    sql_syntax_details = validate_all_sqls(extracted_sqls)
    
    # 使用V3进行参数提取和风险分析
    v3_analysis = call_v3_for_instruction_evaluation(response_text)
    if v3_analysis.get("error"):
        param_accuracy_details = {'score': 0.0, 'error': v3_analysis.get("error")}
        risk_details = {"tolerable_risks": [], "significant_risks": []}
        extracted_params = []
    else:
        # 分离风险分析和参数提取
        risk_details = {
            "tolerable_risks": v3_analysis.get("tolerable_risks", []),
            "significant_risks": v3_analysis.get("significant_risks", [])
        }
        extracted_params = v3_analysis.get("configurable_parameters", [])

    # 验证提取出的参数
    _score, param_accuracy_details = validate_parameters(extracted_params, whitelist_path)

    # 计算最终指令正确性分数
    instruction_score, score_details = calculate_instruction_score(
        sql_syntax_details,
        param_accuracy_details,
        risk_details,
    )
    
    return {
        "instruction_score": instruction_score,
        "sql_syntax_analysis": sql_syntax_details,
        "parameter_analysis": param_accuracy_details,
        "risk_analysis": risk_details,
        "score_components": score_details['components']
    } 

# ============================= 评分结果记录功能 =============================

def save_evaluation_result(solution_str: str, ground_truth: str, expect_score: float, 
                          key_steps_score: float, instruction_score: float, final_score: float,
                          log_dir: str = "/data/local_disk3/zuowei/verl-main/reward_logs") -> None:
    """保存评估结果到文件，用于后续review"""
    try:
        os.makedirs(log_dir, exist_ok=True)
        
        # 生成唯一标识符
        content_hash = hashlib.md5((solution_str + ground_truth).encode()).hexdigest()[:8]
        timestamp = int(time.time())
        
        # 准备记录数据
        record = {
            "timestamp": timestamp,
            "content_hash": content_hash,
            "scores": {
                "expect_coverage_score": round(expect_score, 3),
                "key_steps_coverage_score": round(key_steps_score, 3), 
                "instruction_correctness_score": round(instruction_score, 3),
                "final_combined_score": round(final_score, 3)
            },
            "weights": {
                "expect_coverage_weight": 0.30,
                "key_steps_coverage_weight": 0.30,
                "instruction_weight": 0.40
            },
            "solution_preview": solution_str,
            "ground_truth_preview": ground_truth
        }
        
        # 写入文件（按日期分组）
        date_str = time.strftime("%Y%m%d", time.localtime(timestamp))
        log_file = os.path.join(log_dir, f"reward_evaluation_{date_str}.jsonl")
        
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
            
    except Exception as e:
        print(f"⚠️ 保存评估结果失败: {e}")

# ============================= 异步评估函数 =============================

async def async_evaluate_expect_coverage(client, solution_str: str, ground_truth: str) -> float:
    """异步评估expect步骤覆盖度"""
    if not ground_truth or not ground_truth.strip():
        return 1.0
    
    prompt = f"""
你是一位顶级的MySQL数据库专家。你的任务是评估answer中的排查步骤对expect中所有关键排查步骤的覆盖程度。

**评分标准**：
- 1.0-0.9分：answer中完全覆盖expect所有关键排查步骤无遗漏，步骤逻辑完整
- 0.8-0.7分：覆盖expect大部分关键步骤（高于80%），但可能有轻微遗漏（如缺少一个重要检查点）不影响整体方向
- 0.6-0.5分：覆盖expect部分关键步骤（只覆盖50-80%），排查可能不全面
- 0.4-0.3分：expect中的关键步骤覆盖不全（只覆盖30-50%），较多遗漏，影响问题诊断
- 0.2-0.1分：只覆盖expect中少数关键步骤（低于30%），无法支持有效排查
- 0.0分：无关键步骤覆盖，或步骤完全无关

**Expect关键步骤**：
```
{ground_truth}
```

**Answer排查步骤**：
```
{solution_str}
```

请只返回一个0.0到1.0之间的数字分数，不要任何其他文字。
"""
    
    result_text = await async_call_v3_api(client, prompt)
    try:
        numbers = re.findall(r'\d+\.?\d*', result_text)
        if numbers:
            score = float(numbers[0])
            return max(0.0, min(1.0, score))
        return 0.0
    except:
        return 0.0

async def async_evaluate_key_steps_coverage(client, solution_str: str) -> float:
    """异步评估关键步骤覆盖度"""
    key_steps_requirements = """
**关键步骤覆盖标准**：
1. **性能相关问题**（需要覆盖>=5条）：
   - 执行计划分析：EXPLAIN FORMAT=JSON [query]
   - 实际执行分析：EXPLAIN ANALYZE [query]
   - 优化器跟踪：SET optimizer_trace="enabled=on"; [query]; SELECT * FROM information_schema.optimizer_trace;
   - 统计信息检查：SELECT last_updated FROM mysql.innodb_table_stats WHERE table_name='[table]'
   - 指定连接顺序验证：SELECT /*+ STRAIGHT_JOIN */ ...
   - 制定索引验证：SELECT /*+ FORCE INDEX([index_name]) */ ...

2. **Crash类问题**（需要覆盖>=2条）：
   - 堆栈获取：gdb -q /usr/sbin/mysqld core.[pid] -ex 'thread apply all bt full' --batch > stack.txt
   - 堆栈分析，从过往案例中匹配堆栈
   - Signal解析：检查错误日志，根据signal [number]执行对应操作：grep "Assertion failure" /var/log/mysql/error.log

3. **复制类问题**（需要覆盖>=2条）：
   - 复制状态检查：SHOW SLAVE STATUS\\G
   - GTID完整性验证：SELECT GTID_SUBSET(@@gtid_executed, @@gtid_purged)
   - 检查并行复制是否开启检测：SELECT THREAD_ID FROM performance_schema.threads WHERE NAME LIKE '%parallel%'
"""

    prompt = f"""
你是一位顶级的MySQL数据库专家。你的任务是分析下面的排查步骤文本，判断其属于哪类问题，并评估是否充分覆盖了该类问题的关键排查步骤。

{key_steps_requirements}

**评分标准**：
- 1.0-0.9分：完全覆盖所有关键排查步骤（如错误日志检查、参数验证、性能监控等）无遗漏，步骤逻辑完整
- 0.8-0.7分：覆盖大部分关键步骤（高于阈值），但可能有轻微遗漏（如缺少一个重要检查点），但包含较多对expect以外的符合标准的步骤，不影响整体方向
- 0.6-0.5分：覆盖部分关键步骤，但缺少一些重要步骤（如只覆盖50-70%），排查可能不全面
- 0.4-0.3分：关键步骤覆盖不全（如只覆盖30-50%），较多遗漏，影响问题诊断
- 0.2-0.1分：只覆盖少数关键步骤（如仅1-2个），无法支持有效排查
- 0.0分：无关键步骤覆盖，或步骤完全无关

**待分析的排查步骤**：
```
{solution_str}
```

请只返回一个0.0到1.0之间的数字分数，不要任何其他文字。
"""
    
    result_text = await async_call_v3_api(client, prompt)
    try:
        numbers = re.findall(r'\d+\.?\d*', result_text)
        if numbers:
            score = float(numbers[0])
            return max(0.0, min(1.0, score))
        return 0.0
    except:
        return 0.0

async def async_evaluate_instruction_correctness(client, response_text: str, whitelist_path: str) -> float:
    """异步评估指令正确性"""
    # 提取和验证SQL语法
    extracted_sqls = extract_sql_from_response(response_text)
    sql_syntax_details = validate_all_sqls(extracted_sqls)
    
    # 异步V3分析参数和风险 - 使用与同步版本完全相同的prompt
    prompt = f"""
你是一位顶级的数据库诊断专家和评审员。你的任务是基于"指令正确性"这个核心维度，对下面提供的数据库问题排查建议进行全面的分析，并以一个严格的 JSON 格式返回结果。

你的分析需要覆盖以下几个方面：

1.  **可配置系统参数提取**:
    - 任务：从文本中提取所有可通过 `my.cnf` 或 `SET` 命令修改的**系统参数**。
    - 关键点：必须是**可配置的参数**，而不是只读的状态变量（如 `Slave_IO_Running`）或 Schema 字段。
    - 输出字段：`configurable_parameters` (一个字符串列表)

2.  **风险操作识别**:
    - **可容忍风险 (Tolerable Risk)**:
        - 定义：会改变数据库状态或短暂影响性能，但通常是必要的维护操作。
        - 例子：更新统计信息 (`ANALYZE TABLE`)、检查或修复表 (`CHECK TABLE`, `REPAIR TABLE`)。
        - 输出字段：`tolerable_risks` (一个对象列表，每个对象包含 `operation` 和 `reason` 字段)
    - **明显风险 (Significant Risk)**:
        - 定义：会造成数据库卡顿、长时间锁定或服务中断的操作。
        - 例子：重启数据库服务 (任何形式的 `restart`, `shutdown` 指令)、在超大表上执行无在线工具的 `ALTER TABLE`。
        - 输出字段：`significant_risks` (一个对象列表，每个对象包含 `operation` 和 `reason` 字段)

**关键的排除规则 (非常重要)**:
- **绝对不是风险**: 任何**只读**的、用于监控和诊断的查询指令，都**不属于**任何风险类别。
- **具体例子**:
  - 所有 `SHOW ...` 命令 (如 `SHOW SLAVE STATUS`, `SHOW VARIABLES`)。
  - 所有从 `information_schema` 或 `performance_schema` 中 `SELECT` 数据的查询。
- 如果一个操作属于此类，请直接忽略，不要将其放入 `tolerable_risks` 或 `significant_risks` 列表中。

**输出格式要求**:
你必须严格按照以下 JSON 结构返回你的分析结果。不要添加任何额外的解释、Markdown 标记或注释。你的输出必须是一个合法的 JSON 对象。

```json
{{
  "configurable_parameters": ["param1", "param2"],
  "tolerable_risks": [
    {{"operation": "找到的操作或指令", "reason": "为什么这是可容忍风险"}}
  ],
  "significant_risks": [
    {{"operation": "找到的操作或指令", "reason": "为什么这是明显风险"}}
  ]
}}
```

---
**待分析的排查建议文本**:
```
{response_text}
```
---

现在，请开始分析并返回 JSON 结果。
"""
    
    result_text = await async_call_v3_api(client, prompt, 2048)
    
    try:
        json_start = result_text.find('{')
        json_end = result_text.rfind('}')
        if json_start != -1 and json_end != -1:
            json_str = result_text[json_start:json_end+1]
            v3_analysis = json.loads(json_str)
        else:
            v3_analysis = {"configurable_parameters": [], "tolerable_risks": [], "significant_risks": []}
    except:
        v3_analysis = {"configurable_parameters": [], "tolerable_risks": [], "significant_risks": []}
    
    # 验证参数
    extracted_params = v3_analysis.get("configurable_parameters", [])
    _score, param_accuracy_details = validate_parameters(extracted_params, whitelist_path)
    
    # 分离风险分析
    risk_details = {
        "tolerable_risks": v3_analysis.get("tolerable_risks", []),
        "significant_risks": v3_analysis.get("significant_risks", [])
    }
    
    # 计算最终指令正确性分数
    instruction_score, _ = calculate_instruction_score(
        sql_syntax_details, param_accuracy_details, risk_details
    )
    
    return instruction_score

async def async_evaluate_all_dimensions(solution_str: str, ground_truth: str, whitelist_path: str, log_dir: str = "/data/local_disk3/zuowei/verl-main/reward_logs") -> Tuple[float, float, float]:
    """异步并发评估所有三个维度（优化版：使用共享客户端提升性能）"""
    
    # 使用async with确保客户端正确关闭，避免连接泄漏
    async with openai.AsyncClient(
        base_url=os.getenv("V3_API_URL", "http://43.143.249.90:8081/v1"),
        api_key="EMPTY"
    ) as client:
        
        # 并发调用三个V3评估任务（使用create_task确保立即调度）
        tasks = [
            asyncio.create_task(async_evaluate_expect_coverage(client, solution_str, ground_truth)),
            asyncio.create_task(async_evaluate_key_steps_coverage(client, solution_str)),
            asyncio.create_task(async_evaluate_instruction_correctness(client, solution_str, whitelist_path))
        ]
        
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        elapsed_time = time.time() - start_time
        
        # 处理结果，确保都是float类型，并处理异常
        expect_score = 0.0
        key_steps_score = 0.0
        instruction_score = 0.0
        
        if len(results) >= 1:
            if isinstance(results[0], Exception):
                print(f"[异常] expect评估失败: {results[0]}")
                expect_score = 0.0
            else:
                expect_score = results[0] if isinstance(results[0], (int, float)) else 0.0
                
        if len(results) >= 2:
            if isinstance(results[1], Exception):
                print(f"[异常] 关键步骤评估失败: {results[1]}")
                key_steps_score = 0.0
            else:
                key_steps_score = results[1] if isinstance(results[1], (int, float)) else 0.0
                
        if len(results) >= 3:
            if isinstance(results[2], Exception):
                print(f"[异常] 指令正确性评估失败: {results[2]}")
                instruction_score = 0.0
            else:
                instruction_score = results[2] if isinstance(results[2], (int, float)) else 0.0
        
        # 计算最终分数
        WEIGHT_EXPECT = 0.30
        WEIGHT_KEY_STEPS = 0.30
        WEIGHT_INSTRUCTION = 0.40
        
        final_score = (expect_score * WEIGHT_EXPECT) + \
                      (key_steps_score * WEIGHT_KEY_STEPS) + \
                      (instruction_score * WEIGHT_INSTRUCTION)
        final_score = round(final_score, 2)
        final_score = max(0.0, min(1.0, final_score))
        
        # 异步路径也保存评估结果
        try:
            save_evaluation_result(
                solution_str, ground_truth, expect_score,
                key_steps_score, instruction_score, final_score, log_dir
            )
        except Exception as e:
            print(f"⚠️ 评估结果保存失败: {e}")
        
        return expect_score, key_steps_score, instruction_score

def compute_score(data_source, solution_str, ground_truth, extra_info):
    """
    计算单个样本的奖励分数
    
    Args:
        data_source: 数据源信息
        solution_str: 模型响应文本
        ground_truth: 期望的排查步骤文本
        extra_info: 额外信息
        
    Returns:
        最终奖励分数 (0.0-1.0)
    """
    return format_and_llm_reward(data_source, solution_str, ground_truth, extra_info)

def compute_score_batch(data_sources, solution_strs, ground_truths, extra_infos):
    """
    批量并行计算奖励分数
    
    Args:
        data_sources: 数据源信息列表
        solution_strs: 模型响应文本列表
        ground_truths: 期望的排查步骤文本列表
        extra_infos: 额外信息列表
        
    Returns:
        每个解决方案对应的最终奖励分数列表
    """
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = []
        for data_source, solution_str, ground_truth, extra_info in zip(data_sources, solution_strs, ground_truths, extra_infos):
            future = executor.submit(compute_score, data_source, solution_str, ground_truth, extra_info)
            futures.append(future)

        results = [future.result() for future in futures]

    return results