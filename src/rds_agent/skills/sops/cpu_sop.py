"""CPU 分析 SOP 定义 - 标准化 CPU 使用率问题诊断流程"""

from datetime import datetime

from rds_agent.skills.base import (
    SOP,
    SOPStep,
    SkillType,
)


# CPU 分析 SOP 流程（9步）
CPU_ANALYSIS_SOP = SOP(
    name="cpu_analysis_sop",
    skill_type=SkillType.CPU_ANALYSIS,
    description="CPU 使用率过高问题标准化诊断流程",
    version="1.0",

    steps=[
        # Step 1: 获取 CPU 监控数据
        SOPStep(
            name="get_monitoring_data",
            description="获取实例 CPU 监控数据",
            tool_name="get_monitoring_data",
            tool_params={
                "instance_name": "$instance_name",
                "metric_type": "cpu_usage",
                "time_range": "1h",
            },
            analysis_prompt="分析 CPU 使用率趋势，识别高峰时段",
            timeout=30,
        ),

        # Step 2: 检查会话数变化（关键：判断根因）
        SOPStep(
            name="check_session_change",
            description="检查会话数变化，判断是否有会话突增",
            tool_name="get_monitoring_data",
            tool_params={
                "instance_name": "$instance_name",
                "metric_type": "session_count",
                "time_range": "1h",
            },
            analysis_prompt="对比 CPU 高峰时段的会话数变化",
            dependencies=["get_monitoring_data"],
            timeout=30,
        ),

        # Step 3: 获取 CPU 高峰时段 Profiling
        SOPStep(
            name="get_profiling",
            description="获取 CPU 高峰时段的 Profiling 数据",
            tool_name="get_profiling",
            tool_params={
                "instance_name": "$instance_name",
                "time_range": "$get_monitoring_data.peak_time",
            },
            condition="$get_monitoring_data.cpu_usage > 70",
            analysis_prompt="分析 Profiling 数据，识别高 CPU 操作",
            dependencies=["get_monitoring_data"],
            timeout=60,
        ),

        # Step 4: 获取慢 SQL（与 Profiling 对比）
        SOPStep(
            name="get_slow_queries",
            description="获取 CPU 高峰时段的慢 SQL",
            tool_name="get_slow_queries",
            tool_params={
                "instance_name": "$instance_name",
                "time_range": "$get_monitoring_data.peak_time",
                "limit": 10,
            },
            analysis_prompt="对比慢 SQL 与 Profiling 数据，找出一致性",
            dependencies=["get_monitoring_data"],
            timeout=30,
        ),

        # Step 5: 分析关键 SQL 执行计划
        SOPStep(
            name="analyze_sql_plan",
            description="分析关键 SQL 的执行计划",
            tool_name="analyze_sql_plan",
            tool_params={
                "instance_name": "$instance_name",
                "sql_patterns": "$get_slow_queries.sql_patterns",
            },
            condition="$get_slow_queries.count > 0",
            analysis_prompt="分析 SQL 执行计划，识别性能瓶颈",
            dependencies=["get_slow_queries"],
            timeout=30,
        ),

        # Step 6: 检查锁等待
        SOPStep(
            name="check_lock_status",
            description="检查锁等待情况",
            tool_name="check_lock_status",
            tool_params={
                "instance_name": "$instance_name",
            },
            analysis_prompt="检查是否存在锁等待导致的 CPU 升高",
            dependencies=["get_monitoring_data"],
            timeout=30,
        ),

        # Step 7: 检查 Buffer Pool 命中率
        SOPStep(
            name="check_buffer_pool",
            description="检查 Buffer Pool 命中率",
            tool_name="check_buffer_pool",
            tool_params={
                "instance_name": "$instance_name",
            },
            analysis_prompt="分析 Buffer Pool 命中率对 CPU 的影响",
            dependencies=["get_monitoring_data"],
            timeout=30,
        ),

        # Step 8: 根因分析（综合判断）
        SOPStep(
            name="root_cause_analysis",
            description="综合分析，定位根因",
            tool_name="llm_analysis",
            tool_params={
                "context": "$context",
                "prompt": """
综合以下数据进行根因分析：

1. CPU 监控数据：{get_monitoring_data}
2. 会话数变化：{check_session_change}
3. Profiling 数据：{get_profiling}
4. 慢 SQL：{get_slow_queries}
5. 锁等待：{check_lock_status}
6. Buffer Pool：{check_buffer_pool}

请分析 CPU 使用率高的根本原因，输出格式：
- 根因类型：业务突增 / SQL问题 / 锁等待 / Buffer Pool问题 / 其他
- 根因详情：具体描述
- 置信度：高/中/低
""",
            },
            dependencies=[
                "get_monitoring_data",
                "check_session_change",
                "get_profiling",
                "get_slow_queries",
                "check_lock_status",
                "check_buffer_pool",
            ],
            timeout=60,
        ),

        # Step 9: 生成优化建议
        SOPStep(
            name="generate_recommendations",
            description="生成优化建议",
            tool_name="generate_recommendations",
            tool_params={
                "root_cause": "$root_cause_analysis.root_cause",
            },
            analysis_prompt="根据根因生成具体的优化建议",
            dependencies=["root_cause_analysis"],
            timeout=30,
        ),
    ],

    # 决策点定义
    decision_points={
        "check_session_change": {
            "session_spike": {
                "condition": "$check_session_change.change_rate > 50",
                "root_cause": "业务突增导致会话激增，进而导致 CPU 使用率升高",
                "skip_steps": ["get_profiling", "analyze_sql_plan"],
            },
            "no_spike": {
                "condition": "$check_session_change.change_rate <= 50",
            },
        },
        "check_lock_status": {
            "lock_wait": {
                "condition": "$check_lock_status.lock_wait_count > 10",
                "root_cause": "锁等待导致 CPU 升高，需排查锁冲突",
            },
        },
        "check_buffer_pool": {
            "low_hit_rate": {
                "condition": "$check_buffer_pool.hit_rate < 90",
                "root_cause": "Buffer Pool 命中率低导致大量磁盘读取，CPU 升高",
            },
        },
    },

    # 结论模板
    conclusion_template="""
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
SOP 版本: 1.0
""",
)