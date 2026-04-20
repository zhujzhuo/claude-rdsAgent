"""SQL 优化 Skill - 慢 SQL 标准化优化流程"""

from typing import Any, Dict

from rds_agent.skills.base import (
    BaseSkill,
    SkillState,
    SkillType,
    SOP,
    SOPStep,
)
from rds_agent.utils.logger import get_logger

logger = get_logger("sql_skill")


# SQL 优化 SOP 流程
SQL_OPTIMIZATION_SOP = SOP(
    name="sql_optimization_sop",
    skill_type=SkillType.SQL_OPTIMIZATION,
    description="慢 SQL 标准化优化流程",
    version="1.0",

    steps=[
        SOPStep(
            name="get_slow_queries",
            description="获取慢 SQL 列表",
            tool_name="get_slow_queries",
            tool_params={
                "instance_name": "$instance_name",
                "time_range": "1d",
                "limit": 20,
            },
            analysis_prompt="识别需要优化的慢 SQL",
            timeout=30,
        ),

        SOPStep(
            name="analyze_sql_patterns",
            description="分析慢 SQL 模式",
            tool_name="analyze_sql_patterns",
            tool_params={
                "slow_queries": "$get_slow_queries",
            },
            analysis_prompt="分类慢 SQL 类型",
            dependencies=["get_slow_queries"],
            timeout=30,
        ),

        SOPStep(
            name="analyze_execution_plans",
            description="分析执行计划",
            tool_name="analyze_execution_plan",
            tool_params={
                "instance_name": "$instance_name",
                "sql_list": "$analyze_sql_patterns.top_sqls",
            },
            condition="$get_slow_queries.count > 0",
            analysis_prompt="识别执行计划问题",
            dependencies=["analyze_sql_patterns"],
            timeout=60,
        ),

        SOPStep(
            name="check_indexes",
            description="检查索引使用",
            tool_name="check_index_usage",
            tool_params={
                "instance_name": "$instance_name",
                "sql_patterns": "$analyze_sql_patterns",
            },
            analysis_prompt="检查索引覆盖情况",
            dependencies=["analyze_sql_patterns"],
            timeout=30,
        ),

        SOPStep(
            name="check_table_statistics",
            description="检查表统计信息",
            tool_name="check_table_stats",
            tool_params={
                "instance_name": "$instance_name",
            },
            analysis_prompt="检查统计信息准确性",
            dependencies=["analyze_execution_plans"],
            timeout=30,
        ),

        SOPStep(
            name="generate_optimization_sql",
            description="生成优化 SQL 建议",
            tool_name="llm_analysis",
            tool_params={
                "context": "$context",
                "prompt": "根据分析结果生成 SQL 优化建议",
            },
            dependencies=[
                "analyze_execution_plans",
                "check_indexes",
                "check_table_statistics",
            ],
            timeout=60,
        ),

        SOPStep(
            name="generate_recommendations",
            description="生成优化方案",
            tool_name="generate_recommendations",
            tool_params={
                "root_cause": "$generate_optimization_sql.root_cause",
            },
            dependencies=["generate_optimization_sql"],
            timeout=30,
        ),
    ],

    decision_points={
        "analyze_execution_plans": {
            "full_table_scan": {
                "condition": "$analyze_execution_plans.has_full_scan == True",
                "root_cause": "存在全表扫描，需要添加索引",
            },
            "bad_join": {
                "condition": "$analyze_execution_plans.join_issues == True",
                "root_cause": "JOIN 顺序或条件不佳",
            },
        },
    },

    conclusion_template="""
## SQL 优化分析报告

**实例**: {instance_name}

### 根因定位
{root_cause}

### 关键发现
{key_findings}

### 优化建议
{recommendations}
""",
)


class SQLOptimizationSkill(BaseSkill):
    """SQL 优化 Skill"""

    skill_type = SkillType.SQL_OPTIMIZATION
    sop = SQL_OPTIMIZATION_SOP

    def __init__(self, mysql_client=None, tools_registry: Dict = None):
        super().__init__(mysql_client, tools_registry)

    def get_sop(self) -> SOP:
        return SQL_OPTIMIZATION_SOP

    def _analyze_output(self, step: SOPStep, output: Any) -> str:
        """分析步骤输出"""
        if output is None:
            return "未获取到数据"

        if isinstance(output, dict):
            if step.name == "get_slow_queries":
                count = output.get("count", 0)
                return f"发现 {count} 条慢 SQL"

            elif step.name == "analyze_sql_patterns":
                patterns = output.get("patterns", [])
                return f"SQL 模式：{', '.join(patterns[:3])}"

            elif step.name == "analyze_execution_plans":
                issues = output.get("issues", [])
                if issues:
                    return f"执行计划问题：{', '.join(issues[:3])}"
                return "执行计划正常"

            elif step.name == "check_indexes":
                missing = output.get("missing_indexes", [])
                if missing:
                    return f"缺失索引：{', '.join(missing[:3])}"
                return "索引覆盖良好"

        return f"步骤输出：{str(output)[:100]}"