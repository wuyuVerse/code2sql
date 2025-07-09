#!/usr/bin/env python3
"""
验证器功能演示
"""

import json
import asyncio
from data_processing.validation.validator import RerunValidator

def main():
    """运行单条数据的验证demo"""
    # 使用真实的 PutToRecycle 示例数据
    test_record = {
        "function_name": "/Users/freedom/llms/cos/api-v2-file-system/internal/services/third/mysql/file_recycle.go:161:222:PutToRecycle",
        "source_file": "/data/shawn/venus_api/orm2sql/ivc_temp/5-22-cos.json",
        "orm_code": """func PutToRecycle(ctx context.Context, dbInfo *common.DBInfo, fileInfo *FileSystem, userId string, retentionDays *int32) (*FileRecycle, error) {\n    var err error\n    var code int\n    start := time.Now().UnixNano()\n    defer func() {\n        code = GetErrorCode(err)\n        common.ReportModuleLogTrpc(ctx, CalleeServiceName, \"FileRecycle.PutToRecycle\", dbInfo.GetHostPortStr(), start, code, err, nil)\n    }()\n\n    // get gorm db\n    tx, err := GetMysqlConnManager().GetMysqlConn(dbInfo).GetConn()\n    if err != nil {\n        return nil, ConvertGormError(err)\n    }\n\n    // 开启事务\n    tx = tx.Begin()\n    if tx.Error != nil {\n        return nil, ConvertGormError(tx.Error)\n    }\n\n    recycle := &FileRecycle{\n        FileSystem:  *fileInfo,\n        TrashTime:   time.Now(),\n        TrashUserId: userId,\n    }\n    recycle.ID = 0\n    recycle.Trashed = true\n    if retentionDays != nil {\n        recycle.RetentionDays = *retentionDays\n    }\n\n    // 好像嵌套事务有问题 先这么写吧\n    txres := tx.WithContext(ctx).Table(GenerateTableName(dbInfo, TableNameFileSystem)).Where(\"id = ?  and versionId = ?\", fileInfo.ID, fileInfo.VersionId).Delete(&FileSystem{})\n    if txres.Error != nil {\n        tx.Rollback()\n        err = ConvertGormError(txres.Error)\n        return nil, err\n    }\n    if txres.RowsAffected == 0 {\n        tx.Rollback()\n        err = ErrDBRecordDuplicate\n        return nil, err\n    }\n\n    // 插入file记录\n    err = tx.WithContext(ctx).Table(GenerateTableName(dbInfo, TableNameFileRecycle)).Create(recycle).Error\n    if err != nil {\n        err = ConvertGormError(err)\n        return recycle, err\n    }\n\n    // 提交事务\n    err = tx.Commit().Error\n    if err != nil {\n        tx.Rollback()\n        err = ConvertGormError(err)\n        return recycle, err\n    }\n    return recycle, nil\n}""",
        "caller": "func (f *FileSystemTdsql) PutToRecycle(ctx context.Context, routerInfo *router.RouterInfo, req *fsapi.PutToRecycleReq) (*fsapi.PutToRecycleResp, error) {\n\tslog.WithTrpcContext(ctx).Debug(\"PutToRecycle enter:\", debugRouter(routerInfo, zap.Any(\"req\", req))...)\n\n\treturn nil, errs.New(int(base.ErrSMHFileSystem_ERR_SMH_FS_Invalid_Param), \"PutToRecycle is not supported\")\n}",
        "sql_statement_list": "<NO SQL GENERATE>",
        "sql_types": [],
        "code_meta_data": [
            {
                "code_file": "/Users/freedom/llms/cos/api-v2-file-system/internal/services/third/mysql/file_recycle.go",
                "code_start_line": 36,
                "code_end_line": 44,
                "code_key": "FileRecycle",
                "code_value": "type FileRecycle struct {\\n\\tFileSystem\\n\\tTrashTime     time.Time `gorm:\\\"column:trashTime;not null\\\"`\\n\\tTrashUserId   string    `gorm:\\\"column:trashUserId;type:varchar(100);not null;default:''\\\"`\\n\\tTrashSize     int64     `gorm:\\\"column:trashSize;not null;default:0\\\"`\\n\\tTrashStatus   bool      `gorm:\\\"column:trashStatus;not null;default:0\\\"`\\n\\tRetentionDays int32     `gorm:\\\"column:retentionDays;not null;default:-1\\\"`\\n\\tExpiredTime   time.Time `gorm:\\\"->;type:datetime;column:expiredTime;\\\"`\\n}",
                "code_label": 3,
                "code_type": 3,
                "code_version": "96ea2d12a92542c8e8e5eea015ad1a03dfc603d5"
            },
            {
                "code_file": "/Users/freedom/llms/cos/api-v2-file-system/internal/services/third/mysql/file_recycle.go",
                "code_start_line": 47,
                "code_end_line": 49,
                "code_key": "TableName",
                "code_value": "func (FileRecycle) TableName() string {\\n\\treturn TableNameFileRecycle\\n}",
                "code_label": None,
                "code_type": 2,
                "code_version": "96ea2d12a92542c8e8e5eea015ad1a03dfc603d5"
            },
            {
                "code_file": "/Users/freedom/llms/cos/api-v2-file-system/internal/services/third/mysql/file_recycle.go",
                "code_start_line": 18,
                "code_end_line": 18,
                "code_key": "TableNameFileRecycle",
                "code_value": "var TableNameFileRecycle       = \\\"file_recycle\\\"",
                "code_label": None,
                "code_type": 1,
                "code_version": "96ea2d12a92542c8e8e5eea015ad1a03dfc603d5"
            },
            {
                "code_file": "/Users/freedom/llms/cos/api-v2-file-system/internal/services/third/mysql/file_system.go",
                "code_start_line": 114,
                "code_end_line": 120,
                "code_key": "FileSystem",
                "code_value": "type FileSystem struct {\\n\\tFileUploading\\n\\tTrashed          bool   `gorm:\\\"column:trashed;type:tinyint(1);not null;default:0\\\"`\\n\\tLinkTo           string `gorm:\\\"column:linkTo;type:varchar(32);not null;default:''\\\"`\\n\\tFlag             int    `gorm:\\\"column:flag;type:int(4);not null;default:0\\\"`\\n\\tIsRemovedByQuota bool   `gorm:\\\"->;column:isRemovedByQuota;type:tinyint(1);not null;default:0\\\"`\\n}",
                "code_label": 3,
                "code_type": 3,
                "code_version": "96ea2d12a92542c8e8e5eea015ad1a03dfc603d5"
            },
            {
                "code_file": "/Users/freedom/llms/cos/api-v2-file-system/internal/services/third/mysql/file_system.go",
                "code_start_line": 123,
                "code_end_line": 125,
                "code_key": "TableName",
                "code_value": "func (FileSystem) TableName() string {\\n\\treturn TableNameFileSystem\\n}",
                "code_label": None,
                "code_type": 2,
                "code_version": "96ea2d12a92542c8e8e5eea015ad1a03dfc603d5"
            },
            {
                "code_file": "/Users/freedom/llms/cos/api-v2-file-system/internal/services/third/mysql/file_system.go",
                "code_start_line": 18,
                "code_end_line": 18,
                "code_key": "TableNameFileSystem",
                "code_value": "var TableNameFileSystem       = \\\"file_system\\\"",
                "code_label": None,
                "code_type": 1,
                "code_version": "96ea2d12a92542c8e8e5eea015ad1a03dfc603d5"
            }
        ],
        "sql_pattern_cnt": 7
    }
    
    print("🔧 测试验证器功能")
    print(f"测试数据：{test_record['function_name']}")
    print("="*50)
    
    try:
        # 初始化验证器
        validator = RerunValidator(config_path="config/validation/rerun_config.yaml")
        
        # 执行三段式分析流程
        print("🔄 执行三段式 LLM 分析流程...")
        result = validator.run_three_stage_analysis(test_record)
        
        if result['success']:
            print("✅ 三段式分析流程成功完成！")
            print("\n📋 详细结果：")
            print(f"第一阶段分析结果（前200字）：\n{result['analysis_result'][:200]}...\n")
            print(f"第二阶段验证结果（前200字）：\n{result['verification_result'][:200]}...\n")
            print(f"第三阶段格式化结果（前200字）：\n{result['final_result'][:200]}...\n")
            
            if result['parsed_json']:
                print("🎯 JSON解析成功！")
                print(f"解析后的数据类型：{type(result['parsed_json']).__name__}")
                if isinstance(result['parsed_json'], list):
                    print(f"数组长度：{len(result['parsed_json'])}")
                    if result['parsed_json']:
                        print(f"第一个元素：{result['parsed_json'][0]}")
                elif isinstance(result['parsed_json'], dict):
                    print(f"字典键数量：{len(result['parsed_json'])}")
                    print(f"主要键：{list(result['parsed_json'].keys())}")
            else:
                print("⚠️ JSON解析失败，返回原始文本结果")
        else:
            print(f"❌ 三段式分析流程失败：{result.get('error', '未知错误')}")
            print("📋 部分结果：")
            if result['analysis_result']:
                print(f"  - 第一阶段完成：{len(result['analysis_result'])} 字符")
            if result['verification_result']:
                print(f"  - 第二阶段完成：{len(result['verification_result'])} 字符")
            if result['final_result']:
                print(f"  - 第三阶段完成：{len(result['final_result'])} 字符")
        
    except Exception as e:
        print(f"❌ 测试失败：{e}")
        print(f"错误类型：{type(e).__name__}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 