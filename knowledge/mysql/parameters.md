# MySQL关键参数说明

## InnoDB参数

### innodb_buffer_pool_size
- **说明**：InnoDB缓冲池大小，缓存数据和索引页
- **单位**：字节
- **推荐**：设置为物理内存的70-80%
- **示例**：`innodb_buffer_pool_size = 8G`
- **影响**：直接影响查询性能，越大越好（在内存允许范围内）

### innodb_buffer_pool_instances
- **说明**：Buffer Pool分区数量
- **推荐**：每个实例至少1GB，Buffer Pool大于1GB时设置
- **示例**：`innodb_buffer_pool_instances = 8`
- **影响**：减少锁竞争，提高并发性能

### innodb_log_file_size
- **说明**：InnoDB redo日志文件大小
- **单位**：字节
- **推荐**：Buffer Pool大小的25%
- **示例**：`innodb_log_file_size = 2G`
- **影响**：影响写入性能和恢复时间

### innodb_flush_log_at_trx_commit
- **说明**：事务日志刷盘策略
- **可选值**：
  - 0：每秒刷盘（可能丢失1秒数据）
  - 1：每次事务提交刷盘（最安全）
  - 2：每次提交写入OS缓存，每秒刷盘
- **推荐**：生产环境设为1
- **影响**：影响事务安全性和写入性能

### innodb_flush_method
- **说明**：InnoDB刷盘方法
- **推荐**：Linux使用O_DIRECT
- **示例**：`innodb_flush_method = O_DIRECT`
- **影响**：避免双缓冲，提高IO效率

### innodb_io_capacity
- **说明**：InnoDB后台IO能力
- **单位**：IOPS
- **推荐**：根据磁盘类型设置
  - SSD：2000-5000
  - HDD：200
- **影响**：影响后台刷新和检查点速度

### innodb_lock_wait_timeout
- **说明**：锁等待超时时间
- **单位**：秒
- **默认**：50秒
- **推荐**：根据业务需求调整
- **影响**：长时间锁等待自动放弃

## 连接参数

### max_connections
- **说明**：最大并发连接数
- **默认**：151
- **推荐**：500-1000（根据应用需求）
- **影响**：连接数超限报错

### thread_cache_size
- **说明**：线程缓存数量
- **推荐**：max_connections的10%或更高
- **影响**：减少线程创建开销

### wait_timeout
- **说明**：非交互连接超时时间
- **单位**：秒
- **默认**：28800（8小时）
- **推荐**：根据应用连接池特性调整
- **影响**：长时间空闲连接自动断开

### interactive_timeout
- **说明**：交互连接超时时间
- **单位**：秒
- **默认**：28800
- **推荐**：与wait_timeout保持一致

### max_allowed_packet
- **说明**：最大数据包大小
- **单位**：字节
- **默认**：4MB
- **推荐**：16MB或更大（有大数据导入时）
- **影响**：限制单次传输数据量

## 查询参数

### slow_query_log
- **说明**：慢查询日志开关
- **推荐**：开启
- **示例**：`slow_query_log = ON`

### long_query_time
- **说明**：慢查询阈值
- **单位**：秒
- **默认**：10秒
- **推荐**：1-3秒
- **影响**：记录超过阈值的查询

### log_queries_not_using_indexes
- **说明**：记录未使用索引的查询
- **推荐**：开启
- **影响**：帮助发现优化机会

### query_cache_size (MySQL 5.7)
- **说明**：查询缓存大小
- **注意**：MySQL 8.0已废弃
- **推荐**：MySQL 5.7可适当设置，但效果有限

## 复制参数

### sync_binlog
- **说明**：Binlog同步策略
- **可选值**：
  - 0：依赖OS刷盘
  - 1：每次事务同步（最安全）
  - N>1：每N次事务同步
- **推荐**：生产环境设为1
- **影响**：主从数据安全

### binlog_format
- **说明**：Binlog格式
- **可选值**：ROW, STATEMENT, MIXED
- **推荐**：ROW（最安全）
- **影响**：复制精度和性能

### relay_log_recovery
- **说明**：Slave崩溃后恢复
- **推荐**：开启
- **影响**：提高复制可靠性

## 其他参数

### tmp_table_size
- **说明**：内部临时表大小
- **单位**：字节
- **推荐**：与max_heap_table_size一致
- **影响**：避免临时表转磁盘

### max_heap_table_size
- **说明**：MEMORY表最大大小
- **单位**：字节
- **影响**：内存表大小限制

### character_set_server
- **说明**：服务器默认字符集
- **推荐**：utf8mb4
- **影响**：支持完整Unicode

### collation_server
- **说明**：服务器默认排序规则
- **推荐**：utf8mb4_general_ci
- **影响**：字符比较规则

### default_storage_engine
- **说明**：默认存储引擎
- **推荐**：InnoDB
- **影响**：建表默认引擎