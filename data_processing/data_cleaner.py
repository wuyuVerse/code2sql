"""数据清洗模块 - 展示如何使用LLM客户端进行数据处理"""
import asyncio
import aiohttp
from typing import List, Dict, Any, Optional
from utils.llm_client import LLMClient, LLMClientManager


class DataCleaner:
    """数据清洗器 - 使用LLM进行智能数据清洗"""
    
    def __init__(self, llm_server: str = "v3"):
        """初始化数据清洗器
        
        Args:
            llm_server: 使用的LLM服务器名称 (v3 或 r1)
        """
        self.llm_client = LLMClient(llm_server)
        self.manager = LLMClientManager()
    
    def clean_text_sync(self, dirty_text: str) -> str:
        """同步清洗文本数据
        
        Args:
            dirty_text: 需要清洗的脏数据
            
        Returns:
            清洗后的文本
        """
        prompt = f"""
请帮我清洗以下文本数据，主要任务：
1. 去除无意义的符号和乱码
2. 纠正明显的拼写错误
3. 统一格式
4. 保持原意不变

原始文本：
{dirty_text}

请只返回清洗后的文本，不要包含其他说明：
"""
        
        cleaned_text = self.llm_client.call_sync(prompt, max_tokens=500)
        return cleaned_text.strip() if cleaned_text else dirty_text
    
    async def clean_text_async(self, session: aiohttp.ClientSession, dirty_text: str) -> str:
        """异步清洗文本数据
        
        Args:
            session: aiohttp会话
            dirty_text: 需要清洗的脏数据
            
        Returns:
            清洗后的文本
        """
        prompt = f"""
请帮我清洗以下文本数据，主要任务：
1. 去除无意义的符号和乱码
2. 纠正明显的拼写错误
3. 统一格式
4. 保持原意不变

原始文本：
{dirty_text}

请只返回清洗后的文本，不要包含其他说明：
"""
        
        cleaned_text = await self.llm_client.call_async(session, prompt, max_tokens=500)
        return cleaned_text.strip() if cleaned_text else dirty_text
    
    def extract_structured_data(self, raw_text: str) -> Dict[str, Any]:
        """从非结构化文本中提取结构化数据
        
        Args:
            raw_text: 原始非结构化文本
            
        Returns:
            提取的结构化数据
        """
        prompt = f"""
请从以下文本中提取结构化信息，并以JSON格式返回。
如果某些信息不存在，请用null表示。

文本内容：
{raw_text}

请提取以下字段（如果存在）：
- name: 姓名
- email: 邮箱
- phone: 电话
- address: 地址
- organization: 组织/公司
- date: 日期
- amount: 金额
- description: 描述

请只返回JSON格式的数据，不要包含其他说明：
"""
        
        result = self.llm_client.call_sync(prompt, max_tokens=300)
        try:
            import json
            return json.loads(result)
        except:
            return {"raw_text": raw_text, "extraction_failed": True}
    
    async def batch_clean_async(self, dirty_texts: List[str]) -> List[str]:
        """批量异步清洗文本数据
        
        Args:
            dirty_texts: 需要清洗的文本列表
            
        Returns:
            清洗后的文本列表
        """
        async with aiohttp.ClientSession() as session:
            tasks = []
            for text in dirty_texts:
                task = self.clean_text_async(session, text)
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 处理异常情况
            cleaned_texts = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    print(f"❌ 清洗第{i+1}条数据失败: {result}")
                    cleaned_texts.append(dirty_texts[i])  # 返回原始数据
                else:
                    cleaned_texts.append(result)
            
            return cleaned_texts
    
    def compare_llm_results(self, text: str) -> Dict[str, str]:
        """比较不同LLM的清洗结果
        
        Args:
            text: 需要清洗的文本
            
        Returns:
            不同LLM的清洗结果对比
        """
        prompt = f"""
请清洗以下文本，去除乱码和无意义符号，纠正错误：

{text}

清洗后的文本：
"""
        
        # 使用管理器同时调用所有可用的LLM
        results = {}
        for server_name in self.manager.list_available_servers():
            try:
                client = self.manager.get_client(server_name)
                result = client.call_sync(prompt, max_tokens=300)
                results[server_name] = result.strip() if result else "清洗失败"
            except Exception as e:
                results[server_name] = f"调用失败: {str(e)}"
        
        return results
    
    async def compare_llm_results_async(self, text: str) -> Dict[str, str]:
        """异步比较不同LLM的清洗结果
        
        Args:
            text: 需要清洗的文本
            
        Returns:
            不同LLM的清洗结果对比
        """
        prompt = f"""
请清洗以下文本，去除乱码和无意义符号，纠正错误：

{text}

清洗后的文本：
"""
        
        # 使用管理器异步调用所有LLM
        return await self.manager.call_all_async(prompt, max_tokens=300) 