#!/usr/bin/env python3
"""
LLM Client 测试脚本
"""
import asyncio
import aiohttp
import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.append(str(Path(__file__).parent))

from utils.llm_client import LLMClient
from utils.format_validators import validate_json_format


async def test_llm_client():
    """测试LLM客户端是否正常工作"""
    print("🧪 开始测试LLM客户端...")
    
    try:
        # 创建LLM客户端
        client = LLMClient("v3")
        print(f"✅ LLM客户端创建成功，服务器: {client.server_name}")
        
        # 测试配置
        config = client.config
        print(f"✅ 配置加载成功:")
        print(f"   - 主机: {config.host}")
        print(f"   - 端口: {config.port}")
        print(f"   - 模型: {config.model_name}")
        print(f"   - 超时: {config.timeout}秒")
        print(f"   - 重试次数: {config.max_retries}")
        
        # 测试简单连接
        print("\n🔗 测试服务器连接...")
        async with aiohttp.ClientSession() as session:
            try:
                # 简单的测试请求
                test_prompt = "请返回一个简单的JSON格式响应：{\"status\": \"ok\"}"
                
                response = await client.call_async_with_format_validation(
                    session=session,
                    prompt=test_prompt,
                    validator=validate_json_format,
                    max_tokens=100,
                    temperature=0.0,
                    max_retries=3,
                    retry_delay=1.0
                )
                
                print(f"✅ LLM调用成功!")
                print(f"   响应: {response[:200]}...")
                
            except Exception as e:
                print(f"❌ LLM调用失败: {e}")
                return False
        
        print("\n🎉 LLM客户端测试通过!")
        return True
        
    except Exception as e:
        print(f"❌ LLM客户端测试失败: {e}")
        return False


async def test_sql_generation():
    """测试SQL生成功能"""
    print("\n🧪 测试SQL生成功能...")
    
    try:
        from data_processing.synthetic_data_generator.get_sql import process_json_file_async
        
        # 创建一个简单的测试数据
        test_data = {
            "test_method": {
                "scenario": "单chunk",
                "code_key": "TestMethod",
                "code_value": """
                func (u *User) FindByID(id int) (*User, error) {
                    var user User
                    err := db.Where("id = ?", id).First(&user).Error
                    return &user, err
                }
                """,
                "sql_pattern_cnt": 1,
                "callers": [],
                "callees": [],
                "code_meta_data": []
            }
        }
        
        # 保存测试数据到临时文件
        test_input = "test_input.json"
        test_output = "test_output.json"
        
        import json
        with open(test_input, 'w', encoding='utf-8') as f:
            json.dump(test_data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 测试数据已保存到: {test_input}")
        
        # 测试SQL生成
        try:
            await process_json_file_async(test_input, test_output, concurrency=10)
            print("✅ SQL生成测试成功!")
            
            # 检查输出文件
            if os.path.exists(test_output):
                with open(test_output, 'r', encoding='utf-8') as f:
                    result = json.load(f)
                print(f"✅ 输出文件生成成功，包含 {len(result)} 条记录")
            else:
                print("❌ 输出文件未生成")
                
        except Exception as e:
            print(f"❌ SQL生成测试失败: {e}")
            return False
        
        # 清理临时文件
        for file in [test_input, test_output]:
            if os.path.exists(file):
                os.remove(file)
                print(f"🧹 已清理临时文件: {file}")
        
        return True
        
    except Exception as e:
        print(f"❌ SQL生成功能测试失败: {e}")
        return False


async def main():
    """主测试函数"""
    print("🚀 开始LLM系统测试")
    print("=" * 50)
    
    # 测试LLM客户端
    llm_test_passed = await test_llm_client()
    
    # 测试SQL生成
    sql_test_passed = await test_sql_generation()
    
    print("\n" + "=" * 50)
    print("📊 测试结果汇总:")
    print(f"   LLM客户端测试: {'✅ 通过' if llm_test_passed else '❌ 失败'}")
    print(f"   SQL生成测试: {'✅ 通过' if sql_test_passed else '❌ 失败'}")
    
    if llm_test_passed and sql_test_passed:
        print("\n🎉 所有测试通过!")
        return 0
    else:
        print("\n❌ 部分测试失败，请检查配置和网络连接")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 