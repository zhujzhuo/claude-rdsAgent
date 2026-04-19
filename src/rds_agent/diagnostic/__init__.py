"""诊断Agent模块 - 智能运维诊断助手。"""

from rds_agent.diagnostic.state import (
    DiagnosticType,
    HealthStatus,
    CheckCategory,
    CheckItem,
    DiagnosticResult,
    DiagnosticState,
    InspectionTemplate,
    DEFAULT_INSPECTION_TEMPLATE,
    QUICK_CHECK_TEMPLATE,
)
from rds_agent.diagnostic.agent import DiagnosticAgent, get_diagnostic_agent
from rds_agent.diagnostic.nodes import (
    initialize_diagnostic,
    connect_instance,
    run_checks,
    analyze_results,
    generate_report,
)
from rds_agent.diagnostic.checks import (
    BaseCheck,
    CHECK_REGISTRY,
    get_check_class,
    InstanceRunningCheck,
    ConnectionCountCheck,
    BufferPoolHitRateCheck,
    SlowQueryCountCheck,
    StorageCapacityCheck,
    FragmentationCheck,
)
from rds_agent.diagnostic.report_generator import (
    DiagnosticReportGenerator,
    get_report_generator,
)
from rds_agent.diagnostic.parameter_optimizer import (
    ParameterOptimizer,
    analyze_parameter_optimization,
    get_parameter_recommendations,
    PARAMETER_OPTIMIZATION_RULES,
)

__all__ = [
    # 状态和类型
    "DiagnosticType",
    "HealthStatus",
    "CheckCategory",
    "CheckItem",
    "DiagnosticResult",
    "DiagnosticState",
    "InspectionTemplate",
    "DEFAULT_INSPECTION_TEMPLATE",
    "QUICK_CHECK_TEMPLATE",
    # Agent
    "DiagnosticAgent",
    "get_diagnostic_agent",
    # 节点
    "initialize_diagnostic",
    "connect_instance",
    "run_checks",
    "analyze_results",
    "generate_report",
    # 检查项
    "BaseCheck",
    "CHECK_REGISTRY",
    "get_check_class",
    "InstanceRunningCheck",
    "ConnectionCountCheck",
    "BufferPoolHitRateCheck",
    "SlowQueryCountCheck",
    "StorageCapacityCheck",
    "FragmentationCheck",
    # 报告
    "DiagnosticReportGenerator",
    "get_report_generator",
    # 参数优化
    "ParameterOptimizer",
    "analyze_parameter_optimization",
    "get_parameter_recommendations",
    "PARAMETER_OPTIMIZATION_RULES",
]