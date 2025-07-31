#!/usr/bin/env python3
"""
测试分布式训练环境中的模块导入
"""

import os
import sys
from pathlib import Path

def test_import():
    """测试llamafactory模块导入"""
    try:
        # 设置LLaMA-Factory路径
        llamafactory_dir = Path(__file__).parent / "LLaMA-Factory"
        src_path = str(llamafactory_dir / "src")
        
        # 添加到Python路径
        if src_path not in sys.path:
            sys.path.insert(0, src_path)
        
        # 设置环境变量
        os.environ["PYTHONPATH"] = f"{src_path}:{os.environ.get('PYTHONPATH', '')}"
        
        print(f"LLaMA-Factory目录: {llamafactory_dir}")
        print(f"src路径: {src_path}")
        print(f"Python路径: {sys.path[:3]}...")
        print(f"环境变量PYTHONPATH: {os.environ.get('PYTHONPATH', '')}")
        
        # 尝试导入
        import llamafactory
        print("✅ llamafactory模块导入成功")
        
        # 测试关键模块
        from llamafactory.train.tuner import run_exp
        print("✅ llamafactory.train.tuner.run_exp导入成功")
        
        return True
        
    except Exception as e:
        print(f"❌ 导入失败: {e}")
        return False

if __name__ == "__main__":
    success = test_import()
    sys.exit(0 if success else 1) 