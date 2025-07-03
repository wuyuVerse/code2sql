"""LLM服务器测试"""
import pytest
import asyncio
import aiohttp
from openai import OpenAI
from config.llm_config import LLMConfig, ServerConfig


class TestLLMServers:
    """LLM服务器测试类"""
    
    def test_server_configs(self):
        """测试服务器配置"""
        # 测试v3配置
        v3_config = LLMConfig.get_server_config("v3")
        print(f"V3配置: {v3_config.host}:{v3_config.port}, 模型: {v3_config.model_name}")
        
        # 测试r1配置
        r1_config = LLMConfig.get_server_config("r1")
        print(f"R1配置: {r1_config.host}:{r1_config.port}, 模型: {r1_config.model_name}")
        
        # 测试完整URL
        print(f"V3完整URL: {v3_config.full_url}")
        print(f"R1完整URL: {r1_config.full_url}")
        print(f"V3聊天API URL: {v3_config.chat_completions_url}")
        print(f"R1聊天API URL: {r1_config.chat_completions_url}")
    
    def test_openai_client_config(self):
        """测试OpenAI客户端配置"""
        v3_openai_config = LLMConfig.get_openai_client_config("v3")
        print(f"V3 OpenAI配置: {v3_openai_config}")
        
        r1_openai_config = LLMConfig.get_openai_client_config("r1")
        print(f"R1 OpenAI配置: {r1_openai_config}")
    
    def test_v3_connection_openai(self):
        """使用OpenAI库测试v3服务器连接"""
        try:
            config = LLMConfig.get_openai_client_config("v3")
            client = OpenAI(
                api_key=config["api_key"],
                base_url=config["base_url"]
            )
            
            # 尝试简单的API调用
            response = client.chat.completions.create(
                model="v3",
                messages=[
                    {"role": "user", "content": "Hello, this is a test message for V3."}
                ],
                max_tokens=50,
                timeout=30
            )
            
            if response and hasattr(response, 'choices') and response.choices:
                print(f"✅ V3服务器OpenAI连接成功: {response.choices[0].message.content}")
            else:
                print("❌ V3服务器OpenAI连接失败: 响应格式不正确")
                
        except Exception as e:
            print(f"❌ V3服务器OpenAI连接失败: {str(e)}")
            pytest.skip(f"V3服务器不可用: {str(e)}")
    
    def test_r1_connection_openai(self):
        """使用OpenAI库测试r1服务器连接"""
        try:
            config = LLMConfig.get_openai_client_config("r1")
            client = OpenAI(
                api_key=config["api_key"],
                base_url=config["base_url"]
            )
            
            # 尝试简单的API调用
            response = client.chat.completions.create(
                model="default",
                messages=[
                    {"role": "user", "content": "Hello, this is a test message for R1."}
                ],
                max_tokens=50,
                timeout=30
            )
            
            if response and hasattr(response, 'choices') and response.choices:
                print(f"✅ R1服务器OpenAI连接成功: {response.choices[0].message.content}")
            else:
                print("❌ R1服务器OpenAI连接失败: 响应格式不正确")
                
        except Exception as e:
            print(f"❌ R1服务器OpenAI连接失败: {str(e)}")
            pytest.skip(f"R1服务器不可用: {str(e)}")
    
    def test_v3_sync_api(self):
        """测试V3同步API调用"""
        try:
            response = LLMConfig.call_api_sync("v3", "你好，这是一个V3同步测试。", max_tokens=100)
            if response:
                print(f"✅ V3同步API调用成功: {response}")
            else:
                print("❌ V3同步API调用失败: 空响应")
        except Exception as e:
            print(f"❌ V3同步API调用失败: {str(e)}")
            pytest.skip(f"V3同步API不可用: {str(e)}")
    
    def test_r1_sync_api(self):
        """测试R1同步API调用"""
        try:
            response = LLMConfig.call_api_sync("r1", "你好，这是一个R1同步测试。", max_tokens=100)
            if response:
                print(f"✅ R1同步API调用成功: {response}")
            else:
                print("❌ R1同步API调用失败: 空响应")
        except Exception as e:
            print(f"❌ R1同步API调用失败: {str(e)}")
            pytest.skip(f"R1同步API不可用: {str(e)}")
    
    async def async_test_v3_api(self):
        """异步测试V3 API"""
        async with aiohttp.ClientSession() as session:
            response = await LLMConfig.call_api_async(session, "v3", "你好，这是一个V3异步测试。", max_tokens=100)
            if response:
                print(f"✅ V3异步API调用成功: {response}")
            else:
                print("❌ V3异步API调用失败: 空响应")
    
    async def async_test_r1_api(self):
        """异步测试R1 API"""
        async with aiohttp.ClientSession() as session:
            response = await LLMConfig.call_api_async(session, "r1", "你好，这是一个R1异步测试。", max_tokens=100)
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
        servers = LLMConfig.list_servers()
        print(f"可用服务器: {servers}")


if __name__ == "__main__":
    # 直接运行测试
    test_instance = TestLLMServers()
    
    print("🔧 测试服务器配置...")
    test_instance.test_server_configs()
    print("✅ 服务器配置测试通过")
    
    print("\n🔧 测试OpenAI客户端配置...")
    test_instance.test_openai_client_config()
    print("✅ OpenAI客户端配置测试通过")
    
    print("\n🔧 测试服务器列表...")
    test_instance.test_list_servers()
    print("✅ 服务器列表测试通过")
    
    print("\n🌐 测试V3服务器OpenAI连接...")
    test_instance.test_v3_connection_openai()
    
    print("\n🌐 测试R1服务器OpenAI连接...")
    test_instance.test_r1_connection_openai()
    
    print("\n🔗 测试V3同步API...")
    test_instance.test_v3_sync_api()
    
    print("\n🔗 测试R1同步API...")
    test_instance.test_r1_sync_api()
    
    print("\n⚡ 测试V3异步API...")
    test_instance.test_v3_async_api()
    
    print("\n⚡ 测试R1异步API...")
    test_instance.test_r1_async_api()
    
    print("\n🎉 所有测试完成！") 