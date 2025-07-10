#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
评估结果展示 Web 服务器

使用 FastAPI 和 Jinja2 模板引擎，为不同类型的评估报告提供统一的Web展示入口。
"""

import os
import json
import logging
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# --- 日志配置 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- FastAPI 应用初始化 ---
app = FastAPI(
    title="模型评估报告查看器",
    description="一个用于查看和分析不同类型模型评估报告的Web应用。",
    version="1.0.0"
)

# --- 路径配置 ---
BASE_DIR = Path(__file__).parent.parent
EVALUATION_ROOT_DIR = BASE_DIR / "model" / "evaluation"
WEB_SERVER_DIR = BASE_DIR / "web_server"

# --- 挂载静态文件目录 ---
app.mount("/static", StaticFiles(directory=WEB_SERVER_DIR / "static"), name="static")

# --- 配置Jinja2模板 ---
templates = Jinja2Templates(directory=WEB_SERVER_DIR / "templates")


def scan_for_reports():
    """扫描所有评估结果目录，生成报告列表"""
    reports = {
        'fingerprint_eval': [],
        'comparative_eval': []
    }
    
    # 扫描指纹评估结果
    fingerprint_dir = EVALUATION_ROOT_DIR / "fingerprint_eval" / "results"
    if fingerprint_dir.exists():
        for run_dir in sorted(fingerprint_dir.iterdir(), key=os.path.getmtime, reverse=True):
            if run_dir.is_dir():
                report_html = run_dir / "reports" / "evaluation_report.html"
                if report_html.exists():
                    reports['fingerprint_eval'].append({
                        "timestamp": run_dir.name,
                        "path": f"/reports/fingerprint/{run_dir.name}",
                        "display_name": f"指纹评估 - {run_dir.name}"
                    })

    # 扫描对比评估结果
    comparative_dir = EVALUATION_ROOT_DIR / "comparative_eval" / "results"
    if comparative_dir.exists():
        for run_dir in sorted(comparative_dir.iterdir(), key=os.path.getmtime, reverse=True):
            if run_dir.is_dir():
                result_json = run_dir / "comparative_results.json"
                if result_json.exists():
                    reports['comparative_eval'].append({
                        "timestamp": run_dir.name,
                        "path": f"/reports/comparative/{run_dir.name}",
                        "display_name": f"对比评估 - {run_dir.name}"
                    })
    
    return reports


@app.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    """
    主仪表盘页面，展示所有可用的评估报告。
    """
    logger.info("请求主仪表盘页面")
    all_reports = scan_for_reports()
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "reports": all_reports
        }
    )

@app.get("/reports/fingerprint/{timestamp:path}", response_class=HTMLResponse)
async def get_fingerprint_report(timestamp: str):
    """
    提供对单个指纹评估HTML报告的访问。
    """
    logger.info(f"请求指纹评估报告: {timestamp}")
    report_path = EVALUATION_ROOT_DIR / "fingerprint_eval" / "results" / timestamp / "reports" / "evaluation_report.html"
    
    if not report_path.exists():
        logger.warning(f"指纹报告文件未找到: {report_path}")
        raise HTTPException(status_code=404, detail="报告文件未找到")
        
    return FileResponse(report_path)


@app.get("/reports/comparative/{timestamp:path}", response_class=HTMLResponse)
async def get_comparative_report(request: Request, timestamp: str):
    """
    动态渲染和展示单个对比评估的结果。
    """
    logger.info(f"请求对比评估报告: {timestamp}")
    result_file = EVALUATION_ROOT_DIR / "comparative_eval" / "results" / timestamp / "comparative_results.json"
    
    if not result_file.exists():
        logger.warning(f"对比评估结果文件未找到: {result_file}")
        raise HTTPException(status_code=404, detail="结果文件未找到")
    
    with open(result_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    # 在这里可以添加对数据的预处理或统计
    
    return templates.TemplateResponse(
        "comparative_report.html",
        {
            "request": request,
            "report_data": data,
            "timestamp": timestamp
        }
    )

if __name__ == "__main__":
    import uvicorn
    logger.info("启动开发服务器...")
    uvicorn.run(app, host="0.0.0.0", port=8000) 