# 新增场景Prompt设计分析

## 1. condition_field_mapping场景优化

### 1.1 场景背景

基于用户提供的`FindDeviceCountByFilter`方法，发现了一个特殊的ORM模式：

```go
func (d *Device) FindDeviceCountByFilter(filter map[string]interface{}) (int, error) {
    // ...
    for k, v := range filter {
        if k == "app_id" {
            sql += "AND app_id=? "
            val = append(val, v)
        } else if k == "id" {
            sql += "AND id=? "
            val = append(val, v)
        } else if k == "region" {  // 判断region字段
            cls := v.([]string)
            if len(cls) > 0 {
                sql += "AND cluster_id in (?) "  // 但实际添加cluster_id条件
                val = append(val, cls)
            }
        }
    }
    // ...
}
```

**核心特点**：条件判断中检查一个字段名，但在实际构建SQL where条件时使用不同的字段名。

### 1.2 优化后的Prompt设计

#### ORM Prompt优化：
- **明确实现模式**：使用for循环遍历filter参数
- **具体示例**：提供具体的字段映射示例
- **技术要求**：明确要求方法接收map[string]interface{}类型参数
- **映射逻辑**：强调判断条件中的字段名与SQL中的字段名必须不同

#### Caller Prompt优化：
- **明确参数类型**：强调传递原始字段名而不是映射后的字段名
- **类型安全**：要求确保参数值类型正确
- **具体示例**：提供具体的映射关系示例

## 2. where_condition_with_fixed_values场景设计

### 2.1 场景背景

基于用户提供的`findIncomeIndustryIdList`方法，发现了另一个特殊的ORM模式：

```go
func (c *User) findIncomeIndustryIdList() ([]types.Industry, error) {
    // ...
    err := base.GetInstance().BillingDriver().Clauses(comment).Table(UserInfoTable).
        Select("income_industry_id,income_industry_name").
        Where("status=? and income_industry_id <> ?", 0, 0).  // 指定了准确赋值
        Group("income_industry_id,income_industry_name").Find(&industryInfo).Error
    // ...
}
```

**核心特点**：在where条件中直接指定了具体的值（如status=0, income_industry_id<>0），而不是通过参数传递。

### 2.2 Prompt设计特点

#### ORM Prompt设计：
- **场景描述**：明确指向固定值where条件场景
- **技术要求**：必须在where条件中直接指定具体的固定值
- **语义要求**：固定值应该有意义，如0表示有效状态，NULL表示未删除等
- **数量要求**：至少包含2个不同的固定条件

#### Caller Prompt设计：
- **无参数要求**：ORM方法不需要传递where条件参数，因为条件在方法内部是固定的
- **业务理解**：调用者应该理解这些固定条件的业务含义
- **逻辑一致性**：确保调用者代码符合固定where条件的业务逻辑

### 2.3 典型生成代码示例

#### ORM方法示例：
```go
func (p *Product) GetActiveProducts() ([]Product, error) {
    var products []Product
    err := db.Table("products").
        Where("status = ? AND deleted_at IS NULL AND category_id <> ?", 1, 0).
        Find(&products).Error
    return products, err
}
```

#### Caller方法示例：
```go
func GetAvailableProducts() ([]Product, error) {
    product := &Product{}
    return product.GetActiveProducts()  // 不需要传递where条件参数
}
```

## 3. 总结

通过这次设计，我们成功添加了两个新的场景：

1. **condition_field_mapping**：字段名映射场景
   - 判断一个字段名，但实际在SQL中使用另一个字段名
   - 需要传递原始字段名参数

2. **where_condition_with_fixed_values**：固定值where条件场景
   - 在where条件中直接指定具体的固定值
   - 不需要传递where条件参数

这两个场景的设计都确保了生成的代码符合实际业务需求，提高了数据生成的质量和准确性。

## 1. 场景背景

基于用户提供的`FindDeviceCountByFilter`方法，发现了一个特殊的ORM模式：

```go
func (d *Device) FindDeviceCountByFilter(filter map[string]interface{}) (int, error) {
    // ...
    for k, v := range filter {
        if k == "app_id" {
            sql += "AND app_id=? "
            val = append(val, v)
        } else if k == "id" {
            sql += "AND id=? "
            val = append(val, v)
        } else if k == "region" {  // 判断region字段
            cls := v.([]string)
            if len(cls) > 0 {
                sql += "AND cluster_id in (?) "  // 但实际添加cluster_id条件
                val = append(val, cls)
            }
        }
    }
    // ...
}
```

**核心特点**：条件判断中检查一个字段名，但在实际构建SQL where条件时使用不同的字段名。

## 2. 初始Prompt设计问题

### 2.1 场景描述不够精确
- **问题**：描述过于宽泛，没有明确指出这是字段名映射的具体情况
- **影响**：LLM可能生成不符合要求的代码

### 2.2 缺少具体的实现模式
- **问题**：没有明确指出这种场景的典型实现模式
- **影响**：生成的代码可能不符合实际需求

### 2.3 Caller要求不够明确
- **问题**：Caller需要传递的是原始字段名，而不是映射后的字段名
- **影响**：可能生成错误的调用者代码

## 3. 优化后的Prompt设计

### 3.1 ORM Prompt优化

#### 优化前：
```
场景描述: ORM方法中的条件判断逻辑与实际添加到SQL where条件中的字段名不同，存在字段映射或转换关系。
```

#### 优化后：
```
场景描述: ORM方法接收filter参数，在条件判断中检查某个字段名，但在实际构建SQL where条件时使用不同的字段名。这是字段名映射的典型场景，例如：判断filter中的"region"字段，但实际在SQL中添加"cluster_id"条件；判断"category"字段，但实际添加"type_id"条件等。
```

#### 关键改进：
1. **明确实现模式**：使用for循环遍历filter参数
2. **具体示例**：提供具体的字段映射示例
3. **技术要求**：明确要求方法接收map[string]interface{}类型参数
4. **映射逻辑**：强调判断条件中的字段名与SQL中的字段名必须不同

### 3.2 Caller Prompt优化

#### 优化前：
```
4. **关键要求**：filter参数中必须包含与ORM方法中字段映射对应的原始字段名
```

#### 优化后：
```
4. **关键要求**：filter参数中必须包含与ORM方法中字段映射对应的原始字段名（如：传入"region"而不是"cluster_id"）
5. **关键要求**：至少包含2个不同的字段映射关系（如：传入region但ORM处理cluster_id，传入category但ORM处理type_id）
6. **关键要求**：确保传递的参数值类型正确（如：region传入[]string类型，category传入string类型）
```

#### 关键改进：
1. **明确参数类型**：强调传递原始字段名而不是映射后的字段名
2. **类型安全**：要求确保参数值类型正确
3. **具体示例**：提供具体的映射关系示例

## 4. 优化效果对比

### 4.1 场景描述精确度
- **优化前**：描述模糊，可能导致LLM理解偏差
- **优化后**：描述具体，明确指向字段名映射场景

### 4.2 实现要求明确度
- **优化前**：要求泛化，缺乏具体指导
- **优化后**：要求具体，包含实现模式和示例

### 4.3 代码质量预期
- **优化前**：可能生成不符合要求的代码
- **优化后**：更可能生成符合实际需求的代码

## 5. 典型生成代码示例

### 5.1 ORM方法示例
```go
func (p *Product) FindProductsByFilter(filter map[string]interface{}) ([]Product, error) {
    var products []Product
    val := make([]interface{}, 0)
    sql := "SELECT * FROM products WHERE deleted_at IS NULL "
    
    for k, v := range filter {
        if k == "category" {
            sql += "AND type_id = ? "
            val = append(val, v)
        } else if k == "zone" {
            regions := v.([]string)
            if len(regions) > 0 {
                sql += "AND area_id IN (?) "
                val = append(val, regions)
            }
        } else if k == "brand" {
            sql += "AND manufacturer_id = ? "
            val = append(val, v)
        }
    }
    
    err := db.Raw(sql, val...).Scan(&products).Error
    return products, err
}
```

### 5.2 Caller方法示例
```go
func GetProductsByCategory(category string, zones []string) ([]Product, error) {
    product := &Product{}
    filter := map[string]interface{}{
        "category": category,  // 传入category，ORM处理type_id
        "zone": zones,         // 传入zone，ORM处理area_id
    }
    
    return product.FindProductsByFilter(filter)
}
```

## 6. 总结

通过这次优化，`condition_field_mapping`场景的Prompt设计更加精确和实用：

1. **场景描述更具体**：明确指向字段名映射场景
2. **实现要求更明确**：包含具体的实现模式和技术要求
3. **示例更丰富**：提供具体的映射关系示例
4. **类型安全**：强调参数类型正确性

这些优化确保了生成的代码更符合实际业务需求，提高了数据生成的质量和准确性。 