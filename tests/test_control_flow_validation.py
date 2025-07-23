#!/usr/bin/env python3
"""
控制流验证功能测试脚本

测试包含switch语句的ORM代码的控制流验证功能
"""

import asyncio
import json
import logging
from pathlib import Path
import sys
import os

# 添加项目根目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), '.'))

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 测试用例数据
TEST_CASE = {
    "function_name": "FindUserAppIdListByCustomerType",
    "orm_code": """func (o *Overview) FindUserAppIdListByCustomerType(endTime int64) ([]AppIds, error) {
	appIds := make([]AppIds, 0)
	filter := make(map[string]interface{})
	filter["status"] = 0
	if o.IndustryId > 0 {
		filter["income_industry_id"] = o.IndustryId
	}
	if o.AppId > 0 {
		filter["app_id"] = o.AppId
	}
	if o.CustomerType > 0 {
		switch o.CustomerType {
		case External:
			filter["internal"] = 0
		case Internal:
			filter["internal"] = 1
		case Big:
			filter["big_customer"] = 1
		case Small:
			filter["big_customer"] = 0
		case Corporate:
			filter["corporate"] = 1
		case Personal:
			filter["corporate"] = 0
		default:
			return nil, utils.UnSupportedCustomerTypeError
		}
	}
	var err error
	comment := o.CommentFunc(SELECT_COMMENT)
	if endTime > 0 {
		err = base.GetInstance().BillingDriver().Clauses(comment).Table(UserInfoTable).Select("app_id").Where(filter).
			Where("created_at <= FROM_UNIXTIME(?)", endTime).Scan(&appIds).Error
	} else {
		err = base.GetInstance().BillingDriver().Clauses(comment).Table(UserInfoTable).Select("app_id").Where(filter).Scan(&appIds).Error
	}
	if err != nil {
		if err == db.ErrRecordNotFound {
			return appIds, utils.RecordNotFoundError
		}
		return appIds, err
	}
	return appIds, nil
}""",
    "caller": """ 
func (l *OverviewSummaryLogic) OverviewSummary(req *types.OverviewRequest, log *logger.IvcLog) (resp *types.OverviewResponse, err error) {
	// 外部客户、内部客户、大客户、小客户、企业客户及个人客户
	// 校验参数
	comment := model.NewComment(req.RequestId, model.OverviewSummaryFlow)
	timeIntervals, err := CheckOverviewSummaryParam(req, log)
	if err != nil {
		log.ErrorV(fmt.Sprintf("[OverviewSummary] CheckOverviewSummaryParam:%+v err:%v", *req, err))
		return nil, err
	}
	// 获取用户分类的app_id列表
	ov := &model.Overview{
		CustomerType: req.CustomerType,
		Comment:      comment,
	}
	// 获取总开通用户数
	totalUserNums, err := ov.FindRegisteredUsersCounts()
	if err != nil {
		log.ErrorV(fmt.Sprintf("[OverviewSummary] FindRegisteredUsersCounts err:%v", err))
		return nil, err
	}
	// 获取活跃用户数
	appIds, err := ov.FindUserAppIdListByCustomerType(req.End)
	if err != nil {
		log.ErrorV(fmt.Sprintf("[OverviewSummary] FindUserAppIdListByCustomerType err:%v", err))
		if err == db.ErrRecordNotFound {
			return nil, utils.RecordNotFoundError
		}
		return nil, err
	}
	log.InfoV(fmt.Sprintf("[OverviewSummary] appIds:%+v", appIds))
	// 统计新增用户及历史规模
	userNum, err := ov.FindUserCountByCustomerType(timeIntervals[0], req.End)
	if err != nil {
		log.ErrorV(fmt.Sprintf("[OverviewSummary] FindUserCountByCustomerType err:%v", err))
		return nil, err
	}
	// 获取计费用户数
	billingUsers, err := ov.FindBillingUserCount(timeIntervals[0], timeIntervals[len(timeIntervals)-1])
	if err != nil {
		log.ErrorV(fmt.Sprintf("[OverviewSummary] FindBillingUserCount err:%v", err))
		return nil, err
	}
	userSummary := types.UserSummary{
		TotalUser:   totalUserNums,
		ActiveUser:  len(appIds),
		NewUser:     userNum,
		BillingUser: len(billingUsers),
	}
	/*
		// 从时序数据库获取设备汇总信息
		v := &model.View{
			Begin:    req.Start,
			End:      req.End,
			Interval: 1,
		}
		multipleAppIdsTimeSeriesData, err := v.FindMultipleAppIdsTimeSeriesDataList(log, appIds, timeIntervals, req.CustomerType)
		if err != nil {
			log.ErrorV(fmt.Sprintf("[OverviewSummary] FindMultipleAppIdsTimeSeriesDataList err:%v", err))
			return nil, err
		}
	*/

	// 获取累计在线设备统计数据
	oDevices, err := ov.FindUserOnlineDeviceByAppIds(billingUsers, timeIntervals[0], timeIntervals[len(timeIntervals)-1])
	if err != nil {
		errCode := utils.OperationErr
		if e, ok := err.(*utils.UrsError); ok {
			errCode = e.Id
		}
		log.ErrorV(fmt.Sprintf("[OverviewSummary] FindUserOnlineDeviceByAppIds err:%v", err), errCode)
		return nil, err
	}
	log.InfoV(fmt.Sprintf("[OverviewSummary] FindUserOnlineDeviceByAppIds OnlineDevices:%+v", oDevices))
	odsMap := make(map[string]types.OnlineDevice)
	for _, od := range oDevices {
		date := strings.Split(od.Date, "T")[0]
		activeDev := types.OnlineDevice{
			Date:         date,
			ActiveDevice: od.OnDevice,
		}
		odsMap[date] = activeDev
	}

	// TODO 获取设备综合管理费用户的存储

	// 获取存储信息, 获取流量/带宽信息
	qs, err := ov.FindUserBillingByCustomerType(timeIntervals[0], timeIntervals[len(timeIntervals)-1])
	if err != nil {
		errCode := utils.OperationErr
		if e, ok := err.(*utils.UrsError); ok {
			errCode = e.Id
		}
		log.ErrorV(fmt.Sprintf("[OverviewSummary] FindUserBillingByCustomerType err:%v", err), errCode)
		return nil, err
	}
	log.InfoV(fmt.Sprintf("[OverviewSummary] FindUserBillingByCustomerType qs:%+v", qs))
	sourceMap, _ := model.FilterQuotaByFieldToMap(qs)
	var (
		flows            []types.NetWork
		bands            []types.NetWork
		storages         []types.Storage
		billingChs       []types.BillingChannel
		onlineDevs       []types.OnlineDevice
		totalHotStorage  float64
		totalColdStorage float64
		incrHotStorage   float64
		incrColdStorage  float64
		bigBucket        types.BigAccountBucket
		incrWB           types.IncrWhitelistBucket
	)
	for _, date := range timeIntervals {
		fw := types.NetWork{
			Date: date,
		}
		bw := types.NetWork{
			Date: date,
		}
		s := types.Storage{
			Date: date,
		}
		bc := types.BillingChannel{
			Date: date,
		}
		od := types.OnlineDevice{
			Date: date,
		}
		if dev, ok := odsMap[od.Date]; ok {
			od.ActiveDevice = dev.ActiveDevice
		}
		v, ok := sourceMap[date]
		if ok {
			fw.Up = v.UplinkTraffic
			fw.Down = v.DownlinkTraffic
			bw.Up = v.UplinkBandwidth
			bw.Down = v.DownlinkBandwidth
			s.HotStorage = v.StdStorage
			s.ColdStorage = v.ArcStorage
			bc.ActiveChannel = v.GBDeviceActiveNumber
		}
		storages = append(storages, s)
		flows = append(flows, fw)
		bands = append(bands, bw)
		billingChs = append(billingChs, bc)
		onlineDevs = append(onlineDevs, od)
	}
	if len(storages) > 0 {
		totalHotStorage = storages[len(storages)-1].HotStorage
		totalColdStorage = storages[len(storages)-1].ColdStorage
		incrHotStorage = storages[len(storages)-1].HotStorage - storages[0].HotStorage
		incrColdStorage = storages[len(storages)-1].ColdStorage - storages[0].ColdStorage
		bigBucket.TotalStorage = fmt.Sprintf("%.6f", totalHotStorage+totalColdStorage)
		bigBucket.TotalHotStorage = fmt.Sprintf("%.6f", totalHotStorage)
		bigBucket.TotalColdStorage = fmt.Sprintf("%.6f", totalColdStorage)
		bigBucket.IncrTotalStorage = fmt.Sprintf("%.6f", incrHotStorage+incrColdStorage)
		bigBucket.IncrHotStorage = fmt.Sprintf("%.6f", incrHotStorage)
		bigBucket.IncrColdStorage = fmt.Sprintf("%.6f", incrColdStorage)
	}
	// 获取用户白名单桶存储量
	wStorages, err := ov.FindUserWhitelistBucketByAppIds(appIds, timeIntervals[0], timeIntervals[len(timeIntervals)-1])
	if err != nil {
		errCode := utils.OperationErr
		if e, ok := err.(*utils.UrsError); ok {
			errCode = e.Id
		}
		log.ErrorV(fmt.Sprintf("[OverviewSummary] FindUserWhitelistBucketByAppIds err:%v", err), errCode)
		return nil, err
	}
	whitelistStorages := model.BuildWhitelistBucketList(wStorages, timeIntervals)
	if len(whitelistStorages) > 0 {
		incrWB.IncrTotalStorage = fmt.Sprintf("%.6f", whitelistStorages[len(whitelistStorages)-1].TotalStorage-whitelistStorages[0].TotalStorage)
		incrWB.IncrStdStorage = fmt.Sprintf("%.6f", whitelistStorages[len(whitelistStorages)-1].StdStorage-whitelistStorages[0].StdStorage)
		incrWB.IncrArcStorage = fmt.Sprintf("%.6f", whitelistStorages[len(whitelistStorages)-1].ArcStorage-whitelistStorages[0].ArcStorage)
		incrWB.IncrSiaStorage = fmt.Sprintf("%.6f", whitelistStorages[len(whitelistStorages)-1].SiaStorage-whitelistStorages[0].SiaStorage)
		incrWB.IncrDpArcStorage = fmt.Sprintf("%.6f", whitelistStorages[len(whitelistStorages)-1].DpArcStorage-whitelistStorages[0].DpArcStorage)
	}
	// 获取用户总消耗
	totalConsume, err := ov.FindUserBillingConsumeByCustomerType(timeIntervals[0], timeIntervals[len(timeIntervals)-1])
	if err != nil {
		errCode := utils.OperationErr
		if e, ok := err.(*utils.UrsError); ok {
			errCode = e.Id
		}
		log.ErrorV(fmt.Sprintf("[OverviewSummary] FindUserBillingIncomeByCustomerType err:%v", err), errCode)
		return nil, err
	}
	// 获取用户实际应收
	actualIncome, err := ov.FindUserActualIncomeByAppIds(appIds, timeIntervals[0], timeIntervals[len(timeIntervals)-1])
	if err != nil {
		errCode := utils.OperationErr
		if e, ok := err.(*utils.UrsError); ok {
			errCode = e.Id
		}
		log.ErrorV(fmt.Sprintf("[OverviewSummary] FindUserActualIncomeByAppIds err:%v", err), errCode)
		return nil, err
	}
	// 查询后付费应收（当前调用cos接口，后期可改成查库）
	var (
		dayPostpaid           float64
		monthPostpaid         float64
		postpaid              string
		actualTotalReceivable float64
	)
	if req.CustomerType == 0 {
		dayTimes, monthlyTimes := utils.BuildAfterTimeIntervals(req.Start, req.End)
		// 日结用户账单
		if len(dayTimes) > 0 {
			dayPostpaid = model.CalcPostpaidIncome(dayTimes, log)
		}
		// 月结用户账单
		if len(monthlyTimes) > 0 {
			monthPostpaid = model.CalcMonthlyPostpaidIncome(monthlyTimes, log)
		}
		postpaid = fmt.Sprintf("%.2f", (dayPostpaid+monthPostpaid)/100)
		actualTotalReceivable = (dayPostpaid+monthPostpaid)/100 + actualIncome.PrepaidIncome
	} else {
		postpaid = fmt.Sprintf("%.2f", actualIncome.ActualIncome-actualIncome.PrepaidIncome)
		actualTotalReceivable = actualIncome.ActualIncome
	}

	/*
		 TODO 处理所有用户的预付费应收
		 SELECT SUM(price) as total_average_price FROM iss_prepay_resource
		WHERE DATE(start_date) <= DATE_SUB('2023-09-30', INTERVAL 1 DAY) AND DATE(end_date) >= DATE_SUB('2023-01-01', INTERVAL 1 DAY)
	*/

	resp = &types.OverviewResponse{
		TotalIncome:             fmt.Sprintf("%.2f", totalConsume+actualIncome.PrepaidIncome),
		ActualTotalReceivable:   fmt.Sprintf("%.2f", actualTotalReceivable),
		PrepaidDeduction:        fmt.Sprintf("%.2f", actualIncome.PrepaidIncome),
		Postpaid:                postpaid,
		UserSummaryInfo:         userSummary,
		BigAccountBucketInfo:    bigBucket,
		IncrWhitelistBucketInfo: incrWB,
		Flows:                   flows,
		Bandwidths:              bands,
		Storages:                storages,
		BillingChannels:         billingChs,
		OnlineDevices:           onlineDevs,
		UserWhitelistBuckets:    whitelistStorages,
	}
	return
}
""",
    "sql_statement_list": [
        {
            "type": "param_dependent",
            "variants": [
                {
                    "scenario": "基础查询：endTime=0, IndustryId=0, AppId=0, CustomerType=0",
                    "sql": "SELECT app_id FROM ivc_user_info WHERE status = ?;"
                },
                {
                    "scenario": "包含时间条件：endTime>0, IndustryId=0, AppId=0, CustomerType=0",
                    "sql": "SELECT app_id FROM ivc_user_info WHERE status = ? AND created_at <= FROM_UNIXTIME(?);"
                },
                {
                    "scenario": "包含行业ID：endTime=0, IndustryId>0, AppId=0, CustomerType=0",
                    "sql": "SELECT app_id FROM ivc_user_info WHERE status = ? AND income_industry_id = ?;"
                },
                {
                    "scenario": "包含应用ID：endTime=0, IndustryId=0, AppId>0, CustomerType=0",
                    "sql": "SELECT app_id FROM ivc_user_info WHERE status = ? AND app_id = ?;"
                },
                {
                    "scenario": "External客户类型：endTime=0, IndustryId=0, AppId=0, CustomerType=External",
                    "sql": "SELECT app_id FROM ivc_user_info WHERE status = ? AND internal = ?;"
                },
                {
                    "scenario": "Internal客户类型：endTime=0, IndustryId=0, AppId=0, CustomerType=Internal",
                    "sql": "SELECT app_id FROM ivc_user_info WHERE status = ? AND internal = ?;"
                },
                {
                    "scenario": "Big客户类型：endTime=0, IndustryId=0, AppId=0, CustomerType=Big",
                    "sql": "SELECT app_id FROM ivc_user_info WHERE status = ? AND big_customer = ?;"
                },
                {
                    "scenario": "Small客户类型：endTime=0, IndustryId=0, AppId=0, CustomerType=Small",
                    "sql": "SELECT app_id FROM ivc_user_info WHERE status = ? AND big_customer = ?;"
                },
                {
                    "scenario": "Corporate客户类型：endTime=0, IndustryId=0, AppId=0, CustomerType=Corporate",
                    "sql": "SELECT app_id FROM ivc_user_info WHERE status = ? AND corporate = ?;"
                },
                {
                    "scenario": "Personal客户类型：endTime=0, IndustryId=0, AppId=0, CustomerType=Personal",
                    "sql": "SELECT app_id FROM ivc_user_info WHERE status = ? AND corporate = ?;"
                },
                {
                    "scenario": "复合条件示例（时间+行业+应用+External客户）：endTime>0, IndustryId>0, AppId>0, CustomerType=External",
                    "sql": "SELECT app_id FROM ivc_user_info WHERE status = ? AND income_industry_id = ? AND app_id = ? AND internal = ? AND created_at <= FROM_UNIXTIME(?);"
                },
                {
                    "scenario": "复合条件示例（时间+行业+Big客户）：endTime>0, IndustryId>0, AppId=0, CustomerType=Big",
                    "sql": "SELECT app_id FROM ivc_user_info WHERE status = ? AND income_industry_id = ? AND big_customer = ? AND created_at <= FROM_UNIXTIME(?);"
                }
            ]
        }
    ],
    "sql_types": ["PARAM_DEPENDENT"],
    "code_meta_data": [
        {
            "code_file": "/Users/ymhuan/code/aid-db/temp/aid-main/aid/risk_sql/code/scripts/IVC__ivc-urs/internal/model/overview.go",
            "code_start_line": 8,
            "code_end_line": 8,
            "code_key": "base",
            "code_value": "urs/internal/base",
            "code_label": None,
            "code_type": 4,
            "code_version": "c9bb087a681a6287be10c9b6e8e232a6cfc363c7"
        }
    ],
    "sql_pattern_cnt": 2,
    "source_file": "/data/shawn/venus_api/orm2sql/ivc_temp/IVC__ivc-urs.json"
}


async def test_control_flow_validation():
    """测试控制流验证功能"""
    logger.info("开始测试控制流验证功能")
    
    try:
        # 导入控制流验证器
        from data_processing.validation.control_flow_validator import ControlFlowValidator
        
        # 创建验证器
        output_dir = "test_output/control_flow_validation"
        validator = ControlFlowValidator(output_dir, llm_server="v3")
        
        # 创建测试数据集
        test_data = [TEST_CASE]
        
        logger.info("测试用例分析:")
        logger.info(f"  - 函数名: {TEST_CASE['function_name']}")
        logger.info(f"  - 包含switch语句: {'switch' in TEST_CASE['orm_code'].lower()}")
        logger.info(f"  - 包含if语句: {'if' in TEST_CASE['orm_code'].lower()}")
        logger.info(f"  - SQL变体数量: {len(TEST_CASE['sql_statement_list'][0]['variants'])}")
        
        # 检测控制流记录
        control_flow_records = validator.detect_control_flow_records(test_data)
        logger.info(f"检测到 {len(control_flow_records)} 条控制流记录")
        
        if control_flow_records:
            logger.info("开始验证控制流记录...")
            
            # 执行验证
            validation_result = await validator.validate_dataset(test_data, max_concurrent=1)
            
            logger.info("验证结果:")
            logger.info(f"  - 总记录数: {validation_result['total_records']}")
            logger.info(f"  - 控制流记录: {validation_result['control_flow_records']}")
            logger.info(f"  - 控制流比例: {validation_result['control_flow_rate']:.2f}%")
            logger.info(f"  - 验证正确: {validation_result['correct_records']}")
            logger.info(f"  - 验证错误: {validation_result['incorrect_records']}")
            logger.info(f"  - 验证异常: {validation_result['error_records']}")
            logger.info(f"  - 重新生成: {validation_result.get('regenerated_records', 0)}")
            
            # 保存详细结果
            result_file = Path(output_dir) / "test_validation_result.json"
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(validation_result, f, ensure_ascii=False, indent=2)
            
            logger.info(f"详细结果已保存到: {result_file}")
            
            # 分析switch语句
            orm_code = TEST_CASE['orm_code']
            switch_lines = []
            for i, line in enumerate(orm_code.split('\n'), 1):
                if 'switch' in line.lower():
                    switch_lines.append(i)
            
            logger.info(f"Switch语句位置: 第 {switch_lines} 行")
            
            # 分析case分支
            case_count = 0
            for line in orm_code.split('\n'):
                if 'case' in line.lower() and ':' in line:
                    case_count += 1
            
            logger.info(f"Case分支数量: {case_count}")
            logger.info(f"SQL变体数量: {len(TEST_CASE['sql_statement_list'][0]['variants'])}")
            
            # 判断是否匹配
            if case_count > 0:
                sql_variants = len(TEST_CASE['sql_statement_list'][0]['variants'])
                logger.info(f"分析结果:")
                logger.info(f"  - Switch分支数: {case_count}")
                logger.info(f"  - SQL变体数: {sql_variants}")
                logger.info(f"  - 是否合理: {'是' if sql_variants >= case_count else '否'}")
            
            return validation_result
        else:
            logger.warning("未检测到控制流记录")
            return None
            
    except Exception as e:
        logger.error(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def analyze_test_case():
    """分析测试用例的控制流结构"""
    logger.info("分析测试用例的控制流结构:")
    
    orm_code = TEST_CASE['orm_code']
    
    # 分析switch语句
    switch_pattern = r'switch\s+([^{]+)\s*{'
    switch_matches = re.findall(switch_pattern, orm_code, re.IGNORECASE)
    
    if switch_matches:
        logger.info(f"Switch变量: {switch_matches[0].strip()}")
    
    # 分析case分支
    case_pattern = r'case\s+([^:]+):'
    case_matches = re.findall(case_pattern, orm_code, re.IGNORECASE)
    
    logger.info(f"Case分支:")
    for i, case in enumerate(case_matches, 1):
        logger.info(f"  {i}. {case.strip()}")
    
    # 分析if语句
    if_pattern = r'if\s+([^{]+)\s*{'
    if_matches = re.findall(if_pattern, orm_code, re.IGNORECASE)
    
    logger.info(f"If语句:")
    for i, if_stmt in enumerate(if_matches, 1):
        logger.info(f"  {i}. {if_stmt.strip()}")
    
    # 分析SQL变体
    sql_variants = TEST_CASE['sql_statement_list'][0]['variants']
    logger.info(f"SQL变体分析:")
    for i, variant in enumerate(sql_variants, 1):
        scenario = variant.get('scenario', f'变体{i}')
        sql = variant.get('sql', '')
        logger.info(f"  {i}. {scenario}")
        logger.info(f"     SQL: {sql}")


if __name__ == "__main__":
    import re
    
    logger.info("=" * 60)
    logger.info("控制流验证功能测试")
    logger.info("=" * 60)
    
    # 分析测试用例
    analyze_test_case()
    
    print("\n" + "=" * 60)
    print("开始执行控制流验证测试...")
    print("=" * 60)
    
    # 运行测试
    result = asyncio.run(test_control_flow_validation())
    
    if result:
        print("\n✅ 测试完成!")
        print(f"📊 验证结果: {result['correct_records']} 正确, {result['incorrect_records']} 错误")
    else:
        print("\n❌ 测试失败!") 