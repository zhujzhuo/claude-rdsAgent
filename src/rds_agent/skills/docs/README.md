"""Skills/SOP 文档目录"""

This directory contains Skill definitions in Markdown format.
Each .md file defines a Skill with its SOP (Standard Operating Procedure).

## 文件格式

每个 Skill 文档包含以下部分：

### 元数据 (YAML Front Matter)

```yaml
---
name: cpu_analysis
skill_type: CPU_ANALYSIS
description: CPU 使用率过高问题标准化诊断流程
version: 1.0
author: system
---
```

### SOP 步骤定义

使用表格格式定义步骤：

```markdown
## SOP 步骤

| 步骤 | 名称 | 工具 | 参数 | 条件 | 依赖 | 分析说明 |
|------|------|------|------|------|------|----------|
| 1 | get_monitoring_data | get_monitoring_data | instance_name=$instance_name, metric_type=cpu_usage | - | - | 获取 CPU 监控数据 |
| 2 | check_session_change | get_monitoring_data | instance_name=$instance_name, metric_type=session_count | - | 1 | 检查会话数变化 |
| 3 | get_profiling | get_profiling | instance_name=$instance_name | $cpu_usage > 70 | 1 | 获取 Profiling |
```

### 决策点定义

```markdown
## 决策点

### check_session_change

| 规则名 | 条件 | 根因 | 跳过步骤 |
|--------|------|------|----------|
| session_spike | $change_rate > 50 | 业务突增导致会话激增 | 3, 5 |
| no_spike | $change_rate <= 50 | - | - |
```

### 分析模板

```markdown
## 分析模板

### get_monitoring_data
- 高使用率 (>90%): "CPU 使用率严重过高：{cpu_usage}%"
- 偏高 (>70%): "CPU 使用率偏高：{cpu_usage}%"
- 正常: "CPU 使用率正常：{cpu_usage}%"

### check_session_change
- 突增 (>50%): "会话数突增：当前 {current}，变化率 {change_rate}%"
- 稳定: "会话数稳定：当前 {current}"
```

### 优化建议

```markdown
## 优化建议

### 业务突增
- 评估业务增长趋势，考虑扩容
- 优化连接池配置

### SQL问题
- 优化慢 SQL 执行计划
- 添加必要的索引
```

## 当前 Skills

- `cpu_analysis.md` - CPU 使用率分析
- `storage_analysis.md` - 存储磁盘分析
- `sql_optimization.md` - SQL 优化流程
- `connection_analysis.md` - 连接数分析