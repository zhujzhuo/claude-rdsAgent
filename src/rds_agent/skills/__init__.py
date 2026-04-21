"""Skills/SOP 模块 - 标准化诊断流程执行框架。

该模块提供基于 SOP（标准操作流程）的精确诊断能力，
解决大模型自主规划的因果颠倒问题。

支持两种定义方式：
1. Python 文件定义 (cpu_skill.py 等)
2. Markdown 文档定义 (docs/cpu_analysis.md 等)
"""

from .base import (
    SkillType,
    StepStatus,
    StepResult,
    SOPStep,
    SOP,
    SkillState,
    BaseSkill,
)
from .executor import SkillExecutor, get_skill_executor
from .parser import (
    MarkdownSkillParser,
    MarkdownSkill,
    SkillGenerator,
    get_skill_generator,
    generate_skill_from_markdown,
    generate_all_markdown_skills,
)

# Python 定义 Skills
from .cpu_skill import CPUAnalysisSkill
from .storage_skill import StorageAnalysisSkill
from .sql_skill import SQLOptimizationSkill
from .connection_skill import ConnectionAnalysisSkill

__all__ = [
    # Base classes
    "SkillType",
    "StepStatus",
    "StepResult",
    "SOPStep",
    "SOP",
    "SkillState",
    "BaseSkill",
    # Executor
    "SkillExecutor",
    "get_skill_executor",
    # Markdown parser
    "MarkdownSkillParser",
    "MarkdownSkill",
    "SkillGenerator",
    "get_skill_generator",
    "generate_skill_from_markdown",
    "generate_all_markdown_skills",
    # Python Skills
    "CPUAnalysisSkill",
    "StorageAnalysisSkill",
    "SQLOptimizationSkill",
    "ConnectionAnalysisSkill",
]