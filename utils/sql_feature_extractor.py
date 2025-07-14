from typing import Dict, Optional
import sqlglot
import json
from sqlglot.expressions import (
    CTE,
    Select,
    Insert,
    Update,
    Delete,
    Table,
    Subquery,
    SetOperation,
    Union,
    Intersect,
    Except,
    Expression,
    Identifier,
    Join,
    Where,
    Group,
    Having,
    Order,
    Limit,
    Offset,
    Predicate,
    Unary,
    Binary
)
import csv
import os
import pickle
from tqdm import tqdm
import hashlib
import re
from multiprocessing import Pool, cpu_count
import pandas as pd
import time
from pathlib import Path
# 固定路径
CSV_PATH = "/data/local_disk0/shawn/dirty_work/before_409/dmc_unique.csv"
JSON_PATH = "/data/local_disk0/shawn/api_benchmark/base_test/qwen3_14b_dmc_results_w_caller1.json"
FINGERPRINT_CACHE = "/data/local_disk0/shawn/dirty_work/421/dmc_full_fingerprints_508_upload.pkl"
FINGERPRINT_CACHE_HUMAN = "//data/local_disk0/shawn/dirty_work/421/dmc_full_fingerprints_508_uoload_add_humanx2.pkl"

class DMLType:
    SELECT = 1
    INSERT = 2
    UPDATE = 3
    DELETE = 4


class SQLFeatureExtractor:
    null_identifier = "null"
    join_op = "join"
    inner_join_op = "inner_join"
    left_join_op = "left_join"
    right_join_op = "right_join"
    left_outer_join_op = "left_outer_join"
    right_outer_join_op = "right_outer_join"
    natural_join_op = "natural_join"
    cross_join_op = "cross_join"
    union_op = "union"
    union_all_op = "union_all"
    intersect_op = "intersect"
    intersect_all_op = "intersect_all"
    minus_op = "minus"
    minus_all_op = "minus_all"
    limit_op = "limit"
    offset_op = "offset"
    COUNT_FUNC = "count"
    SUM_FUNC = "sum"
    AVG_FUNC = "avg"
    MIN_FUNC = "min"
    MAX_FUNC = "max"

    # 添加系统函数识别
    system_functions = {
        "last_insert_id", "version", "database", "schema", "user", "current_user", 
        "connection_id", "row_count", "found_rows", "current_date", "current_time",
        "current_timestamp", "now", "sysdate", "curdate", "curtime"
    }

    def __init__(self):
        self.stmt_type = None
        self.join_count_dict = {
            self.join_op: 0,
            self.inner_join_op: 0,
            self.left_join_op: 0,
            self.right_join_op: 0,
            self.left_outer_join_op: 0,
            self.right_outer_join_op: 0,
            self.natural_join_op: 0,
            self.cross_join_op: 0,
        }
        self.set_count_dict = {
            self.union_op: 0,
            self.union_all_op: 0,
            self.intersect_op: 0,
            self.intersect_all_op: 0,
            self.minus_op: 0,
            self.minus_all_op: 0,
        }
        self.sub_query_count = 0
        self.sub_query_tables = set()  # 存储子查询中的表
        self.sub_query_predicates = set()  # 存储子查询中的条件列
        self.has_nested_subquery = False  # 标记是否有嵌套子查询
        # Used by select | insert | update
        self.projection_count_dict = {}
        self.table_count_dict = {}
        self.predicate_count_dict = {}
        self.group_count_dict = {}
        self.order_count_dict = {}
        self.limit_count_dict = {
            self.limit_op: 0,
            self.offset_op: 0
        }
        self.aggregation_count_dict = {
            self.COUNT_FUNC: 0,
            self.SUM_FUNC: 0,
            self.AVG_FUNC: 0,
            self.MIN_FUNC: 0,
            self.MAX_FUNC: 0,
        }
        self.has_group_by = False
        self.has_having = False

    def merge_count_dict(self, count_dict: Dict):
        sl = []
        for k in sorted(count_dict.keys()):
            v = count_dict[k]
            s = f"{k}_{v}"
            sl.append(s)
        return ",".join(sl)

    def calc_hash(self):
        sl = list()
        
        # 添加查询类型信息（提高优先级）
        if self.stmt_type is not None:
            sl.append(f"type_{self.stmt_type}")
        
        # 表结构
        tables = sorted(self.table_count_dict.keys())
        sl.append("tables_" + "_".join(tables))
        
        # 对于UPDATE语句，考虑SET子句中的列名
        if self.stmt_type == DMLType.UPDATE:

            # 添加WHERE条件中的列名列表
            predicates = sorted(self.predicate_count_dict.keys())
            sl.append("where_columns_" + "_".join(predicates))
        # 对于INSERT语句，考虑列名列表
        # if self.stmt_type == DMLType.INSERT:
        #     # 添加列名的完整列表
        #     columns = sorted(self.projection_count_dict.keys())
        #     sl.append("insert_columns_" + "_".join(columns))
        else:
            # 条件列
            predicates = sorted(self.predicate_count_dict.keys())
            sl.append("predicates_" + "_".join(predicates))
        
        # 添加JOIN信息
        join_types = []
        for join_type, count in self.join_count_dict.items():
            if count > 0:
                join_types.append(join_type)
        if join_types:
            sl.append("joins_" + "_".join(sorted(join_types)))
        
        # 添加子查询信息
        if self.sub_query_count > 0:
            sl.append(f"subquery_count_{self.sub_query_count}")
            
            # 添加子查询中的表信息
            if self.sub_query_tables:
                sl.append("subquery_tables_" + "_".join(sorted(self.sub_query_tables)))
            
            # 添加嵌套子查询标记
            if self.has_nested_subquery:
                sl.append("has_nested_subquery")
        
        # 添加聚合函数信息
        has_aggregation = any(count > 0 for count in self.aggregation_count_dict.values())
        if has_aggregation:
            agg_types = []
            for agg_type, count in self.aggregation_count_dict.items():
                if count > 0:
                    agg_types.append(f"{agg_type}_{count}")
            if agg_types:
                sl.append("aggregations_" + "_".join(sorted(agg_types)))
        
        # 添加GROUP BY和HAVING信息
        if self.has_group_by:
            sl.append("has_group_by")
        if self.has_having:
            sl.append("has_having")
        
        fs = ".".join(sl)
        h = hashlib.md5(fs.encode()).hexdigest()
        return h

    def extract_from_insert_stmt(
            self,
            insert: Insert
    ):
        # 设置语句类型为INSERT
        self.stmt_type = DMLType.INSERT
        
        schema = insert.this
        table = schema.this
        table_name = self.get_final_identifier(table.this)
        tc = self.table_count_dict.get(table_name, 0)
        self.table_count_dict[table_name] = tc+1

        columns = schema.expressions
        for column in columns:
            column_name = self.get_final_identifier(column.this)
            cc = self.projection_count_dict.get(column_name, 0)
            self.projection_count_dict[column_name] = cc+1

    def extract_from_update_stmt(
            self,
            update: Update
    ):
        # 设置语句类型为UPDATE
        self.stmt_type = DMLType.UPDATE
        
        table = update.this
        table_name = self.get_final_identifier(table.this)
        tc = self.table_count_dict.get(table_name, 0)
        self.table_count_dict[table_name] = tc+1

        column_updates = update.expressions
        for column_update in column_updates:
            column = column_update.this
            column_name = self.get_final_identifier(column.this)
            cc = self.projection_count_dict.get(column_name, 0)
            self.projection_count_dict[column_name] = cc+1

        where = update.args.get("where")
        if where is not None:
            self.extract_from_where_clause(where)

    def extract_from_delete_stmt(
            self,
            delete: Delete
    ):
        # 设置语句类型为DELETE
        self.stmt_type = DMLType.DELETE
        
        table = delete.this
        table_name = self.get_final_identifier(table.this)
        tc = self.table_count_dict.get(table_name, 0)
        self.table_count_dict[table_name] = tc+1

        where = delete.args.get("where")
        if where is not None:
            self.extract_from_where_clause(where)

    def extract_from_select_stmt(
            self,
            select
    ):
        # 设置语句类型为SELECT
        self.stmt_type = DMLType.SELECT
        
        if isinstance(select, Subquery):
            self.extract_from_sub_query(select)
        elif isinstance(select, SetOperation):
            self.extract_from_set_stmt(select)
        elif isinstance(select, Select):
            self.extract_from_select_body(select)

    def extract_from_select_body(
            self,
            select: Select
    ):
        # 设置语句类型为SELECT（如果之前未设置）
        if self.stmt_type is None:
            self.stmt_type = DMLType.SELECT
            
        columns = select.expressions
        for column in columns:
            if column is None or column.this is None:
                # 处理 SELECT * 的情况
                cc = self.projection_count_dict.get(self.null_identifier, 0)
                self.projection_count_dict[self.null_identifier] = cc+1
            else:
                # 检查是否是聚合函数
                self.check_for_aggregation(column)
                
                column_name = self.get_final_identifier(column.this)
                cc = self.projection_count_dict.get(column_name, 0)
                self.projection_count_dict[column_name] = cc+1

        relation = select.args.get("from")
        # print("From关系类型:", type(relation))
        # if relation is not None:
            # print("From关系内容:", relation)
            # if hasattr(relation, 'this'):
                # print("relation.this:", relation.this)
                # if hasattr(relation.this, 'this'):
                    # print("relation.this.this:", relation.this.this)

        if relation is None:
            pass
        elif hasattr(relation, 'this'):  # 处理From类型
            table_name = self.get_final_identifier(relation.this)
            tc = self.table_count_dict.get(table_name, 0)
            self.table_count_dict[table_name] = tc+1
        elif isinstance(relation, Table):
            table_name = self.get_final_identifier(relation)
            tc = self.table_count_dict.get(table_name, 0)
            self.table_count_dict[table_name] = tc+1
        elif isinstance(relation, Subquery):
            self.extract_from_sub_query(relation)
        elif isinstance(relation, Join):
            self.extract_from_join_clause(relation)

        joins = select.args.get("joins")
        if joins is not None:
            for join in joins:
                if isinstance(join, Join):
                    self.extract_from_join_clause(join)

        where = select.args.get("where")
        # print('where:',where)
        if where is not None:
            self.extract_from_where_clause(where)

        group = select.args.get("group")
        if group is not None:
            self.has_group_by = True
            self.extract_from_group_clause(group)

        having = select.args.get("having")
        if having is not None:
            self.has_having = True
            self.extract_from_having_clause(having)

        order = select.args.get("order")
        if order is not None:
            self.extract_from_order_clause(order)

        cte = select.args.get("with")
        if cte is not None:
            for expression in cte.expressions:
                if isinstance(expression, CTE):
                    cte_expression = expression.this
                    if isinstance(cte_expression, Select):
                        self.extract_from_select_stmt(cte_expression)

        limit = select.args.get("limit")
        offset = select.args.get("offset")
        self.extract_from_limit_clause(limit, offset)

    def extract_from_sub_query(self, sub_query):
        """增强的子查询处理方法"""
        self.sub_query_count += 1
        
        # 记录处理子查询前的表和条件数量
        tables_before = set(self.table_count_dict.keys())
        predicates_before = set(self.predicate_count_dict.keys())
        
        # 处理子查询
        if hasattr(sub_query, 'select'):
            self.extract_from_select_stmt(sub_query.select())
        elif isinstance(sub_query, Select):
            self.extract_from_select_body(sub_query)
        
        # 检查是否有新的表和条件被添加
        tables_after = set(self.table_count_dict.keys())
        predicates_after = set(self.predicate_count_dict.keys())
        
        # 记录子查询中的表和条件
        self.sub_query_tables.update(tables_after - tables_before)
        self.sub_query_predicates.update(predicates_after - predicates_before)
        
        # 检测嵌套子查询
        if self.sub_query_count > 1:
            self.has_nested_subquery = True

    def extract_from_set_stmt(
            self,
            set_op: SetOperation
    ):
        this = set_op.this
        if isinstance(this, SetOperation):
            set_key = None
            if isinstance(this, Union):
                distinct = this.args.get("distinct")
                if distinct:
                    set_key = self.union_op
                else:
                    set_key = self.union_all_op
            elif isinstance(this, Intersect):
                distinct = this.args.get("distinct")
                if distinct:
                    set_key = self.intersect_op
                else:
                    set_key = self.intersect_all_op
            elif isinstance(this, Except):
                distinct = this.args.get("distinct")
                if distinct:
                    set_key = self.minus_op
                else:
                    set_key = self.minus_all_op
            if set_key is not None:
                set_value = self.set_count_dict.get(set_key, 0)
                self.set_count_dict[set_key] = set_value+1
        elif isinstance(this, Subquery):
            self.extract_from_sub_query(this)
        elif isinstance(this, Select):
            self.extract_from_select_body(this)

        expression = this.args.get("expression")
        self.extract_from_select_stmt(expression)

    def get_final_identifier(
            self,
            expression: Expression
    ):
        if expression is None:
            return self.null_identifier
        if isinstance(expression, str):
            return expression
        if isinstance(expression, Identifier):
            return expression.this.replace('`', '').lower()
        elif isinstance(expression, Table):
            # 处理Table对象
            if hasattr(expression, 'name'):
                return expression.name
            elif expression.this and hasattr(expression.this, 'this'):
                return expression.this.this
            else:
                return self.get_final_identifier(expression.this)
        elif hasattr(expression, 'this'):
            if expression.this is None:
                return self.null_identifier
            result = self.get_final_identifier(expression.this)
            # 最后返回前处理标识符
            if isinstance(result, str):
                # 如果是类似t1、t2这样的临时别名，可以规范化
                if re.match(r'^t\d+$', result):
                    return "temp_alias"
                # 移除反引号并转为小写
                return result.replace('`', '').lower()
            return result
        return self.null_identifier # 增加一个默认返回值

    def extract_from_join_clause(
            self,
            join: Join
    ):
        table = join.this
        if isinstance(table, Table):
            table_name = self.get_final_identifier(table.this)
            tc = self.table_count_dict.get(table_name, 0)
            self.table_count_dict[table_name] = tc+1
        elif isinstance(table, Join):
            self.extract_from_join_clause(table)

        on = join.args.get("on")
        if on is not None:
            self.extract_from_predicate(on)

    def extract_from_where_clause(
            self,
            where: Where
    ):
        self.extract_from_predicate(where.this)

    def extract_from_predicate(
            self,
            predicate   # Maybe Predicate | Expression
    ):
        """处理WHERE条件，提取所有条件列"""
        # 只关注列名，完全忽略值
        # print(f'处理谓词({type(predicate).__name__}):', predicate)
        
        # 如果是None，直接返回
        if predicate is None:
            return
            
        # 处理二元操作符(如AND, OR, =, <, >等)
        if isinstance(predicate, Binary):
            # 获取操作符类型
            op_type = predicate.__class__.__name__
            # print(f"二元操作符类型: {op_type}")
            
            # 特殊处理AND和OR操作符，需要递归处理两侧的条件
            if op_type == 'And' or op_type == 'Or':
                # 处理左侧
                # print(f"处理{op_type}操作符的左侧: {predicate.this}")
                self.extract_from_predicate(predicate.this)
                
                # 处理右侧
                # print(f"处理{op_type}操作符的右侧: {predicate.expression}")
                self.extract_from_predicate(predicate.expression)
            
            # 处理比较操作符，如EQ, LT, GT等
            elif op_type in ('EQ', 'NEQ', 'GT', 'GTE', 'LT', 'LTE', 'Like', 'In'):
                # 判断左侧是否是列
                left = predicate.this
                if isinstance(left, Identifier) or (hasattr(left, 'this') and isinstance(left.this, Identifier)):
                    # 直接处理Identifier类型
                    if isinstance(left, Identifier):
                        column_name = left.this
                    else:
                        column_name = left.this.this
                        
                    # print(f"找到谓词列(左侧): {column_name}")
                    # 确认是有效的列名
                    if self.is_valid_column_name(column_name):
                        cc = self.predicate_count_dict.get(column_name, 0)
                        self.predicate_count_dict[column_name] = cc + 1
                        # print(f"添加谓词列(左侧): {column_name}, 当前计数: {cc + 1}")
                    else:
                        # print(f"左侧列名 {column_name} 被判定为无效")
                        pass
                
                # 判断右侧是否是列（可能是列与列的比较）
                right = predicate.expression
                if isinstance(right, Identifier) or (hasattr(right, 'this') and isinstance(right.this, Identifier)):
                    # 直接处理Identifier类型
                    if isinstance(right, Identifier):
                        column_name = right.this
                    else:
                        column_name = right.this.this
                        
                    # print(f"找到谓词列(右侧): {column_name}")
                    # 确认是有效的列名
                    if self.is_valid_column_name(column_name):
                        cc = self.predicate_count_dict.get(column_name, 0)
                        self.predicate_count_dict[column_name] = cc + 1
                        # print(f"添加谓词列(右侧): {column_name}, 当前计数: {cc + 1}")
                    else:
                        # print(f"右侧列名 {column_name} 被判定为无效")
                        pass
        
        # 处理一元操作符(如NOT)
        elif isinstance(predicate, Unary):
            # print(f"处理一元操作符: {predicate}")
            if predicate.this is not None:
                self.extract_from_predicate(predicate.this)
        
        # 处理普通表达式
        elif isinstance(predicate, (Expression, Identifier)):
            # print(f"处理表达式: {predicate}")
            if isinstance(predicate, Identifier):
                column_name = predicate.this
                # print(f"找到标识符: {column_name}")
                if self.is_valid_column_name(column_name):
                    cc = self.predicate_count_dict.get(column_name, 0)
                    self.predicate_count_dict[column_name] = cc + 1
                    # print(f"添加谓词列(标识符): {column_name}, 当前计数: {cc + 1}")
            elif hasattr(predicate, 'this') and predicate.this is not None:
                if isinstance(predicate.this, Identifier):
                    column_name = predicate.this.this
                    # print(f"找到表达式中的标识符: {column_name}")
                    if self.is_valid_column_name(column_name):
                        cc = self.predicate_count_dict.get(column_name, 0)
                        self.predicate_count_dict[column_name] = cc + 1
                        # print(f"添加谓词列(表达式标识符): {column_name}, 当前计数: {cc + 1}")
                else:
                    self.extract_from_predicate(predicate.this)
        
        # 处理Where条件
        elif isinstance(predicate, Where):
            # print(f"处理Where条件: {predicate}")
            if predicate.this is not None:
                self.extract_from_predicate(predicate.this)
        
        # 处理其他类型
        else:
            # print(f"未处理的谓词类型: {type(predicate).__name__} - {predicate}")
            pass

    def is_valid_column_name(self, name):
        """判断是否是有效的列名（排除看起来像值的标识符）"""
        if not isinstance(name, str):
            return False
            
        # 打印所有检查的列名，帮助调试
        # print(f"检查列名有效性: {name}")
        
        # 排除明显的值
        if name.startswith(("'", '"', "`")):
            # print(f"  列名 {name} 以引号开头，判定为无效")
            return False
            
        # 排除数字值
        if name.isdigit():
            # print(f"  列名 {name} 是纯数字，判定为无效")
            return False
            
        # 如果是 "N" 或 "'S'" (标准化后的数字和字符串)，认为是值而非列名
        if name in ("N", "S", "'S'", "NULL"):
            # print(f"  列名 {name} 是标准化的数字或字符串，判定为无效")
            return False
            
        # 默认有效
        # print(f"  列名 {name} 判定为有效")
        return True

    def extract_from_group_clause(
            self,
            group: Group
    ):
        group_column_list = []
        for expression in group.expressions:
            name = self.get_final_identifier(expression)
            group_column_list.append(name)
        full_group_name = "".join(group_column_list)
        group_count = self.group_count_dict.get(full_group_name, 0)
        self.group_count_dict[full_group_name] = group_count+1

    def extract_from_having_clause(
            self,
            having: Having
    ):
        self.extract_from_predicate(having.this)

    def extract_from_order_clause(
            self,
            order: Order
    ):
        order_columns = set()  # 使用集合而非列表
        for expression in order.expressions:
            name = self.get_final_identifier(expression.this)
            order_columns.add(name)
        
        # 转换为排序后的字符串
        full_order_name = "_".join(sorted(order_columns))
        self.order_count_dict[full_order_name] = 1

    def extract_from_limit_clause(
            self,
            limit: Optional[Limit] = None,
            offset: Optional[Offset] = None
    ):
        # 只关注是否有LIMIT/OFFSET，不关注具体值
        if limit is not None:
            self.limit_count_dict[self.limit_op] = 1

        if offset is not None:
            self.limit_count_dict[self.offset_op] = 1

    def normalize_orm_sql(self, sql_text):
        """对SQL进行ORM特定的规范化处理"""
        if not sql_text or not isinstance(sql_text, str):
            return sql_text
        
        # 移除SQL注释
        sql_text = re.sub(r'--.*?$', '', sql_text, flags=re.MULTILINE)
        sql_text = re.sub(r'/\*.*?\*/', '', sql_text, flags=re.DOTALL)
        
        # 1. 规范化换行符和多余空白
        sql_text = re.sub(r'\s+', ' ', sql_text).strip()
        
        # 2. 规范化表别名 (t1, t2 -> t_alias)
        sql_text = re.sub(r'([`"\s])t\d+([`"\s])', r'\1t_alias\2', sql_text)
        
        # 3. 规范化引号样式 (不同ORM可能使用不同引号)
        # 将所有引号类型统一
        
        # 4. 规范化数字值 (不同的数值不应影响指纹)
        sql_text = re.sub(r'=\s*\d+', '= N', sql_text)
        sql_text = re.sub(r'IN\s*\(\s*\d+(\s*,\s*\d+)*\s*\)', 'IN (N)', sql_text, flags=re.IGNORECASE)
        
        # 5. 规范化字符串值
        sql_text = re.sub(r"'[^']*'", "'S'", sql_text)
        sql_text = re.sub(r'"[^"]*"', '"S"', sql_text)
        
        # 6. 规范化LIMIT值
        sql_text = re.sub(r'LIMIT\s+\d+', 'LIMIT N', sql_text, flags=re.IGNORECASE)
        sql_text = re.sub(r'LIMIT\s+\d+\s*,\s*\d+', 'LIMIT N, N', sql_text, flags=re.IGNORECASE)
        
        return sql_text

    def is_transaction_start(self, stmt):
        """检查是否是事务开始语句"""
        # 根据sqlglot的具体实现调整此函数
        return (hasattr(stmt, 'this') and 
                isinstance(stmt.this, str) and 
                stmt.this.upper() in ('BEGIN', 'START TRANSACTION'))
    
    def is_transaction_end(self, stmt):
        """检查是否是事务结束语句"""
        return (hasattr(stmt, 'this') and 
                isinstance(stmt.this, str) and 
                stmt.this.upper() in ('COMMIT', 'ROLLBACK'))
    
    def is_session_setting(self, stmt):
        """检查是否是会话设置语句"""
        return (hasattr(stmt, 'this') and 
                isinstance(stmt.this, str) and 
                stmt.this.upper().startswith('SET'))
    
    def is_system_function_query(self, sql):
        """检查SQL是否是简单的系统函数查询"""
        # 规范化SQL
        sql_lower = sql.lower().strip()
        
        # 检查是否是简单的SELECT函数()形式
        if sql_lower.startswith("select ") and "from" not in sql_lower and "where" not in sql_lower:
            # 提取函数名
            match = re.search(r"select\s+(\w+)\s*\(\s*\)", sql_lower)
            if match:
                func_name = match.group(1)
                return func_name in self.system_functions
        
        return False

    def extract(self, sql_text):
        # 检查是否是系统函数查询
        if self.is_system_function_query(sql_text):
            # 提取函数名作为指纹的一部分
            match = re.search(r"select\s+(\w+)\s*\(\s*\)", sql_text.lower())
            if match:
                func_name = match.group(1)
                return f"system_function_{func_name}"
            else:
                return "system_function_unknown" # 或者其他默认值
            
        # 首先进行ORM特定的规范化
        normalized_sql = self.normalize_orm_sql(sql_text)
        #   print('normalized_sql:',normalized_sql)
        # 简单检查是否是事务控制语句
        if normalized_sql.strip().upper() in ('BEGIN', 'BEGIN;', 'START TRANSACTION', 'START TRANSACTION;'):
            return "transaction_begin"
        if normalized_sql.strip().upper() in ('COMMIT', 'COMMIT;', 'ROLLBACK', 'ROLLBACK;'):
            return "transaction_end"
        
        # 检查是否是会话设置语句
        if normalized_sql.strip().upper().startswith('SET '):
            return "session_setting"
        
        # 检查是否是SHOW语句
        if normalized_sql.strip().upper().startswith('SHOW '):
            return "show_command"
        
        # 检查是否是DDL语句
        if any(normalized_sql.strip().upper().startswith(prefix) for prefix in 
               ['CREATE ', 'ALTER ', 'DROP ', 'TRUNCATE ', 'RENAME ']):
            return "ddl_command"
        
        # 检查是否是非SQL文本
        if not self.looks_like_sql(normalized_sql):
            return "not_sql"
        
        try:
            # 处理多语句SQL
            statements = sqlglot.parse(normalized_sql, read='mysql')
            # print('statements:',statements)
            if not statements:
                return "empty_sql"
            
            # 如果只有一个事务开始语句，这可能不是我们想要匹配的重点
            if len(statements) == 1 and self.is_transaction_start(statements[0]):
                return "transaction_start"
            
            # 处理所有语句，合并特征
            for stmt in statements:
                if isinstance(stmt, Insert):
                    self.stmt_type = DMLType.INSERT  # 设置语句类型
                    self.extract_from_insert_stmt(stmt)
                elif isinstance(stmt, Update):
                    self.stmt_type = DMLType.UPDATE  # 设置语句类型
                    self.extract_from_update_stmt(stmt)
                elif isinstance(stmt, Delete):
                    self.stmt_type = DMLType.DELETE  # 设置语句类型
                    self.extract_from_delete_stmt(stmt)
                elif isinstance(stmt, Select):
                    self.stmt_type = DMLType.SELECT  # 设置语句类型
                    self.extract_from_select_stmt(stmt)
                elif isinstance(stmt, Subquery):
                    self.stmt_type = DMLType.SELECT  # 子查询通常是SELECT
                    self.extract_from_select_stmt(stmt)
                elif isinstance(stmt, SetOperation):
                    self.stmt_type = DMLType.SELECT  # 集合操作通常是SELECT
                    self.extract_from_set_stmt(stmt)
            
            # 使用基本指纹而非变体
            h = self.calc_hash()
            return str(h)
        except Exception as e:
            # 解析失败，可能不是有效的SQL
            return "invalid_sql"  # 使用统一的指纹，不再区分不同的无效SQL
    
    def looks_like_sql(self, text):
        """简单检查文本是否看起来像SQL语句"""
        # 移除注释
        text = re.sub(r'--.*?$', '', text, flags=re.MULTILINE)
        text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
        
        # 移除空白字符
        text = text.strip()
        
        # 如果为空，不是SQL
        if not text:
            return False
        
        # 检查是否以SQL关键字开头
        sql_starters = [
            'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP', 
            'TRUNCATE', 'BEGIN', 'COMMIT', 'ROLLBACK', 'SET', 'SHOW', 'USE',
            'EXPLAIN', 'DESCRIBE', 'DESC', 'GRANT', 'REVOKE', 'ANALYZE'
        ]
        
        first_word = text.split()[0].upper() if text.split() else ""
        
        # 如果不以SQL关键字开头，可能不是SQL
        if first_word not in sql_starters:
            # 额外检查是否包含常见SQL模式
            sql_patterns = [
                r'SELECT\s+.*?\s+FROM',
                r'INSERT\s+INTO',
                r'UPDATE\s+.*?\s+SET',
                r'DELETE\s+FROM',
                r'CREATE\s+TABLE',
                r'ALTER\s+TABLE',
                r'DROP\s+TABLE',
                r'JOIN\s+.*?\s+ON'
            ]
            
            for pattern in sql_patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    return True
            
            return False
        
        return True

    def check_for_aggregation(self, expression):
        """检查表达式是否包含聚合函数"""
        if expression is None:
            return
        
        # 检查函数名称
        if hasattr(expression, 'this') and hasattr(expression.this, 'this'):
            func_name = expression.this.this.lower() if isinstance(expression.this.this, str) else None
            if func_name in [self.COUNT_FUNC, self.SUM_FUNC, self.AVG_FUNC, self.MIN_FUNC, self.MAX_FUNC]:
                # 增加对应聚合函数的计数
                self.aggregation_count_dict[func_name] = self.aggregation_count_dict.get(func_name, 0) + 1
        
        # 检查表达式列表
        if hasattr(expression, 'expressions') and expression.expressions:
            for expr in expression.expressions:
                self.check_for_aggregation(expr)
            
        # 递归检查子表达式
        if hasattr(expression, 'this') and expression.this is not None:
            self.check_for_aggregation(expression.this)

    def extract_tables_and_columns(self, sql_text: str) -> dict:
        """
        提取SQL中涉及到的表名和字段名
        
        Args:
            sql_text: 要分析的SQL语句
            
        Returns:
            dict: 包含表名和字段名的字典，格式如下：
            {
                "tables": set,  # 表名集合
                "columns": set,  # 字段名集合
                "table_columns": dict,  # 表名到字段名的映射 {table_name: set(columns)}
                "select_columns": set,  # SELECT子句中的字段
                "where_columns": set,   # WHERE子句中的字段
                "join_columns": set,    # JOIN子句中的字段
                "group_columns": set,   # GROUP BY子句中的字段
                "order_columns": set,   # ORDER BY子句中的字段
                "insert_columns": set,  # INSERT子句中的字段
                "update_columns": set,  # UPDATE子句中的字段
                "stmt_type": str        # 语句类型
            }
        """
        # 初始化结果字典
        result = {
            "tables": set(),
            "columns": set(),
            "table_columns": {},
            "select_columns": set(),
            "where_columns": set(),
            "join_columns": set(),
            "group_columns": set(),
            "order_columns": set(),
            "insert_columns": set(),
            "update_columns": set(),
            "stmt_type": None
        }
        
        try:
            # 使用现有的extract方法解析SQL
            self.extract(sql_text)
            
            # 从解析结果中提取信息
            result["tables"] = set(self.table_count_dict.keys())
            result["columns"] = set(self.projection_count_dict.keys()) | set(self.predicate_count_dict.keys())
            result["stmt_type"] = self.get_stmt_type_name()
            
            # 按语句类型分别处理
            if self.stmt_type == DMLType.SELECT:
                result["select_columns"] = set(self.projection_count_dict.keys())
                result["where_columns"] = set(self.predicate_count_dict.keys())
                result["group_columns"] = set(self.group_count_dict.keys())
                result["order_columns"] = set(self.order_count_dict.keys())
                
            elif self.stmt_type == DMLType.INSERT:
                result["insert_columns"] = set(self.projection_count_dict.keys())
                
            elif self.stmt_type == DMLType.UPDATE:
                result["update_columns"] = set(self.projection_count_dict.keys())
                result["where_columns"] = set(self.predicate_count_dict.keys())
                
            elif self.stmt_type == DMLType.DELETE:
                result["where_columns"] = set(self.predicate_count_dict.keys())
            
            # 构建表名到字段名的映射
            for table_name in result["tables"]:
                result["table_columns"][table_name] = set()
                
            # 将所有字段按表名分类（简化处理，实际可能需要更复杂的解析）
            for column_name in result["columns"]:
                # 检查字段名是否包含表名前缀
                if '.' in column_name:
                    table_name, col_name = column_name.split('.', 1)
                    if table_name in result["tables"]:
                        result["table_columns"][table_name].add(col_name)
                else:
                    # 如果没有表名前缀，将字段添加到所有表中（简化处理）
                    for table_name in result["tables"]:
                        result["table_columns"][table_name].add(column_name)
            
            # 清理空集合
            for key in list(result.keys()):
                if isinstance(result[key], set) and not result[key]:
                    result[key] = set()
                elif isinstance(result[key], dict):
                    # 清理table_columns中的空集合
                    result[key] = {k: v for k, v in result[key].items() if v}
            
        except Exception as e:
            print(f"提取表名和字段名时出错: {e}")
            # 返回空结果
            pass
        
        return result
    
    def get_stmt_type_name(self) -> str:
        """获取语句类型的名称"""
        if self.stmt_type == DMLType.SELECT:
            return "SELECT"
        elif self.stmt_type == DMLType.INSERT:
            return "INSERT"
        elif self.stmt_type == DMLType.UPDATE:
            return "UPDATE"
        elif self.stmt_type == DMLType.DELETE:
            return "DELETE"
        else:
            return "UNKNOWN"



# 将函数移到外部，使其可以被pickle
def process_single_sql(sql_text):
    try:
        extractor = SQLFeatureExtractor()
        fingerprint = extractor.extract(sql_text)
        return fingerprint, sql_text
    except Exception as e:
        return None, None

def process_csv_and_save_fingerprints(csv_filepath, output_filepath, sql_column_name="Sql"):
    """
    处理CSV文件中的SQL语句，计算指纹并保存
    """
    fingerprints = set()
    fingerprint_to_sql = {}  # 新增：保存指纹到SQL的映射
    
    if isinstance(csv_filepath, list):
        sql_list = []
        for csv_file in csv_filepath:
            print("使用分块读取大型CSV文件...")
            
            for chunk in pd.read_csv(csv_file, usecols=[sql_column_name], chunksize=100000):
                sql_list.extend(chunk[sql_column_name].tolist())
    else:        
    # 使用多进程处理
    # 文件太大，使用分块读取
        print("使用分块读取大型CSV文件...")
        sql_list = []
        for chunk in pd.read_csv(str(csv_filepath), usecols=[sql_column_name], chunksize=100000):
            sql_list.extend(chunk[sql_column_name].tolist())
    
    print(f"从CSV加载了 {len(sql_list)} 条SQL语句")
    
    # 使用进程池并行处理
    num_processes = max(1, min(cpu_count() - 1, 64))  # 限制最大进程数为16
    print(f"使用 {num_processes} 个进程并行处理...")
    
    results = []
    with Pool(processes=num_processes) as pool:
        # 使用tqdm显示进度
        for result in tqdm(pool.imap(process_single_sql, sql_list, chunksize=1000), 
                          total=len(sql_list), 
                          desc="并行处理SQL"):
            fingerprint, sql_text = result
            if fingerprint:
                fingerprints.add(fingerprint)
                
                # 保存指纹到SQL的映射
                if fingerprint not in fingerprint_to_sql:
                    fingerprint_to_sql[fingerprint] = []
                # 移除数量限制，保存所有SQL示例以支持全量分析
                fingerprint_to_sql[fingerprint].append(sql_text)
    
    # 保存指纹和指纹到SQL的映射到文件
    with open(output_filepath, 'wb') as f:
        pickle.dump((fingerprints, fingerprint_to_sql), f)
    
    print(f"CSV文件处理完成，共计算 {len(fingerprints)} 个不同的SQL指纹")
    print(f"指纹已保存到: {output_filepath}")
    return fingerprints, fingerprint_to_sql

def load_fingerprints(cache_path):
    """加载指纹缓存文件"""
    try:
        with open(cache_path, 'rb') as f:
            data = pickle.load(f)
            if isinstance(data, tuple) and len(data) == 2:
                fingerprints, fingerprint_to_sql = data
                
                # 检查是否有额外添加的指纹信息
                extra_add_fingerprints = set()
                for fp, sql_list in fingerprint_to_sql.items():
                    # 检查是否有extra_add标记
                    if hasattr(sql_list, 'get') and callable(getattr(sql_list, 'get')):
                        # 如果是字典格式，检查extra_add标记
                        if sql_list.get('extra_add', False):
                            extra_add_fingerprints.add(fp)
                
                # 如果发现了extra_add标记，打印信息
                if extra_add_fingerprints:
                    print(f"发现 {len(extra_add_fingerprints)} 个额外添加的指纹")
                
                # 如果fingerprint_to_sql中有字典格式，转换为列表格式
                for fp in list(fingerprint_to_sql.keys()):
                    if hasattr(fingerprint_to_sql[fp], 'get') and callable(getattr(fingerprint_to_sql[fp], 'get')):
                        # 如果是字典格式，提取sql_examples
                        if 'sql_examples' in fingerprint_to_sql[fp]:
                            fingerprint_to_sql[fp] = fingerprint_to_sql[fp]['sql_examples']
            else:
                # 兼容旧格式
                fingerprints = data
                fingerprint_to_sql = {}
        print(f"已加载 {len(fingerprints)} 个指纹")
        return fingerprints, fingerprint_to_sql
    except Exception as e:
        print(f"加载指纹缓存失败: {e}")
        return set(), {}

def process_json_and_compare(
    json_filepath,
    csv_fingerprints,
    output_dir: str,
    fingerprint_to_sql=None,
    sql_key="sql_statement_list",
    human_review=False
):

    print(f"开始处理JSON文件: {json_filepath}")

    # --- 数据加载和预处理 ---
    try:
        with open(json_filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"FATAL: 无法加载或解析JSON文件: {json_filepath}, 错误: {e}")
        return

    # --- 兼容性修复：将新的列表格式转换为旧的字典格式 ---
    # 旧格式是 {'func_name': data}, 新格式是 [{'sample_id': 'func_name', ...}]
    if isinstance(data, list):
        print("检测到新的列表格式JSON，正在转换为字典格式以便处理...")
        data_dict = {
            item.get('sample_id', f'item_{i}'): item for i, item in enumerate(data)
        }
        data = data_dict
        print("转换完成。")

    if not isinstance(data, dict):
        print(f"错误：无法处理的数据格式，根对象类型为 {type(data)}，期望为字典。")
        return

    total_lines = len(data) # 总行数就是字典的长度
    matching_count = 0  # SQL语句匹配计数
    valid_sql_count = 0  # 总SQL语句计数（不包括被排除的类型）
    excluded_sql_count = 0  # 被排除的SQL语句计数
    matching_lines = 0  # JSON行匹配计数
    total_lines = 0  # 总JSON行计数
    matching_pairs = []  # 存储匹配的SQL对
    excluded_pairs = []  # 存储被排除的SQL
    unmatched_pairs = []  # 存储未匹配的SQL
    matched_fingerprints = set()  # 记录匹配到的指纹

    # 指定一些排除指纹类型
    excluded_fingerprints = {
        "transaction_begin",
        "transaction_end",
        "session_setting",
        "show_command",
        "ddl_command",
        "empty_sql",
        "not_sql",
        "invalid_sql",
    }

    # 一些系统函数前缀
    system_function_prefixes = ["system_function_"]

    # 用于记录被排除的具体原因及次数
    excluded_types_count = {
        fp: 0 for fp in excluded_fingerprints
    }
    excluded_types_count["transaction_wrapper"] = 0  # 特例

    print(f"CSV指纹总数: {len(csv_fingerprints)}")

    # 过滤CSV指纹（如果有需要）
    valid_csv_fingerprints = set()
    invalid_csv_fingerprints = set()
    for fp in csv_fingerprints:
        if fp not in excluded_fingerprints and not any(fp.startswith(pref) for pref in system_function_prefixes):
            valid_csv_fingerprints.add(fp)
        else:
            invalid_csv_fingerprints.add(fp)
    print(f"有效CSV指纹数: {len(valid_csv_fingerprints)}")
    print(f"被排除的CSV指纹数: {len(csv_fingerprints) - len(valid_csv_fingerprints)}")
    
    # 将被排除的指纹保存到当前评估的输出目录中，用于调试
    invalid_fingerprints_path = os.path.join(output_dir, "invalid_csv_fingerprints.json")
    with open(invalid_fingerprints_path, 'w', encoding='utf-8') as f:
        json.dump(list(invalid_csv_fingerprints), f, ensure_ascii=False, indent=2)
    print(f"被排除的CSV指纹已保存到: {invalid_fingerprints_path}")
    
    log_file = os.path.join(output_dir, "temp.log")
    with open(log_file, 'w', encoding='utf-8') as log:
        log.write("===== SQL解析日志 =====\n\n")

    def write_log(message):
        with open(log_file, 'a', encoding='utf-8') as log:
            log.write(f"{message}\n")

    # 获取文件行数以便显示进度
    try:
        with open(json_filepath, 'r', encoding='utf-8') as f:
            # data = json.load(f) # 注释掉此行，防止覆盖已转换好的data字典
            pass # 添加pass防止语法错误
        # 如果能一次性读取，说明是一个"整体 JSON"，而不是 JSON Lines
        total_lines = len(data)
        is_jsonl = False
    except json.JSONDecodeError:
        # 如果这里抛异常，说明可能是 JSON Lines 格式
        is_jsonl = True
        with open(json_filepath, 'r', encoding='utf-8') as f:
            total_lines = sum(1 for _ in f)

    def get_exclude_type(fingerprint):
        """
        根据指纹判断是否应被排除，并返回对应排除类型
        """
        if fingerprint in excluded_fingerprints:
            return fingerprint
        elif fingerprint.startswith("session_setting_"):
            return "session_setting"
        elif fingerprint.startswith("invalid_sql_"):
            return "invalid_sql"
        elif any(fingerprint.startswith(prefix) for prefix in system_function_prefixes):
            return "system_function"
        else:
            return None

    # 用于解析并返回"是否被排除/命中指纹/提取到的指纹"等信息
    def parse_single_sql(sql_string):
        extractor = SQLFeatureExtractor()
        fingerprint = extractor.extract(sql_string)
        exclude_type = get_exclude_type(fingerprint)
        write_log(f"指纹: {fingerprint}, 排除类型: {exclude_type}")
        return fingerprint, exclude_type

    def handle_transaction_wrapper_check(sql_text):
        """
        判断该SQL是否包含事务包装（begin...commit/rollback）
        如果同时包含 begin/start transaction + commit/rollback，就视为事务包装
        """
        lower_sql = sql_text.lower()
        return (
            ("begin" in lower_sql or "start transaction" in lower_sql)
            and ("commit" in lower_sql or "rollback" in lower_sql)
        )
    
    # 添加一个辅助函数，用于处理单个SQL语句
    def process_single_sql_item(sql_item, function_name):
        nonlocal valid_sql_count, matching_count, excluded_sql_count
        nonlocal line_has_match
        
        # 处理 param_dependent
        if isinstance(sql_item, dict) and sql_item.get("type") == "param_dependent":
            variants = sql_item.get("variants", [])
            if not variants:
                write_log("变体列表为空，跳过处理")
                return
            
            # 1) 先初始化本组统计状态
            variant_valid_sqls = []
            variant_has_match = False
            variant_all_excluded = True
            
            # 2) 遍历所有变体
            for variant_idx, variant in enumerate(variants):
                variant_sql_text = variant.get("sql")
                write_log(f"变体SQL: {variant_sql_text}")
                if not variant_sql_text:
                    continue
                # 如果变体是列表，只取第一个非空字符串
                if isinstance(variant_sql_text, list):
                    variant_sql_text = next(
                        (s for s in variant_sql_text if s and str(s).strip()),
                        None
                    )
                    if not variant_sql_text:
                        continue
                
                # 检查是否事务包装
                if isinstance(variant_sql_text, str) and handle_transaction_wrapper_check(variant_sql_text):
                    excluded_types_count["transaction_wrapper"] += 1
                    write_log("检测到事务包装SQL，跳过处理此变体")
                    continue
                
                # 提取指纹
                fingerprint, exclude_type = parse_single_sql(variant_sql_text.strip())
                
                # 如果被排除
                if exclude_type:
                    # 记录排除
                    if exclude_type in excluded_types_count:
                        excluded_types_count[exclude_type] += 1
                    excluded_pairs.append({
                        "sql": variant_sql_text,
                        "fingerprint": fingerprint,
                        "function_name": function_name,
                        "exclude_type": exclude_type
                    })
                    continue
                
                # 能走到这里说明这条变体是有效SQL
                variant_all_excluded = False
                
                # 如果尚未命中，尝试命中 CSV 指纹
                if fingerprint in csv_fingerprints:
                    variant_valid_sqls.append({
                        "sql": variant_sql_text,
                        "fingerprint": fingerprint,
                    })
                    variant_has_match = True
                    matched_fingerprints.add(fingerprint)
            
            # 3) 遍历完所有变体后，统一更新计数器
            if variant_all_excluded:
                excluded_sql_count += 1
                # 整组都被排除了，直接返回
                return
            
            # 至少有一条有效 SQL
            valid_sql_count += 1
            variant_valid_list = []
            
            # 检查是否有匹配指纹
            if variant_has_match:
                matching_count += 1
                
                for variant_valid_sql in variant_valid_sqls:
                    if fingerprint_to_sql and variant_valid_sql["fingerprint"] in fingerprint_to_sql:
                        if fingerprint_to_sql[variant_valid_sql["fingerprint"]]:
                            csv_sql_example = fingerprint_to_sql[variant_valid_sql["fingerprint"]][0]
                            variant_valid_list.append({
                                "sql": variant_valid_sql["sql"],
                                "fingerprint": variant_valid_sql["fingerprint"],
                                "csv_sql": csv_sql_example,
                            })
                
                # 加入 matching_pairs
                matching_pairs.append({
                    "json_sql": sql_item,  # 整个 param_dependent 对象
                    "matched_variant_sql": variant_valid_list,
                    "function_name": function_name
                })
                line_has_match = True
            else:
                # 未匹配的情况
                unmatched_pairs.append({
                    "sql": sql_item,
                    "fingerprint": "unknown",  # 可能多个变体多个指纹
                    "function_name": function_name
                })
        
        elif isinstance(sql_item, str) and sql_item.strip():
            # 普通 SQL
            sql_text = sql_item.strip()
            
            # 事务包装检测
            if handle_transaction_wrapper_check(sql_text):
                excluded_types_count["transaction_wrapper"] += 1
                write_log("检测到事务包装SQL，跳过处理此SQL")
                return
            
            fingerprint, exclude_type = parse_single_sql(sql_text)
            if exclude_type:
                # 被排除
                if exclude_type in excluded_types_count:
                    excluded_types_count[exclude_type] += 1
                excluded_sql_count += 1
                excluded_pairs.append({
                    "sql": sql_text,
                    "fingerprint": fingerprint,
                    "function_name": function_name,
                    "exclude_type": exclude_type
                })
                return
            
            # 记录到总数
            valid_sql_count += 1
            
            # 判断是否匹配
            if fingerprint in csv_fingerprints:
                matching_count += 1
                matched_fingerprints.add(fingerprint)
                csv_sql_example = ""
                if fingerprint_to_sql and fingerprint_to_sql.get(fingerprint):
                    csv_sql_example = fingerprint_to_sql[fingerprint][0]
                
                matching_pairs.append({
                    "json_sql": sql_text,
                    "csv_sql": csv_sql_example,
                    "fingerprint": fingerprint,
                    "function_name": function_name
                })
                line_has_match = True
            else:
                # 未匹配
                unmatched_pairs.append({
                    "sql": sql_text,
                    "fingerprint": fingerprint,
                    "function_name": function_name
                })
    full_sql_cnt_official = 0
    # 处理 JSON (整体或 JSON Lines)
    if not is_jsonl:
        # 处理整体 JSON
        with open(json_filepath, 'r', encoding='utf-8') as f:
            # data = json.load(f)  # 注释掉此行，防止第二次覆盖
            pass # 添加pass防止语法错误
 
        from tqdm import tqdm
        # 循环处理JSON中的每一项
        # 旧代码期望一个字典，新代码处理列表
        if isinstance(data, dict):
            # 兼容旧的字典格式
            data_iterator = data.items()
        elif isinstance(data, list):
            # 处理新的列表格式
            data_iterator = [
                (item.get('sample_id', f'item_{i}'), item) for i, item in enumerate(data)
            ]
        else:
            print(f"错误：JSON文件根对象既不是字典也不是列表，无法处理。")
            return {} # 或者抛出异常

        for function_name, function_data in tqdm(data_iterator, total=total_lines, desc="处理JSON数据"):
            write_log(f"\n\n===== 处理函数: {function_name} =====")
            
            line_has_match = False
            # --- 兼容性修复 ---
            # 旧格式依赖 "sql_pattern_cnt" 键，新格式需要从 sql 列表的长度动态计算
            if "sql_pattern_cnt" in function_data:
                sql_pattern_cnt = function_data.get("sql_pattern_cnt", 0)
            else:
                # 从我们传入的 sql_key (即 'parsed_sql') 对应的列表长度来计算
                sql_pattern_cnt = len(function_data.get(sql_key, []))
            
            try:
                full_sql_cnt_official += int(sql_pattern_cnt or 0)
            except (ValueError, TypeError):
                # 如果 sql_pattern_cnt 仍然有问题（例如为None或空字符串），则跳过，避免崩溃
                pass
            caller_results = function_data.get("caller_results", [])
            if caller_results:
                write_log(f"发现 {len(caller_results)} 个调用者结果")
                
                # 处理所有调用者结果中的SQL语句
                for caller_idx, caller_result in enumerate(caller_results):
                    caller = caller_result.get("caller", "")
                    write_log(f"\n--- 处理调用者 #{caller_idx+1}: {caller} ---")
                    
                    # 获取调用者对应的SQL语句列表
                    caller_sql_statements = caller_result.get(sql_key, [])
                    if not caller_sql_statements:
                        write_log(f"调用者 {caller} 的SQL语句为空，跳过处理")
                        continue
                    
                    if not isinstance(caller_sql_statements, list):
                        caller_sql_statements = [caller_sql_statements]
                    
                    # 处理该调用者的所有SQL语句
                    for sql_index, sql_item in enumerate(caller_sql_statements):
                        write_log(f"\n--- 处理调用者 {caller} 的SQL项 #{sql_index+1} ---")
                        write_log(f"SQL项类型: {type(sql_item)}")
                        write_log(f"SQL项内容: {sql_item}")
                        
                        # 使用辅助函数处理单个SQL项
                        process_single_sql_item(sql_item, function_name)
            
            # 无论有没有caller_results，都尝试处理主SQL语句列表
            sql_statements = function_data.get(sql_key, [])
            if sql_statements:
                write_log(f"处理主SQL语句列表")
                
                if not isinstance(sql_statements, list):
                    sql_statements = [sql_statements]
                
                for sql_index, sql_item in enumerate(sql_statements):
                    write_log(f"\n--- 处理主SQL项 #{sql_index+1} ---")
                    write_log(f"SQL项类型: {type(sql_item)}")
                    write_log(f"SQL项内容: {sql_item}")
                    
                    # 使用辅助函数处理单个SQL项
                    process_single_sql_item(sql_item, function_name)
            
            elif not caller_results:
                write_log(f"函数 {function_name} 既没有 sql_statements 也没有 caller_results，跳过处理")
            
            if line_has_match:
                matching_lines += 1

    # 处理完成后，保存匹配/未匹配/被排除SQL到文件
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    matching_sql_file = os.path.join(output_dir, "matching_sql_pairs.json") if not human_review else os.path.join(output_dir, "matching_sql_pairs_w_human.json")
    unmatched_sql_file = os.path.join(output_dir, "unmatched_sql_pairs.json") if not human_review else os.path.join(output_dir, "unmatched_sql_pairs_w_human.json")
    excluded_sql_file = os.path.join(output_dir, "excluded_sql_pairs.json") if not human_review else os.path.join(output_dir, "excluded_sql_pairs_w_human.json")

    try:
        with open(matching_sql_file, 'w', encoding='utf-8') as fm:
            json.dump(matching_pairs, fm, ensure_ascii=False, indent=2)
        with open(unmatched_sql_file, 'w', encoding='utf-8') as fu:
            json.dump(unmatched_pairs, fu, ensure_ascii=False, indent=2)
        with open(excluded_sql_file, 'w', encoding='utf-8') as fe:
            json.dump(excluded_pairs, fe, ensure_ascii=False, indent=2)

        print(f"匹配的SQL对已保存到: {matching_sql_file}")
        print(f"未匹配的SQL对已保存到: {unmatched_sql_file}")
        print(f"被排除的SQL对已保存到: {excluded_sql_file}")
    except Exception as e:
        print(f"保存SQL结果出错: {e}")

    # 输出统计信息
    print(f"\n======= 统计结果 =======")
    print(f"总处理行数: {total_lines}")
    print(f"有匹配的行数: {matching_lines}")
    print(f"总SQL计数: {valid_sql_count + excluded_sql_count}")
    print(f"有效SQL语句数: {valid_sql_count}")
    print(f"匹配SQL语句数: {matching_count}")
    print(f"匹配率: {matching_count/valid_sql_count:.2%} ({matching_count}/{valid_sql_count})")
    print(f"被排除SQL语句数: {excluded_sql_count}")
    
    # 输出被排除原因统计
    print(f"\n被排除原因统计:")
    for reason, count in sorted(excluded_types_count.items(), key=lambda x: x[1], reverse=True):
        if count > 0:
            print(f"  - {reason}: {count}条")
    
    # --- 额外写入统计摘要文件，供前端读取 ---
    summary_path = os.path.join(output_dir, "statistics_summary.json")
    try:
        summary_data = {
            # 基本统计
            "total_samples": total_lines,                    # 总样本数
            "matching_lines": matching_lines,                # 有匹配的行数
            "valid_sql_count": valid_sql_count,             # 有效SQL语句数
            "matching_count": matching_count,                # 匹配SQL语句数
            "excluded_sql_count": excluded_sql_count,        # 被排除SQL语句数
            "full_sql_cnt_official": full_sql_cnt_official,  # 官方SQL计数
            
            # 指纹统计
            "total_fingerprints": len(csv_fingerprints),           # CSV指纹总数
            "matched_fingerprints_count": len(matched_fingerprints), # 匹配到的指纹数
            
            # 匹配详情统计
            "matching_pairs_count": len(matching_pairs),     # 匹配SQL对数量
            "unmatched_pairs_count": len(unmatched_pairs),  # 未匹配SQL对数量
            
            # 计算比率
            "sql_match_rate": matching_count / valid_sql_count if valid_sql_count else 0,  # SQL匹配率
            "fingerprint_coverage": len(matched_fingerprints) / len(csv_fingerprints) if csv_fingerprints else 0  # 指纹覆盖率
        }
        
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary_data, f, ensure_ascii=False, indent=4)
        print(f"统计摘要已写入: {summary_path}")
        
        # 打印详细统计信息
        print("\n======= 详细统计信息 =======")
        for key, value in summary_data.items():
            if isinstance(value, float):
                print(f"{key}: {value:.2%}")
            else:
                print(f"{key}: {value}")
                
    except Exception as e:
        print(f"写入统计摘要失败: {e}")
    
    return matching_lines, matching_pairs, matched_fingerprints, total_lines, valid_sql_count, matching_count, unmatched_pairs,excluded_sql_count,csv_fingerprints,full_sql_cnt_official

def find_table_name_matches(unmatched_pairs, fingerprint_to_sql):
    """
    对未匹配上的SQL语句，查找处理相同表名的CSV中的SQL语句
    """
    print("开始基于表名进行匹配分析...")
    table_matches = []
    matched_sql_ids = set()  # 记录找到表名匹配的SQL ID
    
    # 创建CSV SQL的表名索引
    csv_table_index = {}
    # 创建CSV SQL的表名+查询类型索引
    csv_table_query_type_index = {}
    
    for fingerprint, sql_list in fingerprint_to_sql.items():
        for sql in sql_list:
            # 为每个CSV SQL提取表名
            extractor = SQLFeatureExtractor()
            try:
                extractor.extract(sql)
                tables = list(extractor.table_count_dict.keys())
                query_type = extractor.stmt_type  # 获取查询类型
                
                if tables:
                    # 为每个表建立索引
                    for table in tables:
                        if table not in csv_table_index:
                            csv_table_index[table] = []
                        # 索引中存储(指纹, SQL)对
                        csv_table_index[table].append((fingerprint, sql))
                        
                        # 同时为表名+查询类型建立索引
                        table_type_key = f"{table}_{query_type}"
                        if table_type_key not in csv_table_query_type_index:
                            csv_table_query_type_index[table_type_key] = []
                        csv_table_query_type_index[table_type_key].append((fingerprint, sql))
            except Exception as e:
                continue
    
    print(f"从CSV SQL中提取了 {len(csv_table_index)} 个不同的表名")
    print(f"从CSV SQL中提取了 {len(csv_table_query_type_index)} 个不同的表名+查询类型组合")
    
    # 初始化计数器
    no_table_match_count = 0
    table_match_count = 0
    table_type_match_count = 0
    
    # 处理每个未匹配的SQL
    for i, unmatched_pair in enumerate(tqdm(unmatched_pairs, desc="基于表名匹配未匹配SQL")):
        try:
            sql = unmatched_pair["sql"]
            fingerprint = unmatched_pair["fingerprint"]
            function_name = unmatched_pair.get("function_name", "unknown")
            
            # 提取未匹配SQL的表名
            extractor = SQLFeatureExtractor()
            
            # 如果SQL是字典类型，需要特殊处理
            if isinstance(sql, dict):
                # 对于param_dependent类型的字典，尝试从变体中获取SQL
                if sql.get("type") == "param_dependent" and "variants" in sql:
                    variants = sql.get("variants", [])
                    if variants and isinstance(variants, list):
                        for variant in variants:
                            if isinstance(variant, dict) and "sql" in variant:
                                variant_sql = variant["sql"]
                                if isinstance(variant_sql, str) and variant_sql.strip():
                                    sql_to_check = variant_sql
                                    break
                        else:
                            # 如果没有找到有效的变体SQL，跳过此项
                            continue
                else:
                    # 其他类型的字典，跳过处理
                    continue
            # 如果SQL是列表，处理第一个元素
            elif isinstance(sql, list):
                if not sql:  # 空列表检查
                    continue
                first_sql = sql[0]
                if isinstance(first_sql, str):
                    sql_to_check = first_sql
                elif isinstance(first_sql, list) and first_sql and isinstance(first_sql[0], str):  # 二维列表检查
                    sql_to_check = first_sql[0]
                else:
                    # 无法处理的列表类型
                    continue
            # 如果SQL是字符串，直接使用
            elif isinstance(sql, str):
                sql_to_check = sql
            else:
                # 其他类型，跳过处理
                continue
                
            extractor.extract(sql_to_check)
            tables = list(extractor.table_count_dict.keys())
            query_type = extractor.stmt_type
            
            # 检查是否有表名匹配
            table_matched = False
            for table in tables:
                if table in csv_table_index:
                    table_matched = True
                    table_match_count += 1
                    
                    # 检查表名+查询类型匹配
                    table_type_key = f"{table}_{query_type}"
                    if table_type_key in csv_table_query_type_index:
                        # 找到了表名+查询类型匹配
                        table_type_match_count += 1
                        
                        # 记录匹配结果
                        csv_matches = csv_table_query_type_index[table_type_key]
                        for csv_fingerprint, csv_sql in csv_matches[:1]:  # 只取第一个匹配
                            match_data = {
                                "json_sql": sql_to_check,
                                "csv_sql": csv_sql,
                                "json_fingerprint": fingerprint,
                                "csv_fingerprint": csv_fingerprint,
                                "function_name": function_name,
                                "table": table,
                                "query_type": query_type,
                                "match_type": "table_and_type"
                            }
                            table_matches.append(match_data)
                            matched_sql_ids.add(i)
                            break
                    else:
                        # 只有表名匹配，查询类型不匹配
                        csv_matches = csv_table_index[table]
                        for csv_fingerprint, csv_sql in csv_matches[:1]:  # 只取第一个匹配
                            match_data = {
                                "json_sql": sql_to_check,
                                "csv_sql": csv_sql,
                                "json_fingerprint": fingerprint,
                                "csv_fingerprint": csv_fingerprint,
                                "function_name": function_name,
                                "table": table,
                                "json_query_type": query_type,
                                "match_type": "table_only"
                            }
                            table_matches.append(match_data)
                            matched_sql_ids.add(i)
                            break
                    
                    break  # 只要找到一个表匹配就退出循环
            
            if not table_matched:
                no_table_match_count += 1
        except Exception as e:
            print(f"处理SQL匹配时出错: {str(e)}")
            continue
    
    # 不在process_json_and_compare中输出统计信息，只返回结果值
    return table_matches, no_table_match_count, table_match_count, table_type_match_count

def extract_tables_from_fingerprints(fingerprint_to_sql, output_path):
    """
    从指纹对应的SQL中提取所有表名，并保存为JSON文件
    
    参数:
        fingerprint_to_sql: 指纹到SQL的映射字典
        output_path: 输出JSON文件路径
    
    返回:
        fingerprint_to_tables: 指纹到表名的映射字典
    """
    print("开始从指纹中提取表名...")
    fingerprint_to_tables = {}
    all_tables = set()  # 用于统计所有不同的表名
    table_frequency = {}  # 用于统计表名出现频率
    
    # 处理每个指纹
    for fingerprint, sql_list in tqdm(fingerprint_to_sql.items(), desc="提取表名"):
        tables_for_fingerprint = set()
        
        # 对每个指纹最多处理10条SQL样本
        for sql in sql_list[:10]:
            # 移除SQL注释
            sql = re.sub(r'/\*.*?\*/', '', sql)
            
            extractor = SQLFeatureExtractor()
            try:
                extractor.extract(sql)
                # 将该SQL中的表名添加到集合中
                tables_for_fingerprint.update(extractor.table_count_dict.keys())
                
                # 更新表名频率统计
                for table in extractor.table_count_dict.keys():
                    if table not in table_frequency:
                        table_frequency[table] = 0
                    table_frequency[table] += 1
            except Exception as e:
                continue
        
        # 只保存非空的表名集合
        if tables_for_fingerprint:
            fingerprint_to_tables[fingerprint] = list(tables_for_fingerprint)
            all_tables.update(tables_for_fingerprint)
    
    # 保存到JSON文件
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(fingerprint_to_tables, f, ensure_ascii=False, indent=2)
    
    print(f"表名提取完成，共发现 {len(all_tables)} 个不同的表名")
    print(f"指纹到表名的映射已保存到: {output_path}")
    
    # 额外保存所有表名的列表（按频率排序）
    all_tables_list = sorted(table_frequency.items(), key=lambda x: x[1], reverse=True)
    all_tables_path = output_path.replace(".json", "_list.json")
    with open(all_tables_path, "w", encoding="utf-8") as f:
        json.dump(all_tables_list, f, ensure_ascii=False, indent=2)
    
    print(f"所有表名列表（按频率排序）已保存到: {all_tables_path}")
    
    # 额外保存表名频率统计
    table_frequency_path = output_path.replace(".json", "_frequency.json")
    with open(table_frequency_path, "w", encoding="utf-8") as f:
        json.dump(table_frequency, f, ensure_ascii=False, indent=2)
    
    print(f"表名频率统计已保存到: {table_frequency_path}")
    
    return fingerprint_to_tables

def extract_unmatched_csv_fingerprints(csv_fingerprints, matched_fingerprints, fingerprint_to_sql, output_path):
    """
    提取未被JSON文件匹配上的CSV指纹及示例SQL语句，保存为JSON文件
    
    参数:
        csv_fingerprints: CSV文件中的所有有效指纹集合
        matched_fingerprints: 已被匹配上的指纹集合
        fingerprint_to_sql: 指纹到SQL语句的映射
        output_path: 输出JSON文件路径
    """
    print("开始提取未被匹配的CSV指纹...")
    
    # 计算未匹配的指纹
    unmatched_fingerprints = csv_fingerprints - matched_fingerprints
    
    # 排除无效指纹类型
    excluded_fingerprints = {
        "transaction_begin",
        "transaction_end",
        "session_setting",
        "show_command",
        "ddl_command",
        "empty_sql",
        "not_sql",
        "invalid_sql"
    }
    system_function_prefixes = ["system_function_"]
    
    valid_unmatched_fingerprints = set()
    for fp in unmatched_fingerprints:
        if fp not in excluded_fingerprints and not any(fp.startswith(prefix) for prefix in system_function_prefixes):
            valid_unmatched_fingerprints.add(fp)
    
    print(f"未匹配的有效CSV指纹数量: {len(valid_unmatched_fingerprints)}")
    
    # 构建输出数据结构
    result = []
    for fingerprint in valid_unmatched_fingerprints:
        if fingerprint in fingerprint_to_sql:
            # 最多取5条示例SQL
            examples = fingerprint_to_sql[fingerprint][:1]
            # if len(examples) == 5:  
            result.append({
                    "fingerprint": fingerprint,
                    "sql_examples": examples,
                    "example_count": len(examples)
                })
    
    # 按指纹字典序排序
    result.sort(key=lambda x: x["fingerprint"])
    
    # 保存为JSON文件
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "unmatched_count": len(valid_unmatched_fingerprints),
            "unmatched_fingerprints": result
        }, f, ensure_ascii=False, indent=2)
    
    print(f"未匹配的CSV指纹及示例SQL已保存到: {output_path}")
    return valid_unmatched_fingerprints
    
def get_fingerprint_coverage(human_review=False, output_dir="model/evaluation/fingerprint_eval/results"):
    target_fingerprint_cache = FINGERPRINT_CACHE_HUMAN if human_review else FINGERPRINT_CACHE
    csv_path=CSV_PATH
    # csv_path=['/data/local_disk0/shawn/dirty_work/redis.csv','/data/local_disk0/shawn/dirty_work/redis01.csv']
    # 检查是否已经有预先计算的指纹
    if os.path.exists(target_fingerprint_cache):
        print(f"发现预先计算的指纹缓存文件: {target_fingerprint_cache}")
        csv_fingerprints, fingerprint_to_sql = load_fingerprints(target_fingerprint_cache)
    else:
        print("未找到指纹缓存，开始处理CSV文件...")
        # 添加命令行参数支持，允许只处理部分数据进行测试
        import sys
        sample_size = None
        if len(sys.argv) > 1 and sys.argv[1].isdigit():
            sample_size = int(sys.argv[1])
            print(f"将只处理 {sample_size} 条SQL语句进行测试")
        
        csv_fingerprints, fingerprint_to_sql = process_csv_and_save_fingerprints(csv_path, target_fingerprint_cache)
    
    # 提取所有表名并保存
    tables_output_path = os.path.join(output_dir, "fingerprint_tables_w_human.json" if human_review else "fingerprint_tables.json")
    fingerprint_to_tables = extract_tables_from_fingerprints(fingerprint_to_sql, tables_output_path)
    
    # 处理JSON文件并比较
    process_result = process_json_and_compare(
        JSON_PATH, 
        csv_fingerprints, 
        output_dir=output_dir,
        fingerprint_to_sql=fingerprint_to_sql, 
        sql_key="sql_statement_list",
        human_review=human_review
    )
    if process_result is None:
        return None
    
    matching_lines, matching_pairs, matched_fingerprints, total_lines, valid_sql_count, matching_count, unmatched_pairs,excluded_sql_count,csv_fingerprints,full_sql_cnt_official = process_result
    
    try:
        # 使用当前生成的unmatched_pairs，而不是从文件加载
        print(f"\n开始分析 {len(unmatched_pairs)} 条未匹配的SQL语句")
        
        # 对未匹配SQL进行表名匹配分析
        table_matches, no_table_match_count, table_match_count, table_type_match_count = find_table_name_matches(unmatched_pairs, fingerprint_to_sql)
        
        # 明确保存表名+查询类型匹配的结果到单独的文件
        table_type_matches = [match for match in table_matches if match.get("match_type") == "table_and_type"]
        detailed_output_path = os.path.join(output_dir, "table_type_matches_detailed_w_human.json" if human_review else "table_type_matches_detailed.json")
        with open(detailed_output_path, "w", encoding="utf-8") as f:
            json.dump({
                "matches": table_type_matches,
                "statistics": {
                    "total": table_type_match_count,
                }
            }, f, ensure_ascii=False, indent=2)
        print(f"\n表名+查询类型匹配SQL详细信息已保存到: {detailed_output_path}")
        
        # 统一输出完整的SQL匹配统计 
        print(f"\n======= SQL匹配统计结果 =======")
        print(f"  - 完全指纹匹配: {matching_count}条 ({matching_count/valid_sql_count:.2%})")
        print(f"  - 表名匹配但不完全匹配指纹: {table_match_count}条 ({table_match_count/valid_sql_count:.2%})")
        print(f"  - 表名+查询类型匹配: {table_type_match_count}条 ({table_type_match_count/valid_sql_count:.2%})")
        print(f"  - 表名不在CSV中的SQL: {no_table_match_count}条 ({no_table_match_count/valid_sql_count:.2%})")
        print(f"  - 总SQL数: {valid_sql_count}条")
        print(f"  - 代码提取计算总SQL数: {full_sql_cnt_official}条")
        # 计算调整后的匹配率
        valid_denominator = valid_sql_count - no_table_match_count
        if valid_denominator > 0:
            adjusted_match_ratio = matching_count / valid_denominator
            print(f"\n调整后匹配比例 (排除表名不存在的SQL):")
            print(f"  - {adjusted_match_ratio:.2%} ({matching_count}/{valid_denominator})")
        
        # 计算综合匹配率
        comprehensive_match_count = matching_count + table_type_match_count
        if valid_sql_count > 0:
            comprehensive_ratio = comprehensive_match_count / valid_sql_count
            print(f"\n综合匹配率 (指纹匹配+表名和查询类型匹配):")
            print(f"  - {comprehensive_ratio:.2%} ({comprehensive_match_count}/{valid_sql_count})")
        
        # 添加: 提取未匹配的CSV指纹并保存
        unmatched_csv_output_path = os.path.join(output_dir, "unmatched_csv_fingerprints_w_human.json" if human_review else "unmatched_csv_fingerprints.json")
        extract_unmatched_csv_fingerprints(csv_fingerprints, matched_fingerprints, fingerprint_to_sql, unmatched_csv_output_path)
        
        # 添加: 计算指纹覆盖率
        coverage, matched_fingerprint_count, valid_fingerprint_count = calculate_fingerprint_coverage(matched_fingerprints, csv_fingerprints)
        
        print(f"\n======= 指纹覆盖率统计 =======")
        print(f"  - 有效CSV指纹总数: {valid_fingerprint_count}个")
        print(f"  - 已匹配CSV指纹数: {matched_fingerprint_count}个")
        print(f"  - 指纹覆盖率: {coverage:.2%} ({matched_fingerprint_count}/{valid_fingerprint_count})")
        
        # 保存指纹覆盖率信息到JSON文件
        coverage_output_path = os.path.join(output_dir, "fingerprint_coverage_w_human.json" if human_review else "fingerprint_coverage.json")
        with open(coverage_output_path, "w", encoding="utf-8") as f:
            json.dump({
                "valid_fingerprint_count": valid_fingerprint_count,
                "matched_fingerprint_count": matched_fingerprint_count,
                "coverage": coverage,
                "coverage_percentage": f"{coverage:.2%}",
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            }, f, ensure_ascii=False, indent=2)
        print(f"指纹覆盖率信息已保存到: {coverage_output_path}")
        
        # 添加: 按SQL语句类型划分的指纹覆盖率，并提取OTHER类型的SQL
        sql_type_coverage, other_type_sql_examples = analyze_sql_type_coverage(matched_fingerprints, csv_fingerprints, fingerprint_to_sql)
        
        print(f"\n======= 按SQL语句类型的指纹覆盖率 =======")
        for sql_type, stats in sql_type_coverage.items():
            print(f"  - {sql_type}: {stats['coverage']:.2%} ({stats['matched']}/{stats['total']})")
        all_sql_count = valid_sql_count + excluded_sql_count
        # 保存按SQL类型划分的指纹覆盖率信息
        type_coverage_output_path = os.path.join(output_dir, "fingerprint_coverage_by_type_w_human.json" if human_review else "fingerprint_coverage_by_type.json")
        with open(type_coverage_output_path, "w", encoding="utf-8") as f:
            json.dump(sql_type_coverage, f, ensure_ascii=False, indent=2)
        print(f"按SQL语句类型的指纹覆盖率信息已保存到: {type_coverage_output_path}")
        return total_lines,matching_lines,all_sql_count,valid_sql_count,matching_count,table_match_count,matched_fingerprint_count,valid_fingerprint_count,len(csv_fingerprints),full_sql_cnt_official
    except Exception as e:
        print(f"处理未匹配SQL时出错: {e}")
        return None

def main():
    coverage_result = get_fingerprint_coverage()
    if coverage_result is None:
        print("获取覆盖率失败，退出程序。")
        return
        
    total_lines,matching_lines,all_sql_count,valid_sql_count,matching_count,table_match_count,matched_fingerprint_count,valid_fingerprint_count ,csv_fingerprints_count,full_sql_cnt_official = coverage_result

    print("=================================")
    print("========= 人工review结果 ==========")
    print("==================================")
    
    human_review_result = get_fingerprint_coverage(human_review=True)
    if human_review_result is None:
        print("获取人工review覆盖率失败，退出程序。")
        return
        
    human_review_total_lines,human_review_matching_lines,human_review_all_sql_count,human_review_valid_sql_count,human_review_matching_count,human_review_table_match_count,human_review_matched_fingerprint_count,human_review_valid_fingerprint_count,human_review_csv_fingerprints_count,human_review_full_sql_cnt_official = human_review_result
    
    print(f"\n========== 最终完整结果 ==========")
    print(f"代码chunk数: {total_lines}")
    print(f"有匹配的行数: {matching_lines}")
    print(f"代码提取总SQL数: {full_sql_cnt_official}")
    print(f"生成SQL数: {all_sql_count}")
    print(f"有效SQL数: {valid_sql_count}")
    print(f"命中表名有效SQL数: {table_match_count+matching_count}")
    print(f"命中指纹有效SQL数: {matching_count}")
    print(f"SQL生成率: {all_sql_count/full_sql_cnt_official:.2%}")
    print(f"SQL有效率: {valid_sql_count/all_sql_count:.2%}")
    print(f"表名命中率: {(table_match_count+matching_count)/valid_sql_count:.2%}")
    print(f"指纹命中率: {matching_count/valid_sql_count:.2%}")
    print(f"人工review判命中SQL数: {human_review_matching_count-matching_count}")
    print(f"总命中SQL数: {human_review_matching_count}")
    print(f"修正指纹命中率: {human_review_matching_count/human_review_valid_sql_count:.2%}")
    print(f"审计日志指纹数: {valid_fingerprint_count}")
    print(f"审计日志指纹覆盖数: {matched_fingerprint_count}")
    print(f"审计日志指纹覆盖率: {matched_fingerprint_count/valid_fingerprint_count:.2%}")
    print(f"人工review指纹数: {human_review_valid_fingerprint_count}")
    print(f"人工review指纹覆盖数: {human_review_matched_fingerprint_count-matched_fingerprint_count}")
    print(f"修正指纹覆盖率: {human_review_matched_fingerprint_count/human_review_valid_fingerprint_count:.2%}")

def test():
    extractor = SQLFeatureExtractor()
    sql_text1 = """UPDATE dmc_download_config SET external_download = true, vpc_ids = '', ips = '', include_ips = ?, uin = ?, sub_uin = ? WHERE app_id = ?;"""
    
    sql_text2 = """SELECT COUNT(*) FROM work_order wo LEFT JOIN meta_resource mr ON wo.resource_id = mr.resource_id LEFT JOIN c_resource cr ON wo.resource_id = cr.resource_id WHERE wo.app_id = 123 AND wo.uin = 'test_uin' AND wo.sub_account_uin = 'test_sub_uin' AND wo.work_order_id IN ('wo1', 'wo2');"""
    print("SQL1处理:")
    hash_value1 = extractor.extract(sql_text1)
    print("投影字典:", extractor.projection_count_dict)
    print("表字典:", extractor.table_count_dict)
    print("谓词字典:", extractor.predicate_count_dict)

    extractor = SQLFeatureExtractor()  # 重置提取器
    print("\nSQL2处理:")
    hash_value2 = extractor.extract(sql_text2)
    print("投影字典:", extractor.projection_count_dict)
    print("表字典:", extractor.table_count_dict)
    print("谓词字典:", extractor.predicate_count_dict)

    print(hash_value1==hash_value2)

def match_single_sql(sql_text, fingerprint_cache_path=FINGERPRINT_CACHE):
    """
    将单条SQL语句与缓存的指纹进行匹配，并返回匹配结果
    
    参数:
        sql_text: 要匹配的SQL语句
        fingerprint_cache_path: 指纹缓存文件路径
        
    返回:
        dict: 包含匹配结果的字典，格式如下:
            {
                "matched": 布尔值，表示是否匹配成功,
                "fingerprint": 匹配的指纹（如果匹配成功）,
                "example_sql": 与该指纹匹配的示例SQL（如果匹配成功）,
                "excluded": 布尔值，表示SQL是否被排除（如无效SQL等）,
                "excluded_reason": 被排除的原因（如果被排除）
            }
    """
    # 加载指纹缓存
    if not os.path.exists(fingerprint_cache_path):
        return {
            "matched": False,
            "error": "指纹缓存文件不存在"
        }
    
    try:
        with open(fingerprint_cache_path, 'rb') as f:
            data = pickle.load(f)
            if isinstance(data, tuple) and len(data) == 2:
                csv_fingerprints, fingerprint_to_sql = data
            else:
                # 兼容旧格式
                csv_fingerprints = data
                fingerprint_to_sql = {}
    except Exception as e:
        return {
            "matched": False,
            "error": f"加载指纹缓存失败: {str(e)}"
        }
    
    # 排除的指纹类型
    excluded_fingerprints = {
        "transaction_begin",
        "transaction_end", 
        "session_setting",
        "show_command",
        "ddl_command",
        "empty_sql", 
        "not_sql",
        "invalid_sql"
    }
    
    # 计算SQL的指纹
    extractor = SQLFeatureExtractor()
    fingerprint = extractor.extract(sql_text)
    
    # 检查是否是被排除的类型
    if fingerprint in excluded_fingerprints or any(fingerprint.startswith(prefix) for prefix in ["invalid_sql_", "session_setting"]):
        return {
            "matched": False,
            "excluded": True,
            "fingerprint": fingerprint,
            "excluded_reason": "排除的SQL类型"
        }
    
    # 检查是否匹配
    if fingerprint in csv_fingerprints:
        result = {
            "matched": True,
            "fingerprint": fingerprint
        }
        
        # 如果有示例SQL，添加到结果中
        if fingerprint_to_sql and fingerprint in fingerprint_to_sql and fingerprint_to_sql[fingerprint]:
            result["example_sql"] = fingerprint_to_sql[fingerprint][0]  # 取第一个示例
            
            # 如果有多个示例，添加示例数量信息
            if len(fingerprint_to_sql[fingerprint]) > 1:
                result["example_count"] = len(fingerprint_to_sql[fingerprint])
        
        return result
    else:
        return {
            "matched": False,
            "fingerprint": fingerprint,
            "excluded": False
        }

def analyze_sql_type_coverage(matched_fingerprints, csv_fingerprints, fingerprint_to_sql):
    """
    分析不同类型SQL语句的指纹覆盖率
    
    参数:
        matched_fingerprints: 已被JSON匹配上的CSV指纹集合
        csv_fingerprints: CSV文件中的所有指纹集合
        fingerprint_to_sql: 指纹到SQL语句的映射
    
    返回:
        tuple: (按SQL类型分类的覆盖率统计, OTHER类型SQL示例字典)
    """
    # 排除无效指纹类型
    excluded_fingerprints = {
        "transaction_begin",
        "transaction_end",
        "session_setting",
        "show_command",
        "ddl_command",
        "empty_sql",
        "not_sql",
        "invalid_sql"
    }
    system_function_prefixes = ["system_function_"]
    
    # 定义SQL类型
    sql_types = {
        "SELECT": [],
        "INSERT": [],
        "UPDATE": [],
        "DELETE": [],
        "OTHER": []
    }
    
    # 收集OTHER类型的SQL示例
    other_type_sql_examples = {}
    
    # 根据指纹分类SQL类型
    for fp in csv_fingerprints:
        if fp in excluded_fingerprints or any(fp.startswith(prefix) for prefix in system_function_prefixes):
            continue
        
        # 用于确定SQL类型的函数
        def determine_sql_type(sql_text):
            if not sql_text:
                return "OTHER"
            
            # 移除SQL注释
            # 移除/* */形式的注释
            sql_no_comment = re.sub(r'/\*.*?\*/', '', sql_text)
            # 移除-- 形式的注释
            sql_no_comment = re.sub(r'--.*?$', '', sql_no_comment, flags=re.MULTILINE)
            
            # 去除首尾空白
            sql_no_comment = sql_no_comment.strip()
            
            # 检查清理后的SQL
            if not sql_no_comment:
                return "OTHER"
                
            sql_lower = sql_no_comment.lower()
            
            if sql_lower.startswith("select"):
                return "SELECT"
            elif sql_lower.startswith("insert"):
                return "INSERT"
            elif sql_lower.startswith("update"):
                return "UPDATE"
            elif sql_lower.startswith("delete"):
                return "DELETE"
            # 添加对ROLLBACK语句的处理
            elif sql_lower.startswith("rollback"):
                return "TRANSACTION"
            # 添加对SAVEPOINT语句的处理
            elif sql_lower.startswith("savepoint"):
                return "TRANSACTION"
            # 添加对信息查询语句的处理
            elif "information_schema" in sql_lower:
                return "SCHEMA_INFO"
            else:
                return "OTHER"
        
        # 获取该指纹对应的SQL示例
        sql_example = ""
        if fp in fingerprint_to_sql and fingerprint_to_sql[fp]:
            sql_example = fingerprint_to_sql[fp][0]
            sql_type = determine_sql_type(sql_example)
        else:
            # 如果没有SQL示例，无法确定类型
            sql_type = "OTHER"
        
        # 将指纹添加到对应类型
        # 为TRANSACTION和SCHEMA_INFO类型创建新类别
        if sql_type == "TRANSACTION" or sql_type == "SCHEMA_INFO":
            if sql_type not in sql_types:
                sql_types[sql_type] = []
            sql_types[sql_type].append(fp)
        else:
            sql_types[sql_type].append(fp)
        
        # 如果是OTHER类型，收集其SQL示例
        if sql_type == "OTHER":
            is_matched = fp in matched_fingerprints
            other_type_sql_examples[fp] = {
                "fingerprint": fp,
                "sql_example": sql_example,
                "is_matched": is_matched
            }
    
    # 计算每种类型的匹配情况
    result = {}
    for sql_type, fingerprints in sql_types.items():
        total = len(fingerprints)
        if total == 0:
            continue
            
        matched = len([fp for fp in fingerprints if fp in matched_fingerprints])
        coverage = matched / total if total > 0 else 0
        
        result[sql_type] = {
            "total": total,
            "matched": matched,
            "coverage": coverage,
            "coverage_percentage": f"{coverage:.2%}"
        }
    
    # 添加总体统计
    valid_fps = [fp for fp in csv_fingerprints 
                if fp not in excluded_fingerprints and 
                not any(fp.startswith(prefix) for prefix in system_function_prefixes)]
    total = len(valid_fps)
    matched = len([fp for fp in valid_fps if fp in matched_fingerprints])
    coverage = matched / total if total > 0 else 0
    
    result["ALL"] = {
        "total": total,
        "matched": matched,
        "coverage": coverage,
        "coverage_percentage": f"{coverage:.2%}"
    }
    
    return result, other_type_sql_examples

def calculate_fingerprint_coverage(matched_fingerprints, csv_fingerprints):
    """
    计算指纹覆盖率：已匹配的CSV指纹数量与有效CSV指纹总数的比例
    
    参数:
        matched_fingerprints: 已被JSON匹配上的CSV指纹集合
        csv_fingerprints: CSV文件中的所有指纹集合
    
    返回:
        tuple: (覆盖率, 已匹配指纹数, 有效指纹总数)
    """
    # 排除无效指纹类型
    excluded_fingerprints = {
        "transaction_begin",
        "transaction_end",
        "session_setting",
        "show_command",
        "ddl_command",
        "empty_sql",
        "not_sql",
        "invalid_sql"
    }
    system_function_prefixes = ["system_function_"]
    
    # 计算有效指纹总数
    valid_csv_fingerprints = set()
    for fp in csv_fingerprints:
        if fp not in excluded_fingerprints and not any(fp.startswith(prefix) for prefix in system_function_prefixes):
            valid_csv_fingerprints.add(fp)
    
    # 计算有效的已匹配指纹数量
    valid_matched_fingerprints = set()
    for fp in matched_fingerprints:
        if fp not in excluded_fingerprints and not any(fp.startswith(prefix) for prefix in system_function_prefixes):
            valid_matched_fingerprints.add(fp)
    
    # 计算覆盖率
    valid_fingerprint_count = len(valid_csv_fingerprints)
    matched_fingerprint_count = len(valid_matched_fingerprints)
    
    coverage = matched_fingerprint_count / valid_fingerprint_count if valid_fingerprint_count > 0 else 0
    
    return coverage, matched_fingerprint_count, valid_fingerprint_count

# 如果直接运行此文件，则执行主函数
if __name__ == "__main__":
    main()
    # test()
