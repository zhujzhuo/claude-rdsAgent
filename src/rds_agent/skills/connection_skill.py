"""连接分析 Skill - 连接数问题标准化诊断"""

from typing import Any, Dict

from rds_agent.skills.base import (
    BaseSkill,
    SkillState,
    SkillType,
    SOP,
    SOPStep,
)
from rds_agent.utils.logger import get_logger

logger = get_logger("connection_skill")


# 连接分析 SOP 流程
CONNECTION_ANALYSIS_SOP = SOP(
    name="connection_analysis_sop",
    skill_type=SkillType.CONNECTION_ANALYSIS,
    description="连接数过高问题标准化诊断流程",
    version="1.0",

    steps=[
        SOPStep(
            name="get_connection_monitoring",
            description="获取连接数监控数据",
            tool_name="get_monitoring_data",
            tool_params={
                "instance_name": "$instance_name",
                "metric_type": "connection_count",
                "time_range": "1h",
            },
            analysis_prompt="分析连接数趋势",
            timeout=30,
        ),

        SOPStep(
            name="get_current_sessions",
            description="获取当前会话详情",
            tool_name="get_current_sessions",
            tool_params={
                "instance_name": "$instance_name",
            },
            analysis_prompt="分析当前活跃会话",
            dependencies=["get_connection_monitoring"],
            timeout=30,
        ),

        SOPStep(
            name="analyze_session_sources",
            description="分析会话来源",
            tool_name="analyze_session_sources",
            tool_params={
                "sessions": "$get_current_sessions",
            },
            analysis_prompt="识别连接来源分布",
            dependencies=["get_current_sessions"],
            timeout=30,
        ),

        SOPStep(
            name="check_long_transactions",
            description="检查长事务",
            tool_name="check_long_transactions",
            tool_params={
                "instance_name": "$instance_name",
            },
            analysis_prompt="检查长时间占用连接的事务",
            dependencies=["get_current_sessions"],
            timeout=30,
        ),

        SOPStep(
            name="check_idle_connections",
            description="检查空闲连接",
            tool_name="check_idle_connections",
            tool_params={
                "instance_name": "$instance_name",
            },
            analysis_prompt="检查空闲连接占比",
            dependencies=["get_current_sessions"],
            timeout=30,
        ),

        SOPStep(
            name="root_cause_analysis",
            description="综合分析连接根因",
            tool_name="llm_analysis",
            tool_params={
                "context": "$context",
                "prompt": "综合分析连接数过高根因",
            },
            dependencies=[
                "get_connection_monitoring",
                "analyze_session_sources",
                "check_long_transactions",
                "check_idle_connections",
            ],
            timeout=60,
        ),

        SOPStep(
            name="generate_recommendations",
            description="生成连接优化建议",
            tool_name="generate_recommendations",
            tool_params={
                "root_cause": "$root_cause_analysis.root_cause",
            },
            dependencies=["root_cause_analysis"],
            timeout=30,
        ),
    ],

    decision_points={
        "check_long_transactions": {
            "long_tx": {
                "condition": "$check_long_transactions.count > 5",
                "root_cause": "存在长事务占用连接",
            },
        },
        "check_idle_connections": {
            "idle_high": {
                "condition": "$check_idle_connections.ratio > 50",
                "root_cause": "大量空闲连接未释放",
            },
        },
    },

    conclusion_template="""
## 连接数分析报告

**实例**: {instance_name}

### 根因定位
{root_cause}

### 关键发现
{key_findings}

### 优化建议
{recommendations}
""",
)


class ConnectionAnalysisSkill(BaseSkill):
    """连接分析 Skill"""

    skill_type = SkillType.CONNECTION_ANALYSIS
    sop = CONNECTION_ANALYSIS_SOP

    def __init__(self, mysql_client=None, tools_registry: Dict = None):
        super().__init__(mysql_client, tools_registry)

    def get_sop(self) -> SOP:
        return CONNECTION_ANALYSIS_SOP

    def _analyze_output(self, step: SOPStep, output: Any) -> str:
        """分析步骤输出"""
        if output is None:
            return "未获取到数据"

        if isinstance(output, dict):
            if step.name == "get_connection_monitoring":
                current = output.get("current_connections", 0)
                max_conn = output.get("max_connections", 0)
                return f"当前连接：{current}，最大连接：{max_conn}"

            elif step.name == "get_current_sessions":
                count = output.get("session_count", 0)
                return f"当前会话数：{count}"

            elif step.name == "analyze_session_sources":
                sources = output.get("sources", [])
                if sources:
                    return f"连接来源：{', '.join([s.get('host', '') for s in sources[:3]])}"
                return "无会话来源数据"

            elif step.name == "check_long_transactions":
                count = output.get("count", 0)
                if count > 0:
                    return f"发现 {count} 个长事务"
                return "无长事务"

            elif step.name == "check_idle_connections":
                ratio = output.get("ratio", 0)
                return f"空闲连接比例：{ratio}%"

        return f"步骤输出：{str(output)[:100]}"