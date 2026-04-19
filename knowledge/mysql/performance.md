# MySQL性能优化

## 慢查询优化

### 识别慢查询
1. 开启慢查询日志：
   ```sql
   SET GLOBAL slow_query_log = ON;
   SET GLOBAL long_query_time = 1;  # 阈值1秒
   ```

2. 查看慢查询：
   ```sql
   SELECT * FROM mysql.slow_log ORDER BY query_time DESC LIMIT 10;
   ```

### 分析慢查询
使用EXPLAIN分析执行计划：
```sql
EXPLAIN SELECT * FROM orders WHERE user_id = 123;
```

关键指标：
- **type**：访问类型（ALL=全表扫描，index=索引扫描，range=范围扫描，ref=索引查找）
- **key**：实际使用的索引
- **rows**：预估扫描行数
- **Extra**：额外信息（Using filesort=需要额外排序）

### 优化策略

1. **添加合适索引**
   - WHERE条件字段
   - JOIN关联字段
   - ORDER BY排序字段

2. **避免索引失效**
   - 不要在索引列上使用函数
   - 避免LIKE '%xxx'前缀模糊匹配
   - 避免OR条件导致索引失效

3. **减少扫描行数**
   - 使用覆盖索引
   - 添加更精确的WHERE条件
   - 分页优化（使用子查询）

## 索引优化

### 索引类型
- **普通索引**：最基本的索引
- **唯一索引**：值必须唯一
- **主键索引**：特殊的唯一索引
- **联合索引**：多列组合
- **全文索引**：文本搜索

### 联合索引原则
遵循最左前缀原则：
```sql
-- 索引：(a, b, c)
-- 有效：WHERE a=1, WHERE a=1 AND b=2, WHERE a=1 AND b=2 AND c=3
-- 无效：WHERE b=2, WHERE c=3, WHERE b=2 AND c=3
```

### 索引使用建议
- 单表索引数量控制在5个以内
- 联合索引列数控制在5列以内
- 选择区分度高的列（count(distinct col)/count(*)）
- 定期清理无用索引

## Buffer Pool优化

### 配置建议
```sql
-- Buffer Pool大小：建议为内存的70-80%
innodb_buffer_pool_size = 总内存 * 0.75

-- Buffer Pool实例数：建议每个实例至少1GB
innodb_buffer_pool_instances = 8
```

### 监控命中率
```sql
SHOW STATUS LIKE 'Innodb_buffer_pool_read%';
-- 命中率 = (read_requests - reads) / read_requests * 100
-- 建议保持在95%以上
```

## 连接优化

### 连接池配置
- 应用端使用连接池
- 合理设置最大连接数
- 设置连接超时时间

### 参数配置
```sql
-- 最大连接数
max_connections = 1000

-- 连接超时
wait_timeout = 28800
interactive_timeout = 28800

-- 连接缓冲
thread_cache_size = 100
```

## 参数优化

### 关键参数

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| innodb_buffer_pool_size | 内存*0.75 | 缓冲池大小 |
| innodb_log_file_size | buffer_pool*0.25 | 日志文件大小 |
| innodb_flush_log_at_trx_commit | 1 | 安全性优先 |
| sync_binlog | 1 | 主从安全 |
| max_connections | 500-1000 | 根据并发设置 |
| innodb_lock_wait_timeout | 50 | 锁等待超时 |

## 表结构优化

### 选择合适数据类型
- 整数：TINYINT < SMALLINT < INT < BIGINT
- 字符串：VARCHAR vs CHAR
- 时间：DATETIME vs TIMESTAMP
- 避免使用TEXT/BLOB除非必要

### 表设计原则
- 遵循三范式，适度反范式化
- 大表拆分，垂直/水平拆分
- 适当冗余减少JOIN

## 锁优化

### 减少锁等待
- 使用索引避免全表扫描锁
- 减小事务范围
- 避免长事务
- 合理设置隔离级别

### 监控锁信息
```sql
-- 查看锁等待
SELECT * FROM information_schema.INNODB_LOCK_WAITS;

-- 查看锁信息
SELECT * FROM information_schema.INNODB_LOCKS;

-- 查看事务
SELECT * FROM information_schema.INNODB_TRX;
```