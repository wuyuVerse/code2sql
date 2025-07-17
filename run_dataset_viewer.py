#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
数据集查看器启动脚本

现在使用集成后的 main.py，同时提供评估报告查看和数据集查看功能。
"""

import uvicorn
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

if __name__ == "__main__":
    print("启动集成Web服务器...")
    print("功能包括:")
    print("- 模型评估报告查看")
    print("- 数据集查看器")
    print("- API接口")
    print()
    print("访问地址:")
    print("- 主仪表盘: http://localhost:8000/")
    print("- 数据集查看器: http://localhost:8000/dataset_viewer")
    print("- API文档: http://localhost:8000/docs")
    print()
    
    # 启动服务器，只监视web_server目录
    uvicorn.run(
        "web_server.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["web_server"],
        log_level="info"
    ) 