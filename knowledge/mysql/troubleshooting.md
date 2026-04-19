# MySQL故障排查

## 连接问题

### 连接数过高
症状：
- 报错 "Too many connections"
- 应用无法建立新连接

排查：
```sql
SHOW STATUS LIKE 'Threads_connected';
SHOW STATUS LIKE 'max_connections';
SHOW FULL PROCESSLIST;
```

解决：
1. 临时增加max_connections
2. kill长时间空闲连接
3. 优化应用连接池配置

### 连接超时
症状：
- 连接建立缓慢
- 应用报超时错误

排查：
```sql
SHOW STATUS LIKE 'Connection_errors%';
SHOW VARIABLES LIKE 'connect_timeout';
```

解决：
- 检查网络延迟
- 检查服务器负载
- 调整connect_timeout参数

## 性能问题

### 查询变慢
症状：
- 响应时间增加
- 慢查询数量增加

排查步骤：
1. 检查慢查询日志
2. 使用EXPLAIN分析执行计划
3. 检查索引使用情况
4. 检查Buffer Pool命中率
5. 检查锁等待情况

常见原因：
- 索引失效
- 统计信息不准确
- Buffer Pool不足
- 锁等待
- 磁盘IO瓶颈

### CPU使用率过高
排查：
```sql
-- 查看活跃线程
SHOW STATUS LIKE 'Threads_running';

-- 查看执行中的SQL
SHOW FULL PROCESSLIST;
```

解决：
- 找出消耗CPU的查询
- 优化查询执行计划
- 添加合适索引

### 内存使用异常
排查：
```sql
SHOW STATUS LIKE 'Innodb_buffer_pool%';
SHOW VARIABLES LIKE 'innodb_buffer_pool_size';
```

解决：
- 调整Buffer Pool大小
- 检查是否有大查询占用内存
- 优化临时表使用

## 锁问题

### 锁等待超时
症状：
- 报错 "Lock wait timeout exceeded"
- 事务执行失败

排查：
```sql
-- 查看锁等待
SELECT * FROM information_schema.INNODB_LOCK_WAITS;

-- 查看阻塞事务
SELECT r.trx_id, r.trx_query, b.trx_id, b.trx_query
FROM INNODB_LOCK_WAITS w
JOIN INNODB_TRX b ON b.trx_id = w.blocking_trx_id
JOIN INNODB_TRX r ON r.trx_id = w.requesting_trx_id;
```

解决：
- kill阻塞的事务
- 优化事务逻辑
- 减小事务范围

### 死锁
症状：
- 报错 "Deadlock found"
- 事务自动回滚

排查：
```sql
SHOW ENGINE INNODB STATUS;
```

解决：
- 调整事务操作顺序
- 减少事务持锁时间
- 使用SELECT ... FOR UPDATE预锁定

## 存储问题

### 空间不足
症状：
- 报错 "The table is full"
- 无法插入数据

排查：
```sql
-- 查看表大小
SELECT table_schema, SUM(data_length+index_length)/1024/1024 AS size_mb
FROM information_schema.tables
GROUP BY table_schema;

-- 查看最大表
SELECT table_schema, table_name,
       (data_length+index_length)/1024/1024 AS size_mb
FROM information_schema.tables
ORDER BY size_mb DESC LIMIT 10;
```

解决：
- 清理无用数据
- 归档历史数据
- 扩容存储空间

### 磁盘IO瓶颈
症状：
- IO等待高
- 查询响应慢

排查：
- 使用iostat查看IO统计
- 检查innodb_io_capacity配置

解决：
- 增加Buffer Pool减少磁盘读取
- 调整innodb_io_capacity
- 使用SSD存储

## 复制问题

### 主从延迟
症状：
- Slave落后Master太多
- 读写分离数据不一致

排查：
```sql
-- Slave上执行
SHOW SLAVE STATUS;
-- 查看 Seconds_Behind_Master
```

解决：
- 检查Slave负载
- 使用并行复制
- 优化大事务

### 复制中断
症状：
- Slave IO/SQL线程停止
- 报错复制错误

排查：
```sql
SHOW SLAVE STATUS;
-- 查看 Last_IO_Error, Last_SQL_Error
```

解决：
- 根据错误类型处理
- 重建复制（必要时）

## 主从切换

### 故障切换流程
1. 确认Master故障
2. 选择新Master（数据最新的Slave）
3. 停止其他Slave复制
4. 提升新Master
5. 配置其他Slave指向新Master
6. 应用连接新Master

## 常用诊断命令汇总

```sql
-- 查看状态变量
SHOW GLOBAL STATUS;

-- 查看系统变量
SHOW GLOBAL VARIABLES;

-- 查看进程列表
SHOW FULL PROCESSLIST;

-- 查看InnoDB状态
SHOW ENGINE INNODB STATUS;

-- 查看表状态
SHOW TABLE STATUS;

-- 查看索引使用
SHOW INDEX FROM table_name;

-- 查看错误日志位置
SHOW VARIABLES LIKE 'log_error';
```