"""
SQL有效性评估模块
"""
import sys
import os
from typing import List

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from utils.sql_feature_extractor import SQLFeatureExtractor
from utils.response_parser import recursively_extract_sql


def async_evaluate_sql_validity(solution_str: str, debug_mode: bool = False):
    """
    评估SQL语句的有效性（同步实现，CPU密集型无需异步）
    
    Args:
        solution_str: 模型响应文本
        debug_mode: 调试模式开关
        
    Returns:
        平均有效性分数 (0.0-1.0) 和详细信息字典
    """
    try:
        # 提取SQL语句
        extracted_sqls = recursively_extract_sql(solution_str)
        if not extracted_sqls:
            if debug_mode:
                print("[SQL有效性] 未找到SQL语句")
            return 0.0, {"valid_count": 0, "total_count": 0, "invalid_sqls": []}
        
        # 评估每条SQL的有效性
        extractor = SQLFeatureExtractor()
        valid_count = 0
        total_count = len(extracted_sqls)
        
        for sql in extracted_sqls:
            try:
                fingerprint = extractor.extract(sql)
                if fingerprint != "invalid_sql":
                    valid_count += 1
                elif debug_mode:
                    print(f"[SQL有效性] 无效SQL: {sql[:50]}...")
            except Exception as e:
                if debug_mode:
                    print(f"[SQL有效性] SQL解析异常: {e}")
                continue
        
        validity_score = valid_count / total_count if total_count > 0 else 0.0
        
        if debug_mode:
            print(f"[SQL有效性] 有效SQL: {valid_count}/{total_count}, 得分: {validity_score:.2f}")
        
        # 构建详细信息
        invalid_sqls = [sql for sql in extracted_sqls if extractor.extract(sql) == "invalid_sql"]
        detail_dict = {
            "valid_count": valid_count,
            "total_count": total_count,
            "invalid_sqls": invalid_sqls[:3],  # 保存前3条完整的无效SQL
            "all_extracted_sqls": extracted_sqls,  # 保存所有提取的SQL，便于调试
            "invalid_sqls_count": len(invalid_sqls)  # 记录无效SQL总数
        }
        
        return round(validity_score, 2), detail_dict
        
    except Exception as e:
        if debug_mode:
            print(f"[SQL有效性] 评估失败: {e}")
        return 0.0, {"valid_count": 0, "total_count": 0, "invalid_sqls": [], "error": str(e)}, {"valid_count": 0, "total_count": 0, "invalid_sqls": []} 