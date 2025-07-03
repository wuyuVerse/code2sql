"""数据清洗示例测试 - 展示如何使用新架构进行数据处理"""
import asyncio
from data_processing.data_cleaner import DataCleaner


def test_data_cleaning_example():
    """数据清洗示例测试"""
    print("🧹 开始数据清洗示例测试...")
    
    # 创建数据清洗器，使用V3服务器
    cleaner = DataCleaner(llm_server="v3")
    
    # 测试数据 - 一些需要清洗的脏数据
    dirty_texts = [
        "Hllo wrld!!! this is a tset messag with tpos and extr symblx ###",
        "用户姓名：张三@#$，邮箱：zhangsan@email.com，电话：138****1234",
        "产品价格：￥199.99 ￥元，折扣：8.5折 折扣",
        "日期：2023-12-25，备注：this is a 测试 message with 混合语言"
    ]
    
    print("\n📝 原始数据:")
    for i, text in enumerate(dirty_texts, 1):
        print(f"{i}. {text}")
    
    # 同步清洗测试
    print("\n🔄 开始同步清洗...")
    cleaned_texts_sync = []
    for i, dirty_text in enumerate(dirty_texts, 1):
        print(f"清洗第{i}条数据...")
        cleaned = cleaner.clean_text_sync(dirty_text)
        cleaned_texts_sync.append(cleaned)
        print(f"✅ 清洗完成: {cleaned[:100]}...")
    
    print("\n📋 同步清洗结果:")
    for i, cleaned in enumerate(cleaned_texts_sync, 1):
        print(f"{i}. {cleaned}")
    
    # 异步批量清洗测试
    print("\n⚡ 开始异步批量清洗...")
    async def run_async_cleaning():
        cleaned_texts_async = await cleaner.batch_clean_async(dirty_texts)
        return cleaned_texts_async
    
    cleaned_texts_async = asyncio.run(run_async_cleaning())
    
    print("\n📋 异步清洗结果:")
    for i, cleaned in enumerate(cleaned_texts_async, 1):
        print(f"{i}. {cleaned}")
    
    # 结构化数据提取测试
    print("\n🔍 开始结构化数据提取测试...")
    unstructured_text = """
    客户信息：
    姓名：李四
    邮箱：lisi@company.com
    电话：186-1234-5678
    公司：ABC科技有限公司
    地址：北京市朝阳区xxx路123号
    订单金额：2599.00元
    下单日期：2023-12-20
    备注：VIP客户，需要优先处理
    """
    
    print(f"原始非结构化文本:\n{unstructured_text}")
    
    structured_data = cleaner.extract_structured_data(unstructured_text)
    print(f"\n📊 提取的结构化数据:")
    for key, value in structured_data.items():
        print(f"  {key}: {value}")
    
    # 多LLM结果对比测试
    print("\n🆚 开始多LLM结果对比测试...")
    compare_text = "this is a tset messag with tpos!!!"
    comparison_results = cleaner.compare_llm_results(compare_text)
    
    print(f"原始文本: {compare_text}")
    print("不同LLM的清洗结果对比:")
    for llm_name, result in comparison_results.items():
        print(f"  {llm_name.upper()}: {result}")
    
    # 异步对比测试
    print("\n⚡ 开始异步多LLM对比测试...")
    async def run_async_comparison():
        return await cleaner.compare_llm_results_async(compare_text)
    
    async_comparison = asyncio.run(run_async_comparison())
    print("异步多LLM对比结果:")
    for llm_name, result in async_comparison.items():
        print(f"  {llm_name.upper()}: {result}")
    
    print("\n🎉 数据清洗示例测试完成！")


def test_server_switching():
    """测试服务器切换功能"""
    print("\n🔄 测试服务器切换功能...")
    
    # 测试使用不同服务器
    v3_cleaner = DataCleaner(llm_server="v3")
    r1_cleaner = DataCleaner(llm_server="r1")
    
    test_text = "Hello wrld! This is a tset with erors."
    
    print(f"原始文本: {test_text}")
    
    # V3清洗
    v3_result = v3_cleaner.clean_text_sync(test_text)
    print(f"V3清洗结果: {v3_result}")
    
    # R1清洗
    r1_result = r1_cleaner.clean_text_sync(test_text)
    print(f"R1清洗结果: {r1_result}")
    
    print("✅ 服务器切换测试完成！")


if __name__ == "__main__":
    print("🚀 开始数据清洗完整示例...")
    
    # 运行主要测试
    test_data_cleaning_example()
    
    # 运行服务器切换测试
    test_server_switching()
    
    print("\n🏆 所有数据清洗示例测试完成！")
    print("\n💡 总结:")
    print("- ✅ YAML配置文件管理服务器配置")
    print("- ✅ 配置与业务逻辑完全分离")
    print("- ✅ 支持同步和异步数据处理")
    print("- ✅ 支持多LLM服务器对比")
    print("- ✅ 支持批量数据处理")
    print("- ✅ 支持结构化数据提取")
    print("- ✅ 灵活的服务器切换功能") 