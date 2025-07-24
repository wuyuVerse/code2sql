"""
合成数据生成器配置管理
"""
import os
from pathlib import Path
from typing import Dict, List, Optional
from config.llm.llm_config import get_llm_config

# 默认配置文件路径
DEFAULT_FULL_SCENARIO_PATH = "datasets/full_scenario.json"

# 场景定义和描述
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
    "switch": "ORM方法使用switch条件语句来根据不同的参数值或状态构建不同的SQL查询条件，实现动态查询逻辑",
    "if-else+caller": "Caller代码中包含if-else条件判断，根据不同的条件构建不同的filter参数传递给ORM方法，ORM方法根据传入的参数内容使用不同的筛选条件构建SQL查询",
    "if-else+orm": "ORM方法内部包含if-else条件判断，根据不同的分支使用不同的筛选条件构建SQL查询",
    "no-where": "ORM方法需要外部传入部分where条件，但当前没有caller，所以部分where条件无法确定。where条件包含外来传入的参数和固定的查询逻辑",
    "table_mapping_incomplete": "ORM方法中模型将结构体名错误理解为表名，而真实表名通过常量定义。需要明确区分结构体名和真实表名，避免模型错误地将结构体名当作表名使用",
}

# 变量名词库 - 确保生成不同的变量名
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


class SyntheticDataConfig:
    """合成数据生成器配置管理"""
    
    def __init__(self, 
                 llm_server: str = None,
                 full_scenario_path: str = DEFAULT_FULL_SCENARIO_PATH,
                 output_path: str = "synthetic_scenarios.json",
                 max_workers: int = 4,
                 temperature: float = 0.7,
                 top_p: float = 0.8,
                 max_tokens: int = 4096):
        """初始化配置
        
        Args:
            llm_server: LLM服务器名称
            full_scenario_path: 参考样例文件路径
            output_path: 输出文件路径
            max_workers: 最大并行worker数量
            temperature: LLM温度参数
            top_p: LLM top_p参数
            max_tokens: 最大token数
        """
        # 获取LLM服务器配置
        if llm_server is None:
            from config.data_processing.workflow.workflow_config import get_workflow_config
            workflow_config = get_workflow_config()
            llm_server = workflow_config.get_llm_server("synthetic_data_generator")
        
        self.llm_server = llm_server
        self.full_scenario_path = full_scenario_path
        self.output_path = Path(output_path)
        self.max_workers = max_workers
        self.temperature = temperature
        self.top_p = top_p
        self.max_tokens = max_tokens
        
        # 获取LLM配置
        self.llm_config = get_llm_config()
    
    def get_random_names(self) -> Dict[str, str]:
        """获取随机变量名组合"""
        import random
        return {
            "entity_examples": ", ".join(random.sample(VARIABLE_NAMES["entities"], 3)),
            "table_examples": ", ".join(random.sample(VARIABLE_NAMES["tables"], 3)),
            "method_examples": ", ".join(random.sample(VARIABLE_NAMES["methods"], 3)),
            "field_examples": ", ".join(random.sample(VARIABLE_NAMES["fields"], 3)),
            "type_examples": ", ".join(random.sample(VARIABLE_NAMES["entities"], 2)),
            "caller_examples": ", ".join([f"Handle{name}" for name in random.sample(VARIABLE_NAMES["entities"], 2)])
        }
    
    def get_scenario_description(self, scenario: str) -> str:
        """获取场景描述"""
        return SCENARIOS.get(scenario, "未知场景")
    
    def list_scenarios(self) -> List[str]:
        """列出所有支持的场景"""
        return list(SCENARIOS.keys()) 