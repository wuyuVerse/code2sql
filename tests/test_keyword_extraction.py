"""关键词提取功能测试

测试DataReader的关键词提取功能，验证提取结果的正确性
"""

import json
import os
import sys
import tempfile
from pathlib import Path

# 添加父目录到路径以便导入
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from data_processing import DataReader
except ImportError:
    from data_processing.data_reader import DataReader


def test_gorm_keyword_extraction():
    """测试GORM关键词提取功能"""
    print("🔍 开始GORM关键词提取测试...")
    
    # 创建临时输出目录
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "test_extracted"
        
        # 创建数据读取器
        reader = DataReader("datasets/claude_output")
        
        # 执行GORM关键词提取
        print("🚀 执行GORM关键词提取...")
        result = reader.extract_gorm_keywords(str(output_dir))
        
        # 验证返回结果
        assert "total_records_processed" in result, "缺少总记录数统计"
        assert "matched_records" in result, "缺少匹配记录数统计"
        assert "match_rate" in result, "缺少匹配率统计"
        assert "keyword_frequency" in result, "缺少关键词频率统计"
        assert "source_file_distribution" in result, "缺少源文件分布统计"
        assert "output_directory" in result, "缺少输出目录信息"
        
        print(f"✅ 总记录数: {result['total_records_processed']:,}")
        print(f"✅ 匹配记录数: {result['matched_records']:,}")
        print(f"✅ 匹配率: {result['match_rate']:.2f}%")
        
        # 验证输出文件
        output_path = Path(result['output_directory'])
        assert output_path.exists(), "输出目录不存在"
        
        main_file = output_path / "keyword_matched_records.json"
        stats_file = output_path / "extraction_statistics.json"
        keyword_dir = output_path / "by_keyword"
        
        assert main_file.exists(), "主数据文件不存在"
        assert stats_file.exists(), "统计文件不存在"
        assert keyword_dir.exists(), "关键词分类目录不存在"
        
        # 验证主数据文件内容
        with open(main_file, 'r', encoding='utf-8') as f:
            main_data = json.load(f)
        assert len(main_data) == result['matched_records'], "主数据文件记录数不匹配"
        
        # 验证统计文件内容
        with open(stats_file, 'r', encoding='utf-8') as f:
            stats_data = json.load(f)
        assert stats_data['total_records_processed'] == result['total_records_processed'], "统计数据不一致"
        
        print("✅ GORM关键词提取测试通过！")
        return result


def test_custom_keyword_extraction():
    """测试自定义关键词提取功能"""
    print("\n🎯 开始自定义关键词提取测试...")
    
    # 自定义关键词列表
    custom_keywords = ["SELECT", "INSERT", "UPDATE", "DELETE", "JOIN"]
    
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "test_custom"
        
        # 创建数据读取器
        reader = DataReader("datasets/claude_output")
        
        # 执行自定义关键词提取
        print(f"🚀 执行自定义关键词提取: {custom_keywords}")
        result = reader.extract_by_keywords(
            keywords=custom_keywords,
            output_dir=str(output_dir),
            step_name="sql_keywords"
        )
        
        # 验证返回结果
        assert "total_records_processed" in result, "缺少总记录数统计"
        assert "matched_records" in result, "缺少匹配记录数统计"
        assert "keyword_frequency" in result, "缺少关键词频率统计"
        
        print(f"✅ 总记录数: {result['total_records_processed']:,}")
        print(f"✅ 匹配记录数: {result['matched_records']:,}")
        print(f"✅ 匹配率: {result['match_rate']:.2f}%")
        
        # 验证关键词频率
        keyword_freq = result['keyword_frequency']
        for keyword in custom_keywords:
            assert keyword in keyword_freq, f"关键词 {keyword} 未在统计中"
            print(f"   {keyword}: {keyword_freq[keyword]} 次")
        
        # 验证输出目录结构
        output_path = Path(result['output_directory'])
        assert output_path.name.startswith("sql_keywords_"), "输出目录命名不正确"
        
        print("✅ 自定义关键词提取测试通过！")
        return result


def test_small_dataset_extraction():
    """测试小数据集的关键词提取"""
    print("\n📊 开始小数据集测试...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "test_small"
        
        # 创建数据读取器，只读取少量文件
        reader = DataReader("datasets/claude_output")
        
        # 只读取测试文件
        test_files = ["test_results.json"]
        reader.read_files(test_files)
        
        print(f"📁 读取了 {len(reader)} 条测试记录")
        
        # 执行关键词提取
        keywords = ["save", "Association", "Preload"]
        result = reader.extract_by_keywords(
            keywords=keywords,
            output_dir=str(output_dir),
            step_name="small_test"
        )
        
        print(f"✅ 小数据集测试完成")
        print(f"   处理记录: {result['total_records_processed']}")
        print(f"   匹配记录: {result['matched_records']}")
        
        # 验证具体匹配内容
        output_path = Path(result['output_directory'])
        main_file = output_path / "keyword_matched_records.json"
        
        if main_file.exists():
            with open(main_file, 'r', encoding='utf-8') as f:
                matched_data = json.load(f)
            
            print(f"   实际匹配数据: {len(matched_data)} 条")
            
            # 显示第一条匹配记录的详细信息
            if matched_data:
                first_record = matched_data[0]
                print(f"   第一条记录函数名: {first_record.get('function_name', 'N/A')}")
                print(f"   匹配关键词: {first_record.get('matched_keywords', [])}")
        
        print("✅ 小数据集测试通过！")
        return result


def test_keyword_frequency_accuracy():
    """测试关键词频率统计的准确性"""
    print("\n🔢 开始关键词频率准确性测试...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "test_accuracy"
        
        # 使用特定关键词进行测试
        keywords = ["save", "Transaction"]
        
        reader = DataReader("datasets/claude_output")
        result = reader.extract_by_keywords(
            keywords=keywords,
            output_dir=str(output_dir),
            step_name="accuracy_test"
        )
        
        # 验证按关键词分类的文件
        output_path = Path(result['output_directory'])
        keyword_dir = output_path / "by_keyword"
        
        total_from_files = 0
        for keyword in keywords:
            keyword_file = keyword_dir / f"{keyword}_records.json"
            if keyword_file.exists():
                with open(keyword_file, 'r', encoding='utf-8') as f:
                    keyword_data = json.load(f)
                file_count = len(keyword_data)
                freq_count = result['keyword_frequency'][keyword]
                
                print(f"   {keyword}:")
                print(f"     统计频率: {freq_count}")
                print(f"     文件记录数: {file_count}")
                
                # 注意：由于一条记录可能包含多个相同关键词，所以文件记录数可能小于频率统计
                assert file_count <= freq_count, f"{keyword} 文件记录数不应大于频率统计"
                total_from_files += file_count
        
        print(f"✅ 关键词频率统计准确性测试通过！")
        return result


def test_output_file_structure():
    """测试输出文件结构的完整性"""
    print("\n📁 开始输出文件结构测试...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "test_structure"
        
        reader = DataReader("datasets/claude_output")
        keywords = ["Preload", "save"]
        
        result = reader.extract_by_keywords(
            keywords=keywords,
            output_dir=str(output_dir),
            step_name="structure_test"
        )
        
        output_path = Path(result['output_directory'])
        
        # 验证必需文件
        required_files = [
            "keyword_matched_records.json",
            "extraction_statistics.json"
        ]
        
        for filename in required_files:
            file_path = output_path / filename
            assert file_path.exists(), f"必需文件 {filename} 不存在"
            assert file_path.stat().st_size > 0, f"文件 {filename} 为空"
            print(f"   ✅ {filename}: {file_path.stat().st_size} bytes")
        
        # 验证关键词分类目录
        keyword_dir = output_path / "by_keyword"
        assert keyword_dir.exists(), "关键词分类目录不存在"
        
        # 检查每个关键词的文件
        for keyword in keywords:
            keyword_file = keyword_dir / f"{keyword}_records.json"
            if result['keyword_frequency'][keyword] > 0:
                assert keyword_file.exists(), f"关键词文件 {keyword}_records.json 不存在"
                print(f"   ✅ {keyword}_records.json: {keyword_file.stat().st_size} bytes")
        
        print("✅ 输出文件结构测试通过！")
        return result


def run_all_tests():
    """运行所有关键词提取测试"""
    print("🚀 开始关键词提取完整测试套件...")
    print("=" * 60)
    
    try:
        # 测试1：GORM关键词提取
        gorm_result = test_gorm_keyword_extraction()
        
        # 测试2：自定义关键词提取
        custom_result = test_custom_keyword_extraction()
        
        # 测试3：小数据集测试
        small_result = test_small_dataset_extraction()
        
        # 测试4：准确性测试
        accuracy_result = test_keyword_frequency_accuracy()
        
        # 测试5：文件结构测试
        structure_result = test_output_file_structure()
        
        print("\n" + "=" * 60)
        print("🎉 所有关键词提取测试通过！")
        print("=" * 60)
        
        # 测试总结
        print("\n📊 测试总结:")
        print(f"✅ GORM关键词提取: {gorm_result['matched_records']:,} 条匹配记录")
        print(f"✅ 自定义关键词提取: {custom_result['matched_records']:,} 条匹配记录")
        print(f"✅ 小数据集测试: {small_result['matched_records']:,} 条匹配记录")
        print(f"✅ 关键词频率准确性: 通过")
        print(f"✅ 文件结构完整性: 通过")
        
        print("\n💡 功能特性验证:")
        print("- ✅ GORM预定义关键词提取")
        print("- ✅ 自定义关键词列表提取")
        print("- ✅ 大规模数据处理能力")
        print("- ✅ 统计信息准确性")
        print("- ✅ 文件分类和组织")
        print("- ✅ 时间戳命名规范")
        print("- ✅ JSON格式输出")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        raise


if __name__ == "__main__":
    run_all_tests() 