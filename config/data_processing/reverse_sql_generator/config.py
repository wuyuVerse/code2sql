"""
反向SQL生成器配置管理
"""
import os
from pathlib import Path
from typing import Dict, List, Optional
from config.llm.llm_config import get_llm_config

# 场景定义和描述
REVERSE_SCENARIOS = {
    "if-else+caller": "Caller代码中包含if-else条件判断，根据不同的条件构建不同的filter参数传递给ORM方法",
    "if-else+orm": "ORM方法内部包含if-else条件判断，根据不同的分支使用不同的筛选条件构建SQL查询",
    "switch": "ORM方法使用switch条件语句来根据不同的参数值或状态构建不同的SQL查询条件",
    "dynamic_query": "处理动态传入的多个条件，生成多条条件结合的SQL查询",
    "fixed_params": "固定条件查询，不需要条件判断，直接生成对应的SQL查询",
    "complex_control": "复杂控制流，包含多层嵌套的if-else或switch结构"
}

# 复杂度配置
COMPLEXITY_LEVELS = {
    "simple": {
        "description": "简单查询，基本SELECT、WHERE、ORDER BY",
        "sql_features": ["SELECT", "FROM", "WHERE", "ORDER BY"],
        "min_conditions": 1,
        "max_conditions": 3,
        "control_flow": "none"
    },
    "medium": {
        "description": "中等复杂度，包含JOIN、GROUP BY、HAVING等",
        "sql_features": ["SELECT", "FROM", "WHERE", "JOIN", "GROUP BY", "HAVING", "ORDER BY"],
        "min_conditions": 2,
        "max_conditions": 5,
        "control_flow": "simple"
    },
    "complex": {
        "description": "复杂查询，包含子查询、窗口函数、复杂条件组合",
        "sql_features": ["SELECT", "FROM", "WHERE", "JOIN", "GROUP BY", "HAVING", "ORDER BY", "SUBQUERY", "WINDOW"],
        "min_conditions": 3,
        "max_conditions": 8,
        "control_flow": "complex"
    }
}

# 变量名词库
VARIABLE_NAMES = {
    "tables": [
        # 电商领域
        "product_catalog", "order_history", "payment_records", "inventory_items", "shopping_carts",
        "customer_reviews", "seller_profiles", "shipping_addresses", "discount_coupons", "return_requests",
        
        # 金融领域
        "account_balances", "transaction_logs", "loan_applications", "credit_scores", "investment_portfolios",
        "insurance_policies", "risk_assessments", "compliance_records", "fraud_alerts", "market_data",
        
        # 社交媒体
        "user_profiles", "social_posts", "friend_connections", "message_threads", "media_uploads",
        "comment_history", "like_records", "share_activities", "group_memberships", "event_invitations",
        
        # 内容管理
        "article_content", "blog_posts", "media_library", "content_versions", "editorial_calendar",
        "author_profiles", "publication_schedule", "content_categories", "tag_assignments", "reader_analytics",
        
        # 物流配送
        "delivery_routes", "package_tracking", "driver_schedules", "vehicle_fleet", "warehouse_locations",
        "shipping_manifest", "delivery_confirmations", "route_optimization", "fuel_consumption", "maintenance_logs",
        
        # 教育培训
        "student_enrollment", "course_catalog", "grade_records", "assignment_submissions", "exam_results",
        "teacher_profiles", "class_schedules", "curriculum_standards", "learning_materials", "progress_tracking",
        
        # 医疗健康
        "patient_records", "medical_history", "prescription_data", "appointment_schedules", "diagnostic_results",
        "treatment_plans", "doctor_profiles", "hospital_departments", "insurance_claims", "medication_inventory",
        
        # 企业管理
        "employee_records", "department_structure", "project_assignments", "performance_reviews", "payroll_data",
        "expense_reports", "meeting_schedules", "resource_allocation", "budget_planning", "vendor_management",
        
        # 游戏娱乐
        "player_profiles", "game_statistics", "achievement_records", "leaderboards", "virtual_items",
        "game_sessions", "tournament_brackets", "guild_memberships", "chat_messages", "match_history"
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
        "Dispatch", "Cargo", "Fleet", "Hub", "Transit", "Logistics", "Transport", "Freight", "Consignment", "Carrier",
        
        # 教育实体
        "Student", "Course", "Grade", "Assignment", "Exam", "Teacher", "Class", "Curriculum", "Material", "Progress",
        "Enrollment", "Schedule", "Standard", "Assessment", "Certificate", "Module", "Skill", "Attendance", "Communication", "Parent",
        
        # 医疗实体
        "Patient", "Medical", "Prescription", "Appointment", "Diagnostic", "Treatment", "Doctor", "Hospital", "Insurance", "Medication",
        "Record", "History", "Plan", "Department", "Claim", "Lab", "Surgery", "Emergency", "Contact", "Vaccination",
        
        # 企业实体
        "Employee", "Department", "Project", "Performance", "Payroll", "Expense", "Meeting", "Resource", "Budget", "Vendor",
        "Record", "Structure", "Assignment", "Review", "Data", "Report", "Schedule", "Allocation", "Planning", "Management",
        
        # 游戏实体
        "Player", "Game", "Achievement", "Leaderboard", "Virtual", "Session", "Tournament", "Guild", "Chat", "Match",
        "Profile", "Statistics", "Record", "Ranking", "Item", "Game", "Bracket", "Membership", "Message", "History"
    ],
    
    "methods": [
        # 查询方法
        "FindByID", "FindByName", "FindByStatus", "FindByDate", "FindByType", "FindByCategory", "FindByUser", "FindByGroup",
        "SearchByKeyword", "SearchByFilter", "SearchByCondition", "SearchByRange", "SearchByPattern", "SearchByText",
        "QueryByParams", "QueryByFilter", "QueryByCondition", "QueryByRange", "QueryByType", "QueryByStatus",
        "GetByID", "GetByName", "GetByStatus", "GetByDate", "GetByType", "GetByCategory", "GetByUser", "GetByGroup",
        "FetchByID", "FetchByName", "FetchByStatus", "FetchByDate", "FetchByType", "FetchByCategory", "FetchByUser",
        "RetrieveByID", "RetrieveByName", "RetrieveByStatus", "RetrieveByDate", "RetrieveByType", "RetrieveByCategory",
        
        # 更新方法
        "UpdateByID", "UpdateByName", "UpdateByStatus", "UpdateByDate", "UpdateByType", "UpdateByCategory",
        "ModifyByID", "ModifyByName", "ModifyByStatus", "ModifyByDate", "ModifyByType", "ModifyByCategory",
        "ChangeByID", "ChangeByName", "ChangeByStatus", "ChangeByDate", "ChangeByType", "ChangeByCategory",
        "EditByID", "EditByName", "EditByStatus", "EditByDate", "EditByType", "EditByCategory",
        
        # 删除方法
        "DeleteByID", "DeleteByName", "DeleteByStatus", "DeleteByDate", "DeleteByType", "DeleteByCategory",
        "RemoveByID", "RemoveByName", "RemoveByStatus", "RemoveByDate", "RemoveByType", "RemoveByCategory",
        "DropByID", "DropByName", "DropByStatus", "DropByDate", "DropByType", "DropByCategory",
        
        # 统计方法
        "CountByID", "CountByName", "CountByStatus", "CountByDate", "CountByType", "CountByCategory",
        "SumByID", "SumByName", "SumByStatus", "SumByDate", "SumByType", "SumByCategory",
        "AverageByID", "AverageByName", "AverageByStatus", "AverageByDate", "AverageByType", "AverageByCategory",
        
        # 批量方法
        "BatchUpdate", "BatchDelete", "BatchInsert", "BatchModify", "BatchChange", "BatchEdit",
        "BulkUpdate", "BulkDelete", "BulkInsert", "BulkModify", "BulkChange", "BulkEdit",
        "MassUpdate", "MassDelete", "MassInsert", "MassModify", "MassChange", "MassEdit"
    ],
    
    "fields": [
        # 通用字段
        "id", "name", "title", "description", "content", "status", "type", "category", "created_at", "updated_at",
        "user_id", "owner_id", "creator_id", "modifier_id", "parent_id", "root_id", "group_id", "team_id",
        "code", "key", "value", "data", "info", "detail", "remark", "note", "comment", "message",
        "email", "phone", "address", "location", "position", "coordinate", "latitude", "longitude",
        "price", "amount", "cost", "fee", "rate", "percentage", "score", "rating", "level", "grade",
        "count", "number", "quantity", "size", "length", "width", "height", "weight", "volume", "area",
        "date", "time", "datetime", "timestamp", "period", "duration", "interval", "frequency",
        "color", "style", "format", "version", "language", "locale", "timezone", "currency",
        "url", "link", "path", "file", "image", "icon", "logo", "banner", "avatar", "photo",
        "tag", "label", "mark", "flag", "sign", "symbol", "indicator", "signal", "alert", "warning"
    ]
}


class ReverseSQLConfig:
    """反向SQL生成器配置"""
    
    def __init__(self, 
                 llm_server: str = None,
                 output_path: str = "reverse_sql_cases.json",
                 max_workers: int = 4,
                 temperature: float = 0.7,
                 top_p: float = 0.8,
                 max_tokens: int = 4096):
        """初始化配置
        
        Args:
            llm_server: LLM服务器
            output_path: 输出路径
            max_workers: 最大worker数
            temperature: 温度参数
            top_p: top-p参数
            max_tokens: 最大token数
        """
        self.llm_server = llm_server or "v3"
        self.output_path = output_path
        self.max_workers = max_workers
        self.temperature = temperature
        self.top_p = top_p
        self.max_tokens = max_tokens
        
        # 从工作流配置获取max_tokens
        try:
            from config.data_processing.workflow.workflow_config import get_workflow_config
            workflow_config = get_workflow_config()
            self.max_tokens = workflow_config.get_max_tokens("reverse_sql_generator")
        except:
            pass
    
    def get_random_names(self) -> Dict[str, str]:
        """获取随机变量名"""
        import random
        
        return {
            "table_examples": random.choice(VARIABLE_NAMES["tables"]),
            "entity_examples": random.choice(VARIABLE_NAMES["entities"]),
            "method_examples": random.choice(VARIABLE_NAMES["methods"]),
            "field_examples": random.choice(VARIABLE_NAMES["fields"])
        }
    
    def get_scenario_description(self, scenario: str) -> str:
        """获取场景描述"""
        return REVERSE_SCENARIOS.get(scenario, "未知场景")
    
    def list_scenarios(self) -> List[str]:
        """列出所有支持的场景"""
        return list(REVERSE_SCENARIOS.keys())
    
    def get_complexity_config(self, complexity: str) -> Dict:
        """获取复杂度配置"""
        return COMPLEXITY_LEVELS.get(complexity, COMPLEXITY_LEVELS["simple"])
    
    def list_complexities(self) -> List[str]:
        """列出所有复杂度级别"""
        return list(COMPLEXITY_LEVELS.keys()) 