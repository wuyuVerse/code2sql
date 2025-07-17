#!/usr/bin/env python3
"""
FastAPI应用测试脚本

测试数据集查看器的FastAPI应用是否正常工作
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到路径
sys.path.append(os.path.dirname(__file__))

def test_fastapi_import():
    """测试FastAPI相关模块导入"""
    try:
        from fastapi import FastAPI
        import uvicorn
        from fastapi.templating import Jinja2Templates
        print("✅ FastAPI相关模块导入成功")
        return True
    except ImportError as e:
        print(f"❌ FastAPI模块导入失败: {e}")
        return False

def test_app_import():
    """测试应用导入"""
    try:
        from web_server.app import app
        print("✅ 应用导入成功")
        return True
    except Exception as e:
        print(f"❌ 应用导入失败: {e}")
        return False

def test_templates():
    """测试模板目录"""
    template_dir = Path("web_server/templates")
    if template_dir.exists():
        print("✅ 模板目录存在")
        
        # 检查必要的模板文件
        required_templates = ["index.html", "dataset_viewer.html", "error.html"]
        missing_templates = []
        
        for template in required_templates:
            template_file = template_dir / template
            if template_file.exists():
                print(f"✅ 模板文件存在: {template}")
            else:
                print(f"❌ 模板文件缺失: {template}")
                missing_templates.append(template)
        
        if missing_templates:
            print(f"⚠️  缺失的模板文件: {missing_templates}")
            return False
        else:
            print("✅ 所有模板文件都存在")
            return True
    else:
        print("❌ 模板目录不存在")
        return False

def test_data_directory():
    """测试数据目录"""
    data_dir = Path("datasets/claude_output")
    if data_dir.exists():
        print("✅ 数据目录存在")
        
        # 检查JSON文件
        json_files = list(data_dir.glob("*.json"))
        if json_files:
            print(f"✅ 找到 {len(json_files)} 个JSON文件")
            for json_file in json_files[:3]:  # 只显示前3个
                print(f"   📄 {json_file.name}")
            if len(json_files) > 3:
                print(f"   ... 还有 {len(json_files) - 3} 个文件")
            return True
        else:
            print("⚠️  数据目录中没有找到JSON文件")
            return False
    else:
        print("⚠️  数据目录不存在，但应用仍可启动")
        return True

def main():
    """运行所有测试"""
    print("🧪 开始测试FastAPI应用...")
    print("=" * 50)
    
    tests = [
        ("FastAPI模块导入", test_fastapi_import),
        ("应用导入", test_app_import),
        ("模板文件", test_templates),
        ("数据目录", test_data_directory),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n🔍 测试: {test_name}")
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name} 通过")
            else:
                print(f"❌ {test_name} 失败")
        except Exception as e:
            print(f"❌ {test_name} 异常: {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！应用可以正常启动")
        print("\n🚀 启动命令:")
        print("   python run_dataset_viewer.py")
        print("\n🌐 访问地址:")
        print("   http://localhost:5000")
        print("   http://localhost:5000/docs (API文档)")
    else:
        print("⚠️  部分测试失败，请检查相关配置")
        print("\n💡 安装依赖:")
        print("   pip install fastapi uvicorn jinja2")

if __name__ == "__main__":
    main() 