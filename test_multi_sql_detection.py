#!/usr/bin/env python3
"""
测试多语句SQL检测逻辑
"""
import sys
import os
import json
import asyncio

# 添加项目路径
sys.path.append('/data/cloud_disk_1/home/wuyu/code2sql')

# 测试数据
test_solution_str = '''[
  {
    "type": "param_dependent",
    "variants": [
      {
        "scenario": "仅创建AI分析任务",
        "sql": "INSERT INTO ivc_ai_analysis_task (id, channel_id, app_id, uin, status, from_cluster_id, cross_cluster, sub_task_number, source_type, source_protocol, source_path, callback_enabled, callback_type, callback_endpoint, callback_auth_enabled, callback_token, snapshot_enabled, snapshot_interval, ai_enabled, is_user_bucket, storage_bucket_region, storage_bucket_id, storage_life_cycle, storage_image_url_expire, multi_speed, created_time, updated_time, deleted_time) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);"
      },
      {
        "scenario": "创建AI分析任务和子任务",
        "sql": "INSERT INTO ivc_ai_analysis_task (id, channel_id, app_id, uin, status, from_cluster_id, cross_cluster, sub_task_number, source_type, source_protocol, source_path, callback_enabled, callback_type, callback_endpoint, callback_auth_enabled, callback_token, snapshot_enabled, snapshot_interval, ai_enabled, is_user_bucket, storage_bucket_region, storage_bucket_id, storage_life_cycle, storage_image_url_expire, multi_speed, created_time, updated_time, deleted_time) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?); INSERT INTO ivc_ai_analysis_sub_task (id, task_id, policy_id, executor_node_id, node_task_id, status, heartbeat_time, created_time, updated_time) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);"
      },
      {
        "scenario": "创建AI分析任务、子任务和拉流配置",
        "sql": "INSERT INTO ivc_ai_analysis_task (id, channel_id, app_id, uin, status, from_cluster_id, cross_cluster, sub_task_number, source_type, source_protocol, source_path, callback_enabled, callback_type, callback_endpoint, callback_auth_enabled, callback_token, snapshot_enabled, snapshot_interval, ai_enabled, is_user_bucket, storage_bucket_region, storage_bucket_id, storage_life_cycle, storage_image_url_expire, multi_speed, created_time, updated_time, deleted_time) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?); INSERT INTO ivc_ai_analysis_sub_task (id, task_id, policy_id, executor_node_id, node_task_id, status, heartbeat_time, created_time, updated_time) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?); INSERT INTO ivc_ai_pull_stream_config (policy_id, start_time, end_time, work_day, cycle_pull_stream_enabled, cycle_interval_time, cycle_duration_time) VALUES (?, ?, ?, ?, ?, ?, ?);"
      },
      {
        "scenario": "创建所有类型数据（任务、子任务、拉流配置和策略）",
        "sql": "INSERT INTO ivc_ai_analysis_task (id, channel_id, app_id, uin, status, from_cluster_id, cross_cluster, sub_task_number, source_type, source_protocol, source_path, callback_enabled, callback_type, callback_endpoint, callback_auth_enabled, callback_token, snapshot_enabled, snapshot_interval, ai_enabled, is_user_bucket, storage_bucket_region, storage_bucket_id, storage_life_cycle, storage_image_url_expire, multi_speed, created_time, updated_time, deleted_time) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?); INSERT INTO ivc_ai_analysis_sub_task (id, task_id, policy_id, executor_node_id, node_task_id, status, heartbeat_time, created_time, updated_time) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?); INSERT INTO ivc_ai_pull_stream_config (policy_id, start_time, end_time, work_day, cycle_pull_stream_enabled, cycle_interval_time, cycle_duration_time) VALUES (?, ?, ?, ?, ?, ?, ?); INSERT INTO ivc_ai_policy (id, task_id, alg_id, type, model, interval, threshold, rois, stay_time, manufacturer, created_time, updated_time) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);"
      }
    ]
  }
]'''

async def test_detection():
    """测试检测逻辑"""
    print("=" * 80)
    print("测试多语句SQL检测逻辑")
    print("=" * 80)
    
    # 导入检测模块
    try:
        from model.rl.eval_dimensions.multi_sql_penalty import async_evaluate_multi_sql_penalty
        from utils.response_parser import recursively_extract_sql
        import sqlparse
    except ImportError as e:
        print(f"导入失败: {e}")
        return
    
    # 1. 测试SQL提取
    print("\n1. 测试SQL提取结果:")
    print("-" * 40)
    extracted_sqls = recursively_extract_sql(test_solution_str)
    print(f"提取到 {len(extracted_sqls)} 条SQL:")
    for i, sql in enumerate(extracted_sqls):
        print(f"  SQL-{i+1}: {sql[:100]}...")
    
    # 2. 测试每条SQL的多语句检测
    print("\n2. 测试多语句检测:")
    print("-" * 40)
    for i, sql in enumerate(extracted_sqls):
        statements = [stmt for stmt in sqlparse.split(sql) if stmt.strip()]
        is_multi = len(statements) > 1
        print(f"  SQL-{i+1}: {len(statements)} 条语句, 多语句: {is_multi}")
        if is_multi:
            print(f"    - 分解后: {[stmt[:50]+'...' for stmt in statements]}")
    
    # 3. 测试完整检测函数
    print("\n3. 测试完整检测函数:")
    print("-" * 40)
    score, detail = await async_evaluate_multi_sql_penalty(test_solution_str, debug_mode=True)
    print(f"最终检测结果:")
    print(f"  - 得分: {score}")
    print(f"  - 详情: {json.dumps(detail, ensure_ascii=False, indent=2)}")
    
    # 4. 计算惩罚影响
    print("\n4. 惩罚影响计算:")
    print("-" * 40)
    penalty_cap = 0.10  # 默认配置
    penalty_amount = penalty_cap * (1 - score)
    print(f"  - 惩罚上限: {penalty_cap}")
    print(f"  - 实际惩罚: {penalty_amount:.3f}")
    print(f"  - 如果原分数为0.85，扣除后为: {max(0.85 - penalty_amount, 0.0):.3f}")

if __name__ == "__main__":
    asyncio.run(test_detection()) 