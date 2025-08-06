#!/usr/bin/env python3
"""
测试SQL有效性检查器
"""
import sys
import os

# 添加项目路径
sys.path.append('/data/cloud_disk_1/home/wuyu/code2sql')

# 测试SQL
test_sql = "policy_id IN (SELECT policy_id FROM ivc_ai_analysis_sub_task WHERE task_id IN (SELECT id FROM ivc ai analysis_task WHERE channel_ id = ? AND %s))"

def test_sql_validity():
    """测试SQL有效性检查"""
    print("=" * 80)
    print("测试SQL有效性检查器")
    print("=" * 80)
    
    # 导入检测模块
    try:
        from model.rl.eval_dimensions.sql_validity import async_evaluate_sql_validity
        from utils.response_parser import recursively_extract_sql
        from utils.sql_feature_extractor import SQLFeatureExtractor
    except ImportError as e:
        print(f"导入失败: {e}")
        return
    
    print(f"\n测试SQL: {test_sql}")
    print("-" * 40)
    
    # 1. 测试SQL提取
    print("\n1. 测试SQL提取:")
    extracted_sqls = recursively_extract_sql(test_sql)
    print(f"提取到 {len(extracted_sqls)} 条SQL:")
    for i, sql in enumerate(extracted_sqls):
        print(f"  SQL-{i+1}: {sql}")
    
    # 2. 测试SQL特征提取器
    print("\n2. 测试SQL特征提取器:")
    extractor = SQLFeatureExtractor()
    for i, sql in enumerate(extracted_sqls):
        try:
            fingerprint = extractor.extract(sql)
            is_valid = fingerprint != "invalid_sql"
            print(f"  SQL-{i+1}:")
            print(f"    - 指纹: {fingerprint}")
            print(f"    - 有效: {is_valid}")
        except Exception as e:
            print(f"  SQL-{i+1}: 解析异常 - {e}")
    
    # 3. 测试完整的有效性评估函数
    print("\n3. 测试完整有效性评估:")
    score, detail = async_evaluate_sql_validity(test_sql, debug_mode=True)
    print(f"\n最终评估结果:")
    print(f"  - 得分: {score}")
    print(f"  - 详情: {detail}")
    
    # 4. 直接用sqlparse测试
    print("\n4. 使用sqlparse直接解析:")
    try:
        import sqlparse
        parsed = sqlparse.parse(test_sql)
        print(f"  - 解析结果: {len(parsed)} 个语句")
        for i, stmt in enumerate(parsed):
            print(f"  - 语句{i+1}: {stmt.ttype} - {str(stmt)[:100]}...")
    except Exception as e:
        print(f"  - sqlparse解析失败: {e}")

if __name__ == "__main__":
    test_sql_validity() 