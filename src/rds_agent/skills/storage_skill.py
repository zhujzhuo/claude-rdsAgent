"""存储分析 Skill - 存储磁盘问题标准化诊断"""

from typing import Any, Dict

from rds_agent.skills.base import (
    BaseSkill,
    SkillState,
    SkillType,
    SOP,
    SOPStep,
)
from rds_agent.utils.logger import get_logger

logger = get_logger("storage_skill")


# 存储分析 SOP 流程
STORAGE_ANALYSIS_SOP = SOP(
    name="storage_analysis_sop",
    skill_type=SkillType.STORAGE_ANALYSIS,
    description="存储磁盘空间问题标准化诊断流程",
    version="1.0",

    steps=[
        SOPStep(
            name="get_storage_monitoring",
            description="获取存储监控数据",
            tool_name="get_monitoring_data",
            tool_params={
                "instance_name": "$instance_name",
                "metric_type": "storage_usage",
                "time_range": "7d",
            },
            analysis_prompt="分析存储空间使用趋势",
            timeout=30,
        ),

        SOPStep(
            name="get_table_sizes",
            description="获取各表大小",
            tool_name="get_table_sizes",
            tool_params={
                "instance_name": "$instance_name",
            },
            analysis_prompt="识别大表和增长快的表",
            dependencies=["get_storage_monitoring"],
            timeout=30,
        ),

        SOPStep(
            name="analyze_growth_points",
            description="分析存储增长点",
            tool_name="analyze_storage_growth",
            tool_params={
                "instance_name": "$instance_name",
                "table_sizes": "$get_table_sizes",
            },
            analysis_prompt="定位存储增长的主要来源",
            dependencies=["get_table_sizes"],
            timeout=30,
        ),

        SOPStep(
            name="check_binlog_size",
            description="检查 Binlog 大小",
            tool_name="check_binlog",
            tool_params={
                "instance_name": "$instance_name",
            },
            analysis_prompt="检查 Binlog 对存储的影响",
            dependencies=["get_storage_monitoring"],
            timeout=30,
        ),

        SOPStep(
            name="check_temp_tables",
            description="检查临时表",
            tool_name="check_temp_tables",
            tool_params={
                "instance_name": "$instance_name",
            },
            analysis_prompt="检查临时表对存储的影响",
            dependencies=["get_storage_monitoring"],
            timeout=30,
        ),

        SOPStep(
            name="root_cause_analysis",
            description="综合分析存储根因",
            tool_name="llm_analysis",
            tool_params={
                "context": "$context",
                "prompt": "综合分析存储增长根因",
            },
            dependencies=[
                "get_storage_monitoring",
                "get_table_sizes",
                "analyze_growth_points",
                "check_binlog_size",
            ],
            timeout=60,
        ),

        SOPStep(
            name="generate_recommendations",
            description="生成存储优化建议",
            tool_name="generate_recommendations",
            tool_params={
                "root_cause": "$root_cause_analysis.root_cause",
            },
            dependencies=["root_cause_analysis"],
            timeout=30,
        ),
    ],

    decision_points={
        "check_binlog_size": {
            "binlog_large": {
                "condition": "$check_binlog_size.size_gb > 10",
                "root_cause": "Binlog 占用大量存储空间",
            },
        },
    },

    conclusion_template="""
## 存储空间分析报告

**实例**: {instance_name}

### 根因定位
{root_cause}

### 关键发现
{key_findings}

### 优化建议
{recommendations}
""",
)


class StorageAnalysisSkill(BaseSkill):
    """存储分析 Skill"""

    skill_type = SkillType.STORAGE_ANALYSIS
    sop = STORAGE_ANALYSIS_SOP

    def __init__(self, mysql_client=None, tools_registry: Dict = None):
        super().__init__(mysql_client, tools_registry)

    def get_sop(self) -> SOP:
        return STORAGE_ANALYSIS_SOP

    def _analyze_output(self, step: SOPStep, output: Any) -> str:
        """分析步骤输出"""
        if output is None:
            return "未获取到数据"

        # 简化分析逻辑
        if isinstance(output, dict):
            if step.name == "get_storage_monitoring":
                usage = output.get("storage_usage", 0)
                return f"存储使用率：{usage}%"

            elif step.name == "get_table_sizes":
                tables = output.get("tables", [])
                if tables:
                    top_tables = sorted(
                        tables, key=lambda x: x.get("size_mb", 0), reverse=True
                    )[:3]
                    return f"大表：{', '.join([t.get('name', '') for t in top_tables])}"
                return "无表数据"

            elif step.name == "analyze_growth_points":
                growth_points = output.get("growth_points", [])
                if growth_points:
                    return f"增长点：{', '.join(growth_points[:3])}"
                return "未发现明显增长点"

        return f"步骤输出：{str(output)[:100]}"