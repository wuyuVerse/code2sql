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
    "table_mapping_incomplete": "ORM方法中模型将结构体名错误理解为表名，而真实表名通过常量定义。需要明确区分结构体名和真实表名，避免模型错误地将结构体名当作表名使用。必须使用const定义表名常量，并在ORM方法中使用.Table(TableName)明确指定表名，确保code_meta_data中包含表名常量定义。",
    "condition_field_mapping": "ORM方法中的条件判断逻辑与实际添加到SQL where条件中的字段名不同，存在字段映射或转换关系。例如：判断region字段但实际添加cluster_id条件，判断category字段但实际添加type_id条件等",
    "where_condition_with_fixed_values": "ORM方法在where条件中直接指定了具体的值，而不是通过参数传递。这些值在代码中是固定的，通常用于过滤有效数据、排除特定值等。例如：status=0（有效状态）, income_industry_id<>0（非空行业ID）, deleted_at IS NULL（未删除记录）等",
    "where_condition_mixed": "ORM方法在where条件中同时包含固定值和动态条件。固定值直接在代码中指定（如status=0, deleted_at IS NULL），同时包含if-else等动态条件判断。固定条件用于基础过滤，动态条件根据传入参数进行灵活查询",
    "mutual_exclusive_conditions": "ORM方法接收包含互斥条件的filter参数，使用if-else逻辑处理不同的条件组合。每个条件对应不同的SQL查询策略，条件之间互斥（不会同时出现）。Caller层面使用if-else if-else if-else结构检查不同的参数，ORM层面使用if-else逻辑处理不同的条件组合，确保每次只有一个条件生效。",
    "table_name_from_caller": "ORM方法的表名信息从caller中传递过来，而不是在ORM方法内部硬编码。Caller负责确定具体的固定表名，ORM方法接收表名作为参数或通过其他方式获取。Caller中的表名应该是确定的、固定的表名，而不是动态生成的占位符。这种模式适用于需要动态切换表名的场景，如多租户系统、分表查询等。必须确保callers不为空，因为表名信息依赖于caller的上下文。",
    "raw_sql_in_code": "ORM方法中直接包含原始SQL语句，使用db.Raw()方法执行自定义SQL查询。通常用于复杂的多表关联查询、聚合查询或需要特殊优化的场景。SQL语句在代码中硬编码，通过Scan()方法将结果映射到结构体。这种模式适用于GORM无法直接表达的复杂查询逻辑。",
    "with_first": "基于其他场景生成的ORM方法，在数据库查询语句中添加First()方法，自动生成LIMIT 1的SQL。如果无法添加First()方法（如聚合查询、批量操作等），则返回no并丢弃该数据。",
    "with_take": "基于其他场景生成的ORM方法，在数据库查询语句中添加Take()方法，自动生成LIMIT 1的SQL。如果无法添加Take()方法（如聚合查询、批量操作等），则返回no并丢弃该数据。",
    "with_last": "基于其他场景生成的ORM方法，在数据库查询语句中添加Last()方法，自动生成LIMIT 1和ORDER BY主键DESC的SQL。如果无法添加Last()方法（如聚合查询、批量操作等），则返回no并丢弃该数据。",
    "with_find_no_limit": "基于其他场景生成的ORM方法，确保使用Find()方法而不添加任何LIMIT限制，返回多条记录的完整结果集。如果原始查询已经包含First()、Take()、Last()等限制方法，则将其替换为Find()方法。适用于需要获取全部匹配记录的查询场景。",
    "with_count": "基于其他场景生成的ORM方法，使用Count()方法生成SELECT COUNT(*)查询，用于统计满足条件的记录数量。将原始的查询操作（Find、First、Take、Last等）转换为Count()操作，返回int64类型的计数结果。适用于数据统计和分析场景。",
}

# 变量名词库 - 确保生成不同的变量名
VARIABLE_NAMES = {
    "tables": [
        # 电商领域
        "product_catalog", "order_history", "payment_records", "inventory_items", "shopping_carts",
        "customer_reviews", "seller_profiles", "shipping_addresses", "discount_coupons", "return_requests",
        "product_categories", "brand_info", "warehouse_stock", "price_history", "vendor_contracts",
        "product_variants", "sku_mapping", "inventory_alerts", "stock_movements", "supplier_orders",
        "product_attributes", "category_hierarchy", "brand_collections", "price_promotions", "flash_sales",
        "wishlist_items", "product_recommendations", "view_history", "search_logs", "browsing_patterns",
        
        # 金融领域
        "account_balances", "transaction_logs", "loan_applications", "credit_scores", "investment_portfolios",
        "insurance_policies", "risk_assessments", "compliance_records", "fraud_alerts", "market_data",
        "currency_rates", "trading_orders", "fund_transfers", "account_statements", "tax_documents",
        "derivative_contracts", "futures_trading", "options_pricing", "bond_yields", "equity_positions",
        "margin_accounts", "collateral_pledges", "interest_calculations", "amortization_schedules", "payment_schedules",
        "credit_limits", "overdraft_protection", "foreign_exchange", "settlement_instructions", "custody_accounts",
        
        # 社交媒体
        "user_profiles", "social_posts", "friend_connections", "message_threads", "media_uploads",
        "comment_history", "like_records", "share_activities", "group_memberships", "event_invitations",
        "notification_queue", "privacy_settings", "content_reports", "trending_topics", "hashtag_usage",
        "story_archives", "live_streams", "poll_responses", "voting_records", "challenge_participations",
        "badge_achievements", "level_progress", "virtual_gifts", "subscription_tiers", "premium_features",
        "content_moderation", "spam_detection", "bot_identification", "engagement_metrics", "viral_content",
        
        # 内容管理
        "article_content", "blog_posts", "media_library", "content_versions", "editorial_calendar",
        "author_profiles", "publication_schedule", "content_categories", "tag_assignments", "reader_analytics",
        "comment_moderation", "subscription_tiers", "content_licenses", "seo_metadata", "content_archive",
        "draft_revisions", "approval_workflows", "content_syndication", "rss_feeds", "newsletter_templates",
        "multimedia_assets", "translation_memory", "content_localization", "access_controls", "usage_statistics",
        "content_curation", "featured_content", "trending_articles", "related_content", "content_recommendations",
        
        # 物流配送
        "delivery_routes", "package_tracking", "driver_schedules", "vehicle_fleet", "warehouse_locations",
        "shipping_manifest", "delivery_confirmations", "route_optimization", "fuel_consumption", "maintenance_logs",
        "cargo_manifests", "dispatch_orders", "logistics_hubs", "transit_times", "delivery_zones",
        "last_mile_delivery", "pickup_schedules", "return_processing", "damage_reports", "insurance_claims",
        "customs_clearance", "import_permits", "export_documentation", "freight_forwarding", "container_tracking",
        "temperature_monitoring", "hazardous_materials", "perishable_goods", "oversized_cargo", "express_services",
        
        # 教育培训
        "student_enrollment", "course_catalog", "grade_records", "assignment_submissions", "exam_results",
        "teacher_profiles", "class_schedules", "curriculum_standards", "learning_materials", "progress_tracking",
        "certification_records", "training_modules", "skill_assessments", "attendance_logs", "parent_communications",
        "online_lectures", "virtual_labs", "peer_reviews", "group_projects", "discussion_forums",
        "learning_analytics", "adaptive_content", "gamification_elements", "achievement_badges", "competency_frameworks",
        "academic_calendar", "semester_schedules", "graduation_requirements", "transfer_credits", "academic_advising",
        
        # 医疗健康
        "patient_records", "medical_history", "prescription_data", "appointment_schedules", "diagnostic_results",
        "treatment_plans", "doctor_profiles", "hospital_departments", "insurance_claims", "medication_inventory",
        "lab_test_results", "surgery_schedules", "emergency_contacts", "health_metrics", "vaccination_records",
        "vital_signs", "allergy_information", "family_history", "immunization_records", "screening_results",
        "telemedicine_sessions", "remote_monitoring", "health_goals", "wellness_programs", "preventive_care",
        "clinical_trials", "research_protocols", "drug_interactions", "side_effects", "dosage_calculations",
        
        # 企业管理
        "employee_records", "department_structure", "project_assignments", "performance_reviews", "payroll_data",
        "expense_reports", "meeting_schedules", "resource_allocation", "budget_planning", "vendor_management",
        "contract_agreements", "asset_inventory", "security_clearances", "training_certifications", "compliance_audits",
        "time_tracking", "leave_management", "benefits_enrollment", "retirement_plans", "stock_options",
        "corporate_governance", "board_meetings", "shareholder_communications", "regulatory_filings", "risk_management",
        "business_intelligence", "market_research", "competitive_analysis", "strategic_planning", "merger_acquisitions",
        
        # 游戏娱乐
        "player_profiles", "game_statistics", "achievement_records", "leaderboards", "virtual_items",
        "game_sessions", "tournament_brackets", "guild_memberships", "chat_messages", "match_history",
        "character_inventory", "skill_trees", "quest_progress", "reward_systems", "player_rankings",
        "battle_logs", "clan_wars", "seasonal_events", "limited_editions", "cosmetic_items",
        "game_economy", "virtual_currency", "marketplace_listings", "trading_history", "auction_records",
        "esports_tournaments", "streaming_sessions", "content_creation", "mod_workshop", "community_events",
        
        # 房地产
        "property_listings", "real_estate_agents", "mortgage_applications", "property_valuations", "rental_agreements",
        "maintenance_requests", "tenant_profiles", "lease_contracts", "property_inspections", "closing_documents",
        "commission_splits", "market_analysis", "comparable_sales", "property_taxes", "insurance_policies",
        "home_improvements", "energy_efficiency", "zoning_regulations", "building_permits", "construction_projects",
        
        # 旅游酒店
        "hotel_bookings", "flight_reservations", "car_rentals", "tour_packages", "travel_itineraries",
        "customer_preferences", "loyalty_programs", "reward_points", "special_offers", "cancellation_policies",
        "room_inventory", "flight_schedules", "seat_assignments", "baggage_tracking", "boarding_passes",
        "travel_insurance", "visa_applications", "passport_services", "currency_exchange", "travel_advisories",
        
        # 餐饮服务
        "menu_items", "order_management", "table_reservations", "delivery_zones", "kitchen_inventory",
        "ingredient_suppliers", "recipe_database", "nutritional_info", "allergen_warnings", "preparation_times",
        "customer_feedback", "loyalty_cards", "promotional_campaigns", "seasonal_menus", "wine_pairings",
        "staff_schedules", "training_programs", "health_inspections", "food_safety", "cost_analysis",
        
        # 汽车服务
        "vehicle_registrations", "service_appointments", "maintenance_records", "parts_inventory", "warranty_claims",
        "insurance_policies", "financing_options", "trade_in_values", "test_drive_schedules", "dealer_locations",
        "recall_notifications", "emissions_testing", "safety_inspections", "roadside_assistance", "fleet_management",
        "fuel_efficiency", "mileage_tracking", "driver_profiles", "route_optimization", "vehicle_telematics",
        
        # 农业科技
        "crop_monitoring", "soil_analysis", "weather_data", "irrigation_systems", "pest_management",
        "harvest_schedules", "storage_conditions", "quality_control", "traceability_systems", "organic_certification",
        "livestock_tracking", "feed_inventory", "vaccination_records", "breeding_programs", "market_prices",
        "equipment_maintenance", "fuel_consumption", "labor_scheduling", "financial_planning", "risk_management",
        
        # 能源管理
        "power_generation", "consumption_monitoring", "billing_statements", "meter_readings", "grid_operations",
        "renewable_sources", "energy_storage", "demand_response", "peak_load_management", "efficiency_programs",
        "carbon_footprint", "emissions_tracking", "compliance_reports", "maintenance_schedules", "outage_management",
        "customer_service", "payment_processing", "rate_structures", "incentive_programs", "energy_audits",
        
        # 政府服务
        "citizen_records", "license_applications", "permit_requests", "tax_assessments", "voting_registration",
        "public_safety", "emergency_response", "code_enforcement", "zoning_applications", "budget_allocations",
        "contract_bidding", "procurement_process", "audit_reports", "compliance_monitoring", "public_records",
        "service_requests", "complaint_tracking", "performance_metrics", "transparency_reports", "citizen_feedback",
        
        # 区块链/加密货币
        "blockchain_transactions", "crypto_wallets", "smart_contracts", "token_transfers", "mining_operations",
        "decentralized_apps", "nft_collections", "defi_protocols", "liquidity_pools", "yield_farming",
        "governance_tokens", "staking_rewards", "validator_nodes", "consensus_mechanisms", "block_explorers",
        "crypto_exchanges", "trading_pairs", "order_books", "market_makers", "arbitrage_opportunities",
        "cross_chain_bridges", "layer2_solutions", "oracle_networks", "prediction_markets", "decentralized_identity",
        
        # 物联网
        "sensor_data", "device_registry", "iot_gateways", "edge_computing", "device_telemetry",
        "firmware_updates", "device_provisioning", "connectivity_management", "data_streams", "alert_systems",
        "smart_home_devices", "industrial_sensors", "wearable_technology", "connected_vehicles", "smart_cities",
        "environmental_monitoring", "asset_tracking", "predictive_maintenance", "remote_control", "automation_rules",
        
        # 人工智能/机器学习
        "model_registry", "training_datasets", "inference_requests", "model_versions", "feature_stores",
        "experiment_tracking", "hyperparameter_tuning", "model_evaluation", "data_pipelines", "ml_workflows",
        "neural_networks", "deep_learning_models", "computer_vision", "natural_language_processing", "recommendation_engines",
        "anomaly_detection", "predictive_analytics", "automated_ml", "model_monitoring", "ai_ethics",
        
        # 网络安全
        "threat_intelligence", "vulnerability_scans", "security_incidents", "firewall_rules", "intrusion_detection",
        "malware_analysis", "penetration_testing", "security_audits", "compliance_checks", "risk_assessments",
        "identity_management", "access_controls", "encryption_keys", "certificate_management", "security_policies",
        "incident_response", "forensic_analysis", "threat_hunting", "security_training", "phishing_detection",
        
        # 环保/可持续发展
        "carbon_footprint", "renewable_energy", "waste_management", "recycling_programs", "sustainability_metrics",
        "green_building", "energy_efficiency", "water_conservation", "biodiversity_monitoring", "climate_data",
        "environmental_impact", "sustainable_supply_chain", "circular_economy", "green_certifications", "eco_friendly_products",
        "carbon_credits", "emissions_tracking", "sustainability_reports", "environmental_compliance", "green_technology",
        
        # 娱乐/媒体
        "streaming_content", "video_on_demand", "live_broadcasts", "content_catalog", "subscription_services",
        "advertising_campaigns", "viewer_analytics", "content_ratings", "parental_controls", "recommendation_algorithms",
        "music_library", "playlist_curation", "podcast_episodes", "gaming_content", "esports_tournaments",
        "virtual_reality", "augmented_reality", "interactive_content", "user_generated_content", "social_media_integration",
        
        # 法律/合规
        "legal_documents", "contract_management", "compliance_reports", "regulatory_updates", "risk_assessments",
        "audit_trails", "evidence_management", "case_tracking", "legal_research", "document_review",
        "intellectual_property", "patent_management", "trademark_registration", "copyright_protection", "licensing_agreements",
        "data_privacy", "gdpr_compliance", "data_protection", "privacy_policies", "consent_management",
        
        # 科研/学术
        "research_projects", "experiment_data", "scientific_papers", "peer_reviews", "citation_analysis",
        "laboratory_equipment", "sample_collection", "data_analysis", "statistical_models", "research_funding",
        "academic_conferences", "collaboration_networks", "publication_metrics", "research_ethics", "open_access",
        "clinical_trials", "research_protocols", "scientific_datasets", "reproducibility_studies", "meta_analysis"
    ],
    
    "entities": [
        # 电商实体
        "Product", "Order", "Customer", "Vendor", "Category", "Brand", "Inventory", "Coupon", "Review", "Cart",
        "Shipment", "Payment", "Refund", "Wishlist", "Recommendation", "Auction", "Marketplace", "Seller", "Buyer", "Deal",
        "SKU", "Variant", "Bundle", "Subscription", "Membership", "Loyalty", "Promotion", "FlashSale", "Bundle", "GiftCard",
        "Warranty", "Return", "Exchange", "Complaint", "Feedback", "Rating", "Comment", "Question", "Answer", "Support",
        
        # 金融实体
        "Account", "Transaction", "Portfolio", "Investment", "Loan", "Credit", "Insurance", "Policy", "Claim", "Fund",
        "Bond", "Stock", "Currency", "Exchange", "Wallet", "Statement", "Report", "Budget", "Forecast", "Risk",
        "Derivative", "Future", "Option", "Swap", "Hedge", "Margin", "Collateral", "Interest", "Principal", "Amortization",
        "Settlement", "Clearing", "Custody", "Trust", "Estate", "Annuity", "Pension", "401k", "IRA", "Roth",
        
        # 社交实体
        "Profile", "Post", "Comment", "Message", "Friend", "Group", "Event", "Photo", "Video", "Story",
        "Notification", "Like", "Share", "Follow", "Block", "Report", "Stream", "Feed", "Timeline", "Tag",
        "Hashtag", "Mention", "Reaction", "Emoji", "Gif", "Meme", "Poll", "Quiz", "Challenge", "Trend",
        "Influencer", "Creator", "Moderator", "Admin", "Bot", "Spam", "Viral", "Engagement", "Reach", "Impressions",
        
        # 内容实体
        "Article", "Blog", "Media", "Author", "Editor", "Publication", "Newsletter", "Magazine", "Book", "Chapter",
        "Section", "Paragraph", "Image", "Audio", "Video", "Document", "Template", "Layout", "Theme", "Widget",
        "Podcast", "Webinar", "Tutorial", "Guide", "Manual", "FAQ", "Wiki", "Forum", "Commentary", "Review",
        "Interview", "PressRelease", "Whitepaper", "CaseStudy", "Infographic", "Slideshow", "Gallery", "Playlist", "Channel", "Series",
        
        # 物流实体
        "Package", "Delivery", "Route", "Driver", "Vehicle", "Warehouse", "Shipment", "Manifest", "Tracking", "Zone",
        "Hub", "Carrier", "Express", "Freight", "Container", "Pallet", "Label", "Scanner", "GPS", "Schedule",
        "Dispatch", "Pickup", "Dropoff", "Transit", "Customs", "Border", "Port", "Terminal", "Dock", "Berth",
        "Cargo", "Luggage", "Parcel", "Envelope", "Box", "Crate", "Barrel", "Tank", "Trailer", "Truck",
        
        # 教育实体
        "Student", "Teacher", "Course", "Lesson", "Assignment", "Grade", "Exam", "Quiz", "Certificate", "Diploma",
        "Curriculum", "Textbook", "Classroom", "Schedule", "Semester", "Module", "Skill", "Achievement", "Progress", "Assessment",
        "Tutor", "Mentor", "Advisor", "Counselor", "Dean", "Principal", "Professor", "Instructor", "Lecturer", "TA",
        "Alumni", "Graduate", "Undergraduate", "Freshman", "Sophomore", "Junior", "Senior", "Transfer", "Exchange", "International",
        
        # 医疗实体
        "Patient", "Doctor", "Nurse", "Appointment", "Diagnosis", "Treatment", "Prescription", "Medicine", "Hospital", "Clinic",
        "Surgery", "Lab", "Test", "Result", "Symptom", "Disease", "Allergy", "Vaccine", "Insurance", "Claim",
        "Specialist", "Surgeon", "Therapist", "Pharmacist", "Technician", "Radiologist", "Pathologist", "Anesthesiologist", "Cardiologist", "Oncologist",
        "Emergency", "Urgent", "Routine", "Followup", "Screening", "Preventive", "Rehabilitation", "Palliative", "Hospice", "Morgue",
        
        # 企业实体
        "Employee", "Manager", "Department", "Project", "Task", "Meeting", "Resource", "Budget", "Contract", "Vendor",
        "Client", "Proposal", "Invoice", "Expense", "Asset", "Equipment", "Office", "Team", "Role", "Permission",
        "Executive", "Director", "Supervisor", "Coordinator", "Assistant", "Intern", "Consultant", "Contractor", "Freelancer", "Partner",
        "Shareholder", "Investor", "Board", "Committee", "Division", "Branch", "Subsidiary", "Affiliate", "JointVenture", "Merger",
        
        # 游戏实体
        "Player", "Character", "Game", "Level", "Quest", "Achievement", "Item", "Weapon", "Armor", "Spell",
        "Guild", "Tournament", "Match", "Score", "Ranking", "Reward", "Experience", "Skill", "Inventory", "Trade",
        "Avatar", "Pet", "Mount", "Companion", "Familiar", "Summon", "Minion", "Boss", "NPC", "Mob",
        "Clan", "Alliance", "Faction", "Guild", "Corporation", "Squad", "Team", "Party", "Raid", "Dungeon",
        
        # 房地产实体
        "Property", "Listing", "Agent", "Broker", "Owner", "Tenant", "Landlord", "Mortgage", "Deed", "Title",
        "Appraisal", "Inspection", "Contract", "Lease", "Rent", "Deposit", "Commission", "Closing", "Escrow", "Title",
        "Building", "Apartment", "House", "Condo", "Townhouse", "Duplex", "Studio", "Penthouse", "Loft", "Villa",
        "Neighborhood", "Community", "Development", "Subdivision", "Complex", "Tower", "Plaza", "Mall", "Office", "Retail",
        
        # 旅游酒店实体
        "Hotel", "Reservation", "Guest", "Room", "Suite", "Amenity", "Service", "Concierge", "Bellhop", "Housekeeper",
        "Flight", "Passenger", "Seat", "Cabin", "Crew", "Pilot", "Steward", "Airline", "Airport", "Terminal",
        "Destination", "Tour", "Guide", "Itinerary", "Booking", "Ticket", "Passport", "Visa", "Customs", "Immigration",
        "Cruise", "Ship", "Cabin", "Deck", "Port", "Shore", "Excursion", "Excursion", "Excursion", "Excursion",
        
        # 餐饮服务实体
        "Restaurant", "Menu", "Dish", "Ingredient", "Recipe", "Chef", "Server", "Host", "Bartender", "Sommelier",
        "Table", "Reservation", "Order", "Bill", "Tip", "Gratuity", "Discount", "Promotion", "HappyHour", "Special",
        "Kitchen", "Prep", "Line", "Expo", "Expediter", "Runner", "Busser", "Manager", "Owner", "Franchise",
        "Catering", "Event", "Party", "Wedding", "Corporate", "Private", "Buffet", "A_la_carte", "Tasting", "Pairing",
        
        # 汽车服务实体
        "Vehicle", "Car", "Truck", "SUV", "Sedan", "Coupe", "Convertible", "Hatchback", "Wagon", "Van",
        "Dealer", "Salesperson", "Mechanic", "Technician", "Service", "Repair", "Maintenance", "Warranty", "Insurance", "Financing",
        "Registration", "Title", "License", "Plate", "VIN", "Make", "Model", "Year", "Color", "Mileage",
        "Engine", "Transmission", "Brake", "Tire", "Battery", "Filter", "Oil", "Coolant", "Fuel", "Exhaust",
        
        # 农业科技实体
        "Farm", "Crop", "Field", "Plot", "Greenhouse", "Irrigation", "Fertilizer", "Pesticide", "Harvest", "Storage",
        "Livestock", "Cattle", "Pig", "Chicken", "Sheep", "Goat", "Horse", "Dairy", "Beef", "Pork",
        "Equipment", "Tractor", "Harvester", "Planter", "Sprayer", "Irrigator", "Sensor", "Drone", "Satellite", "Weather",
        "Soil", "Nutrient", "pH", "Moisture", "Temperature", "Humidity", "Rainfall", "Wind", "Sunlight", "Climate",
        
        # 能源管理实体
        "Power", "Generator", "Turbine", "Solar", "Wind", "Hydro", "Nuclear", "Coal", "Gas", "Oil",
        "Grid", "Transformer", "Substation", "Line", "Cable", "Meter", "SmartMeter", "Battery", "Storage", "Inverter",
        "Utility", "Provider", "Supplier", "Distributor", "Retailer", "Wholesaler", "Consumer", "Commercial", "Industrial", "Residential",
        "Rate", "Tariff", "Plan", "Tier", "Peak", "OffPeak", "Demand", "Supply", "Load", "Capacity",
        
        # 政府服务实体
        "Citizen", "Resident", "Voter", "Taxpayer", "Licensee", "Permit", "Application", "Registration", "Certificate", "Document",
        "Department", "Agency", "Bureau", "Office", "Division", "Section", "Unit", "Team", "Staff", "Official",
        "Law", "Regulation", "Policy", "Procedure", "Guideline", "Standard", "Requirement", "Compliance", "Enforcement", "Violation",
        "Service", "Program", "Initiative", "Project", "Campaign", "Outreach", "Education", "Awareness", "Prevention", "Response",
        
        # 区块链/加密货币实体
        "Blockchain", "Transaction", "Wallet", "SmartContract", "Token", "Coin", "NFT", "DeFi", "Mining", "Staking",
        "Validator", "Node", "Consensus", "Block", "Chain", "Hash", "Address", "PrivateKey", "PublicKey", "Signature",
        "Exchange", "Trading", "Liquidity", "Yield", "Governance", "Oracle", "Bridge", "Layer2", "Protocol", "DApp",
        
        # 物联网实体
        "Device", "Sensor", "Gateway", "Edge", "Telemetry", "Firmware", "Connectivity", "Stream", "Alert", "Automation",
        "SmartHome", "Industrial", "Wearable", "Vehicle", "SmartCity", "Environmental", "Asset", "Maintenance", "Control", "Rule",
        "IoT", "M2M", "Embedded", "Actuator", "Controller", "Hub", "Network", "Protocol", "API", "Cloud",
        
        # 人工智能/机器学习实体
        "Model", "Dataset", "Feature", "Algorithm", "NeuralNetwork", "DeepLearning", "ComputerVision", "NLP", "ML", "AI",
        "Training", "Inference", "Prediction", "Classification", "Regression", "Clustering", "Recommendation", "Anomaly", "Optimization", "Hyperparameter",
        "Tensor", "Gradient", "Loss", "Accuracy", "Precision", "Recall", "F1Score", "ROC", "AUC", "ConfusionMatrix",
        
        # 网络安全实体
        "Threat", "Vulnerability", "Incident", "Firewall", "Intrusion", "Malware", "Penetration", "Audit", "Risk", "Compliance",
        "Identity", "Access", "Encryption", "Certificate", "Policy", "Forensics", "Hunting", "Training", "Phishing", "SOC",
        "SIEM", "EDR", "XDR", "SOAR", "ZeroTrust", "MFA", "SSO", "VPN", "IDS", "IPS",
        
        # 环保/可持续发展实体
        "Sustainability", "Carbon", "Renewable", "Waste", "Recycling", "Green", "Energy", "Water", "Biodiversity", "Climate",
        "Environmental", "Impact", "SupplyChain", "Circular", "Certification", "EcoFriendly", "Credit", "Emission", "Report", "Technology",
        "Solar", "Wind", "Hydro", "Biomass", "Geothermal", "Tidal", "Wave", "Nuclear", "Fossil", "Clean",
        
        # 娱乐/媒体实体
        "Streaming", "Video", "Live", "Content", "Subscription", "Advertising", "Analytics", "Rating", "Control", "Recommendation",
        "Music", "Playlist", "Podcast", "Gaming", "Esports", "VR", "AR", "Interactive", "UserGenerated", "Social",
        "Entertainment", "Media", "Broadcast", "Channel", "Program", "Show", "Episode", "Season", "Series", "Movie",
        
        # 法律/合规实体
        "Legal", "Contract", "Compliance", "Regulatory", "Risk", "Audit", "Evidence", "Case", "Research", "Review",
        "IntellectualProperty", "Patent", "Trademark", "Copyright", "License", "Privacy", "GDPR", "Protection", "Policy", "Consent",
        "Lawyer", "Attorney", "Judge", "Court", "Jury", "Witness", "Plaintiff", "Defendant", "Prosecutor", "Defense",
        
        # 科研/学术实体
        "Research", "Experiment", "Paper", "Review", "Citation", "Laboratory", "Sample", "Analysis", "Model", "Funding",
        "Conference", "Collaboration", "Publication", "Ethics", "OpenAccess", "Trial", "Protocol", "Dataset", "Reproducibility", "Meta",
        "Scientist", "Researcher", "Professor", "Student", "Laboratory", "Institute", "University", "Journal", "Conference", "Workshop"
    ],
    
    "methods": [
        # 查询类方法
        "QueryByCondition", "FetchWithFilter", "SearchByKeyword", "GetByStatus", "ListWithPaging", "FindByCategory",
        "RetrieveByDate", "SelectByRange", "LoadByType", "ScanByPattern", "FilterByAttribute", "SortByField",
        "GroupByCategory", "CountByStatus", "AggregateByType", "CalculateByFormula", "ValidateByRules", "MatchByPattern",
        "LookupByKey", "FindByCriteria", "SearchByPattern", "FilterByExpression", "QueryByParameter", "SelectByCondition",
        "ExtractByFilter", "ParseByFormat", "ScanByCriteria", "BrowseByCategory", "NavigateByHierarchy", "ExploreByPath",
        
        # 业务逻辑方法
        "ProcessPayment", "ValidateOrder", "CalculateDiscount", "GenerateReport", "SendNotification", "UpdateInventory",
        "CreateInvoice", "ScheduleDelivery", "VerifyIdentity", "AssignTask", "ApproveRequest", "RejectApplication",
        "ArchiveData", "BackupRecords", "RestoreFromBackup", "MigrateData", "SyncWithExternal", "ImportFromFile",
        "ProcessRefund", "HandleComplaint", "ResolveIssue", "EscalateTicket", "CloseCase", "ReopenRequest",
        "CalculateTax", "ComputeInterest", "DetermineEligibility", "AssessRisk", "EvaluatePerformance", "MeasureSatisfaction",
        
        # CRUD操作方法
        "CreateRecord", "UpdateEntity", "DeleteItem", "InsertBatch", "BulkUpdate", "SoftDelete", "HardDelete",
        "UpsertData", "MergeRecords", "DuplicateEntry", "CloneObject", "CopyStructure", "MoveToArchive", "RestoreDeleted",
        "InitializeRecord", "ModifyEntity", "RemoveItem", "AddEntry", "ReplaceData", "TruncateTable", "DropRecord",
        "DuplicateRecord", "CopyEntity", "CloneStructure", "ReplicateData", "MirrorContent", "SynchronizeRecords",
        
        # 统计分析方法
        "AnalyzePerformance", "GenerateMetrics", "CalculateStatistics", "TrackBehavior", "MonitorActivity", "MeasureEfficiency",
        "EvaluateResults", "CompareData", "PredictTrends", "ForecastDemand", "OptimizeRoutes", "RecommendActions",
        "ComputeAverage", "CalculateMedian", "DetermineMode", "FindPercentile", "CalculateVariance", "ComputeStandardDeviation",
        "GenerateHistogram", "CreatePivotTable", "BuildDashboard", "ExportReport", "ScheduleAnalysis", "AutomateMetrics",
        
        # 安全验证方法
        "AuthenticateUser", "AuthorizeAccess", "ValidatePermissions", "EncryptData", "DecryptInfo", "HashPassword",
        "VerifySignature", "CheckIntegrity", "AuditChanges", "LogActivity", "DetectFraud", "PreventAttack",
        "ValidateToken", "CheckCredentials", "VerifyIdentity", "AuthenticateSession", "AuthorizeRequest", "ValidateSession",
        "EncryptMessage", "DecryptContent", "HashFile", "VerifyCertificate", "CheckCompliance", "AuditTrail",
        
        # 系统管理方法
        "ConfigureSettings", "ManageResources", "MonitorHealth", "OptimizePerformance", "ScaleCapacity", "LoadBalance",
        "CacheData", "ClearCache", "RefreshIndex", "RebuildIndex", "CleanupOldData", "PurgeExpiredRecords",
        "InitializeSystem", "SetupEnvironment", "ConfigureDatabase", "ManageConnections", "MonitorResources", "OptimizeQueries",
        "ScaleHorizontally", "ScaleVertically", "LoadBalanceTraffic", "DistributeLoad", "CacheResults", "InvalidateCache",
        
        # 数据处理方法
        "TransformData", "NormalizeValues", "StandardizeFormat", "ValidateInput", "SanitizeContent", "ParseString",
        "ConvertType", "FormatOutput", "EncodeData", "DecodeContent", "CompressFile", "DecompressArchive",
        "SerializeObject", "DeserializeData", "MarshalContent", "UnmarshalPayload", "SerializeToJSON", "ParseFromXML",
        
        # 通信网络方法
        "SendMessage", "ReceiveData", "BroadcastEvent", "SubscribeToTopic", "PublishContent", "NotifySubscribers",
        "EstablishConnection", "CloseSession", "MaintainConnection", "ReconnectClient", "HandleTimeout", "ProcessResponse",
        "RouteMessage", "ForwardPacket", "FilterTraffic", "MonitorBandwidth", "OptimizeLatency", "ReduceJitter",
        
        # 文件操作方法
        "ReadFile", "WriteContent", "AppendData", "TruncateFile", "CopyFile", "MoveFile", "DeleteFile", "RenameFile",
        "CreateDirectory", "RemoveFolder", "ListContents", "SearchFiles", "FilterResults", "SortEntries",
        "CompressArchive", "ExtractFiles", "ValidateIntegrity", "CheckChecksum", "VerifySignature", "ScanVirus",
        
        # 数据库操作方法
        "ExecuteQuery", "PrepareStatement", "BindParameters", "FetchResults", "CommitTransaction", "RollbackChanges",
        "BeginTransaction", "EndTransaction", "LockTable", "UnlockTable", "CreateIndex", "DropIndex",
        "OptimizeTable", "AnalyzeStructure", "RepairDatabase", "BackupData", "RestoreBackup", "MigrateSchema",
        
        # 缓存操作方法
        "SetCache", "GetCache", "DeleteCache", "ClearCache", "UpdateCache", "InvalidateCache", "RefreshCache",
        "WarmCache", "PreloadData", "CacheHit", "CacheMiss", "CacheExpiry", "CacheSize", "CachePolicy",
        "DistributedCache", "LocalCache", "RemoteCache", "MemoryCache", "DiskCache", "NetworkCache",
        
        # 队列处理方法
        "EnqueueMessage", "DequeueItem", "PeekQueue", "ClearQueue", "PurgeQueue", "GetQueueSize", "GetQueueStatus",
        "ProcessQueue", "HandleMessage", "RetryFailed", "DeadLetter", "MoveToQueue", "CopyToQueue",
        "PriorityQueue", "DelayQueue", "BatchQueue", "StreamQueue", "TopicQueue", "FanoutQueue",
        
        # 定时任务方法
        "ScheduleTask", "CancelTask", "RescheduleJob", "PauseTask", "ResumeTask", "GetTaskStatus", "ListScheduledJobs",
        "ExecuteCron", "RunPeriodic", "TriggerEvent", "HandleTimeout", "ProcessInterval", "ManageSchedule",
        "DailyTask", "WeeklyJob", "MonthlyProcess", "QuarterlyReport", "YearlyMaintenance", "AdhocExecution",
        
        # 日志记录方法
        "LogInfo", "LogWarning", "LogError", "LogDebug", "LogTrace", "LogFatal", "LogCritical", "LogNotice",
        "WriteLog", "ReadLog", "ClearLog", "ArchiveLog", "RotateLog", "CompressLog", "SearchLog", "FilterLog",
        "StructuredLog", "UnstructuredLog", "BinaryLog", "TextLog", "JSONLog", "XMLLog", "CSVLog", "Syslog",
        
        # 区块链/加密货币方法
        "MineBlock", "ValidateTransaction", "CreateWallet", "SignTransaction", "VerifySignature", "DeployContract",
        "ExecuteSmartContract", "TransferToken", "StakeTokens", "UnstakeTokens", "ClaimRewards", "VoteOnProposal",
        "CreateNFT", "MintToken", "BurnToken", "SwapTokens", "AddLiquidity", "RemoveLiquidity", "HarvestYield",
        "BridgeAssets", "CrossChainTransfer", "ValidateBlock", "ConsensusVote", "UpdateOracle", "ExecuteGovernance",
        
        # 物联网方法
        "CollectSensorData", "ProcessTelemetry", "UpdateFirmware", "ProvisionDevice", "ManageConnectivity",
        "MonitorDevice", "ControlActuator", "ProcessAlert", "ExecuteAutomation", "ManageEdgeComputing",
        "StreamData", "AnalyzeIoTData", "PredictMaintenance", "OptimizeEnergy", "TrackAsset", "RemoteControl",
        "ConfigureDevice", "AuthenticateDevice", "EncryptIoTData", "ValidateSensorReading",
        
        # 人工智能/机器学习方法
        "TrainModel", "EvaluateModel", "DeployModel", "InferencePrediction", "FeatureEngineering", "HyperparameterTuning",
        "CrossValidate", "EnsembleModels", "TransferLearning", "FineTuneModel", "OptimizeHyperparameters", "AblationStudy",
        "DataPreprocessing", "FeatureSelection", "DimensionalityReduction", "ModelInterpretation", "ExplainableAI",
        "ModelMonitoring", "DriftDetection", "RetrainModel", "ModelVersioning", "ExperimentTracking",
        
        # 网络安全方法
        "DetectThreat", "AnalyzeVulnerability", "RespondToIncident", "ConfigureFirewall", "MonitorIntrusion",
        "AnalyzeMalware", "ConductPenetrationTest", "PerformSecurityAudit", "AssessRisk", "EnforceCompliance",
        "ManageIdentity", "ControlAccess", "EncryptData", "ManageCertificates", "EnforcePolicy", "ConductForensics",
        "HuntThreats", "TrainSecurity", "DetectPhishing", "MonitorSOC", "AnalyzeSIEM", "RespondToEDR",
        
        # 环保/可持续发展方法
        "CalculateCarbonFootprint", "MonitorEmissions", "TrackSustainability", "ManageWaste", "OptimizeRecycling",
        "MonitorEnergyEfficiency", "ConserveWater", "TrackBiodiversity", "AnalyzeClimateData", "AssessEnvironmentalImpact",
        "OptimizeSupplyChain", "ImplementCircularEconomy", "CertifyGreen", "DevelopEcoFriendly", "TradeCarbonCredits",
        "TrackEmissions", "GenerateSustainabilityReport", "EnsureEnvironmentalCompliance", "DeployGreenTechnology",
        
        # 娱乐/媒体方法
        "StreamContent", "ProcessVideo", "BroadcastLive", "ManageSubscription", "TargetAdvertising", "AnalyzeViewer",
        "RateContent", "ControlParental", "RecommendContent", "CuratePlaylist", "ProducePodcast", "DevelopGame",
        "OrganizeEsports", "CreateVR", "DevelopAR", "GenerateInteractive", "ModerateUserContent", "IntegrateSocial",
        "ManageEntertainment", "ProcessMedia", "BroadcastChannel", "ProduceProgram", "CreateShow", "EditEpisode",
        
        # 法律/合规方法
        "DraftLegalDocument", "ManageContract", "EnsureCompliance", "UpdateRegulatory", "AssessRisk", "ConductAudit",
        "ManageEvidence", "TrackCase", "ConductResearch", "ReviewDocument", "ProtectIntellectualProperty", "ManagePatent",
        "RegisterTrademark", "ProtectCopyright", "ManageLicense", "EnsurePrivacy", "ComplyGDPR", "ProtectData",
        "EnforcePolicy", "ManageConsent", "RepresentClient", "ArgueCase", "PresideCourt", "DeliberateJury",
        
        # 科研/学术方法
        "ConductResearch", "DesignExperiment", "PublishPaper", "PeerReview", "AnalyzeCitation", "ManageLaboratory",
        "CollectSample", "AnalyzeData", "BuildModel", "SecureFunding", "OrganizeConference", "FacilitateCollaboration",
        "TrackPublication", "EnsureEthics", "PromoteOpenAccess", "ConductTrial", "FollowProtocol", "ManageDataset",
        "EnsureReproducibility", "PerformMetaAnalysis", "AdvanceScience", "MentorResearcher", "TeachStudent",
        "ManageInstitute", "PublishJournal", "OrganizeWorkshop"
    ],
    
    "fields": [
        # 通用标识字段
        "RecordId", "EntityId", "UniqueKey", "ReferenceCode", "SequenceNumber", "TrackingId", "SessionToken",
        "AuthToken", "RefreshKey", "ApiKey", "SecretHash", "PublicKey", "PrivateKey", "CertificateId", "LicenseKey",
        "GUID", "UUID", "HashCode", "Checksum", "Signature", "Fingerprint", "TokenId", "AccessCode", "SecurityKey", "EncryptionKey",
        "InstanceId", "ProcessId", "ThreadId", "ConnectionId", "RequestId", "CorrelationId", "TraceId", "SpanId", "TransactionId", "BatchId",
        
        # 时间相关字段
        "CreationTime", "ModificationDate", "ExpirationTime", "StartDate", "EndDate", "ScheduledTime", "DeadlineDate",
        "LastAccessTime", "FirstLoginDate", "RegistrationTime", "ActivationDate", "SuspensionTime", "ReactivationDate",
        "CreatedAt", "UpdatedAt", "DeletedAt", "PublishedAt", "ArchivedAt", "ExpiredAt", "RenewedAt", "CancelledAt",
        "Timestamp", "DateTime", "DateCreated", "DateModified", "DateExpired", "DateScheduled", "DateCompleted", "DateCancelled",
        "TimeCreated", "TimeModified", "TimeExpired", "TimeScheduled", "TimeCompleted", "TimeCancelled", "TimeZone", "LocalTime", "UTCTime",
        
        # 状态和类型字段
        "CurrentStatus", "ProcessingState", "ApprovalLevel", "PriorityRank", "CategoryType", "ClassificationLevel",
        "SecurityLevel", "AccessLevel", "PermissionType", "RoleCode", "DepartmentCode", "LocationCode", "RegionCode",
        "Status", "State", "Phase", "Stage", "Level", "Tier", "Grade", "Class", "Type", "Category",
        "ApprovalStatus", "ReviewStatus", "ValidationStatus", "VerificationStatus", "AuthenticationStatus", "AuthorizationStatus",
        "ProcessingStatus", "ExecutionStatus", "CompletionStatus", "ErrorStatus", "WarningStatus", "InfoStatus", "DebugStatus",
        
        # 数值和度量字段
        "TotalAmount", "UnitPrice", "DiscountRate", "TaxAmount", "NetValue", "GrossValue", "Quantity", "Weight",
        "Volume", "Dimension", "Percentage", "Ratio", "Score", "Rating", "Points", "Credits", "Balance", "Limit",
        "Amount", "Price", "Cost", "Value", "Rate", "Fee", "Charge", "Payment", "Refund", "Credit",
        "Count", "Number", "Index", "Position", "Rank", "Order", "Sequence", "Priority", "Weight", "Size",
        "Length", "Width", "Height", "Depth", "Area", "Perimeter", "Circumference", "Diameter", "Radius", "Volume",
        
        # 用户和客户字段
        "UserName", "DisplayName", "FullName", "FirstName", "LastName", "MiddleName", "NickName", "EmailAddress",
        "PhoneNumber", "MobileNumber", "ContactInfo", "HomeAddress", "WorkAddress", "MailingAddress", "BillingAddress",
        "LoginName", "AccountName", "ProfileName", "ScreenName", "Handle", "Alias", "Pseudonym", "PenName", "StageName", "BrandName",
        "Email", "Phone", "Mobile", "Fax", "Pager", "Extension", "DirectLine", "TollFree", "Emergency", "Hotline",
        "StreetAddress", "PostalAddress", "PhysicalAddress", "VirtualAddress", "IPAddress", "MACAddress", "URL", "Website", "Domain", "Subdomain",
        
        # 业务特定字段
        "ProductCode", "OrderNumber", "InvoiceNumber", "ContractNumber", "ProjectCode", "TaskId", "TicketNumber",
        "CaseNumber", "RequestId", "ApplicationId", "TransactionId", "PaymentId", "ShipmentId", "DeliveryCode",
        "SKU", "UPC", "ISBN", "ISSN", "EAN", "GTIN", "ASIN", "MPN", "VIN", "IMEI",
        "SerialNumber", "BatchNumber", "LotNumber", "PartNumber", "ModelNumber", "VersionNumber", "BuildNumber", "RevisionNumber", "PatchNumber", "ReleaseNumber",
        "AccountNumber", "CardNumber", "RoutingNumber", "SWIFT", "IBAN", "BIC", "SortCode", "CheckNumber", "ReferenceNumber", "ConfirmationNumber",
        
        # 技术字段
        "DatabaseName", "TableName", "ColumnName", "IndexName", "ConnectionString", "ConfigurationKey", "ParameterName",
        "VariableName", "FunctionName", "MethodName", "ClassName", "NamespaceName", "ModuleName", "ServiceName",
        "SchemaName", "ViewName", "ProcedureName", "TriggerName", "ConstraintName", "ForeignKeyName", "PrimaryKeyName", "UniqueKeyName",
        "HostName", "ServerName", "InstanceName", "ClusterName", "NodeName", "PodName", "ContainerName", "ImageName", "RegistryName", "RepositoryName",
        "APIName", "EndpointName", "RouteName", "PathName", "URLName", "DomainName", "SubdomainName", "ProtocolName", "PortName", "SocketName",
        
        # 内容和媒体字段
        "Title", "Description", "Content", "Summary", "Keywords", "Tags", "Category", "SubCategory", "Topic",
        "Subject", "Theme", "Genre", "Format", "Language", "Version", "Edition", "Publication", "Author", "Editor",
        "Headline", "Caption", "Subtitle", "Abstract", "Excerpt", "Snippet", "Preview", "Teaser", "Blurb", "Synopsis",
        "Text", "Body", "Message", "Comment", "Note", "Remark", "Observation", "Feedback", "Review", "Rating",
        "FileType", "MimeType", "Encoding", "Compression", "Resolution", "Bitrate", "Framerate", "Duration", "Size", "Checksum",
        
        # 位置和地理字段
        "Country", "State", "City", "District", "Street", "Building", "Floor", "Room", "PostalCode", "ZipCode",
        "Latitude", "Longitude", "Timezone", "Locale", "Region", "Territory", "Continent", "Area", "Zone", "Sector",
        "Province", "County", "Town", "Village", "Neighborhood", "Community", "Subdivision", "Development", "Complex", "Campus",
        "Address", "Location", "Place", "Site", "Venue", "Facility", "Establishment", "Institution", "Organization", "Company",
        "Coordinates", "Position", "Point", "Spot", "Place", "Location", "Site", "Venue", "Facility", "Establishment",
        
        # 金融相关字段
        "AccountBalance", "TransactionAmount", "InterestRate", "PrincipalAmount", "MonthlyPayment", "AnnualIncome",
        "CreditLimit", "AvailableCredit", "OutstandingBalance", "MinimumPayment", "DueDate", "PaymentDate",
        "ExchangeRate", "CurrencyCode", "ConversionRate", "BaseCurrency", "TargetCurrency", "CrossRate", "SpotRate", "ForwardRate",
        "MarketPrice", "BidPrice", "AskPrice", "LastPrice", "OpenPrice", "ClosePrice", "HighPrice", "LowPrice", "Volume", "Turnover",
        
        # 时间相关扩展字段
        "Year", "Month", "Day", "Hour", "Minute", "Second", "Millisecond", "Microsecond", "Nanosecond", "Week",
        "Quarter", "Semester", "FiscalYear", "AcademicYear", "CalendarYear", "BusinessYear", "TaxYear", "ReportingPeriod", "BillingCycle", "MaintenanceWindow",
        "Duration", "ElapsedTime", "ProcessingTime", "ResponseTime", "Latency", "Timeout", "Interval", "Frequency", "Period", "Cycle",
        
        # 状态扩展字段
        "IsActive", "IsEnabled", "IsVisible", "IsRequired", "IsOptional", "IsValid", "IsInvalid", "IsComplete", "IsIncomplete", "IsPending",
        "IsApproved", "IsRejected", "IsCancelled", "IsSuspended", "IsTerminated", "IsExpired", "IsRenewed", "IsModified", "IsDeleted", "IsArchived",
        "HasPermission", "HasAccess", "HasPrivilege", "HasRole", "HasGroup", "HasAttribute", "HasProperty", "HasMethod", "HasFunction", "HasCapability",
        
        # 配置和设置字段
        "ConfigValue", "SettingValue", "ParameterValue", "OptionValue", "PreferenceValue", "DefaultValue", "CustomValue", "OverrideValue",
        "ThresholdValue", "LimitValue", "MaximumValue", "MinimumValue", "OptimalValue", "TargetValue", "ExpectedValue", "ActualValue", "CalculatedValue", "EstimatedValue",
        "EnabledFlag", "DisabledFlag", "TrueFlag", "FalseFlag", "YesFlag", "NoFlag", "OnFlag", "OffFlag", "ActiveFlag", "InactiveFlag",
        
        # 网络和通信字段
        "IPAddress", "MACAddress", "HostName", "DomainName", "URL", "URI", "Endpoint", "Port", "Protocol", "Method",
        "RequestHeader", "ResponseHeader", "Cookie", "Session", "Token", "Bearer", "APIKey", "SecretKey", "PublicKey", "PrivateKey",
        "ConnectionString", "ConnectionId", "SessionId", "RequestId", "CorrelationId", "TraceId", "SpanId", "TransactionId", "BatchId", "JobId",
        
        # 文件和存储字段
        "FileName", "FilePath", "FileSize", "FileType", "FileExtension", "FileHash", "FileChecksum", "FileSignature", "FileVersion", "FileRevision",
        "DirectoryName", "DirectoryPath", "DirectorySize", "DirectoryCount", "DirectoryDepth", "DirectoryLevel", "DirectoryStructure", "DirectoryTree", "DirectoryList", "DirectoryMap",
        "StoragePath", "StorageSize", "StorageType", "StorageClass", "StorageTier", "StoragePolicy", "StorageQuota", "StorageUsage", "StorageAvailable", "StorageUsed",
        
        # 安全和权限字段
        "PermissionLevel", "AccessLevel", "SecurityLevel", "PrivilegeLevel", "RoleLevel", "GroupLevel", "UserLevel", "AdminLevel", "SupervisorLevel", "ManagerLevel",
        "AuthenticationMethod", "AuthorizationType", "EncryptionType", "HashAlgorithm", "SignatureAlgorithm", "KeyAlgorithm", "CertificateType", "TokenType", "SessionType", "ConnectionType",
        "PasswordHash", "PasswordSalt", "PasswordExpiry", "PasswordHistory", "PasswordPolicy", "PasswordStrength", "PasswordComplexity", "PasswordLength", "PasswordAge", "PasswordAttempts",
        
        # 区块链/加密货币字段
        "BlockHash", "TransactionHash", "WalletAddress", "PrivateKey", "PublicKey", "Signature", "Nonce", "GasLimit", "GasPrice", "BlockNumber",
        "TokenAddress", "TokenSymbol", "TokenDecimals", "TokenSupply", "TokenBalance", "StakingAmount", "RewardRate", "ValidatorAddress", "ConsensusType", "BlockTime",
        "ExchangeRate", "TradingVolume", "MarketCap", "PriceChange", "LiquidityPool", "YieldRate", "GovernanceToken", "VotingPower", "ProposalId", "OraclePrice",
        
        # 物联网字段
        "DeviceId", "SensorType", "SensorValue", "TelemetryData", "FirmwareVersion", "ConnectivityType", "SignalStrength", "BatteryLevel", "Temperature", "Humidity",
        "Pressure", "LightLevel", "MotionDetected", "LocationData", "Timestamp", "DataQuality", "CalibrationStatus", "MaintenanceDue", "AlertThreshold", "AutomationRule",
        "EdgeNodeId", "GatewayId", "ProtocolType", "DataRate", "Latency", "Bandwidth", "PowerConsumption", "EnvironmentalCondition", "AssetTag", "PredictiveMaintenance",
        
        # 人工智能/机器学习字段
        "ModelId", "ModelVersion", "TrainingAccuracy", "ValidationAccuracy", "TestAccuracy", "Precision", "Recall", "F1Score", "AUC", "ConfusionMatrix",
        "FeatureVector", "PredictionScore", "ConfidenceLevel", "ModelSize", "InferenceTime", "TrainingTime", "Hyperparameter", "LearningRate", "BatchSize", "EpochCount",
        "LossValue", "GradientNorm", "OverfittingScore", "DriftScore", "FeatureImportance", "ModelInterpretation", "ExplainabilityScore", "BiasScore", "FairnessMetric", "RobustnessScore",
        
        # 网络安全字段
        "ThreatId", "VulnerabilityId", "IncidentId", "SeverityLevel", "RiskScore", "ThreatType", "AttackVector", "CVEId", "CVSSScore", "Exploitability",
        "FirewallRule", "IntrusionAlert", "MalwareSignature", "PenetrationResult", "AuditFinding", "ComplianceStatus", "IdentityProvider", "AccessLevel", "EncryptionKey", "CertificateExpiry",
        "ForensicEvidence", "HuntingQuery", "TrainingScore", "PhishingScore", "SOCAlert", "SIEMEvent", "EDRAlert", "XDRIncident", "ZeroTrustScore", "MFASuccess",
        
        # 环保/可持续发展字段
        "CarbonFootprint", "EmissionsAmount", "SustainabilityScore", "WasteAmount", "RecyclingRate", "EnergyEfficiency", "WaterConsumption", "BiodiversityIndex", "ClimateData", "EnvironmentalImpact",
        "SupplyChainScore", "CircularEconomyIndex", "GreenCertification", "EcoFriendlyScore", "CarbonCredits", "EmissionTracking", "SustainabilityReport", "EnvironmentalCompliance", "GreenTechnology", "RenewableEnergy",
        "SolarCapacity", "WindCapacity", "HydroCapacity", "BiomassEnergy", "GeothermalEnergy", "TidalEnergy", "WaveEnergy", "NuclearEnergy", "FossilFuel", "CleanEnergy",
        
        # 娱乐/媒体字段
        "StreamingQuality", "VideoResolution", "LiveLatency", "ContentRating", "SubscriptionTier", "AdvertisingTarget", "ViewerAnalytics", "ContentRating", "ParentalControl", "RecommendationScore",
        "MusicGenre", "PlaylistLength", "PodcastDuration", "GamingScore", "EsportsRanking", "VRExperience", "ARInteraction", "InteractiveLevel", "UserGeneratedContent", "SocialIntegration",
        "EntertainmentType", "MediaFormat", "BroadcastChannel", "ProgramDuration", "ShowRating", "EpisodeNumber", "SeasonNumber", "SeriesGenre", "MovieLength", "ContentCategory",
        
        # 法律/合规字段
        "LegalDocumentId", "ContractVersion", "ComplianceStatus", "RegulatoryUpdate", "RiskAssessment", "AuditResult", "EvidenceId", "CaseNumber", "ResearchTopic", "ReviewStatus",
        "IntellectualPropertyId", "PatentNumber", "TrademarkRegistration", "CopyrightStatus", "LicenseType", "PrivacyLevel", "GDPRCompliance", "DataProtection", "PolicyVersion", "ConsentStatus",
        "LawyerId", "AttorneyLicense", "JudgeId", "CourtId", "JurySize", "WitnessId", "PlaintiffId", "DefendantId", "ProsecutorId", "DefenseAttorney",
        
        # 科研/学术字段
        "ResearchProjectId", "ExperimentId", "PaperId", "ReviewStatus", "CitationCount", "LaboratoryId", "SampleId", "AnalysisType", "ModelType", "FundingAmount",
        "ConferenceId", "CollaborationId", "PublicationId", "EthicsApproval", "OpenAccessStatus", "TrialId", "ProtocolId", "DatasetId", "ReproducibilityScore", "MetaAnalysisId",
        "ScientistId", "ResearcherId", "ProfessorId", "StudentId", "LaboratoryName", "InstituteId", "UniversityId", "JournalId", "ConferenceName", "WorkshopId",
        
        # 新兴技术字段
        "QuantumBit", "QuantumState", "QuantumEntanglement", "QuantumAlgorithm", "QuantumCircuit", "QuantumError", "QuantumCorrection", "QuantumKey", "QuantumRandom", "QuantumSimulation",
        "EdgeComputing", "FogComputing", "CloudComputing", "ServerlessFunction", "MicroserviceId", "ContainerId", "KubernetesPod", "DockerImage", "VirtualMachine", "BareMetal",
        "5GNetwork", "6GNetwork", "WiFi6", "Bluetooth5", "NFC", "RFID", "LoRaWAN", "Sigfox", "NB_IoT", "SatelliteCommunication",
        
        # 生物技术字段
        "DNASequence", "GeneExpression", "ProteinStructure", "CellCulture", "BiologicalSample", "GeneticMarker", "MutationType", "Phenotype", "Genotype", "BiologicalPathway",
        "CRISPR", "GeneEditing", "SyntheticBiology", "Bioinformatics", "ComputationalBiology", "SystemsBiology", "Metabolomics", "Proteomics", "Transcriptomics", "Genomics",
        "Biomarker", "DrugTarget", "TherapeuticArea", "ClinicalPhase", "TrialArm", "Dosage", "Efficacy", "Safety", "Toxicity", "Pharmacokinetics",
        
        # 太空技术字段
        "SatelliteId", "OrbitType", "Altitude", "Inclination", "Eccentricity", "Period", "LaunchDate", "MissionType", "PayloadWeight", "PowerConsumption",
        "SpacecraftId", "RocketType", "LaunchVehicle", "MissionControl", "GroundStation", "TelemetryData", "Trajectory", "PropulsionSystem", "LifeSupport", "ThermalControl",
        "SpaceDebris", "CollisionRisk", "OrbitalDecay", "ReentryTime", "AtmosphericDrag", "SolarRadiation", "CosmicRays", "Microgravity", "VacuumLevel", "TemperatureExtreme"
    ]
}


# === Auto-generated extensions to enlarge VARIABLE_NAMES ===
from itertools import product


def _extend_list(target: list, items):
    """Append unique items to target list, preserving order."""
    for itm in items:
        if itm not in target:
            target.append(itm)


def _extend_variable_names():
    """Dynamically generate additional variable names to greatly enlarge
    the available vocabulary for synthetic data generation. The goal is to
    create hundreds of extra plausible names without having to maintain a
    huge static list manually. This keeps the original hand-crafted examples
    while massively increasing variety.
    """
    # 1) Table names: adjective + noun pattern (e.g., archived_events)
    adjectives = [
        "archived", "historic", "temp", "backup", "staging", "raw", "processed",
        "aggregated", "daily", "monthly", "hourly", "delta", "snapshot",
        "transient", "secure", "encrypted", "public", "private", "regional",
        "central", "edge", "mobile", "web", "api", "system", "external",
    ]
    base_table_nouns = [
        "logs", "events", "metrics", "sessions", "configs", "changes",
        "jobs", "tasks", "errors", "alerts", "notifications", "messages",
        "audits", "analytics", "profiles", "settings", "requests",
        "responses", "archives", "attachments", "uploads", "downloads",
        "activities", "permissions",
    ]
    _extend_list(
        VARIABLE_NAMES["tables"],
        [f"{adj}_{noun}" for adj, noun in product(adjectives, base_table_nouns)],
    )

    # 2) Entity names: CamelCase version of adjective + noun (e.g., ArchivedEvent)
    base_entity_nouns = [
        "Log", "Event", "Metric", "Session", "Config", "Change", "Job",
        "Task", "Error", "Alert", "Notification", "Message", "Audit",
        "Profile", "Setting", "Request", "Response", "Archive",
        "Attachment", "Upload", "Download", "Activity", "Permission",
    ]
    _extend_list(
        VARIABLE_NAMES["entities"],
        [f"{adj.capitalize()}{noun}" for adj, noun in product(adjectives, base_entity_nouns)],
    )

    # 3) Method names: Verb + Noun (e.g., SyncData, PurgeCache)
    verbs = [
        "Sync", "Refresh", "Reload", "Purge", "Clean", "Flush", "Archive",
        "Validate", "Sanitize", "Process", "Analyze", "Monitor", "Collect",
        "Generate", "Compute", "Update", "Load", "Export", "Import", "Encrypt",
        "Decrypt", "Sign", "Verify", "Compress", "Decompress",
    ]
    method_objects = [
        "Data", "Cache", "Logs", "Metrics", "Schema", "Backup", "Index",
        "Report", "Snapshot", "Job", "Queue", "Message", "Alert", "Record",
        "Entry", "Session", "Token", "Request", "Response", "Archive",
    ]
    _extend_list(
        VARIABLE_NAMES["methods"],
        [f"{verb}{obj}" for verb, obj in product(verbs, method_objects)],
    )

    # 4) Field names: noun + suffix / prefix patterns
    field_bases = [
        "Retry", "Error", "Warning", "Info", "Debug", "Max", "Min",
        "Average", "Median", "StdDev", "Threshold", "Limit", "Quota",
        "Offset", "Cursor", "Flag", "Enabled", "Disabled",
    ]
    suffixes = [
        "Count", "Total", "Rate", "Time", "Duration", "Size", "Value",
        "Level", "Code", "Id", "Hash", "Checksum", "Timestamp",
    ]
    _extend_list(
        VARIABLE_NAMES["fields"],
        [f"{base}{suffix}" for base, suffix in product(field_bases, suffixes)],
    )


# Invoke the extension once at import time
_extend_variable_names()
# === End of auto-generated extensions ===


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