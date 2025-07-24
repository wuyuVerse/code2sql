"""
格式验证器模块

提供常用的LLM响应格式验证函数
"""
import json
import re
import logging
from typing import Dict, Any, Union, List, Optional, Callable

logger = logging.getLogger(__name__)


def validate_json_format(response: str) -> Union[bool, Dict[str, Any]]:
    """验证JSON格式
    
    Args:
        response: LLM响应内容
        
    Returns:
        True表示格式正确，Dict包含验证结果和错误信息
    """
    try:
        # 尝试直接解析JSON
        json.loads(response)
        return True
    except json.JSONDecodeError:
        # 尝试提取JSON内容
        json_match = re.search(r'```json\s*({.*?})\s*```', response, re.DOTALL)
        if json_match:
            try:
                json.loads(json_match.group(1))
                return True
            except json.JSONDecodeError as e:
                return {
                    'valid': False,
                    'error': f'JSON格式错误: {str(e)}',
                    'extracted_content': json_match.group(1)
                }
        
        # 尝试提取大括号内容
        brace_match = re.search(r'({.*})', response, re.DOTALL)
        if brace_match:
            try:
                json.loads(brace_match.group(1))
                return True
            except json.JSONDecodeError as e:
                return {
                    'valid': False,
                    'error': f'JSON格式错误: {str(e)}',
                    'extracted_content': brace_match.group(1)
                }
        
        return {
            'valid': False,
            'error': '未找到有效的JSON内容',
            'response': response[:200]
        }


def validate_boolean_response(response: str, expected_keywords: Optional[List[str]] = None) -> Union[bool, Dict[str, Any]]:
    """验证布尔值响应格式
    
    Args:
        response: LLM响应内容
        expected_keywords: 期望的关键词列表
        
    Returns:
        True表示格式正确，Dict包含验证结果
    """
    if not response:
        return {
            'valid': False,
            'error': '响应为空'
        }
    
    response_lower = response.strip().lower()
    
    # 检查是否包含明确的布尔值
    if '是' in response_lower or 'yes' in response_lower or 'true' in response_lower:
        return True
    elif '否' in response_lower or 'no' in response_lower or 'false' in response_lower:
        return True
    
    # 检查特定关键词
    if expected_keywords:
        for keyword in expected_keywords:
            if keyword.lower() in response_lower:
                return True
    
    return {
        'valid': False,
        'error': f'响应内容不包含明确的布尔值: {response[:100]}',
        'response': response
    }


def validate_structured_response(response: str, required_fields: Optional[List[str]] = None) -> Union[bool, Dict[str, Any]]:
    """验证结构化响应格式
    
    Args:
        response: LLM响应内容
        required_fields: 必需字段列表
        
    Returns:
        True表示格式正确，Dict包含验证结果
    """
    # 首先验证JSON格式
    json_result = validate_json_format(response)
    if json_result is True:
        # 尝试解析JSON
        try:
            if '```json' in response:
                json_match = re.search(r'```json\s*({.*?})\s*```', response, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group(1))
                else:
                    return {
                        'valid': False,
                        'error': '未找到JSON内容',
                        'response': response[:200]
                    }
            else:
                data = json.loads(response)
            
            # 检查必需字段
            if required_fields:
                missing_fields = []
                for field in required_fields:
                    if field not in data:
                        missing_fields.append(field)
                
                if missing_fields:
                    return {
                        'valid': False,
                        'error': f'缺少必需字段: {missing_fields}',
                        'data': data
                    }
            
            return True
        except Exception as e:
            return {
                'valid': False,
                'error': f'解析结构化响应失败: {str(e)}',
                'response': response[:200]
            }
    else:
        return json_result


def validate_list_format(response: str, item_validator: Optional[Callable] = None) -> Union[bool, Dict[str, Any]]:
    """验证列表格式
    
    Args:
        response: LLM响应内容
        item_validator: 列表项验证函数
        
    Returns:
        True表示格式正确，Dict包含验证结果
    """
    # 首先验证JSON格式
    json_result = validate_json_format(response)
    if json_result is True:
        try:
            if '```json' in response:
                json_match = re.search(r'```json\s*(\[.*?\])\s*```', response, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group(1))
                else:
                    return {
                        'valid': False,
                        'error': '未找到JSON列表内容',
                        'response': response[:200]
                    }
            else:
                data = json.loads(response)
            
            if not isinstance(data, list):
                return {
                    'valid': False,
                    'error': '响应不是列表格式',
                    'data': data
                }
            
            # 验证列表项
            if item_validator:
                for i, item in enumerate(data):
                    item_result = item_validator(item)
                    if not item_result:
                        return {
                            'valid': False,
                            'error': f'列表项 {i} 验证失败',
                            'item': item
                        }
            
            return True
        except Exception as e:
            return {
                'valid': False,
                'error': f'解析列表格式失败: {str(e)}',
                'response': response[:200]
            }
    else:
        return json_result


def validate_sql_completeness_response(response: str) -> Union[bool, Dict[str, Any]]:
    """验证SQL完整性检查响应
    
    Args:
        response: LLM响应内容
        
    Returns:
        True表示格式正确，Dict包含验证结果
    """
    if not response:
        return {
            'valid': False,
            'error': '响应为空'
        }
    
    response_lower = response.strip().lower()
    
    # 检查是否包含明确的判断
    if response_lower.startswith('是') or response_lower.startswith('否'):
        return True
    
    # 检查是否包含原因说明
    if '，' in response or ',' in response:
        return True
    
    return {
        'valid': False,
        'error': f'响应格式不符合SQL完整性检查要求: {response[:100]}',
        'response': response
    }


def validate_sql_correctness_response(response: str) -> Union[bool, Dict[str, Any]]:
    """验证SQL正确性检查响应
    
    Args:
        response: LLM响应内容
        
    Returns:
        True表示格式正确，Dict包含验证结果
    """
    if not response:
        return {
            'valid': False,
            'error': '响应为空'
        }
    
    response_lower = response.strip().lower()
    
    # 检查是否包含明确的判断
    if response_lower.startswith('是') or response_lower.startswith('否'):
        return True
    
    # 检查是否包含原因说明
    if '，' in response or ',' in response:
        return True
    
    return {
        'valid': False,
        'error': f'响应格式不符合SQL正确性检查要求: {response[:100]}',
        'response': response
    }


def validate_keyword_extraction_response(response: str) -> Union[bool, Dict[str, Any]]:
    """
    严格验证关键词提取响应，只允许两种格式：
    1. "No" 或 'No'（允许前后空白、单双引号）
    2. JSON数组字符串，如 ["Preload", "Transaction"]
    """
    import json
    if not response or not isinstance(response, str):
        return {'valid': False, 'error': '响应为空或非字符串'}

    resp = response.strip()
    # 允许 "No" 或 'No'，不区分单双引号
    if resp in ('"No"', "'No'", 'No'):
        return True

    # 必须是JSON数组
    try:
        arr = json.loads(resp)
        if isinstance(arr, list) and all(isinstance(x, str) for x in arr):
            return True
        else:
            return {'valid': False, 'error': f'不是字符串数组: {response[:100]}'}
    except Exception:
        return {'valid': False, 'error': f'响应格式不符合要求，只能是\"No\"或JSON关键词数组: {response[:100]}'}


def validate_redundant_sql_validation_response(response: str) -> Union[bool, Dict[str, Any]]:
    """验证冗余SQL验证响应
    
    Args:
        response: LLM响应内容
        
    Returns:
        True表示格式正确，Dict包含验证结果
    """
    # 首先尝试JSON格式验证
    json_result = validate_json_format(response)
    if json_result is True:
        return True
    
    # 如果不是JSON，检查是否包含明确的判断
    response_lower = response.strip().lower()
    if '是，冗余' in response_lower or '否，不冗余' in response_lower:
        return True
    
    return {
        'valid': False,
        'error': f'响应格式不符合冗余SQL验证要求: {response[:100]}',
        'response': response
    }


def validate_control_flow_validation_response(response: str) -> Union[bool, Dict[str, Any]]:
    """验证控制流验证响应
    
    Args:
        response: LLM响应内容
        
    Returns:
        True表示格式正确，Dict包含验证结果
    """
    # 首先尝试JSON格式验证
    json_result = validate_json_format(response)
    if json_result is True:
        return True
    
    # 如果不是JSON，检查是否包含明确的判断
    response_lower = response.strip().lower()
    if '合理' in response_lower or '不合理' in response_lower:
        return True
    
    return {
        'valid': False,
        'error': f'响应格式不符合控制流验证要求: {response[:100]}',
        'response': response
    }


def validate_control_flow_sql_regeneration_response(response: str) -> Union[bool, Dict[str, Any]]:
    """验证控制流SQL重新生成响应
    
    Args:
        response: LLM响应内容
        
    Returns:
        True表示格式正确，Dict包含验证结果
    """
    # 首先尝试JSON数组格式验证
    json_result = validate_json_format(response)
    if json_result is True:
        try:
            # 尝试解析JSON数组
            if '```json' in response:
                json_match = re.search(r'```json\s*(\[.*?\])\s*```', response, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group(1))
                else:
                    return {
                        'valid': False,
                        'error': '未找到JSON数组内容',
                        'response': response[:200]
                    }
            else:
                data = json.loads(response)
            
            if not isinstance(data, list):
                return {
                    'valid': False,
                    'error': '响应不是JSON数组格式',
                    'data': data
                }
            
            # 验证数组中的每个元素
            for i, item in enumerate(data):
                if isinstance(item, str):
                    # 字符串应该是SQL语句
                    if not item.strip().endswith(';'):
                        return {
                            'valid': False,
                            'error': f'SQL语句 {i} 必须以分号结尾',
                            'item': item
                        }
                elif isinstance(item, dict):
                    # 字典应该是param_dependent类型
                    if item.get('type') != 'param_dependent':
                        return {
                            'valid': False,
                            'error': f'字典项 {i} 类型不是param_dependent',
                            'item': item
                        }
                    
                    variants = item.get('variants', [])
                    if not isinstance(variants, list):
                        return {
                            'valid': False,
                            'error': f'字典项 {i} 缺少variants数组',
                            'item': item
                        }
                    
                    for j, variant in enumerate(variants):
                        if not isinstance(variant, dict):
                            return {
                                'valid': False,
                                'error': f'变体 {j} 不是字典格式',
                                'variant': variant
                            }
                        
                        if 'scenario' not in variant or 'sql' not in variant:
                            return {
                                'valid': False,
                                'error': f'变体 {j} 缺少scenario或sql字段',
                                'variant': variant
                            }
                        
                        if not variant['sql'].strip().endswith(';'):
                            return {
                                'valid': False,
                                'error': f'变体 {j} 的SQL必须以分号结尾',
                                'variant': variant
                            }
                else:
                    return {
                        'valid': False,
                        'error': f'数组项 {i} 格式不正确',
                        'item': item
                    }
            
            return True
        except Exception as e:
            return {
                'valid': False,
                'error': f'解析控制流SQL重新生成响应失败: {str(e)}',
                'response': response[:200]
            }
    else:
        return json_result


def validate_sql_generation_response(response: str) -> Union[bool, Dict[str, Any]]:
    """验证SQL生成响应
    
    Args:
        response: LLM响应内容
        
    Returns:
        True表示格式正确，Dict包含验证结果
    """
    # 首先尝试JSON数组格式验证
    json_result = validate_json_format(response)
    if json_result is True:
        try:
            # 尝试解析JSON数组
            if '```json' in response:
                json_match = re.search(r'```json\s*(\[.*?\])\s*```', response, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group(1))
                else:
                    return {
                        'valid': False,
                        'error': '未找到JSON数组内容',
                        'response': response[:200]
                    }
            else:
                data = json.loads(response)
            
            if not isinstance(data, list):
                return {
                    'valid': False,
                    'error': '响应不是JSON数组格式',
                    'data': data
                }
            
            # 验证数组中的每个元素
            for i, item in enumerate(data):
                if isinstance(item, str):
                    # 字符串应该是SQL语句
                    if not item.strip().endswith(';'):
                        return {
                            'valid': False,
                            'error': f'SQL语句 {i} 必须以分号结尾',
                            'item': item
                        }
                elif isinstance(item, dict):
                    # 检查字典类型
                    item_type = item.get('type')
                    if item_type == 'param_dependent':
                        # param_dependent类型验证
                        variants = item.get('variants', [])
                        if not isinstance(variants, list):
                            return {
                                'valid': False,
                                'error': f'字典项 {i} 缺少variants数组',
                                'item': item
                            }
                        
                        for j, variant in enumerate(variants):
                            if not isinstance(variant, dict):
                                return {
                                    'valid': False,
                                    'error': f'变体 {j} 不是字典格式',
                                    'variant': variant
                                }
                            
                            if 'scenario' not in variant or 'sql' not in variant:
                                return {
                                    'valid': False,
                                    'error': f'变体 {j} 缺少scenario或sql字段',
                                    'variant': variant
                                }
                            
                            if not variant['sql'].strip().endswith(';'):
                                return {
                                    'valid': False,
                                    'error': f'变体 {j} 的SQL必须以分号结尾',
                                    'variant': variant
                                }
                    elif item_type in ['LACK_INFORMATION', 'NO_SQL_GENERATE']:
                        # 边界条件类型验证
                        variants = item.get('variants', [])
                        if not isinstance(variants, list):
                            return {
                                'valid': False,
                                'error': f'字典项 {i} 缺少variants数组',
                                'item': item
                            }
                        
                        for j, variant in enumerate(variants):
                            if not isinstance(variant, dict):
                                return {
                                    'valid': False,
                                    'error': f'变体 {j} 不是字典格式',
                                    'variant': variant
                                }
                            
                            if 'scenario' not in variant or 'sql' not in variant:
                                return {
                                    'valid': False,
                                    'error': f'变体 {j} 缺少scenario或sql字段',
                                    'variant': variant
                                }
                    else:
                        return {
                            'valid': False,
                            'error': f'字典项 {i} 类型不正确: {item_type}',
                            'item': item
                        }
                else:
                    return {
                        'valid': False,
                        'error': f'数组项 {i} 格式不正确',
                        'item': item
                    }
            
            return True
        except Exception as e:
            return {
                'valid': False,
                'error': f'解析SQL生成响应失败: {str(e)}',
                'response': response[:200]
            }
    else:
        return json_result


def validate_fix_review_response(response: str) -> Union[bool, Dict[str, Any]]:
    """验证修复审查响应
    
    Args:
        response: LLM响应内容
        
    Returns:
        True表示格式正确，Dict包含验证结果
    """
    # 首先尝试JSON格式验证
    json_result = validate_json_format(response)
    if json_result is True:
        try:
            # 尝试解析JSON对象
            if '```json' in response:
                json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group(1))
                else:
                    return {
                        'valid': False,
                        'error': '未找到JSON对象内容',
                        'response': response[:200]
                    }
            else:
                data = json.loads(response)
            
            if not isinstance(data, dict):
                return {
                    'valid': False,
                    'error': '响应不是JSON对象格式',
                    'data': data
                }
            
            # 验证必需字段
            if 'accepted' not in data:
                return {
                    'valid': False,
                    'error': '缺少accepted字段',
                    'data': data
                }
            
            if not isinstance(data['accepted'], bool):
                return {
                    'valid': False,
                    'error': 'accepted字段必须是布尔值',
                    'data': data
                }
            
            # replacement字段是可选的，但如果存在必须是字符串
            if 'replacement' in data and not isinstance(data['replacement'], str):
                return {
                    'valid': False,
                    'error': 'replacement字段必须是字符串',
                    'data': data
                }
            
            return True
        except Exception as e:
            return {
                'valid': False,
                'error': f'解析修复审查响应失败: {str(e)}',
                'response': response[:200]
            }
    else:
        return json_result


def validate_precheck_response(response: str) -> Union[bool, Dict[str, Any]]:
    """验证预检查响应
    
    Args:
        response: LLM响应内容
        
    Returns:
        True表示格式正确，Dict包含验证结果
    """
    # 预检查响应通常是简单的 "yes" 或 "no" 字符串
    if not response:
        return {
            'valid': False,
            'error': '响应为空',
            'response': response
        }
    
    # 清理响应内容
    cleaned_response = response.strip().lower()
    
    # 检查是否为有效的预检查响应
    valid_responses = ['yes', 'no', 'true', 'false', '1', '0']
    if cleaned_response in valid_responses:
        return True
    
    # 如果包含JSON格式，尝试解析
    try:
        if '```json' in response:
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(1))
                # 检查是否包含预检查相关的字段
                if 'will_generate_sql' in data or 'generate_sql' in data:
                    return True
        else:
            # 尝试直接解析JSON
            data = json.loads(response)
            if 'will_generate_sql' in data or 'generate_sql' in data:
                return True
    except (json.JSONDecodeError, TypeError):
        pass
    
    # 如果都不匹配，检查是否包含关键词
    if any(keyword in cleaned_response for keyword in ['yes', 'no', 'will', 'generate', 'sql']):
        return True
    
    return {
        'valid': False,
        'error': f'预检查响应格式不正确: {response[:200]}',
        'response': response[:200]
    }


def validate_synthetic_data_response(response: str, data_type: str) -> Union[bool, Dict[str, Any]]:
    """验证合成数据生成响应
    
    Args:
        response: LLM响应内容
        data_type: 数据类型 (orm, caller, meta)
        
    Returns:
        True表示格式正确，Dict包含验证结果
    """
    try:
        # 提取JSON内容
        if '```json' in response:
            # 支持数组和对象格式
            json_match = re.search(r'```json\s*(\[.*?\]|{.*?})\s*```', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(1))
            else:
                return {
                    'valid': False,
                    'error': '未找到JSON内容',
                    'response': response[:200]
                }
        else:
            data = json.loads(response)
        
        # 根据数据类型验证
        if data_type == 'orm':
            return validate_orm_response(data)
        elif data_type == 'caller':
            return validate_caller_response(data)
        elif data_type == 'meta':
            return validate_meta_response(data)
        else:
            return {
                'valid': False,
                'error': f'未知的数据类型: {data_type}'
            }
    except Exception as e:
        return {
            'valid': False,
            'error': f'解析合成数据响应失败: {str(e)}',
            'response': response[:200]
        }


def validate_orm_response(data: Any) -> Union[bool, Dict[str, Any]]:
    """验证ORM响应格式"""
    # ORM数据可以是单个对象或数组格式
    if isinstance(data, list):
        # 数组格式：验证第一个元素
        if len(data) == 0:
            return {
                'valid': False,
                'error': 'ORM数组不能为空',
                'data': data
            }
        data = data[0]  # 使用第一个元素进行验证
    
    if not isinstance(data, dict):
        return {
            'valid': False,
            'error': 'ORM数据必须是对象格式',
            'data': data
        }
    
    required_fields = ['scenario', 'code_key', 'code_value', 'sql_pattern_cnt']
    missing_fields = []
    for field in required_fields:
        if field not in data:
            missing_fields.append(field)
    
    if missing_fields:
        return {
            'valid': False,
            'error': f'缺少必需字段: {missing_fields}',
            'data': data
        }
    
    return True


def validate_caller_response(data: Any) -> Union[bool, Dict[str, Any]]:
    """验证Caller响应格式"""
    # Caller数据可以是单个对象或数组格式
    if isinstance(data, list):
        # 数组格式：验证第一个元素
        if len(data) == 0:
            return {
                'valid': False,
                'error': 'Caller数组不能为空',
                'data': data
            }
        data = data[0]  # 使用第一个元素进行验证
    
    if not isinstance(data, dict):
        return {
            'valid': False,
            'error': 'Caller数据必须是对象格式',
            'data': data
        }
    
    required_fields = ['code_key', 'code_value']
    missing_fields = []
    for field in required_fields:
        if field not in data:
            missing_fields.append(field)
    
    if missing_fields:
        return {
            'valid': False,
            'error': f'缺少必需字段: {missing_fields}',
            'data': data
        }
    
    return True


def validate_meta_response(data: Any) -> Union[bool, Dict[str, Any]]:
    """验证Meta响应格式"""
    # meta必须是数组格式
    if not isinstance(data, list):
        return {
            'valid': False,
            'error': 'meta数据必须是数组格式',
            'data': data
        }
    
    # 验证数组中的每个元素
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            return {
                'valid': False,
                'error': f'数组元素 {i} 不是对象格式',
                'data': item
            }
        
        if 'code_key' not in item or 'code_value' not in item:
            return {
                'valid': False,
                'error': f'数组元素 {i} 缺少必需字段: code_key, code_value',
                'data': item
            }
    
    return True


def validate_reverse_sql_response(response: str) -> Union[bool, Dict[str, Any]]:
    """验证反向SQL生成响应
    
    Args:
        response: LLM响应内容
        
    Returns:
        True表示格式正确，Dict包含验证结果
    """
    # 首先验证JSON格式
    json_result = validate_json_format(response)
    if json_result is True:
        try:
            # 尝试解析JSON对象
            if '```json' in response:
                json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group(1))
                else:
                    return {
                        'valid': False,
                        'error': '未找到JSON对象内容',
                        'response': response[:200]
                    }
            else:
                data = json.loads(response)
            
            if not isinstance(data, dict):
                return {
                    'valid': False,
                    'error': '响应不是JSON对象格式',
                    'data': data
                }
            
            # 验证必需字段
            required_fields = ['query', 'table', 'fields', 'conditions']
            missing_fields = []
            for field in required_fields:
                if field not in data:
                    missing_fields.append(field)
            
            if missing_fields:
                return {
                    'valid': False,
                    'error': f'缺少必需字段: {missing_fields}',
                    'data': data
                }
            
            # 验证字段类型
            if not isinstance(data['fields'], list):
                return {
                    'valid': False,
                    'error': 'fields字段必须是数组',
                    'data': data
                }
            
            if not isinstance(data['conditions'], list):
                return {
                    'valid': False,
                    'error': 'conditions字段必须是数组',
                    'data': data
                }
            
            # 验证SQL语法
            sql_query = data['query']
            if not sql_query.strip().lower().startswith('select'):
                return {
                    'valid': False,
                    'error': 'SQL查询必须以SELECT开头',
                    'data': data
                }
            
            return True
        except Exception as e:
            return {
                'valid': False,
                'error': f'解析反向SQL响应失败: {str(e)}',
                'response': response[:200]
            }
    else:
        return json_result


def validate_reverse_sql_variants_response(response: str) -> Union[bool, Dict[str, Any]]:
    """验证反向SQL变体生成响应
    
    Args:
        response: LLM响应内容
        
    Returns:
        True表示格式正确，Dict包含验证结果
    """
    # 首先验证JSON格式
    json_result = validate_json_format(response)
    if json_result is True:
        try:
            # 尝试解析JSON数组
            if '```json' in response:
                json_match = re.search(r'```json\s*(\[.*?\])\s*```', response, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group(1))
                else:
                    return {
                        'valid': False,
                        'error': '未找到JSON数组内容',
                        'response': response[:200]
                    }
            else:
                data = json.loads(response)
            
            if not isinstance(data, list):
                return {
                    'valid': False,
                    'error': '响应不是JSON数组格式',
                    'data': data
                }
            
            # 验证数组中的每个元素
            for i, item in enumerate(data):
                if not isinstance(item, dict):
                    return {
                        'valid': False,
                        'error': f'数组元素 {i} 不是对象格式',
                        'item': item
                    }
                
                # 验证必需字段（根据提示词模板）
                required_fields = ['query', 'table', 'fields', 'conditions', 'branch', 'description']
                missing_fields = []
                for field in required_fields:
                    if field not in item:
                        missing_fields.append(field)
                
                if missing_fields:
                    return {
                        'valid': False,
                        'error': f'数组元素 {i} 缺少必需字段: {missing_fields}',
                        'item': item
                    }
                
                # 验证字段类型
                if not isinstance(item['fields'], list):
                    return {
                        'valid': False,
                        'error': f'数组元素 {i} 的fields字段必须是数组',
                        'item': item
                    }
                
                if not isinstance(item['conditions'], list):
                    return {
                        'valid': False,
                        'error': f'数组元素 {i} 的conditions字段必须是数组',
                        'item': item
                    }
                
                # 验证branch和description字段
                if not isinstance(item['branch'], str) or not item['branch'].strip():
                    return {
                        'valid': False,
                        'error': f'数组元素 {i} 的branch字段不能为空',
                        'item': item
                    }
                
                if not isinstance(item['description'], str) or not item['description'].strip():
                    return {
                        'valid': False,
                        'error': f'数组元素 {i} 的description字段不能为空',
                        'item': item
                    }
                
                # 验证SQL语法
                sql_query = item['query']
                if not sql_query.strip().lower().startswith('select'):
                    return {
                        'valid': False,
                        'error': f'数组元素 {i} 的SQL查询必须以SELECT开头',
                        'item': item
                    }
            
            return True
        except Exception as e:
            return {
                'valid': False,
                'error': f'解析反向SQL变体响应失败: {str(e)}',
                'response': response[:200]
            }
    else:
        return json_result


def validate_reverse_orm_response(response: str) -> Union[bool, Dict[str, Any]]:
    """验证反向ORM映射响应
    
    Args:
        response: LLM响应内容
        
    Returns:
        True表示格式正确，Dict包含验证结果
    """
    # 首先验证JSON格式
    json_result = validate_json_format(response)
    if json_result is True:
        try:
            # 尝试解析JSON对象
            if '```json' in response:
                json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group(1))
                else:
                    return {
                        'valid': False,
                        'error': '未找到JSON对象内容',
                        'response': response[:200]
                    }
            else:
                data = json.loads(response)
            
            if not isinstance(data, dict):
                return {
                    'valid': False,
                    'error': '响应不是JSON对象格式',
                    'data': data
                }
            
            # 验证必需字段（根据提示词模板）
            required_fields = ['method_name', 'code', 'parameters', 'return_type', 'table', 'fields', 'conditions']
            missing_fields = []
            for field in required_fields:
                if field not in data:
                    missing_fields.append(field)
            
            if missing_fields:
                return {
                    'valid': False,
                    'error': f'缺少必需字段: {missing_fields}',
                    'data': data
                }
            
            # 验证字段类型
            if not isinstance(data['parameters'], list):
                return {
                    'valid': False,
                    'error': 'parameters字段必须是数组',
                    'data': data
                }
            
            if not isinstance(data['fields'], list):
                return {
                    'valid': False,
                    'error': 'fields字段必须是数组',
                    'data': data
                }
            
            if not isinstance(data['conditions'], list):
                return {
                    'valid': False,
                    'error': 'conditions字段必须是数组',
                    'data': data
                }
            
            # 验证代码不为空
            if not data['code'].strip():
                return {
                    'valid': False,
                    'error': 'code字段不能为空',
                    'data': data
                }
            
            # 验证Go代码格式
            code_lower = data['code'].lower()
            if 'func' not in code_lower or 'return' not in code_lower:
                return {
                    'valid': False,
                    'error': '代码必须包含func和return关键字',
                    'data': data
                }
            
            return True
        except Exception as e:
            return {
                'valid': False,
                'error': f'解析反向ORM响应失败: {str(e)}',
                'response': response[:200]
            }
    else:
        return json_result


def validate_reverse_caller_response(response: str) -> Union[bool, Dict[str, Any]]:
    """验证反向Caller生成响应
    
    Args:
        response: LLM响应内容
        
    Returns:
        True表示格式正确，Dict包含验证结果
    """
    # 首先验证JSON格式
    json_result = validate_json_format(response)
    if json_result is True:
        try:
            # 尝试解析JSON对象
            if '```json' in response:
                json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group(1))
                else:
                    return {
                        'valid': False,
                        'error': '未找到JSON对象内容',
                        'response': response[:200]
                    }
            else:
                data = json.loads(response)
            
            if not isinstance(data, dict):
                return {
                    'valid': False,
                    'error': '响应不是JSON对象格式',
                    'data': data
                }
            
            # 验证必需字段
            required_fields = ['method_name', 'code', 'parameters', 'return_type']
            missing_fields = []
            for field in required_fields:
                if field not in data:
                    missing_fields.append(field)
            
            if missing_fields:
                return {
                    'valid': False,
                    'error': f'缺少必需字段: {missing_fields}',
                    'data': data
                }
            
            # 验证字段类型
            if not isinstance(data['parameters'], list):
                return {
                    'valid': False,
                    'error': 'parameters字段必须是数组',
                    'data': data
                }
            
            # 验证代码不为空
            if not data['code'].strip():
                return {
                    'valid': False,
                    'error': 'code字段不能为空',
                    'data': data
                }
            
            # 验证Go代码格式
            code_lower = data['code'].lower()
            if 'func' not in code_lower or 'return' not in code_lower:
                return {
                    'valid': False,
                    'error': '代码必须包含func和return关键字',
                    'data': data
                }
            
            return True
        except Exception as e:
            return {
                'valid': False,
                'error': f'解析反向Caller响应失败: {str(e)}',
                'response': response[:200]
            }
    else:
        return json_result


# 验证器映射表
VALIDATORS = {
    'json': validate_json_format,
    'boolean': validate_boolean_response,
    'structured': validate_structured_response,
    'list': validate_list_format,
    'sql_completeness': validate_sql_completeness_response,
    'sql_correctness': validate_sql_correctness_response,
    'keyword_extraction': validate_keyword_extraction_response,
    'redundant_sql_validation': validate_redundant_sql_validation_response,
    'control_flow_validation': validate_control_flow_validation_response,
    'control_flow_sql_regeneration': validate_control_flow_sql_regeneration_response,
    'sql_generation': validate_sql_generation_response,
    'fix_review': validate_fix_review_response,
    'precheck': validate_precheck_response,
    'synthetic_data': validate_synthetic_data_response,
    # 反向SQL生成器验证器
    'reverse_sql': validate_reverse_sql_response,
    'reverse_sql_variants': validate_reverse_sql_variants_response,
    'reverse_orm': validate_reverse_orm_response,
    'reverse_caller': validate_reverse_caller_response,
}


def get_validator(validator_type: str, **kwargs) -> Callable:
    """获取验证器函数
    
    Args:
        validator_type: 验证器类型
        **kwargs: 验证器参数
        
    Returns:
        验证器函数
    """
    if validator_type not in VALIDATORS:
        raise ValueError(f"未知的验证器类型: {validator_type}")
    
    validator = VALIDATORS[validator_type]
    
    # 如果有参数，返回包装函数
    if kwargs:
        def wrapped_validator(response: str):
            return validator(response, **kwargs)
        return wrapped_validator
    
    return validator 