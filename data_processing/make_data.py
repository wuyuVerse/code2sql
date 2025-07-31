# -*- coding: utf-8 -*-
"""
make_data.py
------------
用于自动生成**合成ORM数据包**的工具，这些数据包镜像真实提取样本的结构（如`full_scenario.json`中的样本）。

它与本地或远程OpenAI兼容端点通信（参见`BASE_URL`），分三个阶段进行，确保每个生成的包都符合声明的`scenario`要求：

1. **ORM代码块** – 核心GORM/Django/SQLAlchemy风格的方法。
2. **调用者块** – 调用ORM API的真实函数。
3. **元数据** – 两个块的`code_meta_data`，以及场景所需的任何全局变量（如表名）。

结果写入单个JSON文件，您可以直接合并到训练/测试语料库中。

运行方式:
    python make_data.py                               # 一次性，所有场景
    python make_data.py --count 10 --scenario objvar   # 自定义生成

"""
from __future__ import annotations

import argparse
import json
import os
import time
import uuid
import random
import threading
from pathlib import Path
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

import openai

#####################################################################
# 配置
#####################################################################
BASE_URL = os.getenv("OPENAI_BASE_URL", "http://212.64.90.3:8081/v1")
API_KEY = os.getenv("OPENAI_API_KEY", "EMPTY")
MODEL = os.getenv("OPENAI_MODEL", "default")
TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))
TOP_P = float(os.getenv("OPENAI_TOP_P", "0.8"))
MAX_TOKENS = int(os.getenv("OPENAI_MAX_TOKENS", "4096"))

# full_scenario.json路径
FULL_SCENARIO_PATH = "/data/cloud_disk_1/home/wuyu/code2sql/full_scenario.json"

client = openai.Client(base_url=BASE_URL, api_key=API_KEY)

# 线程锁用于保护共享资源
_print_lock = threading.Lock()
_stats_lock = threading.Lock()

# 全局统计
_generation_stats = {
    "total_requests": 0,
    "successful_requests": 0,
    "failed_requests": 0,
    "total_tokens": 0
}

#####################################################################
# 场景定义和描述
#####################################################################
SCENARIOS = {
    "对象var+chunk": "ORM方法仅依赖接收者对象的成员变量和结构体字段来组装SQL查询，不需要任何外部参数或全局变量",
    "caller+global variable": "ORM方法需要依赖外部全局常量或变量（如表名、配置等），这些变量由调用者提供",
    "caller+chunk": "ORM方法需要调用者传递的参数chunks来构建SQL查询，方法本身不包含完整的查询逻辑",
    "caller的callee+caller": "ORM方法会调用其他子方法（callees），同时被上层调用者（caller）调用，形成调用链",
    "单chunk": "ORM方法只处理单一的数据块或查询片段，通常是最基础的CRUD操作",
    "单chunk+meta(global var)": "ORM方法使用单一数据块，同时依赖全局变量（如配置常量）来构建查询",
    "preload特殊函数": "ORM方法使用预加载功能（如GORM的Preload），用于优化关联查询，减少N+1查询问题",
    "association特殊函数": "ORM方法处理关联关系操作（如Association的Add、Delete、Replace等），用于管理模型间的关联",
    "单chunk+meta(local var)": "ORM方法使用单一数据块，同时依赖方法内部的局部变量来构建查询条件",
    "单chunk+meta(对象var)": "ORM方法使用单一数据块，同时依赖对象成员变量来补充查询条件",
    "一度caller+chunk": "存在一层调用关系的ORM方法，caller直接调用ORM方法并传递chunk参数",
    "二度caller+chunk": "存在两层调用关系的ORM方法，caller调用中间方法，中间方法再调用ORM方法并传递关键参数",
    "对象const+chunk": "ORM方法同时依赖对象常量成员变量和orm代码本身来构建查询",
    "if-else+caller": "Caller代码中包含if-else条件判断，根据不同的条件构建不同的filter参数传递给ORM方法，ORM方法根据传入的参数内容使用不同的筛选条件构建SQL查询"
}

#####################################################################
# 空值字典样例模板
#####################################################################
EMPTY_TEMPLATE = {
    "example_key": {
        "scenario": "",
        "code_key": "",
        "code_value": "",
        "sql_pattern_cnt": 1,
        "callers": [],
        "callees": [],
        "code_meta_data": []
    }
}

EMPTY_CALLER_TEMPLATE = {
    "code_key": "",
    "code_value": ""
}

EMPTY_META_TEMPLATE = {
    "code_key": "",
    "code_value": ""
}

#####################################################################
# 变量名词库 - 确保生成不同的变量名
#####################################################################
VARIABLE_NAMES = {
    "tables": [
        # 电商领域
        "product_catalog", "order_history", "payment_records", "inventory_items", "shopping_carts",
        "customer_reviews", "seller_profiles", "shipping_addresses", "discount_coupons", "return_requests",
        "product_categories", "brand_info", "warehouse_stock", "price_history", "vendor_contracts",
        
        # 金融领域
        "account_balances", "transaction_logs", "loan_applications", "credit_scores", "investment_portfolios",
        "insurance_policies", "risk_assessments", "compliance_records", "fraud_alerts", "market_data",
        "currency_rates", "trading_orders", "fund_transfers", "account_statements", "tax_documents",
        
        # 社交媒体
        "user_profiles", "social_posts", "friend_connections", "message_threads", "media_uploads",
        "comment_history", "like_records", "share_activities", "group_memberships", "event_invitations",
        "notification_queue", "privacy_settings", "content_reports", "trending_topics", "hashtag_usage",
        
        # 内容管理
        "article_content", "blog_posts", "media_library", "content_versions", "editorial_calendar",
        "author_profiles", "publication_schedule", "content_categories", "tag_assignments", "reader_analytics",
        "comment_moderation", "subscription_tiers", "content_licenses", "seo_metadata", "content_archive",
        
        # 物流配送
        "delivery_routes", "package_tracking", "driver_schedules", "vehicle_fleet", "warehouse_locations",
        "shipping_manifest", "delivery_confirmations", "route_optimization", "fuel_consumption", "maintenance_logs",
        "cargo_manifests", "dispatch_orders", "logistics_hubs", "transit_times", "delivery_zones",
        
        # 教育培训
        "student_enrollment", "course_catalog", "grade_records", "assignment_submissions", "exam_results",
        "teacher_profiles", "class_schedules", "curriculum_standards", "learning_materials", "progress_tracking",
        "certification_records", "training_modules", "skill_assessments", "attendance_logs", "parent_communications",
        
        # 医疗健康
        "patient_records", "medical_history", "prescription_data", "appointment_schedules", "diagnostic_results",
        "treatment_plans", "doctor_profiles", "hospital_departments", "insurance_claims", "medication_inventory",
        "lab_test_results", "surgery_schedules", "emergency_contacts", "health_metrics", "vaccination_records",
        
        # 企业管理
        "employee_records", "department_structure", "project_assignments", "performance_reviews", "payroll_data",
        "expense_reports", "meeting_schedules", "resource_allocation", "budget_planning", "vendor_management",
        "contract_agreements", "asset_inventory", "security_clearances", "training_certifications", "compliance_audits",
        
        # 游戏娱乐
        "player_profiles", "game_statistics", "achievement_records", "leaderboards", "virtual_items",
        "game_sessions", "tournament_brackets", "guild_memberships", "chat_messages", "match_history",
        "character_inventory", "skill_trees", "quest_progress", "reward_systems", "player_rankings"
    ],
    
    "entities": [
        # 电商实体
        "Product", "Order", "Customer", "Vendor", "Category", "Brand", "Inventory", "Coupon", "Review", "Cart",
        "Shipment", "Payment", "Refund", "Wishlist", "Recommendation", "Auction", "Marketplace", "Seller", "Buyer", "Deal",
        
        # 金融实体
        "Account", "Transaction", "Portfolio", "Investment", "Loan", "Credit", "Insurance", "Policy", "Claim", "Fund",
        "Bond", "Stock", "Currency", "Exchange", "Wallet", "Statement", "Report", "Budget", "Forecast", "Risk",
        
        # 社交实体
        "Profile", "Post", "Comment", "Message", "Friend", "Group", "Event", "Photo", "Video", "Story",
        "Notification", "Like", "Share", "Follow", "Block", "Report", "Stream", "Feed", "Timeline", "Tag",
        
        # 内容实体
        "Article", "Blog", "Media", "Author", "Editor", "Publication", "Newsletter", "Magazine", "Book", "Chapter",
        "Section", "Paragraph", "Image", "Audio", "Video", "Document", "Template", "Layout", "Theme", "Widget",
        
        # 物流实体
        "Package", "Delivery", "Route", "Driver", "Vehicle", "Warehouse", "Shipment", "Manifest", "Tracking", "Zone",
        "Hub", "Carrier", "Express", "Freight", "Container", "Pallet", "Label", "Scanner", "GPS", "Schedule",
        
        # 教育实体
        "Student", "Teacher", "Course", "Lesson", "Assignment", "Grade", "Exam", "Quiz", "Certificate", "Diploma",
        "Curriculum", "Textbook", "Classroom", "Schedule", "Semester", "Module", "Skill", "Achievement", "Progress", "Assessment",
        
        # 医疗实体
        "Patient", "Doctor", "Nurse", "Appointment", "Diagnosis", "Treatment", "Prescription", "Medicine", "Hospital", "Clinic",
        "Surgery", "Lab", "Test", "Result", "Symptom", "Disease", "Allergy", "Vaccine", "Insurance", "Claim",
        
        # 企业实体
        "Employee", "Manager", "Department", "Project", "Task", "Meeting", "Resource", "Budget", "Contract", "Vendor",
        "Client", "Proposal", "Invoice", "Expense", "Asset", "Equipment", "Office", "Team", "Role", "Permission",
        
        # 游戏实体
        "Player", "Character", "Game", "Level", "Quest", "Achievement", "Item", "Weapon", "Armor", "Spell",
        "Guild", "Tournament", "Match", "Score", "Ranking", "Reward", "Experience", "Skill", "Inventory", "Trade"
    ],
    
    "methods": [
        # 查询类方法
        "QueryByCondition", "FetchWithFilter", "SearchByKeyword", "GetByStatus", "ListWithPaging", "FindByCategory",
        "RetrieveByDate", "SelectByRange", "LoadByType", "ScanByPattern", "FilterByAttribute", "SortByField",
        "GroupByCategory", "CountByStatus", "AggregateByType", "CalculateByFormula", "ValidateByRules", "MatchByPattern",
        
        # 业务逻辑方法
        "ProcessPayment", "ValidateOrder", "CalculateDiscount", "GenerateReport", "SendNotification", "UpdateInventory",
        "CreateInvoice", "ScheduleDelivery", "VerifyIdentity", "AssignTask", "ApproveRequest", "RejectApplication",
        "ArchiveData", "BackupRecords", "RestoreFromBackup", "MigrateData", "SyncWithExternal", "ImportFromFile",
        
        # CRUD操作方法
        "CreateRecord", "UpdateEntity", "DeleteItem", "InsertBatch", "BulkUpdate", "SoftDelete", "HardDelete",
        "UpsertData", "MergeRecords", "DuplicateEntry", "CloneObject", "CopyStructure", "MoveToArchive", "RestoreDeleted",
        
        # 统计分析方法
        "AnalyzePerformance", "GenerateMetrics", "CalculateStatistics", "TrackBehavior", "MonitorActivity", "MeasureEfficiency",
        "EvaluateResults", "CompareData", "PredictTrends", "ForecastDemand", "OptimizeRoutes", "RecommendActions",
        
        # 安全验证方法
        "AuthenticateUser", "AuthorizeAccess", "ValidatePermissions", "EncryptData", "DecryptInfo", "HashPassword",
        "VerifySignature", "CheckIntegrity", "AuditChanges", "LogActivity", "DetectFraud", "PreventAttack",
        
        # 系统管理方法
        "ConfigureSettings", "ManageResources", "MonitorHealth", "OptimizePerformance", "ScaleCapacity", "LoadBalance",
        "CacheData", "ClearCache", "RefreshIndex", "RebuildIndex", "CleanupOldData", "PurgeExpiredRecords"
    ],
    
    "fields": [
        # 通用标识字段
        "RecordId", "EntityId", "UniqueKey", "ReferenceCode", "SequenceNumber", "TrackingId", "SessionToken",
        "AuthToken", "RefreshKey", "ApiKey", "SecretHash", "PublicKey", "PrivateKey", "CertificateId", "LicenseKey",
        
        # 时间相关字段
        "CreationTime", "ModificationDate", "ExpirationTime", "StartDate", "EndDate", "ScheduledTime", "DeadlineDate",
        "LastAccessTime", "FirstLoginDate", "RegistrationTime", "ActivationDate", "SuspensionTime", "ReactivationDate",
        
        # 状态和类型字段
        "CurrentStatus", "ProcessingState", "ApprovalLevel", "PriorityRank", "CategoryType", "ClassificationLevel",
        "SecurityLevel", "AccessLevel", "PermissionType", "RoleCode", "DepartmentCode", "LocationCode", "RegionCode",
        
        # 数值和度量字段
        "TotalAmount", "UnitPrice", "DiscountRate", "TaxAmount", "NetValue", "GrossValue", "Quantity", "Weight",
        "Volume", "Dimension", "Percentage", "Ratio", "Score", "Rating", "Points", "Credits", "Balance", "Limit",
        
        # 用户和客户字段
        "UserName", "DisplayName", "FullName", "FirstName", "LastName", "MiddleName", "NickName", "EmailAddress",
        "PhoneNumber", "MobileNumber", "ContactInfo", "HomeAddress", "WorkAddress", "MailingAddress", "BillingAddress",
        
        # 业务特定字段
        "ProductCode", "OrderNumber", "InvoiceNumber", "ContractNumber", "ProjectCode", "TaskId", "TicketNumber",
        "CaseNumber", "RequestId", "ApplicationId", "TransactionId", "PaymentId", "ShipmentId", "DeliveryCode",
        
        # 技术字段
        "DatabaseName", "TableName", "ColumnName", "IndexName", "ConnectionString", "ConfigurationKey", "ParameterName",
        "VariableName", "FunctionName", "MethodName", "ClassName", "NamespaceName", "ModuleName", "ServiceName",
        
        # 内容和媒体字段
        "Title", "Description", "Content", "Summary", "Keywords", "Tags", "Category", "SubCategory", "Topic",
        "Subject", "Theme", "Genre", "Format", "Language", "Version", "Edition", "Publication", "Author", "Editor",
        
        # 位置和地理字段
        "Country", "State", "City", "District", "Street", "Building", "Floor", "Room", "PostalCode", "ZipCode",
        "Latitude", "Longitude", "Timezone", "Locale", "Region", "Territory", "Continent", "Area", "Zone", "Sector"
    ]
}

#####################################################################
# 样例数据加载
#####################################################################
def load_full_scenarios(scenario_path: str) -> Dict:
    """加载full_scenario.json文件。"""
    try:
        with open(scenario_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"警告: 无法加载 {scenario_path}: {e}")
        return {}

def get_scenario_example(scenario: str, full_scenarios: Dict) -> Optional[Dict]:
    """根据场景标签获取第一个匹配的样例。"""
    for key, value in full_scenarios.items():
        if value.get('scenario') == scenario:
            return {key: value}
    return None

def format_example_for_prompt(example: Dict, remove_fields: List[str] = None) -> str:
    """格式化样例用于提示词显示。"""
    if not example:
        return "无样例数据"
    
    if remove_fields is None:
        remove_fields = ["code_file", "code_version", "code_label", "code_type", 
                        "code_start_line", "code_end_line", "code_start_column"]
    
    # 深拷贝以避免修改原始数据
    example_copy = json.loads(json.dumps(example))
    
    # 递归移除不需要的字段
    def remove_unwanted_fields(obj):
        if isinstance(obj, dict):
            for field in remove_fields:
                obj.pop(field, None)
            for value in obj.values():
                remove_unwanted_fields(value)
        elif isinstance(obj, list):
            for item in obj:
                remove_unwanted_fields(item)
    
    remove_unwanted_fields(example_copy)
    
    return json.dumps(example_copy, indent=2, ensure_ascii=False)

#####################################################################
# 提示词模板 – 调优使LLM只输出*结构化JSON*
#####################################################################
PROMPT_ORM = """
你需要根据给定的场景标签生成一个真实的Go语言ORM方法。

场景标签: "{scenario}"
场景描述: {scenario_desc}

参考以下真实样例（但生成完全不同的内容）:
{example}

请严格按照以下JSON格式输出，确保字段完整：
```json
{{
    "scenario": "{scenario}",
    "code_key": "方法名（使用{method_examples}等不同命名）",
    "code_value": "完整的Go代码（使用{entity_examples}等实体，{table_examples}等表名）",
    "sql_pattern_cnt": 1,
    "callers": [],
    "callees": []
}}
```

代码要求：
1. 使用多样化的变量名，避免重复使用User、Order等常见名词
2. 实体名使用：{entity_examples}
3. 表名使用：{table_examples}  
4. 方法名使用：{method_examples}
5. 字段名使用：{field_examples}
6. 代码必须是完整可运行的Go代码，使用GORM框架
7. 代码长度控制在25行以内
8. 根据场景要求正确实现相应的逻辑模式
9. 生成的内容必须与参考样例完全不同，使用不同的业务域、变量名、逻辑结构

只返回JSON格式，不要包含markdown标记或其他文本。
"""

PROMPT_CALLER = """
你需要为以下ORM代码块编写一个调用者函数。

ORM代码块:
{orm_block}

参考以下真实样例（但生成完全不同的内容）:
{example_caller}

请严格按照以下JSON格式输出：
```json
{{
    "code_key": "调用者方法名",
    "code_value": "完整的Go调用者代码"
}}
```

调用者代码要求：
1. 方法名与ORM方法不同，使用{caller_examples}等命名
2. 正确创建和初始化ORM对象
3. 根据场景正确传递参数或设置全局变量
4. 包含适当的错误处理
5. 代码长度控制在20行以内
6. 变量名要多样化，避免重复
7. 生成的内容必须与参考样例完全不同

只返回JSON格式，不要包含markdown标记或其他文本。
"""

PROMPT_META = """
基于以下ORM代码块和其调用者，创建完整的`code_meta_data`数组。

ORM代码块:
{orm_block}

调用者代码块:
{caller_block}

参考以下真实样例（但生成完全不同的内容）:
{example_meta}

请严格按照以下JSON数组格式输出：
```json
[
    {{
        "code_key": "结构体或类型名",
        "code_value": "Go类型定义代码"
    }},
    {{
        "code_key": "常量或变量名", 
        "code_value": "Go常量或变量定义"
    }}
]
```

元数据要求：
1. 包含所有相关的结构体定义（请求、响应、实体类型）
2. 包含必要的常量定义（表名、状态值等）
3. 包含全局变量定义（如果场景需要）
4. 类型名使用{type_examples}等多样化命名
5. 确保代码完整性和正确性
6. 每个元素都是独立的代码片段
7. 生成的内容必须与参考样例完全不同

只返回JSON数组格式，不要包含markdown标记或其他文本。
"""

#####################################################################
# 辅助函数
#####################################################################

def get_random_names():
    """获取随机变量名组合。"""
    return {
        "entity_examples": ", ".join(random.sample(VARIABLE_NAMES["entities"], 3)),
        "table_examples": ", ".join(random.sample(VARIABLE_NAMES["tables"], 3)),
        "method_examples": ", ".join(random.sample(VARIABLE_NAMES["methods"], 3)),
        "field_examples": ", ".join(random.sample(VARIABLE_NAMES["fields"], 3)),
        "type_examples": ", ".join(random.sample(VARIABLE_NAMES["entities"], 2)),
        "caller_examples": ", ".join([f"Handle{name}" for name in random.sample(VARIABLE_NAMES["entities"], 2)])
    }

def thread_safe_print(*args, **kwargs):
    """线程安全的打印函数。"""
    with _print_lock:
        print(*args, **kwargs)

def update_stats(success: bool, tokens: int = 0):
    """更新全局统计信息。"""
    with _stats_lock:
        _generation_stats["total_requests"] += 1
        if success:
            _generation_stats["successful_requests"] += 1
        else:
            _generation_stats["failed_requests"] += 1
        _generation_stats["total_tokens"] += tokens

def call_llm(prompt: str, request_type: str = "unknown") -> str:
    """调用大语言模型的底层封装。"""
    try:
        thread_id = threading.current_thread().name
        thread_safe_print(f"[{thread_id}] 开始 {request_type} 请求...")
        
        rsp = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=TEMPERATURE,
            top_p=TOP_P,
            max_tokens=MAX_TOKENS,
        )
        
        content = rsp.choices[0].message.content.strip()
        tokens = rsp.usage.total_tokens if hasattr(rsp, 'usage') and rsp.usage else 0
        
        update_stats(True, tokens)
        thread_safe_print(f"[{thread_id}] {request_type} 请求完成 (tokens: {tokens})")
        
        return content
    except Exception as e:
        update_stats(False)
        thread_safe_print(f"[{threading.current_thread().name}] 调用LLM时出错 ({request_type}): {e}")
        raise

def call_llm_parallel(prompts_and_types: List[tuple]) -> List[str]:
    """并行调用多个LLM请求。
    
    Args:
        prompts_and_types: [(prompt, request_type), ...] 的列表
    
    Returns:
        响应列表，顺序与输入一致
    """
    max_workers = min(len(prompts_and_types), 3)  # 限制并发数，避免过载API
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        future_to_index = {}
        for i, (prompt, request_type) in enumerate(prompts_and_types):
            future = executor.submit(call_llm, prompt, request_type)
            future_to_index[future] = i
        
        # 收集结果，保持顺序
        results = [None] * len(prompts_and_types)
        for future in as_completed(future_to_index):
            index = future_to_index[future]
            try:
                results[index] = future.result()
            except Exception as e:
                thread_safe_print(f"并行请求失败 (index {index}): {e}")
                raise
        
        return results


def clean_json_response(response: str) -> str:
    """清理LLM响应，提取JSON部分。"""
    # 移除可能的markdown代码块标记
    response = response.replace("```json", "").replace("```", "")
    response = response.strip()
    
    # 查找JSON开始和结束位置
    start_idx = -1
    end_idx = -1
    
    # 查找第一个 { 或 [
    for i, char in enumerate(response):
        if char in ['{', '[']:
            start_idx = i
            break
    
    if start_idx == -1:
        return response
    
    # 查找匹配的结束符
    bracket_count = 0
    start_char = response[start_idx]
    end_char = '}' if start_char == '{' else ']'
    
    for i in range(start_idx, len(response)):
        if response[i] == start_char:
            bracket_count += 1
        elif response[i] == end_char:
            bracket_count -= 1
            if bracket_count == 0:
                end_idx = i
                break
    
    if end_idx == -1:
        return response[start_idx:]
    
    return response[start_idx:end_idx + 1]


def generate_pack(scenario: str, full_scenarios: Dict) -> Dict:
    """为给定场景标签生成*一个*合成包（串行版本）。"""
    thread_safe_print(f"正在生成场景: {scenario}")
    
    # 获取随机变量名
    var_names = get_random_names()
    scenario_desc = SCENARIOS.get(scenario, "未知场景")
    
    # 获取场景样例
    example = get_scenario_example(scenario, full_scenarios)
    example_str = format_example_for_prompt(example) if example else "无对应场景样例"
    
    if example:
        thread_safe_print(f"  - 找到场景样例: {list(example.keys())[0]}")
    else:
        thread_safe_print(f"  - 未找到场景样例，将使用通用模板")
    
    # 1) ORM代码块
    thread_safe_print("  - 生成ORM代码块...")
    
    # 根据场景选择不同的ORM提示词模板
    if scenario == "if-else+caller":
        from config.data_processing.synthetic_data_generator.prompts import PROMPT_ORM_IF_ELSE_CALLER
        orm_prompt = PROMPT_ORM_IF_ELSE_CALLER.format(
            example=example_str,
            **var_names
        )
    elif scenario == "switch":
        from config.data_processing.synthetic_data_generator.prompts import PROMPT_ORM_SWITCH
        orm_prompt = PROMPT_ORM_SWITCH.format(
            example=example_str,
            **var_names
        )
    else:
        orm_prompt = PROMPT_ORM.format(
            scenario=scenario,
            scenario_desc=scenario_desc,
            example=example_str,
            **var_names
        )
    orm_response = call_llm(orm_prompt, "ORM")
    orm_json = clean_json_response(orm_response)
    
    try:
        orm_block = json.loads(orm_json)
    except json.JSONDecodeError as e:
        thread_safe_print(f"解析ORM JSON失败: {e}")
        thread_safe_print(f"原始响应: {orm_response}")
        thread_safe_print(f"清理后: {orm_json}")
        raise
    
    # 确保必要的字段存在
    if 'callers' not in orm_block:
        orm_block['callers'] = []
    if 'callees' not in orm_block:
        orm_block['callees'] = []
    
    # 2) 调用者代码块
    thread_safe_print("  - 生成调用者代码块...")
    
    # 提取样例中的caller信息
    example_caller = "无样例数据"
    if example:
        example_data = list(example.values())[0]
        if 'callers' in example_data and example_data['callers']:
            caller_data = example_data['callers'][0]
            # 移除不需要的字段
            caller_clean = {k: v for k, v in caller_data.items() 
                          if k not in ["code_file", "code_version", "code_label", "code_type", 
                                     "code_start_line", "code_end_line", "code_start_column"]}
            example_caller = json.dumps(caller_clean, indent=2, ensure_ascii=False)
    
    # 根据场景选择不同的Caller提示词模板
    if scenario == "if-else+caller":
        from config.data_processing.synthetic_data_generator.prompts import PROMPT_CALLER_IF_ELSE
        caller_prompt = PROMPT_CALLER_IF_ELSE.format(
            orm_block=json.dumps(orm_block, ensure_ascii=False),
            example_caller=example_caller,
            **var_names
        )
    elif scenario == "switch":
        from config.data_processing.synthetic_data_generator.prompts import PROMPT_CALLER_SWITCH
        caller_prompt = PROMPT_CALLER_SWITCH.format(
            orm_block=json.dumps(orm_block, ensure_ascii=False),
            example_caller=example_caller,
            **var_names
        )
    else:
        caller_prompt = PROMPT_CALLER.format(
            orm_block=json.dumps(orm_block, ensure_ascii=False),
            example_caller=example_caller,
            **var_names
        )
    caller_response = call_llm(caller_prompt, "Caller")
    caller_json = clean_json_response(caller_response)
    
    try:
        caller_block = json.loads(caller_json)
    except json.JSONDecodeError as e:
        thread_safe_print(f"解析调用者JSON失败: {e}")
        thread_safe_print(f"原始响应: {caller_response}")
        thread_safe_print(f"清理后: {caller_json}")
        raise
    
    # 3) 元数据
    thread_safe_print("  - 生成元数据...")
    
    # 提取样例中的meta信息
    example_meta = "无样例数据"
    if example:
        example_data = list(example.values())[0]
        if 'code_meta_data' in example_data:
            meta_data = example_data['code_meta_data']
            # 移除不需要的字段
            meta_clean = []
            for item in meta_data:
                item_clean = {k: v for k, v in item.items() 
                            if k not in ["code_file", "code_version", "code_label", "code_type", 
                                       "code_start_line", "code_end_line", "code_start_column"]}
                meta_clean.append(item_clean)
            example_meta = json.dumps(meta_clean, indent=2, ensure_ascii=False)
    
    meta_prompt = PROMPT_META.format(
        orm_block=json.dumps(orm_block, ensure_ascii=False),
        caller_block=json.dumps(caller_block, ensure_ascii=False),
        example_meta=example_meta,
        **var_names
    )
    meta_response = call_llm(meta_prompt, "Meta")
    meta_json = clean_json_response(meta_response)
    
    try:
        meta_block = json.loads(meta_json)
    except json.JSONDecodeError as e:
        thread_safe_print(f"解析元数据JSON失败: {e}")
        thread_safe_print(f"原始响应: {meta_response}")
        thread_safe_print(f"清理后: {meta_json}")
        raise
    
    # 组装最终字典，镜像full_scenario.json结构
    pack_key = f"synthetic_{scenario.replace('+', '_').replace(' ', '_').replace('(', '').replace(')', '')}_{orm_block['code_key']}"
    pack = {
        pack_key: {
            **orm_block,
            "code_meta_data": meta_block,
            "callers": [caller_block],
        }
    }
    
    thread_safe_print(f"  - 成功生成包: {pack_key}")
    return pack

def generate_pack_parallel(scenario: str, full_scenarios: Dict) -> Dict:
    """为给定场景标签生成*一个*合成包（并行版本）。"""
    thread_safe_print(f"[并行] 正在生成场景: {scenario}")
    
    # 获取随机变量名
    var_names = get_random_names()
    scenario_desc = SCENARIOS.get(scenario, "未知场景")
    
    # 获取场景样例
    example = get_scenario_example(scenario, full_scenarios)
    example_str = format_example_for_prompt(example) if example else "无对应场景样例"
    
    if example:
        thread_safe_print(f"  - 找到场景样例: {list(example.keys())[0]}")
    else:
        thread_safe_print(f"  - 未找到场景样例，将使用通用模板")
    
    # 提取样例信息（为后续请求准备）
    example_caller = "无样例数据"
    example_meta = "无样例数据"
    
    if example:
        example_data = list(example.values())[0]
        
        # 准备caller样例
        if 'callers' in example_data and example_data['callers']:
            caller_data = example_data['callers'][0]
            caller_clean = {k: v for k, v in caller_data.items() 
                          if k not in ["code_file", "code_version", "code_label", "code_type", 
                                     "code_start_line", "code_end_line", "code_start_column"]}
            example_caller = json.dumps(caller_clean, indent=2, ensure_ascii=False)
        
        # 准备meta样例
        if 'code_meta_data' in example_data:
            meta_data = example_data['code_meta_data']
            meta_clean = []
            for item in meta_data:
                item_clean = {k: v for k, v in item.items() 
                            if k not in ["code_file", "code_version", "code_label", "code_type", 
                                       "code_start_line", "code_end_line", "code_start_column"]}
                meta_clean.append(item_clean)
            example_meta = json.dumps(meta_clean, indent=2, ensure_ascii=False)
    
    # 第一阶段：生成ORM代码块
    thread_safe_print("  - [阶段1] 生成ORM代码块...")
    
    # 根据场景选择不同的ORM提示词模板
    if scenario == "if-else+caller":
        from config.data_processing.synthetic_data_generator.prompts import PROMPT_ORM_IF_ELSE_CALLER
        orm_prompt = PROMPT_ORM_IF_ELSE_CALLER.format(
            example=example_str,
            **var_names
        )
    elif scenario == "switch":
        from config.data_processing.synthetic_data_generator.prompts import PROMPT_ORM_SWITCH
        orm_prompt = PROMPT_ORM_SWITCH.format(
            example=example_str,
            **var_names
        )
    else:
        orm_prompt = PROMPT_ORM.format(
            scenario=scenario,
            scenario_desc=scenario_desc,
            example=example_str,
            **var_names
        )
    
    orm_response = call_llm(orm_prompt, "ORM")
    orm_json = clean_json_response(orm_response)
    
    try:
        orm_block = json.loads(orm_json)
    except json.JSONDecodeError as e:
        thread_safe_print(f"解析ORM JSON失败: {e}")
        raise
    
    # 确保必要的字段存在
    if 'callers' not in orm_block:
        orm_block['callers'] = []
    if 'callees' not in orm_block:
        orm_block['callees'] = []
    
    # 第二阶段：并行生成Caller和Meta（因为Meta需要依赖ORM，所以分两个阶段）
    thread_safe_print("  - [阶段2] 并行生成Caller和Meta...")
    
    # 准备并行请求
    # 根据场景选择不同的Caller提示词模板
    if scenario == "if-else+caller":
        from config.data_processing.synthetic_data_generator.prompts import PROMPT_CALLER_IF_ELSE
        caller_prompt = PROMPT_CALLER_IF_ELSE.format(
            orm_block=json.dumps(orm_block, ensure_ascii=False),
            example_caller=example_caller,
            **var_names
        )
    elif scenario == "switch":
        from config.data_processing.synthetic_data_generator.prompts import PROMPT_CALLER_SWITCH
        caller_prompt = PROMPT_CALLER_SWITCH.format(
            orm_block=json.dumps(orm_block, ensure_ascii=False),
            example_caller=example_caller,
            **var_names
        )
    else:
        caller_prompt = PROMPT_CALLER.format(
            orm_block=json.dumps(orm_block, ensure_ascii=False),
            example_caller=example_caller,
            **var_names
        )
    
    meta_prompt = PROMPT_META.format(
        orm_block=json.dumps(orm_block, ensure_ascii=False),
        caller_block="",  # 这里暂时为空，因为我们还没有caller
        example_meta=example_meta,
        **var_names
    )
    
    # 并行发送请求
    prompts_and_types = [
        (caller_prompt, "Caller"),
        (meta_prompt, "Meta")
    ]
    
    responses = call_llm_parallel(prompts_and_types)
    caller_response, meta_response = responses
    
    # 解析结果
    caller_json = clean_json_response(caller_response)
    meta_json = clean_json_response(meta_response)
    
    try:
        caller_block = json.loads(caller_json)
        meta_block = json.loads(meta_json)
    except json.JSONDecodeError as e:
        thread_safe_print(f"解析并行响应JSON失败: {e}")
        raise
    
    # 组装最终字典
    pack_key = f"synthetic_{scenario.replace('+', '_').replace(' ', '_').replace('(', '').replace(')', '')}_{orm_block['code_key']}"
    pack = {
        pack_key: {
            **orm_block,
            "code_meta_data": meta_block,
            "callers": [caller_block],
        }
    }
    
    thread_safe_print(f"  - [并行] 成功生成包: {pack_key}")
    return pack

def generate_multiple_packs_parallel(scenarios_and_counts: List[tuple], full_scenarios: Dict, max_workers: int = 4) -> Dict:
    """并行生成多个场景的数据包。
    
    Args:
        scenarios_and_counts: [(scenario, count), ...] 的列表
        full_scenarios: 参考样例数据
        max_workers: 最大并行worker数量
    
    Returns:
        所有生成的包的字典
    """
    all_packs = {}
    
    # 创建所有任务
    tasks = []
    for scenario, count in scenarios_and_counts:
        for i in range(count):
            tasks.append((scenario, full_scenarios, i + 1, count))
    
    thread_safe_print(f"开始并行生成 {len(tasks)} 个数据包，使用 {max_workers} 个worker...")
    
    def generate_single_task(args):
        scenario, full_scenarios, index, total = args
        thread_id = threading.current_thread().name
        thread_safe_print(f"[{thread_id}] 开始生成 {scenario} ({index}/{total})")
        
        try:
            pack = generate_pack_parallel(scenario, full_scenarios)
            thread_safe_print(f"[{thread_id}] 完成 {scenario} ({index}/{total})")
            return pack
        except Exception as e:
            thread_safe_print(f"[{thread_id}] 生成失败 {scenario} ({index}/{total}): {e}")
            return None
    
    # 并行执行所有任务
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_task = {executor.submit(generate_single_task, task): task for task in tasks}
        
        completed = 0
        for future in as_completed(future_to_task):
            completed += 1
            task = future_to_task[future]
            scenario = task[0]
            
            try:
                pack = future.result()
                if pack:
                    all_packs.update(pack)
                thread_safe_print(f"进度: {completed}/{len(tasks)} 完成")
            except Exception as e:
                thread_safe_print(f"任务执行失败 {scenario}: {e}")
    
    return all_packs


def validate_pack(pack: Dict) -> bool:
    """验证生成的包是否符合预期格式。"""
    for key, value in pack.items():
        required_fields = ['scenario', 'code_key', 'code_value', 
                          'sql_pattern_cnt', 'callers', 'code_meta_data']
        
        for field in required_fields:
            if field not in value:
                print(f"警告: 包 {key} 缺少必需字段: {field}")
                return False
        
        # 验证callers结构
        if not isinstance(value['callers'], list) or len(value['callers']) == 0:
            print(f"警告: 包 {key} 的callers字段格式不正确")
            return False
        
        caller = value['callers'][0]
        caller_required = ['code_key', 'code_value']
        for field in caller_required:
            if field not in caller:
                print(f"警告: 包 {key} 的caller缺少字段: {field}")
                return False
                
        # 验证code_meta_data结构
        if not isinstance(value['code_meta_data'], list):
            print(f"警告: 包 {key} 的code_meta_data不是数组")
            return False
    
    return True


#####################################################################
# CLI入口点
#####################################################################

def print_generation_stats():
    """打印生成统计信息。"""
    with _stats_lock:
        stats = _generation_stats.copy()
    
    thread_safe_print(f"\n📊 生成统计:")
    thread_safe_print(f"  - 总请求数: {stats['total_requests']}")
    thread_safe_print(f"  - 成功请求: {stats['successful_requests']}")
    thread_safe_print(f"  - 失败请求: {stats['failed_requests']}")
    thread_safe_print(f"  - 成功率: {stats['successful_requests']/max(stats['total_requests'], 1)*100:.1f}%")
    thread_safe_print(f"  - 总Token数: {stats['total_tokens']}")
    if stats['successful_requests'] > 0:
        thread_safe_print(f"  - 平均Token/请求: {stats['total_tokens']/stats['successful_requests']:.0f}")

def main():
    parser = argparse.ArgumentParser(description="生成伪造的ORM场景数据")
    parser.add_argument("--scenario", choices=list(SCENARIOS.keys()), 
                       help="要生成的场景标签", default=None)
    parser.add_argument("--count", type=int, default=1, help="每个场景生成多少个包")
    parser.add_argument("--out", type=Path, default=Path("synthetic_scenarios.json"), 
                       help="输出文件路径")
    parser.add_argument("--validate", action="store_true", help="验证生成的数据格式")
    parser.add_argument("--list-scenarios", action="store_true", help="列出所有支持的场景")
    parser.add_argument("--full-scenario-path", type=str, default=FULL_SCENARIO_PATH,
                       help="full_scenario.json文件路径")
    
    # 并行相关参数
    parser.add_argument("--parallel", action="store_true", help="启用并行模式")
    parser.add_argument("--workers", type=int, default=50, help="并行worker数量 (默认: 4)")
    parser.add_argument("--no-delay", action="store_true", help="禁用请求间延迟（并行模式下自动禁用）")
    parser.add_argument("--stats", action="store_true", help="显示详细统计信息")
    
    args = parser.parse_args()

    if args.list_scenarios:
        print("支持的场景列表:")
        for scenario, desc in SCENARIOS.items():
            print(f"  - {scenario}: {desc}")
        return

    # 使用命令行参数指定的路径
    scenario_path = args.full_scenario_path

    # 加载参考样例
    thread_safe_print(f"加载参考样例: {scenario_path}")
    full_scenarios = load_full_scenarios(scenario_path)
    
    if full_scenarios:
        thread_safe_print(f"成功加载 {len(full_scenarios)} 个参考样例")
        # 统计各场景的样例数量
        scenario_counts = {}
        for value in full_scenarios.values():
            scenario = value.get('scenario', '未知')
            scenario_counts[scenario] = scenario_counts.get(scenario, 0) + 1
        
        thread_safe_print("各场景样例数量:")
        for scenario, count in scenario_counts.items():
            thread_safe_print(f"  - {scenario}: {count} 个")
    else:
        thread_safe_print("警告: 未能加载参考样例，将使用通用模板生成")

    scenarios = [args.scenario] if args.scenario else list(SCENARIOS.keys())

    # 记录开始时间
    start_time = time.time()
    all_packs: Dict = {}
    total_generated = 0
    
    if args.parallel:
        # 并行模式
        thread_safe_print(f"\n🚀 启用并行模式 (workers: {args.workers})")
        scenarios_and_counts = [(sc, args.count) for sc in scenarios]
        
        try:
            all_packs = generate_multiple_packs_parallel(
                scenarios_and_counts, 
                full_scenarios, 
                max_workers=args.workers
            )
            total_generated = len(all_packs)
            
        except Exception as e:
            thread_safe_print(f"并行生成时出错: {e}")
            return
    else:
        # 串行模式
        thread_safe_print(f"\n📝 串行模式生成")
        for sc in scenarios:
            thread_safe_print(f"\n开始生成场景: {sc}")
            thread_safe_print(f"场景描述: {SCENARIOS[sc]}")
            for i in range(args.count):
                thread_safe_print(f"生成第 {i+1}/{args.count} 个包...")
                try:
                    pack = generate_pack(sc, full_scenarios)
                    
                    if args.validate and not validate_pack(pack):
                        thread_safe_print(f"包验证失败，跳过...")
                        continue
                    
                    all_packs.update(pack)
                    total_generated += 1
                    
                    # 串行模式下的延迟（除非禁用）
                    if not args.no_delay:
                        time.sleep(0.5)
                    
                except Exception as e:
                    thread_safe_print(f"生成包时出错: {e}")
                    continue

    # 计算总耗时
    elapsed_time = time.time() - start_time
    
    # 验证生成的数据（如果启用）
    if args.validate:
        thread_safe_print(f"\n🔍 验证生成的数据...")
        valid_count = 0
        for key, pack_data in all_packs.items():
            if validate_pack({key: pack_data}):
                valid_count += 1
        thread_safe_print(f"验证结果: {valid_count}/{len(all_packs)} 个包通过验证")

    # 保存结果
    try:
        args.out.write_text(json.dumps(all_packs, indent=2, ensure_ascii=False), encoding='utf-8')
        thread_safe_print(f"\n✅ 成功生成 {total_generated} 个包 → {args.out}")
        thread_safe_print(f"包含以下场景: {scenarios}")
        thread_safe_print(f"总耗时: {elapsed_time:.2f} 秒")
        
        if total_generated > 0:
            thread_safe_print(f"平均每包耗时: {elapsed_time/total_generated:.2f} 秒")
        
        # 显示生成的包的键
        if all_packs and len(all_packs) <= 10:
            thread_safe_print("\n生成的包键:")
            for key in all_packs.keys():
                thread_safe_print(f"  - {key}")
        elif all_packs:
            thread_safe_print(f"\n生成了 {len(all_packs)} 个包 (键列表略)")
                
    except Exception as e:
        thread_safe_print(f"保存文件时出错: {e}")
        return
    
    # 显示统计信息
    if args.stats or args.parallel:
        print_generation_stats()


if __name__ == "__main__":
    main()
