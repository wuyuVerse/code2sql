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
                # 寻找新的核心报告文件
                # 兼容旧格式：如果没有statistics_summary.json，则尝试evaluation_summary.json
                report_json = run_dir / "statistics_summary.json"
                if not report_json.exists():
                    report_json = run_dir / "evaluation_summary.json"

                if report_json.exists():
                    reports['fingerprint_eval'].append({
                        "timestamp": run_dir.name,
                        # 更新路径以指向新的动态端点
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
async def get_fingerprint_report(request: Request, timestamp: str):
    """
    动态渲染和展示单个指纹评估的完整报告。
    """
    logger.info(f"请求指纹评估报告: {timestamp}")
    report_dir = EVALUATION_ROOT_DIR / "fingerprint_eval" / "results" / timestamp
    
    # summary 同时兼容新旧两种文件名
    files_to_load = {
        "summary": ["statistics_summary.json", "evaluation_summary.json"],
        "matched": "matching_sql_pairs.json",
        "unmatched": "unmatched_sql_pairs.json",
        "excluded": "excluded_sql_pairs.json",
        "coverage": "fingerprint_coverage.json"
    }
    report_data = {}

    # 逐个加载报告文件
    for key, filename in files_to_load.items():
        if isinstance(filename, list):
            # 针对summary，尝试两个文件名
            loaded = None
            for fn in filename:
                file_path = report_dir / fn
                if file_path.exists():
                    with open(file_path, 'r', encoding='utf-8') as f:
                        try:
                            loaded = json.load(f)
                        except json.JSONDecodeError:
                            logger.error(f"无法解析JSON文件: {file_path}")
                            loaded = {"error": f"无法解析 {fn}"}
                    break
            report_data[key] = loaded
        else:
            file_path = report_dir / filename
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    try:
                        report_data[key] = json.load(f)
                    except json.JSONDecodeError:
                        logger.error(f"无法解析JSON文件: {file_path}")
                        report_data[key] = {"error": f"无法解析 {filename}"}
            else:
                report_data[key] = None

    # 如果核心的摘要文件不存在，则报告无法展示
    if report_data["summary"] is None:
        logger.warning(f"核心报告文件 'statistics_summary.json' 未找到于: {report_dir}")
        raise HTTPException(status_code=404, detail="核心报告文件未找到")

    # 扁平化summary，方便模板渲染
    flat_summary = {}
    summary = report_data["summary"]
    if isinstance(summary, dict):
        for sec_key, sec_val in summary.items():
            if isinstance(sec_val, dict):
                for k, v in sec_val.items():
                    flat_summary[k] = v
            else:
                flat_summary[sec_key] = sec_val
    else:
        flat_summary = {"summary": summary}

    # 若覆盖率文件存在, 合并相关指标
    cov = report_data.get("coverage")
    if isinstance(cov, dict):
        flat_summary["指纹覆盖率"] = cov.get("coverage_percentage") or cov.get("coverage")
        flat_summary["有效CSV指纹总数"] = cov.get("valid_fingerprint_count")
        flat_summary["已匹配CSV指纹数"] = cov.get("matched_fingerprint_count")

    report_data["flat_summary"] = flat_summary

    # 若缺少命中率/覆盖率等关键指标，则根据已加载列表动态补充
    matched_cnt = len(report_data.get("matched") or [])
    unmatched_cnt = len(report_data.get("unmatched") or [])
    excluded_cnt = len(report_data.get("excluded") or [])
    total_valid_sql = matched_cnt + unmatched_cnt

    if "匹配到CSV指纹的SQL数" not in flat_summary:
        flat_summary["匹配到CSV指纹的SQL数"] = matched_cnt
    if "未匹配SQL数" not in flat_summary:
        flat_summary["未匹配SQL数"] = unmatched_cnt
    if "被排除SQL数" not in flat_summary:
        flat_summary["被排除SQL数"] = excluded_cnt
    if "精准率" not in flat_summary and total_valid_sql > 0:
        flat_summary["精准率"] = round(matched_cnt / total_valid_sql, 4)
    if "有效SQL总数" not in flat_summary:
        flat_summary["有效SQL总数"] = total_valid_sql
        
    return templates.TemplateResponse(
        "fingerprint_report.html",
        {
            "request": request,
            "report_data": report_data,
            "timestamp": timestamp
        }
    )


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