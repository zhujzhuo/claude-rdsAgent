---
name: cpu_analysis
skill_type: CPU_ANALYSIS
description: CPU 使用率过高问题标准化诊断流程
version: 1.0
author: system
tags: [cpu, performance, diagnosis]
---

# CPU 使用率分析 Skill

标准化诊断流程，用于分析 CPU 使用率过高问题。

**关键特性**: 通过决策点强制检查会话变化，避免大模型因果颠倒问题。

## SOP 步骤

| 序号 | 名称 | 工具 | 参数 | 条件 | 依赖 | 分析说明 | 超时 |
|------|------|------|------|------|------|----------|------|
| 1 | get_monitoring_data | get_monitoring_data | instance_name=$instance_name, metric_type=cpu_usage, time_range=1h | - | - | 获取 CPU 监控数据，识别高峰时段 | 30s |
| 2 | check_session_change | get_monitoring_data | instance_name=$instance_name, metric_type=session_count, time_range=1h | - | 1 | 检查会话数变化（关键决策点） | 30s |
| 3 | get_profiling | get_profiling | instance_name=$instance_name, time_range=$peak_time | $cpu_usage > 70 | 1 | 获取 CPU 高峰时段 Profiling | 60s |
| 4 | get_slow_queries | get_slow_queries | instance_name=$instance_name, time_range=$peak_time, limit=10 | - | 1 | 获取慢 SQL，与 Profiling 对比 | 30s |
| 5 | analyze_sql_plan | analyze_sql_plan | instance_name=$instance_name, sql_patterns=$sql_patterns | $slow_query_count > 0 | 4 | 分析关键 SQL 执行计划 | 30s |
| 6 | check_lock_status | check_lock_status | instance_name=$instance_name | - | 1 | 检查锁等待情况 | 30s |
| 7 | check_buffer_pool | check_buffer_pool | instance_name=$instance_name | - | 1 | 检查 Buffer Pool 命中率 | 30s |
| 8 | root_cause_analysis | llm_analysis | context=$context, prompt=root_cause_prompt | - | 1,2,3,4,6,7 | 综合分析，定位根因 | 60s |
| 9 | generate_recommendations | generate_recommendations | root_cause=$root_cause | - | 8 | 生成优化建议 | 30s |

## 决策点

### check_session_change (关键决策点)

| 规则名 | 条件 | 根因 | 动作 |
|--------|------|------|------|
| session_spike | `$session_change_rate > 50` | 业务突增导致会话激增，进而导致 CPU 使用率升高 | skip_steps=[3,5], end_analysis=true |
| no_session_spike | `$session_change_rate <= 50` | - | continue |

**说明**: 会话突增超过 50% 时，直接定位根因为业务突增，跳过部分步骤。

### check_lock_status

| 规则名 | 条件 | 根因 | 动作 |
|--------|------|------|------|
| lock_wait | `$lock_wait_count > 10` | 锁等待导致 CPU 升高，需排查锁冲突 | set_flag=lock_issue |

### check_buffer_pool

| 规则名 | 条件 | 根因 | 动作 |
|--------|------|------|------|
| low_hit_rate | `$buffer_pool_hit_rate < 90` | Buffer Pool 命中率低导致大量磁盘读取 | set_flag=buffer_issue |

## 分析模板

### get_monitoring_data

```
输入: {cpu_usage, peak_time}

条件分支:
  - cpu_usage > 90: "CPU 使用率严重过高：{cpu_usage}%，高峰时段：{peak_time}"
  - cpu_usage > 70: "CPU 使用率偏高：{cpu_usage}%，高峰时段：{peak_time}"
  - cpu_usage <= 70: "CPU 使用率正常：{cpu_usage}%"

存储上下文:
  - cpu_usage
  - peak_time
```

### check_session_change

```
输入: {current_sessions, avg_sessions, change_rate}

条件分支:
  - change_rate > 50: "会话数突增：当前 {current_sessions}，平均 {avg_sessions}，变化率 {change_rate:.1f}%"
  - change_rate > 20: "会话数略有增长：当前 {current_sessions}，变化率 {change_rate:.1f}%"
  - change_rate <= 20: "会话数稳定：当前 {current_sessions}，变化率 {change_rate:.1f}%"

存储上下文:
  - session_change_rate (关键变量)
```

### get_profiling

```
输入: {top_operations}

分析逻辑:
  - 提取 cpu_time > 100ms 的操作
  - 输出格式: "高 CPU 操作：{operation} ({cpu_time}ms)"
  - 无高 CPU 操作: "未发现明显高 CPU 操作"
```

### get_slow_queries

```
输入: {count, slow_queries, sql_patterns}

条件分支:
  - count > 0: "发现 {count} 条慢 SQL，模式：{patterns}"
  - count == 0: "未发现慢 SQL"

存储上下文:
  - slow_query_count
```

### check_lock_status

```
输入: {lock_wait_count}

条件分支:
  - lock_wait_count > 10: "存在严重锁等待：{lock_wait_count} 个锁等待"
  - lock_wait_count > 0: "存在少量锁等待：{lock_wait_count} 个"
  - lock_wait_count == 0: "无锁等待"

存储上下文:
  - lock_wait_count
```

### check_buffer_pool

```
输入: {hit_rate}

条件分支:
  - hit_rate < 90: "Buffer Pool 命中率低：{hit_rate}%"
  - hit_rate < 95: "Buffer Pool 命中率偏低：{hit_rate}%"
  - hit_rate >= 95: "Buffer Pool 命中率正常：{hit_rate}%"

存储上下文:
  - buffer_pool_hit_rate
```

## 根因分析模板

```markdown
综合以下数据进行根因分析：

1. CPU 监控数据：{get_monitoring_data.output}
2. 会话数变化：{check_session_change.output}
3. Profiling 数据：{get_profiling.output}
4. 慢 SQL：{get_slow_queries.output}
5. 锁等待：{check_lock_status.output}
6. Buffer Pool：{check_buffer_pool.output}

请分析 CPU 使用率高的根本原因，输出格式：
- 根因类型：业务突增 / SQL问题 / 锁等待 / Buffer Pool问题 / 其他
- 根因详情：具体描述
- 置信度：高/中/低
```

## 优化建议

### 业务突增导致会话激增

- 评估业务增长趋势，考虑扩容或读写分离
- 检查是否有不必要的全表扫描查询
- 优化连接池配置，限制最大连接数

### SQL 问题

- 优化慢 SQL 执行计划
- 添加必要的索引
- 避免全表扫描和大结果集

### 锁等待问题

- 排查锁冲突的业务逻辑
- 优化事务设计，减少锁持有时间
- 考虑使用乐观锁或减少锁粒度

### Buffer Pool 问题

- 增加 Buffer Pool 大小
- 优化热点数据访问模式
- 检查是否有大量冷数据读取

### 通用建议

- 持续监控 CPU 使用率
- 定期检查慢 SQL 和 Profiling 数据
- 建立性能基线，定期进行性能巡检

## 结论模板

```markdown
## CPU 使用率分析报告

**实例**: {instance_name}

### 根因定位
{root_cause}

### 关键发现
{key_findings}

### 优化建议
{recommendations}

---
分析时间: {timestamp}
SOP 版本: {version}
```

## 示例场景

### 场景1: 业务突增导致 CPU 过高

```
用户输入: "db-01 的 CPU 使用率过高"

执行流程:
1. 获取监控数据: cpu_usage=95%, peak_time=10:30
2. 检查会话变化: current=200, avg=100, change_rate=100%

决策点触发:
- session_change_rate > 50%
- 根因定位: "业务突增导致会话激增"
- 跳过步骤: Profiling(3), SQL执行计划分析(5)

后续步骤:
6. 检查锁等待: lock_wait_count=0
7. 检查 Buffer Pool: hit_rate=95%
8. 根因分析确认
9. 生成建议

输出:
- 根因: 业务突增导致会话激增
- 建议: 评估业务增长、优化连接池配置、考虑扩容
```

### 场景2: SQL 问题导致 CPU 过高

```
用户输入: "db-01 的 CPU 使用率异常"

执行流程:
1. 获取监控数据: cpu_usage=85%, peak_time=14:00
2. 检查会话变化: current=50, avg=45, change_rate=11%

决策点:
- session_change_rate <= 50%
- 继续后续步骤

后续步骤:
3. Profiling: 发现 SELECT * FROM large_table 占用高 CPU
4. 慢 SQL: 发现 10 条慢查询，包含全表扫描
5. 执行计划: 发现缺少索引
6. 锁等待: 0
7. Buffer Pool: 92%
8. 根因分析: "慢 SQL 全表扫描导致 CPU 升高"

输出:
- 根因: 慢 SQL 全表扫描，缺少索引
- 建议: 添加索引、优化 SQL、避免全表扫描
```