#!/usr/bin/env python3
"""
测试复杂ORM代码的SQL生成
"""
import json
import asyncio
import sys
from pathlib import Path
from typing import Dict, Any, List

# 添加项目根目录到Python路径
sys.path.append(str(Path(__file__).parent))

from data_processing.synthetic_data_generator.get_sql import process_json_file_async


def create_complex_orm_test_file():
    """创建包含复杂ORM代码的测试文件"""
    complex_orm_data = {
        "complex_refresh_index": {
            "scenario": "table_mapping_incomplete",
            "code_key": "RefreshIndex",
            "code_value": """func (r *Report) RefreshIndex(filter map[string]interface{}) ([]Report, error) {
    var reports []Report
    values := make([]interface{}, 0)
    sql := "SELECT * FROM publication_schedule WHERE deleted_at IS NULL "

    for k, v := range filter {
        if k == "BillingAddress" {
            sql += "AND location_id=? "
            values = append(values, v)
        } else if k == "Subject" {
            sql += "AND topic_id=? "
            values = append(values, v)
        } else if k == "Zone" {
            sql += "AND area_id IN (?) "
            values = append(values, v)
        } else if k == "Publisher" {
            sql += "AND author_id=? "
            values = append(values, v)
        }
    }

    err := db.Raw(sql, values...).Scan(&reports).Error
    if err != nil {
        return nil, err
    }
    return reports, nil
}""",
            "sql_pattern_cnt": 1,
            "callers": [
                {
                    "code_key": "HandleActiveCourses",
                    "code_value": """func HandleActiveCourses() ([]types.Curriculum, error) {
    expressObj := &Express{}
    courses, err := expressObj.RefreshIndex()
    if err != nil {
        log.Printf("Failed to fetch active courses: %v", err)
        return nil, fmt.Errorf("course retrieval error")
    }
    return courses, nil
}"""
                }
            ],
            "code_meta_data": [
                {
                    "code_key": "Report",
                    "code_value": """type Report struct {
    ID            uint      `gorm:"primaryKey"`
    LocationID    uint      `gorm:"column:location_id"`
    TopicID       uint      `gorm:"column:topic_id"`
    AreaID        uint      `gorm:"column:area_id"`
    AuthorID      uint      `gorm:"column:author_id"`
    CreatedAt     time.Time `gorm:"column:created_at"`
    UpdatedAt     time.Time `gorm:"column:updated_at"`
    DeletedAt     gorm.DeletedAt `gorm:"column:deleted_at;index"`
}"""
                },
                {
                    "code_key": "PublicationScheduleTable",
                    "code_value": "const PublicationScheduleTable = \"publication_schedule\""
                }
            ]
        }
    }
    
    # 保存测试文件
    with open("test_complex_orm.json", 'w', encoding='utf-8') as f:
        json.dump(complex_orm_data, f, ensure_ascii=False, indent=2)
    
    print("✅ 创建复杂ORM测试文件: test_complex_orm.json")
    return "test_complex_orm.json"


async def test_complex_orm_sql_generation():
    """测试复杂ORM代码的SQL生成"""
    print("🧪 开始复杂ORM代码SQL生成测试...")
    
    # 创建测试文件
    input_file = create_complex_orm_test_file()
    output_file = "test_complex_orm_output.json"
    
    try:
        # 生成SQL
        result = await process_json_file_async(input_file, output_file, concurrency=1)
        print(f"✅ SQL生成完成，返回结果: {result}")
        
        # 分析结果
        with open(output_file, 'r', encoding='utf-8') as f:
            output_data = json.load(f)
        
        print(f"\n📊 输出数据: {len(output_data)} 条记录")
        
        for i, record in enumerate(output_data):
            function_name = record.get('function_name', 'Unknown')
            orm_code = record.get('orm_code', '')
            sql_statements = record.get('sql_statement_list', [])
            
            print(f"\n--- 记录 {i+1}: {function_name} ---")
            print(f"ORM代码长度: {len(orm_code)} 字符")
            print(f"生成的SQL数量: {len(sql_statements)}")
            
            if sql_statements:
                for j, sql in enumerate(sql_statements):
                    print(f"SQL {j+1}: {sql}")
            
            # 检查SQL类型
            sql_types = record.get('sql_types', [])
            print(f"SQL类型: {sql_types}")
        
        return True
    except Exception as e:
        print(f"❌ SQL生成失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主函数"""
    print("🔧 开始复杂ORM代码SQL生成测试...")
    
    success = await test_complex_orm_sql_generation()
    
    if success:
        print("🎉 复杂ORM测试完成！")
    else:
        print("⚠️  复杂ORM测试失败")


if __name__ == "__main__":
    asyncio.run(main()) 