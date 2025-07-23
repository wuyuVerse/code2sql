#!/usr/bin/env python3
"""
生成"对象const+chunk"场景的合成数据
"""
import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from data_processing.workflow.workflow_manager import run_synthetic_data_generation_workflow


async def main():
    """生成"对象const+chunk"场景的合成数据"""
    print("🚀 开始生成'对象const+chunk'场景的合成数据...")
    
    try:
        # 调用合成数据生成工作流
        result = await run_synthetic_data_generation_workflow(
            base_output_dir="synthetic_output",
            # scenarios=["对象const+chunk"],  # 指定要生成的场景
            scenarios=["no-where"],
            count_per_scenario=10,  # 每个场景生成100个数据包
            llm_server="v3",  # 使用v3服务器
            temperature=0.7,
            max_tokens=4096,
            parallel=True,  # 开启并行模式
            max_workers=2,
            validate=True
        )
        
        print("\n✅ 合成数据生成成功!")
        print(f"📁 工作流目录: {result['workflow_directory']}")
        print(f"📋 摘要文件: {result['summary_path']}")
        
        if 'generation_result' in result:
            gen_result = result['generation_result']
            print(f"📊 生成统计:")
            print(f"  - 生成的数据包数量: {len(gen_result.get('generated_packs', {}))}")
            print(f"  - 验证通过的数据包: {gen_result.get('validated_count', 0)}")
            print(f"  - 验证失败的数据包: {gen_result.get('validation_failed_count', 0)}")
        
        return result
        
    except Exception as e:
        print(f"❌ 生成失败: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    import asyncio
    asyncio.run(main()) 