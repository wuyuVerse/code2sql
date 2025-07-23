#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
评估结果展示 Web 服务器

使用 FastAPI 和 Jinja2 模板引擎，为不同类型的评估报告提供统一的Web展示入口。
同时集成数据集查看器功能。
"""

import os
import json
import logging
import requests
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from datetime import datetime
from bs4 import BeautifulSoup
from bs4.element import NavigableString
from jinja2 import Environment, FileSystemLoader, select_autoescape

# --- 日志配置 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- FastAPI 应用初始化 ---
app = FastAPI(
    title="模型评估报告查看器",
    description="一个用于查看和分析不同类型模型评估报告的Web应用，同时支持数据集查看功能。",
    version="1.0.0"
)

# --- 自定义JSON编码器 ---
class ChineseJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

def load_json_file(file_path: Path) -> dict:
    """加载JSON文件，确保中文正确解码"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

# --- 路径配置 ---
BASE_DIR = Path(__file__).parent.parent
EVALUATION_ROOT_DIR = BASE_DIR / "model" / "evaluation"
WEB_SERVER_DIR = BASE_DIR / "web_server"

# --- 挂载静态文件目录 ---
app.mount("/static", StaticFiles(directory=WEB_SERVER_DIR / "static"), name="static")

# --- 配置Jinja2模板 ---
templates = Jinja2Templates(directory=WEB_SERVER_DIR / "templates")

# --- 自定义Jinja2过滤器 ---
def basename_filter(path):
    """提取文件路径的文件名"""
    return Path(path).name

def datetime_filter(timestamp):
    """将时间戳转换为可读的日期时间格式"""
    if timestamp is not None:
        try:
            dt = datetime.fromtimestamp(float(timestamp))
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError, OSError):
            return str(timestamp)
    return ""

# 注册过滤器
templates.env.filters["basename"] = basename_filter
templates.env.filters["datetime"] = datetime_filter

def get_template_resources() -> dict:
    """从模板中提取所有外部资源，提供多个CDN源"""
    return {
        'bootstrap_css': [
            'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css',
            'https://cdnjs.cloudflare.com/ajax/libs/bootstrap/5.3.0/css/bootstrap.min.css',
            'https://unpkg.com/bootstrap@5.3.0/dist/css/bootstrap.min.css'
        ],
        'prism_css': [
            'https://cdn.jsdelivr.net/npm/prismjs@1.29.0/themes/prism.css',
            'https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/themes/prism.min.css',
            'https://unpkg.com/prismjs@1.29.0/themes/prism.css'
        ],
        'bootstrap_icons': [
            'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/font/bootstrap-icons.css',
            'https://cdnjs.cloudflare.com/ajax/libs/bootstrap-icons/1.10.5/font/bootstrap-icons.min.css',
            'https://unpkg.com/bootstrap-icons@1.10.5/font/bootstrap-icons.css'
        ],
        'bootstrap_js': [
            'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js',
            'https://cdnjs.cloudflare.com/ajax/libs/bootstrap/5.3.0/js/bootstrap.bundle.min.js',
            'https://unpkg.com/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js'
        ],
        'prism_js': [
            'https://cdn.jsdelivr.net/npm/prismjs@1.29.0/components/prism-core.min.js',
            'https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-core.min.js',
            'https://unpkg.com/prismjs@1.29.0/components/prism-core.min.js'
        ],
        'prism_sql': [
            'https://cdn.jsdelivr.net/npm/prismjs@1.29.0/components/prism-sql.min.js',
            'https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-sql.min.js',
            'https://unpkg.com/prismjs@1.29.0/components/prism-sql.min.js'
        ],
        'prism_python': [
            'https://cdn.jsdelivr.net/npm/prismjs@1.29.0/components/prism-python.min.js',
            'https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-python.min.js',
            'https://unpkg.com/prismjs@1.29.0/components/prism-python.min.js'
        ],
        'prism_autoloader': [
            'https://cdn.jsdelivr.net/npm/prismjs@1.29.0/plugins/autoloader/prism-autoloader.min.js',
            'https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/plugins/autoloader/prism-autoloader.min.js',
            'https://unpkg.com/prismjs@1.29.0/plugins/autoloader/prism-autoloader.min.js'
        ]
    }

def get_external_resource_content(urls: list) -> str:
    """获取外部资源内容，支持多个CDN源"""
    if isinstance(urls, str):
        urls = [urls]
    
    for url in urls:
        try:
            logger.info(f"尝试下载资源: {url}")
            response = requests.get(url, timeout=3)
            response.raise_for_status()
            logger.info(f"成功下载资源: {url}")
            return response.text
        except Exception as e:
            logger.warning(f"下载失败: {url} - {e}")
            continue
    
    logger.warning(f"所有CDN源都失败，使用本地备用资源")
    return ""

def get_local_bootstrap_icons() -> str:
    """获取本地Bootstrap图标样式"""
    return """
        @font-face {
            font-family: "bootstrap-icons";
            src: url("data:font/woff2;base64,d09GMgABAAAAAA...") format("woff2");
        }
        .bi {
            display: inline-block;
            font-family: bootstrap-icons !important;
            font-style: normal;
            font-weight: normal !important;
            font-variant: normal;
            text-transform: none;
            line-height: 1;
            vertical-align: -.125em;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }
        .bi-search::before { content: "\\f52a"; }
        .bi-file-earmark-text::before { content: "\\f39d"; }
        .bi-exclamation-triangle::before { content: "\\f33a"; }
        .bi-x-circle::before { content: "\\f622"; }
        .bi-check-circle::before { content: "\\f26b"; }
    """

def get_fallback_styles() -> str:
    """获取降级样式，当外部资源无法获取时使用"""
    return """
        /* Bootstrap 基础样式 */
        * {
            box-sizing: border-box;
        }
        
        body {
            margin: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            font-size: 1rem;
            line-height: 1.5;
            color: #212529;
            background-color: #f8f9fa;
        }
        
        .container-fluid {
            width: 100%;
            padding-right: 15px;
            padding-left: 15px;
            margin-right: auto;
            margin-left: auto;
            padding-top: 2rem;
        }
        
        .row {
            display: flex;
            flex-wrap: wrap;
            margin-right: -15px;
            margin-left: -15px;
        }
        
        .col-md-3, .col-md-4, .col-md-6, .col-md-12 {
            position: relative;
            width: 100%;
            padding-right: 15px;
            padding-left: 15px;
        }
        
        .col-md-3 { flex: 0 0 25%; max-width: 25%; }
        .col-md-4 { flex: 0 0 33.333333%; max-width: 33.333333%; }
        .col-md-6 { flex: 0 0 50%; max-width: 50%; }
        .col-md-12 { flex: 0 0 100%; max-width: 100%; }
        
        .card {
            position: relative;
            display: flex;
            flex-direction: column;
            min-width: 0;
            word-wrap: break-word;
            background-color: #fff;
            background-clip: border-box;
            border: 1px solid rgba(0, 0, 0, 0.125);
            border-radius: 0.375rem;
            margin-bottom: 1rem;
        }
        
        .card-body {
            flex: 1 1 auto;
            padding: 1.25rem;
        }
        
        .card-title {
            margin-bottom: 0.75rem;
            font-size: 1.25rem;
            font-weight: 500;
        }
        
        .card-text {
            margin-top: 0;
            margin-bottom: 1rem;
        }
        
        .text-center {
            text-align: center !important;
        }
        
        .btn {
            display: inline-block;
            font-weight: 400;
            text-align: center;
            vertical-align: middle;
            user-select: none;
            border: 1px solid transparent;
            padding: 0.375rem 0.75rem;
            font-size: 1rem;
            line-height: 1.5;
            border-radius: 0.25rem;
            transition: color 0.15s ease-in-out, background-color 0.15s ease-in-out, border-color 0.15s ease-in-out, box-shadow 0.15s ease-in-out;
            text-decoration: none;
            cursor: pointer;
        }
        
        .btn-success {
            color: #fff;
            background-color: #198754;
            border-color: #198754;
        }
        
        .btn-info {
            color: #fff;
            background-color: #0dcaf0;
            border-color: #0dcaf0;
        }
        
        .btn-secondary {
            color: #fff;
            background-color: #6c757d;
            border-color: #6c757d;
        }
        
        .btn-outline-primary {
            color: #0d6efd;
            border-color: #0d6efd;
            background-color: transparent;
        }
        
        .btn-outline-success {
            color: #198754;
            border-color: #198754;
            background-color: transparent;
        }
        
        .btn-outline-warning {
            color: #ffc107;
            border-color: #ffc107;
            background-color: transparent;
        }
        
        .btn-outline-info {
            color: #0dcaf0;
            border-color: #0dcaf0;
            background-color: transparent;
        }
        
        .btn-outline-secondary {
            color: #6c757d;
            border-color: #6c757d;
            background-color: transparent;
        }
        
        .btn-group {
            position: relative;
            display: inline-flex;
            vertical-align: middle;
        }
        
        .btn-group .btn {
            position: relative;
            flex: 1 1 auto;
        }
        
        .btn-group .btn:not(:first-child) {
            margin-left: -1px;
            border-top-left-radius: 0;
            border-bottom-left-radius: 0;
        }
        
        .btn-group .btn:not(:last-child) {
            border-top-right-radius: 0;
            border-bottom-right-radius: 0;
        }
        
        .badge {
            display: inline-block;
            padding: 0.35em 0.65em;
            font-size: 0.75em;
            font-weight: 700;
            line-height: 1;
            color: #fff;
            text-align: center;
            white-space: nowrap;
            vertical-align: baseline;
            border-radius: 0.375rem;
        }
        
        .bg-primary { background-color: #0d6efd !important; }
        .bg-success { background-color: #198754 !important; }
        .bg-secondary { background-color: #6c757d !important; }
        .bg-info { background-color: #0dcaf0 !important; }
        .bg-warning { background-color: #ffc107 !important; }
        .bg-danger { background-color: #dc3545 !important; }
        
        .accordion {
            --bs-accordion-color: #212529;
            --bs-accordion-bg: #fff;
            --bs-accordion-transition: color 0.15s ease-in-out, background-color 0.15s ease-in-out, border-color 0.15s ease-in-out, box-shadow 0.15s ease-in-out, border-radius 0.375s ease;
            --bs-accordion-border-color: var(--bs-border-color);
            --bs-accordion-border-width: 1px;
            --bs-accordion-border-radius: 0.375rem;
            --bs-accordion-inner-border-radius: calc(0.375rem - 1px);
            --bs-accordion-btn-padding-x: 1.25rem;
            --bs-accordion-btn-padding-y: 1rem;
            --bs-accordion-btn-color: var(--bs-accordion-color);
            --bs-accordion-btn-bg: var(--bs-accordion-bg);
            --bs-accordion-btn-icon: url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16' fill='%236c757d'%3e%3cpath fill-rule='evenodd' d='M1.646 4.646a.5.5 0 0 1 .708 0L8 10.293l5.646-5.647a.5.5 0 0 1 .708.708l-6 6a.5.5 0 0 1-.708 0l-6-6a.5.5 0 0 1 0-.708z'/%3e%3c/svg%3e");
            --bs-accordion-btn-icon-width: 1.25rem;
            --bs-accordion-btn-icon-transform: rotate(-180deg);
            --bs-accordion-btn-icon-transition: transform 0.2s ease-in-out;
            --bs-accordion-btn-active-icon: url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16' fill='%230c63e4'%3e%3cpath fill-rule='evenodd' d='M1.646 4.646a.5.5 0 0 1 .708 0L8 10.293l5.646-5.647a.5.5 0 0 1 .708.708l-6 6a.5.5 0 0 1-.708 0l-6-6a.5.5 0 0 1 0-.708z'/%3e%3c/svg%3e");
            --bs-accordion-btn-focus-border-color: #86b7fe;
            --bs-accordion-btn-focus-box-shadow: 0 0 0 0.25rem rgba(13, 110, 253, 0.25);
            --bs-accordion-body-padding-x: 1.25rem;
            --bs-accordion-body-padding-y: 1rem;
            --bs-accordion-active-color: #0c63e4;
            --bs-accordion-active-bg: #e7f1ff;
        }
        
        .accordion-item {
            color: var(--bs-accordion-color);
            background-color: var(--bs-accordion-bg);
            border: var(--bs-accordion-border-width) solid var(--bs-accordion-border-color);
        }
        
        .accordion-item:not(:first-of-type) {
            border-top: 0;
        }
        
        .accordion-item:first-of-type {
            border-top-left-radius: var(--bs-accordion-border-radius);
            border-top-right-radius: var(--bs-accordion-border-radius);
        }
        
        .accordion-item:last-of-type {
            border-bottom-right-radius: var(--bs-accordion-border-radius);
            border-bottom-left-radius: var(--bs-accordion-border-radius);
        }
        
        .accordion-button {
            position: relative;
            display: flex;
            align-items: center;
            width: 100%;
            padding: var(--bs-accordion-btn-padding-y) var(--bs-accordion-btn-padding-x);
            font-size: 1rem;
            color: var(--bs-accordion-btn-color);
            text-align: left;
            background-color: var(--bs-accordion-btn-bg);
            border: 0;
            border-radius: 0;
            overflow-anchor: none;
            transition: var(--bs-accordion-transition);
            cursor: pointer;
        }
        
        .accordion-button:not(.collapsed) {
            color: var(--bs-accordion-active-color);
            background-color: var(--bs-accordion-active-bg);
            box-shadow: inset 0 calc(-1 * var(--bs-accordion-border-width)) 0 var(--bs-accordion-border-color);
        }
        
        .accordion-button::after {
            flex-shrink: 0;
            width: var(--bs-accordion-btn-icon-width);
            height: var(--bs-accordion-btn-icon-width);
            margin-left: auto;
            content: "";
            background-image: var(--bs-accordion-btn-icon);
            background-repeat: no-repeat;
            background-size: var(--bs-accordion-btn-icon-width);
            transition: var(--bs-accordion-btn-icon-transition);
        }
        
        .accordion-button:not(.collapsed)::after {
            background-image: var(--bs-accordion-btn-active-icon);
            transform: var(--bs-accordion-btn-icon-transform);
        }
        
        .accordion-collapse {
            display: none;
        }
        
        .accordion-collapse.show {
            display: block;
        }
        
        .accordion-body {
            padding: var(--bs-accordion-body-padding-y) var(--bs-accordion-body-padding-x);
        }
        
        .list-group {
            display: flex;
            flex-direction: column;
            padding-left: 0;
            margin-bottom: 0;
            border-radius: 0.375rem;
        }
        
        .list-group-item {
            position: relative;
            display: block;
            padding: 0.5rem 1rem;
            color: #212529;
            text-decoration: none;
            background-color: #fff;
            border: 1px solid rgba(0, 0, 0, 0.125);
        }
        
        .list-group-item:first-child {
            border-top-left-radius: inherit;
            border-top-right-radius: inherit;
        }
        
        .list-group-item:last-child {
            border-bottom-right-radius: inherit;
            border-bottom-left-radius: inherit;
        }
        
        .d-flex {
            display: flex !important;
        }
        
        .justify-content-between {
            justify-content: space-between !important;
        }
        
        .align-items-center {
            align-items: center !important;
        }
        
        .text-end {
            text-align: right !important;
        }
        
        .text-muted {
            color: #6c757d !important;
        }
        
        .mb-0 { margin-bottom: 0 !important; }
        .mb-1 { margin-bottom: 0.25rem !important; }
        .mb-2 { margin-bottom: 0.5rem !important; }
        .mb-3 { margin-bottom: 1rem !important; }
        .mb-4 { margin-bottom: 1.5rem !important; }
        
        .mt-2 { margin-top: 0.5rem !important; }
        .mt-3 { margin-top: 1rem !important; }
        
        .my-4 { margin-top: 1.5rem !important; margin-bottom: 1.5rem !important; }
        
        .w-100 { width: 100% !important; }
        
        .d-block { display: block !important; }
        
        .hidden {
            display: none !important;
        }
        
        /* 代码样式 */
        pre {
            display: block;
            padding: 1rem;
            margin: 0 0 1rem;
            font-size: 0.875rem;
            line-height: 1.5;
            color: #212529;
            word-break: break-all;
            word-wrap: break-word;
            background-color: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 0.375rem;
            overflow-x: auto;
        }
        
        code {
            font-size: 0.875em;
            color: #d63384;
            word-wrap: break-word;
            font-family: SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
        }
        
        pre code {
            color: inherit;
            word-break: normal;
        }
        
        .sql-code {
            background-color: #e9ecef;
            padding: 0.75rem;
            border-radius: 0.3rem;
            font-family: 'Courier New', Courier, monospace;
            white-space: pre-wrap;
            word-break: break-all;
            font-size: 0.875rem;
        }
        
        .orm-code-highlight {
            background-color: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 0.375rem;
            padding: 1rem;
            font-family: 'Courier New', Courier, monospace;
            font-size: 0.875rem;
            line-height: 1.5;
            max-height: 300px;
            overflow-y: auto;
        }
        
        .meta-data-highlight {
            background-color: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 0.375rem;
            padding: 1rem;
            font-family: 'Courier New', Courier, monospace;
            font-size: 0.875rem;
            line-height: 1.5;
            max-height: 200px;
            overflow-y: auto;
        }
        
        /* 响应式设计 */
        @media (max-width: 768px) {
            .col-md-3, .col-md-4, .col-md-6 {
                flex: 0 0 100%;
                max-width: 100%;
            }
        }
        
        /* 打印样式 */
        @media print {
            .no-print {
                display: none !important;
            }
            .accordion-collapse {
                display: block !important;
            }
            .accordion-button::after {
                display: none;
            }
            .accordion-button {
                border: none !important;
                padding: 1rem 0;
            }
            .container-fluid {
                width: 100% !important;
                max-width: none !important;
                padding: 0 !important;
            }
        }
    """

def generate_standalone_html(data_path: str, summary: dict, file_list: list, dataset_data: list) -> str:
    """
    生成独立的HTML文件，包含所有数据，确保可以独立运行。
    """
    # 使用Jinja2模板引擎直接渲染
    template = templates.get_template("dataset_viewer.html")
    html_content = template.render({
        "request": None,  # 导出时不需要request对象
        "data_path": data_path,
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "summary": summary,
        "file_list": file_list,
        "dataset_data": dataset_data
    })
    
    # 使用BeautifulSoup处理HTML，将外部CDN资源内联
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 确保文件列表折叠样式被包含 - 直接插入到head最前面
    file_list_collapsed_style = """
.file-list-card {
    transition: all 0.3s ease;
}
.file-list-card.collapsed {
    max-height: 0;
    overflow: hidden;
}
"""
    
    # 在head标签最前面插入折叠样式，确保不被覆盖
    if soup.head:
        style_tag = soup.new_tag('style')
        style_tag.string = file_list_collapsed_style
        soup.head.insert(0, style_tag)
    else:
        # 如果没有head标签，创建一个
        head_tag = soup.new_tag('head')
        style_tag = soup.new_tag('style')
        style_tag.string = file_list_collapsed_style
        head_tag.append(style_tag)
        soup.insert(0, head_tag)
    
    # 处理<link rel="stylesheet" href=...>
    for link in soup.find_all('link', rel='stylesheet'):
        href = link.get('href')
        logger.info(f"正在下载CSS资源: {href}")
        
        # 根据href确定资源类型和对应的CDN源列表
        resources = get_template_resources()
        css_urls = None
        
        if 'bootstrap' in href.lower() and 'icons' not in href.lower():
            css_urls = resources['bootstrap_css']
        elif 'bootstrap-icons' in href.lower():
            css_urls = resources['bootstrap_icons']
        elif 'prism' in href.lower():
            css_urls = resources['prism_css']
        else:
            # 对于未知资源，尝试直接下载
            css_urls = [href]
        
        # 尝试从多个CDN源下载
        css = get_external_resource_content(css_urls)
        
        # 如果所有CDN源都失败，使用本地备用样式
        if not css:
            if 'bootstrap' in href.lower() and 'icons' not in href.lower():
                css = get_fallback_styles()
                logger.info("使用本地Bootstrap样式")
            elif 'bootstrap-icons' in href.lower():
                css = get_local_bootstrap_icons()
                if not css:
                    css = """
                    /* Bootstrap Icons 基础样式 */
                    @font-face {
                        font-family: "bootstrap-icons";
                        src: url("data:font/woff2;charset=utf-8;base64,d09GMgABAAAAAA...") format("woff2");
                    }
                    
                    .bi::before,
                    [class^="bi-"]::before,
                    [class*=" bi-"]::before {
                        display: inline-block;
                        font-family: bootstrap-icons !important;
                        font-style: normal;
                        font-weight: normal !important;
                        font-variant: normal;
                        text-transform: none;
                        line-height: 1;
                        vertical-align: -.125em;
                        -webkit-font-smoothing: antialiased;
                        -moz-osx-font-smoothing: grayscale;
                    }
                    
                    /* 常用图标 */
                    .bi-search::before { content: "\\f52a"; }
                    .bi-file-earmark-text::before { content: "\\f31d"; }
                    .bi-journal-code::before { content: "\\f3b3"; }
                    .bi-diagram-2::before { content: "\\f43a"; }
                    .bi-file-earmark-code::before { content: "\\f31c"; }
                    .bi-tags::before { content: "\\f5c3"; }
                    .bi-info-circle::before { content: "\\f430"; }
                    .bi-folder2-open::before { content: "\\f75e"; }
                    .bi-chevron-down::before { content: "\\f282"; }
                    .bi-chevron-up::before { content: "\\f285"; }
                    .bi-exclamation-triangle::before { content: "\\f33a"; }
                    .bi-x-circle::before { content: "\\f5e7"; }
                    .bi-check-circle::before { content: "\\f26b"; }
                    .bi-file-earmark-json::before { content: "\\f31b"; }
                    """
                logger.info("使用本地Bootstrap图标")
            elif 'prism' in href.lower():
                css = """
                /* Prism.js 完整样式 */
                code[class*="language-"],
                pre[class*="language-"] {
                    color: #333;
                    background: none;
                    font-family: Consolas, Monaco, 'Andale Mono', 'Ubuntu Mono', monospace;
                    font-size: 1em;
                    text-align: left;
                    white-space: pre;
                    word-spacing: normal;
                    word-break: normal;
                    word-wrap: normal;
                    line-height: 1.5;
                    tab-size: 4;
                    hyphens: none;
                }
                
                pre[class*="language-"] {
                    padding: 1em;
                    margin: .5em 0;
                    overflow: auto;
                    border-radius: 0.3em;
                }
                
                :not(pre) > code[class*="language-"] {
                    padding: .2em;
                    border-radius: .3em;
                    white-space: normal;
                }
                
                .token.comment,
                .token.prolog,
                .token.doctype,
                .token.cdata {
                    color: #999;
                }
                
                .token.punctuation {
                    color: #333;
                }
                
                .token.namespace {
                    opacity: .7;
                }
                
                .token.property,
                .token.tag,
                .token.boolean,
                .token.number,
                .token.constant,
                .token.symbol,
                .token.deleted {
                    color: #905;
                }
                
                .token.selector,
                .token.attr-name,
                .token.string,
                .token.char,
                .token.builtin,
                .token.inserted {
                    color: #690;
                }
                
                .token.operator,
                .token.entity,
                .token.url,
                .language-css .token.string,
                .style .token.string {
                    color: #a67f59;
                    background: rgba(255, 255, 255, 0.5);
                }
                
                .token.atrule,
                .token.attr-value,
                .token.keyword {
                    color: #07a;
                }
                
                .token.function {
                    color: #dd4a68;
                }
                
                .token.regex,
                .token.important,
                .token.variable {
                    color: #e90;
                }
                
                .token.important,
                .token.bold {
                    font-weight: bold;
                }
                
                .token.italic {
                    font-style: italic;
                }
                
                .token.entity {
                    cursor: help;
                }
                
                /* 新增样式 */
                .token.class-name {
                    color: #dd4a68;
                }
                
                .token.boolean {
                    color: #905;
                }
                
                /* 确保代码块有适当的背景色 */
                .orm-code-highlight,
                .meta-data-highlight,
                .sql-code {
                    background-color: #f8f9fa;
                    border: 1px solid #dee2e6;
                    border-radius: 0.375rem;
                    padding: 1rem;
                    font-family: 'Courier New', Courier, monospace;
                    font-size: 0.875rem;
                    line-height: 1.5;
                }
                
                /* 代码高亮增强 */
                pre code {
                    display: block;
                    overflow-x: auto;
                    padding: 1em;
                    background: #f8f9fa;
                    border-radius: 0.375rem;
                }
                
                /* 确保token样式正确显示 */
                .token.keyword {
                    color: #007bff;
                    font-weight: bold;
                }
                
                .token.string {
                    color: #28a745;
                }
                
                .token.number {
                    color: #fd7e14;
                }
                
                .token.comment {
                    color: #6c757d;
                    font-style: italic;
                }
                
                .token.function {
                    color: #e83e8c;
                }
                
                .token.operator {
                    color: #6f42c1;
                }
                
                /* 确保隐藏功能正常工作 */
                .accordion-item.hidden {
                    display: none !important;
                }
                
                .hidden {
                    display: none !important;
                }
                """
                logger.info("使用本地Prism.js样式")
            else:
                css = f'/* 获取失败: {href} */'
        
        style_tag = soup.new_tag('style')
        style_tag.string = css
        link.replace_with(style_tag)
    
    # 处理<script src=...>
    for script in soup.find_all('script', src=True):
        src = script.get('src')
        logger.info(f"正在下载JS资源: {src}")
        
        # 根据src确定资源类型和对应的CDN源列表
        resources = get_template_resources()
        js_urls = None
        
        if 'bootstrap' in src.lower():
            js_urls = resources['bootstrap_js']
        elif 'prism-core' in src.lower():
            js_urls = resources['prism_js']
        elif 'prism-autoloader' in src.lower():
            js_urls = resources['prism_autoloader']
        elif 'prism-sql' in src.lower():
            js_urls = resources['prism_sql']
        elif 'prism-python' in src.lower():
            js_urls = resources['prism_python']
        elif 'prism' in src.lower() and 'autoloader' not in src.lower():
            js_urls = resources['prism_js']  # 默认使用prism-core
        else:
            # 对于未知资源，尝试直接下载
            js_urls = [src]
        
        # 尝试从多个CDN源下载
        js = get_external_resource_content(js_urls)
        
        # 如果所有CDN源都失败，使用本地备用功能
        if not js:
            if 'bootstrap' in src.lower():
                js = """
                // 完全内联的搜索和过滤功能
                var currentFilter = 'all';
                var fileSearchTerm = '';
                var contentSearchTerm = '';
                var fileListCollapsed = false;
                
                // 文件名搜索函数
                function performFileSearch() {
                    var searchInput = document.getElementById('fileSearch');
                    var statusDiv = document.getElementById('fileSearchStatus');
                    fileSearchTerm = searchInput.value;
                    
                    console.log('执行文件名搜索:', fileSearchTerm);
                    
                    if (fileSearchTerm.trim() === '') {
                        statusDiv.innerHTML = '<span class="text-warning"><i class="bi bi-exclamation-triangle"></i> 请输入搜索关键词</span>';
                        updateFilters();
                        return;
                    }
                    
                    statusDiv.innerHTML = '<span class="text-info"><i class="bi bi-search"></i> 正在搜索...</span>';
                    
                    // 立即执行搜索
                    updateFilters();
                    var visibleItems = document.querySelectorAll('.accordion-item:not(.hidden)');
                    
                    console.log('搜索结果:', visibleItems.length, '/', document.querySelectorAll('.accordion-item').length);
                    
                    if (visibleItems.length === 0) {
                        statusDiv.innerHTML = '<span class="text-danger"><i class="bi bi-x-circle"></i> 未找到匹配的文件</span>';
                    } else {
                        statusDiv.innerHTML = '<span class="text-success"><i class="bi bi-check-circle"></i> 找到 ' + visibleItems.length + ' 个匹配项</span>';
                    }
                }
                
                // 内容搜索函数
                function performContentSearch() {
                    var searchInput = document.getElementById('contentSearch');
                    var statusDiv = document.getElementById('contentSearchStatus');
                    contentSearchTerm = searchInput.value;
                    
                    console.log('执行内容搜索:', contentSearchTerm);
                    
                    if (contentSearchTerm.trim() === '') {
                        statusDiv.innerHTML = '<span class="text-warning"><i class="bi bi-exclamation-triangle"></i> 请输入搜索关键词</span>';
                        updateFilters();
                        return;
                    }
                    
                    statusDiv.innerHTML = '<span class="text-info"><i class="bi bi-search"></i> 正在搜索...</span>';
                    
                    // 立即执行搜索
                    updateFilters();
                    var visibleItems = document.querySelectorAll('.accordion-item:not(.hidden)');
                    
                    console.log('搜索结果:', visibleItems.length, '/', document.querySelectorAll('.accordion-item').length);
                    
                    if (visibleItems.length === 0) {
                        statusDiv.innerHTML = '<span class="text-danger"><i class="bi bi-x-circle"></i> 未找到匹配的内容</span>';
                    } else {
                        statusDiv.innerHTML = '<span class="text-success"><i class="bi bi-check-circle"></i> 找到 ' + visibleItems.length + ' 个匹配项</span>';
                    }
                }
                
                // 更新过滤和搜索
                function updateFilters() {
                    var items = document.querySelectorAll('.accordion-item');
                    var visibleCount = 0;
                    
                    console.log('更新过滤条件:', {
                        fileSearch: fileSearchTerm,
                        contentSearch: contentSearchTerm,
                        filter: currentFilter
                    });
                    
                    for (var i = 0; i < items.length; i++) {
                        var item = items[i];
                        var functionName = item.querySelector('code').textContent || '';
                        var ormCode = item.dataset.ormCode || '';
                        var filename = item.dataset.filename || '';
                        
                        console.log('检查项目:', {
                            functionName: functionName,
                            ormCode: ormCode.substring(0, 50) + '...',
                            filename: filename
                        });
                        
                        var showItem = true;
                        
                        // 文件名搜索
                        if (fileSearchTerm && fileSearchTerm.trim() !== '') {
                            var searchTerm = fileSearchTerm.toLowerCase();
                            var filenameLower = filename.toLowerCase();
                            if (filenameLower.indexOf(searchTerm) === -1) {
                                showItem = false;
                                console.log('文件名不匹配:', filename, 'vs', searchTerm);
                            }
                        }
                        
                        // 内容搜索
                        if (contentSearchTerm && contentSearchTerm.trim() !== '') {
                            var searchTerm = contentSearchTerm.toLowerCase();
                            var functionNameLower = functionName.toLowerCase();
                            var ormCodeLower = ormCode.toLowerCase();
                            var filenameLower = filename.toLowerCase();
                            
                            var hasMatch = functionNameLower.indexOf(searchTerm) !== -1 || 
                                         ormCodeLower.indexOf(searchTerm) !== -1 ||
                                         filenameLower.indexOf(searchTerm) !== -1;
                            
                            if (!hasMatch) {
                                showItem = false;
                                console.log('内容不匹配:', searchTerm);
                            }
                        }
                        
                        // 类型过滤
                        if (showItem && currentFilter !== 'all') {
                            var sqlContent = item.querySelector('.sql-code');
                            var hasSql = sqlContent && sqlContent.textContent.trim() !== '';
                            var isParamDependent = item.querySelector('.badge.bg-info') && 
                                                 item.querySelector('.badge.bg-info').textContent.indexOf('PARAM_DEPENDENT') !== -1;
                            var isControlFlow = item.querySelector('.badge.bg-warning') && 
                                              item.querySelector('.badge.bg-warning').textContent.indexOf('控制流') !== -1;
                            
                            switch(currentFilter) {
                                case 'has-sql':
                                    showItem = hasSql;
                                    break;
                                case 'no-sql':
                                    showItem = !hasSql;
                                    break;
                                case 'param-dependent':
                                    showItem = isParamDependent;
                                    break;
                                case 'control-flow':
                                    showItem = isControlFlow;
                                    break;
                            }
                        }
                        
                        // 应用显示/隐藏
                        if (showItem) {
                            visibleCount++;
                            item.style.display = '';
                            item.classList.remove('hidden');
                        } else {
                            item.style.display = 'none';
                            item.classList.add('hidden');
                        }
                    }
                    
                    console.log('过滤完成: 显示 ' + visibleCount + ' / ' + items.length + ' 条记录');
                }
                
                // 文件列表折叠
                function toggleFileList() {
                    var content = document.getElementById('fileListContent');
                    var toggle = document.getElementById('fileListToggle');
                    
                    if (fileListCollapsed) {
                        content.classList.remove('collapsed');
                        toggle.classList.remove('bi-chevron-up');
                        toggle.classList.add('bi-chevron-down');
                        fileListCollapsed = false;
                    } else {
                        content.classList.add('collapsed');
                        toggle.classList.remove('bi-chevron-down');
                        toggle.classList.add('bi-chevron-up');
                        fileListCollapsed = true;
                    }
                }
                
                // 手风琴折叠功能
                function initAccordion() {
                    var accordionButtons = document.querySelectorAll('.accordion-button');
                    for (var i = 0; i < accordionButtons.length; i++) {
                        var button = accordionButtons[i];
                        button.addEventListener('click', function() {
                            var targetId = this.getAttribute('data-bs-target');
                            var target = document.querySelector(targetId);
                            if (target) {
                                var isCollapsed = target.classList.contains('show');
                                if (isCollapsed) {
                                    target.classList.remove('show');
                                    this.classList.add('collapsed');
                                    this.setAttribute('aria-expanded', 'false');
                                } else {
                                    target.classList.add('show');
                                    this.classList.remove('collapsed');
                                    this.setAttribute('aria-expanded', 'true');
                                }
                            }
                        });
                    }
                }
                
                // 初始化过滤按钮
                function initFilterButtons() {
                    var filterButtons = document.querySelectorAll('.filter-btn');
                    for (var i = 0; i < filterButtons.length; i++) {
                        var btn = filterButtons[i];
                        btn.addEventListener('click', function() {
                            var allButtons = document.querySelectorAll('.filter-btn');
                            for (var j = 0; j < allButtons.length; j++) {
                                allButtons[j].classList.remove('active');
                            }
                            this.classList.add('active');
                            currentFilter = this.dataset.filter;
                            updateFilters();
                        });
                    }
                }
                
                // 初始化搜索输入框回车事件
                function initSearchInputs() {
                    var fileSearchInput = document.getElementById('fileSearch');
                    if (fileSearchInput) {
                        fileSearchInput.addEventListener('keypress', function(e) {
                            if (e.key === 'Enter') {
                                performFileSearch();
                            }
                        });
                    }
                    
                    var contentSearchInput = document.getElementById('contentSearch');
                    if (contentSearchInput) {
                        contentSearchInput.addEventListener('keypress', function(e) {
                            if (e.key === 'Enter') {
                                performContentSearch();
                            }
                        });
                    }
                }
                
                // 导出功能
                function exportHTML() {
                    alert('导出功能在独立HTML文件中不可用，请使用在线版本进行导出。');
                }
                
                function exportJSON() {
                    alert('导出功能在独立HTML文件中不可用，请使用在线版本进行导出。');
                }
                
                // 页面加载完成后初始化
                document.addEventListener('DOMContentLoaded', function() {
                    console.log('初始化搜索和过滤功能...');
                    initAccordion();
                    initFilterButtons();
                    initSearchInputs();
                    
                    // 确保所有元素初始可见
                    var allItems = document.querySelectorAll('.accordion-item');
                    for (var i = 0; i < allItems.length; i++) {
                        allItems[i].style.display = '';
                        allItems[i].classList.remove('hidden');
                    }
                    console.log('初始化完成，共 ' + allItems.length + ' 个项目');
                });
                """
                logger.info("使用本地折叠功能")
            elif 'prism' in src.lower():
                js = """
                /* Prism.js 完整功能实现 */
                var Prism = (function() {
                    var _self = {};
                    
                    _self.highlightElement = function(element) {
                        if (element && element.textContent) {
                            var language = _self.getLanguage(element.className);
                            element.innerHTML = _self.highlight(element.textContent, language);
                        }
                    };
                    
                    _self.highlightAll = function() {
                        var elements = document.querySelectorAll('pre code');
                        for (var i = 0; i < elements.length; i++) {
                            _self.highlightElement(elements[i]);
                        }
                    };
                    
                    _self.getLanguage = function(className) {
                        if (!className) return '';
                        var match = className.match(/language-(\\w+)/);
                        return match ? match[1] : '';
                    };
                    
                    _self.highlight = function(text, language) {
                        if (!language) return text;
                        
                        switch(language.toLowerCase()) {
                            case 'sql':
                            return _self.highlightSQL(text);
                            case 'python':
                            return _self.highlightPython(text);
                            case 'json':
                                return _self.highlightJSON(text);
                            default:
                        return text;
                        }
                    };
                    
                    _self.highlightSQL = function(text) {
                        return text
                            .replace(/\\b(SELECT|FROM|WHERE|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|TABLE|INDEX|PRIMARY|KEY|FOREIGN|REFERENCES|INNER|LEFT|RIGHT|OUTER|JOIN|ON|GROUP|BY|ORDER|HAVING|UNION|ALL|DISTINCT|AS|IN|NOT|AND|OR|IS|NULL|LIKE|BETWEEN|EXISTS|CASE|WHEN|THEN|ELSE|END|COUNT|SUM|AVG|MAX|MIN|LIMIT|OFFSET|ASC|DESC|DISTINCT|UNIQUE|CHECK|DEFAULT|CASCADE|RESTRICT|SET|VALUES|INTO)\\b/gi, '<span class="token keyword">$1</span>')
                            .replace(/\\b(\\d+(\\.\\d+)?)\\b/g, '<span class="token number">$1</span>')
                            .replace(/('.*?')/g, '<span class="token string">$1</span>')
                            .replace(/(".*?")/g, '<span class="token string">$1</span>')
                            .replace(/(\\w+)\\.(\\w+)/g, '<span class="token property">$1</span>.<span class="token property">$2</span>')
                            .replace(/([;,\\(\\)])/g, '<span class="token punctuation">$1</span>')
                            .replace(/\\b(\\w+)\\s*\\(/g, '<span class="token function">$1</span>(');
                    };
                    
                    _self.highlightPython = function(text) {
                        return text
                            .replace(/\\b(def|class|import|from|as|return|if|else|elif|for|in|while|try|except|finally|with|lambda|True|False|None|and|or|not|is|in|del|pass|break|continue|raise|yield|global|nonlocal|self|super|__init__|__str__|__repr__|__len__|__getitem__|__setitem__|__delitem__|__iter__|__next__|__enter__|__exit__)\\b/g, '<span class="token keyword">$1</span>')
                            .replace(/\\b(\\d+(\\.\\d+)?)\\b/g, '<span class="token number">$1</span>')
                            .replace(/('.*?')/g, '<span class="token string">$1</span>')
                            .replace(/(".*?")/g, '<span class="token string">$1</span>')
                            .replace(/(#.*)$/gm, '<span class="token comment">$1</span>')
                            .replace(/([+\\-*/=<>!&|%]|\\+=|\\-=|\\*=|/=|%=|==|!=|<=|>=|\\*\\*|//|\\*\\*=|//=)/g, '<span class="token operator">$1</span>')
                            .replace(/\\b([A-Z][a-zA-Z0-9_]*)\\b/g, '<span class="token class-name">$1</span>')
                            .replace(/\\b([a-zA-Z_][a-zA-Z0-9_]*)\\s*\\(/g, '<span class="token function">$1</span>(');
                    };
                    
                    _self.highlightJSON = function(text) {
                        return text
                            .replace(/(".*?")\\s*:/g, '<span class="token property">$1</span>:')
                            .replace(/:\\s*(".*?")/g, ': <span class="token string">$1</span>')
                            .replace(/:\\s*(\\d+(\\.\\d+)?)/g, ': <span class="token number">$1</span>')
                            .replace(/:\\s*(true|false|null)/gi, ': <span class="token boolean">$1</span>')
                            .replace(/([{}\\[\\],])/g, '<span class="token punctuation">$1</span>');
                    };
                    
                    return _self;
                })();
                
                // 确保在DOM加载完成后执行高亮
                document.addEventListener('DOMContentLoaded', function() {
                    if (typeof Prism !== 'undefined') {
                        Prism.highlightAll();
                    }
                });
                
                // 监听手风琴展开事件，重新高亮代码
                document.addEventListener('shown.bs.collapse', function(event) {
                    if (event.target.classList.contains('accordion-collapse')) {
                        const codeBlocks = event.target.querySelectorAll('pre code');
                        codeBlocks.forEach(block => {
                            if (typeof Prism !== 'undefined') {
                                Prism.highlightElement(block);
                            }
                        });
                    }
                });
                """
                logger.info("使用本地Prism.js功能")
            else:
                js = f'// 获取失败: {src}'
        
        script_tag = soup.new_tag('script')
        script_tag.string = js
        script.replace_with(script_tag)
    
    # 返回最终HTML
    return str(soup)

def scan_for_reports():
    """扫描所有评估结果目录，生成报告列表"""
    reports = {
        'fingerprint_eval': [],
        'comparative_eval': [],
        'reward_logs': []
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
    
    # 扫描reward日志文件
    reward_logs_dir = BASE_DIR / "model" / "rl" / "reward_logs"
    if reward_logs_dir.exists():
        for jsonl_file in sorted(reward_logs_dir.glob("*.jsonl"), key=os.path.getmtime, reverse=True):
            if jsonl_file.is_file():
                reports['reward_logs'].append({
                    "timestamp": jsonl_file.stem,  # 文件名（不含扩展名）
                    "path": f"/reward_viewer/{jsonl_file.stem}",
                    "display_name": f"Reward日志 - {jsonl_file.stem}",
                    "filename": jsonl_file.name
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
    
    try:
        data = load_json_file(result_file)
        
        # 预处理数据，确保所有字符串都是原始Unicode形式
        def decode_unicode(obj):
            if isinstance(obj, str):
                return obj
            elif isinstance(obj, dict):
                return {k: decode_unicode(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [decode_unicode(item) for item in obj]
            return obj
        
        data = decode_unicode(data)
        
        # 为每个结果项预生成格式化的JSON字符串
        if isinstance(data, dict) and 'results' in data:
            for result in data['results']:
                if isinstance(result, dict):
                    if 'baseline_sql' in result:
                        result['baseline_sql_formatted'] = json.dumps(result['baseline_sql'], indent=2, ensure_ascii=False)
                    if 'model_generated_structured' in result:
                        result['model_generated_structured_formatted'] = json.dumps(result['model_generated_structured'], indent=2, ensure_ascii=False)
                    if 'code_meta_data' in result:
                        result['code_meta_data_formatted'] = json.dumps(result['code_meta_data'], indent=2, ensure_ascii=False)
        
        return templates.TemplateResponse(
            "comparative_report.html",
            {
                "request": request,
                "report_data": data,
                "timestamp": timestamp
            }
        )
    except Exception as e:
        logger.error(f"处理结果文件时出错: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"处理结果文件时出错: {str(e)}")

@app.get("/dataset_viewer", response_class=HTMLResponse)
async def dataset_viewer(request: Request, path: str = "datasets/claude_output"):
    """数据集查看器页面"""
    try:
        # 读取指定路径下的所有JSON文件
        data_dir = Path(path)
        if not data_dir.exists():
            return templates.TemplateResponse("error.html", {
                "request": request,
                "error": f"数据路径不存在: {path}"
            })
        
        # 查找所有JSON文件
        json_files = list(data_dir.glob('*.json'))
        if not json_files:
            return templates.TemplateResponse("error.html", {
                "request": request,
                "error": f"在 {path} 中未找到JSON文件"
            })
        
        # 读取所有数据
        all_data = []
        file_list = []
        total_records = 0
        records_with_sql = 0
        records_without_sql = 0
        param_dependent_count = 0
        control_flow_count = 0
        total_sql_variants = 0
        
        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    file_data = json.load(f)
                
                # 确保数据是列表格式
                if isinstance(file_data, list):
                    records = file_data
                elif isinstance(file_data, dict) and 'records' in file_data:
                    records = file_data['records']
                elif isinstance(file_data, dict) and 'data' in file_data:
                    records = file_data['data']
                else:
                    records = [file_data] if isinstance(file_data, dict) else []
                
                # 统计文件信息
                file_record_count = len(records)
                file_sql_count = 0
                file_param_dependent_count = 0
                file_control_flow_count = 0
                
                # 处理每条记录
                for record in records:
                    if isinstance(record, dict):
                        # 格式化代码元数据
                        code_meta_data = record.get('code_meta_data', [])
                        if code_meta_data:
                            formatted_meta = []
                            for meta in code_meta_data:
                                if isinstance(meta, dict):
                                    parts = []
                                    if 'code_file' in meta:
                                        parts.append(f"文件: {meta['code_file']}")
                                    if 'code_start_line' in meta and 'code_end_line' in meta:
                                        parts.append(f"行号: {meta['code_start_line']}-{meta['code_end_line']}")
                                    if 'code_key' in meta:
                                        parts.append(f"键: {meta['code_key']}")
                                    if 'code_value' in meta:
                                        parts.append(f"值: {meta['code_value']}")
                                    formatted_meta.append(' | '.join(parts))
                            record['code_meta_data_formatted'] = '\n'.join(formatted_meta)
                        
                        # 统计SQL相关信息
                        sql_list = record.get('sql_statement_list', [])
                        if sql_list:
                            file_sql_count += 1
                            records_with_sql += 1
                            
                            # 统计参数依赖类型
                            if isinstance(sql_list, list):
                                for sql_item in sql_list:
                                    if isinstance(sql_item, dict) and sql_item.get('type') == 'param_dependent':
                                        file_param_dependent_count += 1
                                        param_dependent_count += 1
                                        variants = sql_item.get('variants', [])
                                        total_sql_variants += len(variants)
                        else:
                            records_without_sql += 1
                        
                        # 统计控制流
                        orm_code = record.get('orm_code', '')
                        if 'switch' in orm_code.lower() or 'if' in orm_code.lower():
                            file_control_flow_count += 1
                            control_flow_count += 1
                        
                        # 添加源文件信息
                        record['source_file'] = str(json_file)
                
                # 添加到总数据
                all_data.extend(records)
                total_records += file_record_count
                
                # 文件信息
                file_info = {
                    'filename': json_file.name,
                    'file_path': str(json_file),
                    'record_count': file_record_count,
                    'sql_count': file_sql_count,
                    'param_dependent_count': file_param_dependent_count,
                    'control_flow_count': file_control_flow_count,
                    'file_size': f"{json_file.stat().st_size / 1024:.1f} KB"
                }
                file_list.append(file_info)
                
            except Exception as e:
                logger.error(f"读取文件 {json_file} 失败: {e}")
                continue
        
        # 计算摘要统计
        summary = {
            'file_count': len(file_list),
            'total_records': total_records,
            'records_with_sql': records_with_sql,
            'records_without_sql': records_without_sql,
            'param_dependent_count': param_dependent_count,
            'control_flow_count': control_flow_count,
            'avg_sql_variants': total_sql_variants / max(records_with_sql, 1)
        }
        
        return templates.TemplateResponse("dataset_viewer.html", {
            "request": request,
            "data_path": path,
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "summary": summary,
            "file_list": file_list,
            "dataset_data": all_data
        })
        
    except Exception as e:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": f"处理数据时出错: {str(e)}"
        })

@app.get("/api/dataset_info")
async def api_dataset_info(path: str = "datasets/claude_output"):
    """API接口：获取数据集信息"""
    try:
        data_dir = Path(path)
        if not data_dir.exists():
            raise HTTPException(status_code=404, detail=f"数据路径不存在: {path}")
        
        json_files = list(data_dir.glob('*.json'))
        file_info = []
        
        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    file_data = json.load(f)
                
                if isinstance(file_data, list):
                    record_count = len(file_data)
                elif isinstance(file_data, dict):
                    record_count = 1
                else:
                    record_count = 0
                
                file_info.append({
                    'filename': json_file.name,
                    'file_path': str(json_file),
                    'record_count': record_count,
                    'file_size': json_file.stat().st_size
                })
                
            except Exception as e:
                file_info.append({
                    'filename': json_file.name,
                    'file_path': str(json_file),
                    'error': str(e)
                })
        
        return {
            'data_path': path,
            'file_count': len(file_info),
            'files': file_info
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/export_dataset_html")
async def export_dataset_html(path: str = "datasets/claude_output"):
    """API接口：导出数据集为独立HTML文件"""
    try:
        logger.info(f"开始导出数据集HTML: {path}")
        
        # 读取指定路径下的所有JSON文件
        data_dir = Path(path)
        if not data_dir.exists():
            raise HTTPException(status_code=404, detail=f"数据路径不存在: {path}")
        
        # 查找所有JSON文件
        json_files = list(data_dir.glob('*.json'))
        if not json_files:
            raise HTTPException(status_code=404, detail=f"在 {path} 中未找到JSON文件")
        
        # 读取所有数据
        all_data = []
        file_list = []
        total_records = 0
        records_with_sql = 0
        records_without_sql = 0
        param_dependent_count = 0
        control_flow_count = 0
        total_sql_variants = 0
        
        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    file_data = json.load(f)
                
                # 确保数据是列表格式
                if isinstance(file_data, list):
                    records = file_data
                elif isinstance(file_data, dict) and 'records' in file_data:
                    records = file_data['records']
                elif isinstance(file_data, dict) and 'data' in file_data:
                    records = file_data['data']
                else:
                    records = [file_data] if isinstance(file_data, dict) else []
                
                # 统计文件信息
                file_record_count = len(records)
                file_sql_count = 0
                file_param_dependent_count = 0
                file_control_flow_count = 0
                
                # 处理每条记录
                for record in records:
                    if isinstance(record, dict):
                        # 格式化代码元数据
                        code_meta_data = record.get('code_meta_data', [])
                        if code_meta_data:
                            formatted_meta = []
                            for meta in code_meta_data:
                                if isinstance(meta, dict):
                                    parts = []
                                    if 'code_file' in meta:
                                        parts.append(f"文件: {meta['code_file']}")
                                    if 'code_start_line' in meta and 'code_end_line' in meta:
                                        parts.append(f"行号: {meta['code_start_line']}-{meta['code_end_line']}")
                                    if 'code_key' in meta:
                                        parts.append(f"键: {meta['code_key']}")
                                    if 'code_value' in meta:
                                        parts.append(f"值: {meta['code_value']}")
                                    formatted_meta.append(' | '.join(parts))
                            record['code_meta_data_formatted'] = '\n'.join(formatted_meta)
                        
                        # 统计SQL相关信息
                        sql_list = record.get('sql_statement_list', [])
                        if sql_list:
                            file_sql_count += 1
                            records_with_sql += 1
                            
                            # 统计参数依赖类型
                            if isinstance(sql_list, list):
                                for sql_item in sql_list:
                                    if isinstance(sql_item, dict) and sql_item.get('type') == 'param_dependent':
                                        file_param_dependent_count += 1
                                        param_dependent_count += 1
                                        variants = sql_item.get('variants', [])
                                        total_sql_variants += len(variants)
                        else:
                            records_without_sql += 1
                        
                        # 统计控制流
                        orm_code = record.get('orm_code', '')
                        if 'switch' in orm_code.lower() or 'if' in orm_code.lower():
                            file_control_flow_count += 1
                            control_flow_count += 1
                        
                        # 添加源文件信息
                        record['source_file'] = str(json_file)
                
                # 添加到总数据
                all_data.extend(records)
                total_records += file_record_count
                
                # 文件信息
                file_info = {
                    'filename': json_file.name,
                    'file_path': str(json_file),
                    'record_count': file_record_count,
                    'sql_count': file_sql_count,
                    'param_dependent_count': file_param_dependent_count,
                    'control_flow_count': file_control_flow_count,
                    'file_size': f"{json_file.stat().st_size / 1024:.1f} KB"
                }
                file_list.append(file_info)
                
            except Exception as e:
                logger.error(f"读取文件 {json_file} 失败: {e}")
                continue
        
        # 计算摘要统计
        summary = {
            'file_count': len(file_list),
            'total_records': total_records,
            'records_with_sql': records_with_sql,
            'records_without_sql': records_without_sql,
            'param_dependent_count': param_dependent_count,
            'control_flow_count': control_flow_count,
            'avg_sql_variants': total_sql_variants / max(records_with_sql, 1)
        }
        
        # 生成独立HTML
        logger.info("开始生成HTML内容...")
        logger.info(f"数据统计: {len(all_data)} 条记录, {len(file_list)} 个文件")
        
        # 确保数据可以正确序列化
        try:
            # 测试数据序列化
            test_json = json.dumps(all_data[:1], ensure_ascii=False, default=str)
            logger.info("数据序列化测试通过")
        except Exception as e:
            logger.error(f"数据序列化测试失败: {e}")
            # 清理数据，移除可能导致序列化问题的字段
            for item in all_data:
                if isinstance(item, dict):
                    # 移除可能导致问题的字段
                    item.pop('_sa_instance_state', None)
                    item.pop('__dict__', None)
                    # 确保所有值都是可序列化的
                    for key, value in list(item.items()):
                        try:
                            json.dumps(value, ensure_ascii=False, default=str)
                        except:
                            # 如果某个值无法序列化，转换为字符串
                            item[key] = str(value)
        
        html_content = generate_standalone_html(path, summary, file_list, all_data)
        
        # 验证HTML内容包含数据
        if 'dataset_data' not in html_content or len(html_content) < 10000:
            logger.warning("HTML内容可能不完整，尝试重新生成...")
            # 如果内容太短，可能有问题，重新生成
        html_content = generate_standalone_html(path, summary, file_list, all_data)
        
        # 返回HTML文件
        from fastapi.responses import Response
        filename = f"dataset_viewer_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        
        logger.info(f"HTML导出完成: {filename}, 大小: {len(html_content)} 字符")
        logger.info(f"HTML包含数据: {'dataset_data' in html_content}, 包含记录数: {html_content.count('accordion-item')}")
        
        return Response(
            content=html_content,
            media_type="text/html",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        logger.error(f"导出HTML时出错: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"导出HTML时出错: {str(e)}")

@app.get("/reward_viewer", response_class=HTMLResponse)
async def reward_viewer(request: Request):
    """展示reward日志列表页面"""
    logger.info("请求reward日志列表页面")
    all_reports = scan_for_reports()
    return templates.TemplateResponse(
        "reward_list.html",
        {
            "request": request,
            "reports": all_reports
        }
    )

@app.get("/reward_viewer/{filename:path}", response_class=HTMLResponse)
async def reward_viewer_detail(request: Request, filename: str):
    """展示指定reward日志文件的详细内容"""
    try:
        # 读取指定的reward日志文件
        reward_file_path = BASE_DIR / "model" / "rl" / "reward_logs" / f"{filename}.jsonl"
        
        if not reward_file_path.exists():
            raise HTTPException(status_code=404, detail=f"Reward日志文件 {filename}.jsonl 不存在")
        
        reward_data = []
        with open(reward_file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                if line.strip():
                    try:
                        data = json.loads(line.strip())
                        data['line_number'] = line_num
                        reward_data.append(data)
                    except json.JSONDecodeError as e:
                        logger.warning(f"解析第{line_num}行JSON失败: {e}")
                        continue
        
        # 计算统计信息
        total_records = len(reward_data)
        valid_scores = [item.get('score', 0) for item in reward_data if item.get('score') is not None]
        avg_score = sum(valid_scores) / len(valid_scores) if valid_scores else 0
        
        # 按分数分组统计
        score_ranges = {
            '优秀 (0.8-1.0)': len([item for item in reward_data if item.get('score') is not None and 0.8 <= item.get('score', 0) <= 1.0]),
            '良好 (0.6-0.8)': len([item for item in reward_data if item.get('score') is not None and 0.6 <= item.get('score', 0) < 0.8]),
            '一般 (0.4-0.6)': len([item for item in reward_data if item.get('score') is not None and 0.4 <= item.get('score', 0) < 0.6]),
            '较差 (0.0-0.4)': len([item for item in reward_data if item.get('score') is not None and 0.0 <= item.get('score', 0) < 0.4])
        }
        
        # 获取模板资源
        resources = get_template_resources()
        
        return templates.TemplateResponse("reward_viewer_enhanced.html", {
            "request": request,
            "reward_data": reward_data,
            "total_records": total_records,
            "avg_score": round(avg_score, 3),
            "score_ranges": score_ranges,
            "filename": filename
        })
        
    except Exception as e:
        logger.error(f"加载reward日志失败: {e}")
        raise HTTPException(status_code=500, detail=f"加载reward日志失败: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    logger.info("启动开发服务器...")
    uvicorn.run(app, host="0.0.0.0", port=8000) 