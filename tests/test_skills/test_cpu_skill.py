"""CPU 分析 Skill 测试"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from rds_agent.skills.base import (
    SkillType,
    StepStatus,
    SOPStep,
    SOP,
    BaseSkill,
    SkillState,
)
from rds_agent.skills.cpu_skill import CPUAnalysisSkill, CPU_ANALYSIS_SOP
from rds_agent.skills.executor import SkillExecutor, get_skill_executor


class TestCPUAnalysisSOP:
    """CPU 分析 SOP 定义测试"""

    def test_sop_name(self):
        """测试 SOP 名称"""
        assert CPU_ANALYSIS_SOP.name == "cpu_analysis_sop"

    def test_sop_skill_type(self):
        """测试 SOP 类型"""
        assert CPU_ANALYSIS_SOP.skill_type == SkillType.CPU_ANALYSIS

    def test_sop_steps_count(self):
        """测试 SOP 步骤数量"""
        assert len(CPU_ANALYSIS_SOP.steps) == 9

    def test_sop_first_step(self):
        """测试第一个步骤"""
        first_step = CPU_ANALYSIS_SOP.steps[0]
        assert first_step.name == "get_monitoring_data"
        assert first_step.tool_name == "get_monitoring_data"

    def test_sop_decision_points(self):
        """测试决策点"""
        assert "check_session_change" in CPU_ANALYSIS_SOP.decision_points
        assert "session_spike" in CPU_ANALYSIS_SOP.decision_points["check_session_change"]

    def test_step_build_params(self):
        """测试步骤参数构建"""
        step = SOPStep(
            name="test_step",
            tool_name="test_tool",
            tool_params={
                "instance_name": "$instance_name",
                "time_range": "1h",
            }
        )

        context = {"instance_name": "db-prod-01"}
        params = step.build_params(context)

        assert params["instance_name"] == "db-prod-01"
        assert params["time_range"] == "1h"


class TestCPUAnalysisSkill:
    """CPU 分析 Skill 测试"""

    def test_skill_type(self):
        """测试 Skill 类型"""
        skill = CPUAnalysisSkill()
        assert skill.skill_type == SkillType.CPU_ANALYSIS

    def test_get_sop(self):
        """测试获取 SOP"""
        skill = CPUAnalysisSkill()
        sop = skill.get_sop()
        assert sop.name == "cpu_analysis_sop"

    def test_analyze_monitoring_data_high(self):
        """测试 CPU 监控数据分析 - 高使用率"""
        skill = CPUAnalysisSkill()
        step = CPU_ANALYSIS_SOP.steps[0]

        output = {"cpu_usage": 95, "peak_time": "10:30"}
        analysis = skill._analyze_output(step, output)

        assert "严重过高" in analysis
        assert "95" in analysis

    def test_analyze_monitoring_data_normal(self):
        """测试 CPU 监控数据分析 - 正常"""
        skill = CPUAnalysisSkill()
        step = CPU_ANALYSIS_SOP.steps[0]

        output = {"cpu_usage": 50, "peak_time": "10:30"}
        analysis = skill._analyze_output(step, output)

        assert "正常" in analysis

    def test_analyze_session_change_spike(self):
        """测试会话变化分析 - 突增"""
        skill = CPUAnalysisSkill()
        skill.state = {
            "context": {},
            "step_results": [],
        }
        step = CPU_ANALYSIS_SOP.steps[1]

        output = {
            "current_sessions": 200,
            "avg_sessions": 100,
            "change_rate": 100,
        }
        analysis = skill._analyze_output(step, output)

        assert "突增" in analysis
        # 检查上下文是否更新
        assert skill.state["context"]["session_change_rate"] == 100

    def test_analyze_session_change_stable(self):
        """测试会话变化分析 - 稳定"""
        skill = CPUAnalysisSkill()
        skill.state = {
            "context": {},
            "step_results": [],
        }
        step = CPU_ANALYSIS_SOP.steps[1]

        output = {
            "current_sessions": 105,
            "avg_sessions": 100,
            "change_rate": 5,
        }
        analysis = skill._analyze_output(step, output)

        assert "稳定" in analysis

    def test_analyze_slow_queries_found(self):
        """测试慢 SQL 分析 - 有慢 SQL"""
        skill = CPUAnalysisSkill()
        skill.state = {"context": {}}
        step = CPU_ANALYSIS_SOP.steps[3]

        output = {"count": 10, "slow_queries": [], "sql_patterns": ["SELECT * FROM users"]}
        analysis = skill._analyze_output(step, output)

        assert "10" in analysis

    def test_analyze_slow_queries_none(self):
        """测试慢 SQL 分析 - 无慢 SQL"""
        skill = CPUAnalysisSkill()
        skill.state = {"context": {}}
        step = CPU_ANALYSIS_SOP.steps[3]

        output = {"count": 0, "slow_queries": []}
        analysis = skill._analyze_output(step, output)

        assert "未发现" in analysis

    def test_generate_recommendations_session_spike(self):
        """测试生成建议 - 会话突增"""
        skill = CPUAnalysisSkill()
        skill.state = {
            "root_cause": "业务突增导致会话激增",
            "context": {},
        }

        recommendations = skill._generate_recommendations()

        assert any("扩容" in rec for rec in recommendations)
        assert any("连接池" in rec for rec in recommendations)

    def test_generate_recommendations_sql_issue(self):
        """测试生成建议 - SQL 问题"""
        skill = CPUAnalysisSkill()
        skill.state = {
            "root_cause": "慢 SQL 导致 CPU 升高",
            "context": {},
        }

        recommendations = skill._generate_recommendations()

        assert any("索引" in rec for rec in recommendations)


class TestSkillExecutor:
    """Skill 执行器测试"""

    def test_executor_init(self):
        """测试执行器初始化"""
        executor = SkillExecutor()
        assert executor is not None

    def test_executor_list_skills(self):
        """测试列出已注册 Skill"""
        executor = SkillExecutor()
        skills = executor.list_skills()
        # CPU Skill 应该被自动注册
        assert SkillType.CPU_ANALYSIS in skills

    def test_executor_has_skill(self):
        """测试检查 Skill 是否注册"""
        executor = SkillExecutor()
        assert executor.has_skill(SkillType.CPU_ANALYSIS)

    def test_executor_get_skill(self):
        """测试获取 Skill"""
        executor = SkillExecutor()
        skill = executor.get_skill(SkillType.CPU_ANALYSIS)
        assert skill is not None
        assert isinstance(skill, CPUAnalysisSkill)


class TestGetSkillExecutor:
    """get_skill_executor 函数测试"""

    def test_get_skill_executor_singleton(self):
        """测试单例模式"""
        # 重置全局实例
        import rds_agent.skills.executor as executor_module
        executor_module._skill_executor = None

        executor1 = get_skill_executor()
        executor2 = get_skill_executor()

        assert executor1 is executor2

    def test_create_skill_executor_new_instance(self):
        """测试创建新实例"""
        executor1 = SkillExecutor()
        executor2 = SkillExecutor()

        assert executor1 is not executor2