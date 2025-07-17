#!/usr/bin/env python3
"""
测试合并后的控制流验证和SQL重新生成提示词
"""

import sys
import os
sys.path.append('.')

from config.data_clean.control_flow_validation_prompt import (
    get_control_flow_validation_prompt,
    get_control_flow_sql_regeneration_prompt
)


def test_control_flow_validation_prompt():
    """测试控制流验证提示词"""
    print("🔍 测试控制流验证提示词...")
    
    # 测试数据
    orm_code = """func (o *Overview) FindUserCountByCustomerType(startTime string, end int64) (int, error) {
    var counts int64
    filter := make(map[string]interface{})
    filter["status"] = 0
    if o.CustomerType > 0 {
        switch o.CustomerType {
        case External:
            filter["internal"] = 0
        case Internal:
            filter["internal"] = 1
        case Big:
            filter["big_customer"] = 1
        case Small:
            filter["big_customer"] = 0
        case Corporate:
            filter["corporate"] = 1
        case Personal:
            filter["corporate"] = 0
        default:
            return int(counts), utils.UnSupportedCustomerTypeError
        }
    }
    comment := o.CommentFunc(SELECT_COMMENT)
    endTime := time.Unix(end, 0)
    err := base.GetInstance().BillingDriver().Clauses(comment).Table(UserInfoTable).Where(filter).Where("updated_at BETWEEN ? AND ?", startTime, endTime).Count(&counts).Error
    if err != nil {
        return int(counts), err
    }
    return int(counts), nil
}"""
    
    caller = """func (c *Comment) CommentFunc(action string) hints.Hints {
	if c == nil {
		c = NewComment(uuid.NewString(), DefalutFlow)
	}
	return hints.CommentBefore(action, string(*c))
}
urs/internal/base
o.CommentFunc(SELECT_COMMENT)
type Overview struct {
	CustomerType int
	IndustryId   int
	AppId        int

	*Comment
}
type Comment string
const SELECT_COMMENT = "SELECT"
const UserInfoTable        = "ivc_user_info"
make(map[string]interface{})
make([]AppIds, 0)
type AppIds struct {
	AppId int `json:"app_id" gorm:"column:app_id"`
}"""
    code_meta_data = "测试元数据"
    current_sql_variants = """[
  {
    "type": "param_dependent",
    "variants": [
      {"scenario": "CustomerType <= 0", "sql": "SELECT count(*) FROM user_info WHERE status = ? AND updated_at BETWEEN ? AND ?;"},
      {"scenario": "CustomerType = External", "sql": "SELECT count(*) FROM user_info WHERE status = ? AND internal = ? AND updated_at BETWEEN ? AND ?;"},
      {"scenario": "CustomerType = Internal", "sql": "SELECT count(*) FROM user_info WHERE status = ? AND internal = ? AND updated_at BETWEEN ? AND ?;"},
      {"scenario": "CustomerType = Big", "sql": "SELECT count(*) FROM user_info WHERE status = ? AND big_customer = ? AND updated_at BETWEEN ? AND ?;"},
      {"scenario": "CustomerType = Small", "sql": "SELECT count(*) FROM user_info WHERE status = ? AND big_customer = ? AND updated_at BETWEEN ? AND ?;"},
      {"scenario": "CustomerType = Corporate", "sql": "SELECT count(*) FROM user_info WHERE status = ? AND corporate = ? AND updated_at BETWEEN ? AND ?;"},
      {"scenario": "CustomerType = Personal", "sql": "SELECT count(*) FROM user_info WHERE status = ? AND corporate = ? AND updated_at BETWEEN ? AND ?;"}
    ]
  }
]"""
    
    # 生成验证提示词
    validation_prompt = get_control_flow_validation_prompt(
        orm_code=orm_code,
        caller=caller,
        code_meta_data=code_meta_data,
        current_sql_variants=current_sql_variants
    )
    
    print("✅ 控制流验证提示词生成成功")
    print(f"📝 提示词长度: {len(validation_prompt)} 字符")
    print(f"📋 包含关键词: {'switch' in validation_prompt}, {'if' in validation_prompt}")
    
    return validation_prompt


def test_sql_regeneration_prompt():
    """测试SQL重新生成提示词"""
    print("\n🔄 测试SQL重新生成提示词...")
    
    # 测试数据
    orm_code = """func (o *Overview) FindUserCountByCustomerType(startTime string, end int64) (int, error) {
    // ... 省略代码 ...
}"""
    
    caller = "FindUserCountByCustomerType"
    code_meta_data = "测试元数据"
    validation_result = """验证结果: 错误
原因: SQL变体数量过多，switch语句有6个case分支但生成了7个SQL变体
期望SQL变体数量: 6
实际SQL变体数量: 7
发现的问题:
  - 生成了多余的SQL变体
  - 没有考虑default分支的处理
控制流分析:
  Switch语句:
    变量: o.CustomerType
    行号: 115-125
      分支: External -> filter["internal"] = 0 (应有SQL: true)
      分支: Internal -> filter["internal"] = 1 (应有SQL: true)
      分支: Big -> filter["big_customer"] = 1 (应有SQL: true)
      分支: Small -> filter["big_customer"] = 0 (应有SQL: true)
      分支: Corporate -> filter["corporate"] = 1 (应有SQL: true)
      分支: Personal -> filter["corporate"] = 0 (应有SQL: true)
      分支: default -> return error (应有SQL: false)"""
    
    # 生成重新生成提示词
    regeneration_prompt = get_control_flow_sql_regeneration_prompt(
        orm_code=orm_code,
        caller=caller,
        code_meta_data=code_meta_data,
        validation_result=validation_result
    )
    
    print("✅ SQL重新生成提示词生成成功")
    print(f"📝 提示词长度: {len(regeneration_prompt)} 字符")
    print(f"📋 包含关键词: {'重新生成' in regeneration_prompt}, {'控制流' in regeneration_prompt}")
    
    return regeneration_prompt


def main():
    """主测试函数"""
    print("🧪 开始测试合并后的控制流验证和SQL重新生成提示词")
    print("=" * 60)
    
    try:
        # 测试控制流验证提示词
        validation_prompt = test_control_flow_validation_prompt()
        
        # 测试SQL重新生成提示词
        regeneration_prompt = test_sql_regeneration_prompt()
        
        print("\n" + "=" * 60)
        print("✅ 所有测试通过！")
        print("📁 合并后的prompt文件工作正常")
        print("🔧 可以正常生成控制流验证和SQL重新生成提示词")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main() 