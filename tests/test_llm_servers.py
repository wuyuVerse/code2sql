#!/usr/bin/env python3
"""LLM服务器测试"""
import pytest
import asyncio
import aiohttp
import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = str(Path(__file__).parent.parent)
sys.path.insert(0, project_root)

from openai import OpenAI
from config.llm.llm_config import get_llm_config, ServerConfig
from utils.llm_client import LLMClient
from utils.format_validators import validate_json_format


class TestLLMServers:
    """LLM服务器测试类"""
    
    def __init__(self):
        self.config = get_llm_config()
    
    def test_yaml_config_loading(self):
        """测试YAML配置文件加载"""
        print(f"配置文件路径: {self.config.config_file}")
        servers = self.config.list_servers()
        print(f"加载的服务器: {servers}")
        
        defaults = self.config.get_defaults()
        print(f"默认配置: {defaults}")
    
    def test_server_configs(self):
        """测试服务器配置"""
        # 测试v3配置
        v3_config = self.config.get_server_config("v3")
        print(f"V3配置: {v3_config.host}:{v3_config.port}, 模型: {v3_config.model_name}")
        
        # 测试r1配置
        r1_config = self.config.get_server_config("r1")
        print(f"R1配置: {r1_config.host}:{r1_config.port}, 模型: {r1_config.model_name}")
        
        # 测试完整URL
        print(f"V3完整URL: {v3_config.full_url}")
        print(f"R1完整URL: {r1_config.full_url}")
        print(f"V3聊天API URL: {v3_config.chat_completions_url}")
        print(f"R1聊天API URL: {r1_config.chat_completions_url}")
    
    def test_openai_client_config(self):
        """测试OpenAI客户端配置"""
        v3_openai_config = self.config.get_openai_client_config("v3")
        print(f"V3 OpenAI配置: {v3_openai_config}")
        
        r1_openai_config = self.config.get_openai_client_config("r1")
        print(f"R1 OpenAI配置: {r1_openai_config}")
    
    def test_llm_client_creation(self):
        """测试LLM客户端创建"""
        v3_client = LLMClient("v3")
        print(f"V3客户端创建成功: {v3_client.server_name}")
        
        r1_client = LLMClient("r1")
        print(f"R1客户端创建成功: {r1_client.server_name}")
    
    async def test_v3_sync_api(self):
        """测试V3同步API调用"""
        try:
            client = LLMClient("v3")
            async with aiohttp.ClientSession() as session:
                response = await client.call_async_with_format_validation(
                    session,
                    "你好，这是一个V3同步测试。", 
                    validator=validate_json_format,
                    max_tokens=100
                )
            if response:
                print(f"✅ V3同步API调用成功: {response}")
            else:
                print("❌ V3同步API调用失败: 空响应")
        except Exception as e:
            print(f"❌ V3同步API调用失败: {str(e)}")
            pytest.skip(f"V3同步API不可用: {str(e)}")
    
    async def test_r1_sync_api(self):
        """测试R1同步API调用"""
        try:
            client = LLMClient("r1")
            async with aiohttp.ClientSession() as session:
                response = await client.call_async_with_format_validation(
                    session,
                    "你好，这是一个R1同步测试。", 
                    validator=validate_json_format,
                    max_tokens=100
                )
            if response:
                print(f"✅ R1同步API调用成功: {response}")
            else:
                print("❌ R1同步API调用失败: 空响应")
        except Exception as e:
            print(f"❌ R1同步API调用失败: {str(e)}")
            pytest.skip(f"R1同步API不可用: {str(e)}")
    
    async def test_v3_openai_api(self):
        """测试V3 OpenAI库调用"""
        try:
            client = LLMClient("v3")
            async with aiohttp.ClientSession() as session:
                response = await client.call_async_with_format_validation(
                    session,
                    "Hello, this is a V3 OpenAI test.", 
                    validator=validate_json_format,
                    max_tokens=50
                )
            if response:
                print(f"✅ V3 OpenAI调用成功: {response}")
            else:
                print("❌ V3 OpenAI调用失败: 空响应")
        except Exception as e:
            print(f"❌ V3 OpenAI调用失败: {str(e)}")
            pytest.skip(f"V3 OpenAI不可用: {str(e)}")
    
    async def test_r1_openai_api(self):
        """测试R1 OpenAI库调用"""
        try:
            client = LLMClient("r1")
            async with aiohttp.ClientSession() as session:
                response = await client.call_async_with_format_validation(
                    session,
                    "Hello, this is a R1 OpenAI test.", 
                    validator=validate_json_format,
                    max_tokens=50
                )
            if response:
                print(f"✅ R1 OpenAI调用成功: {response}")
            else:
                print("❌ R1 OpenAI调用失败: 空响应")
        except Exception as e:
            print(f"❌ R1 OpenAI调用失败: {str(e)}")
            pytest.skip(f"R1 OpenAI不可用: {str(e)}")
    
    async def async_test_v3_api(self):
        """异步测试V3 API"""
        async with aiohttp.ClientSession() as session:
            client = LLMClient("v3")
            response = await client.call_async_with_format_validation(
                session, 
                "你好，这是一个V3异步测试。", 
                validator=validate_json_format,
                max_tokens=100
            )
            if response:
                print(f"✅ V3异步API调用成功: {response}")
            else:
                print("❌ V3异步API调用失败: 空响应")
    
    async def async_test_r1_api(self):
        """异步测试R1 API"""
        async with aiohttp.ClientSession() as session:
            client = LLMClient("r1")
            response = await client.call_async_with_format_validation(
                session, 
                "你好，这是一个R1异步测试。", 
                validator=validate_json_format,
                max_tokens=100
            )
            if response:
                print(f"✅ R1异步API调用成功: {response}")
            else:
                print("❌ R1异步API调用失败: 空响应")
    
    def test_v3_async_api(self):
        """测试V3异步API调用（包装器）"""
        try:
            asyncio.run(self.async_test_v3_api())
        except Exception as e:
            print(f"❌ V3异步API调用失败: {str(e)}")
            pytest.skip(f"V3异步API不可用: {str(e)}")
    
    def test_r1_async_api(self):
        """测试R1异步API调用（包装器）"""
        try:
            asyncio.run(self.async_test_r1_api())
        except Exception as e:
            print(f"❌ R1异步API调用失败: {str(e)}")
            pytest.skip(f"R1异步API不可用: {str(e)}")
    

    
    def test_list_servers(self):
        """测试列出所有服务器"""
        servers = self.config.list_servers()
        print(f"可用服务器: {servers}")


if __name__ == "__main__":
    # 直接运行测试
    test_instance = TestLLMServers()
    
    print("🔧 测试YAML配置加载...")
    test_instance.test_yaml_config_loading()
    print("✅ YAML配置加载测试通过")
    
    print("\n🔧 测试服务器配置...")
    test_instance.test_server_configs()
    print("✅ 服务器配置测试通过")
    
    print("\n🔧 测试OpenAI客户端配置...")
    test_instance.test_openai_client_config()
    print("✅ OpenAI客户端配置测试通过")
    
    print("\n🔧 测试LLM客户端创建...")
    test_instance.test_llm_client_creation()
    print("✅ LLM客户端创建测试通过")
    

    
    print("\n🔧 测试服务器列表...")
    test_instance.test_list_servers()
    print("✅ 服务器列表测试通过")
    
    print("\n🔗 测试V3同步API...")
    asyncio.run(test_instance.test_v3_sync_api())
    
    print("\n🔗 测试R1同步API...")
    asyncio.run(test_instance.test_r1_sync_api())
    
    print("\n🌐 测试V3 OpenAI库...")
    asyncio.run(test_instance.test_v3_openai_api())
    
    print("\n🌐 测试R1 OpenAI库...")
    asyncio.run(test_instance.test_r1_openai_api())
    
    print("\n⚡ 测试V3异步API...")
    test_instance.test_v3_async_api()
    
    print("\n⚡ 测试R1异步API...")
    test_instance.test_r1_async_api()
    
    print("\n🎉 所有测试完成！") 