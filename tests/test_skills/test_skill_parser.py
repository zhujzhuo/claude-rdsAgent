"""Skills/SOP Markdown 解析器和生成器测试"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from rds_agent.skills.parser import (
    MarkdownSkillParser,
    MarkdownSkill,
    SkillGenerator,
)
from rds_agent.skills.base import SkillType, SOP, SOPStep


class TestMarkdownSkillParser:
    """Markdown Skill 解析器测试"""

    def test_parser_init(self):
        """测试解析器初始化"""
        parser = MarkdownSkillParser()
        assert parser.skills_dir is not None

    def test_parse_front_matter(self):
        """测试 YAML Front Matter 解析"""
        parser = MarkdownSkillParser()

        content = """---
name: cpu_analysis
skill_type: CPU_ANALYSIS
description: CPU 使用率分析
version: 1.0
---

# CPU 分析
"""
        metadata = parser._parse_front_matter(content)

        assert metadata["name"] == "cpu_analysis"
        assert metadata["skill_type"] == "CPU_ANALYSIS"
        assert metadata["description"] == "CPU 使用率分析"
        assert metadata["version"] == "1.0"

    def test_parse_params(self):
        """测试参数解析"""
        parser = MarkdownSkillParser()

        params_str = "instance_name=$instance_name, metric_type=cpu_usage, time_range=1h"
        params = parser._parse_params(params_str)

        assert params["instance_name"] == "$instance_name"
        assert params["metric_type"] == "cpu_usage"
        assert params["time_range"] == "1h"

    def test_parse_dependencies(self):
        """测试依赖解析"""
        parser = MarkdownSkillParser()

        deps_str = "1,2,3"
        deps = parser._parse_dependencies(deps_str)

        assert len(deps) == 3
        assert "step_1" in deps

    def test_parse_action(self):
        """测试动作解析"""
        parser = MarkdownSkillParser()

        action_str = "skip_steps=[3,5], end_analysis=true"
        action = parser._parse_action(action_str)

        assert action["skip_steps"] == [3, 5]
        assert action["end_analysis"] == True

    def test_build_sop(self):
        """测试 SOP 构建"""
        parser = MarkdownSkillParser()

        parsed_data = {
            "metadata": {
                "name": "test_skill",
                "skill_type": "CPU_ANALYSIS",
                "description": "测试 Skill",
                "version": "1.0",
            },
            "steps": [],
            "decision_points": {},
            "conclusion_template": "",
        }

        sop = parser.build_sop(parsed_data)

        assert sop.name == "test_skill"
        assert sop.skill_type == SkillType.CPU_ANALYSIS

    def test_list_skill_files(self):
        """测试列出 Skill 文件"""
        parser = MarkdownSkillParser()
        files = parser.list_skill_files()

        # 应该找到 README.md 和 cpu_analysis.md
        assert len(files) >= 1


class TestSkillGenerator:
    """Skill 生成器测试"""

    def test_generator_init(self):
        """测试生成器初始化"""
        generator = SkillGenerator()
        assert generator.skills_dir is not None

    def test_list_available_skills(self):
        """测试列出可用 Skills"""
        generator = SkillGenerator()
        skills = generator.list_available_skills()

        assert len(skills) >= 1
        assert "cpu_analysis.md" in skills

    def test_create_skill_template(self):
        """测试创建 Skill 模板"""
        generator = SkillGenerator()

        template = generator.create_skill_template(
            "test_skill", "PERFORMANCE_ANALYSIS"
        )

        assert "---" in template
        assert "name: test_skill" in template
        assert "skill_type: PERFORMANCE_ANALYSIS" in template
        assert "## SOP 步骤" in template
        assert "## 决策点" in template

    def test_generate_all(self):
        """测试生成所有 Skills"""
        generator = SkillGenerator()
        skills = generator.generate_all()

        # 至少应该生成 CPU Skill
        assert len(skills) >= 1
        assert SkillType.CPU_ANALYSIS in skills


class TestMarkdownSkill:
    """Markdown Skill 测试"""

    def test_skill_from_markdown(self):
        """测试从 Markdown 创建 Skill"""
        skills_dir = Path(__file__).parent.parent.parent / "src" / "rds_agent" / "skills" / "docs"
        cpu_md = skills_dir / "cpu_analysis.md"

        if not cpu_md.exists():
            pytest.skip("CPU analysis markdown file not found")

        skill = MarkdownSkill(str(cpu_md))

        assert skill.skill_type == SkillType.CPU_ANALYSIS
        assert skill.sop.name == "cpu_analysis"
        assert len(skill.sop.steps) == 9

    def test_skill_get_sop(self):
        """测试获取 SOP"""
        skills_dir = Path(__file__).parent.parent.parent / "src" / "rds_agent" / "skills" / "docs"
        cpu_md = skills_dir / "cpu_analysis.md"

        if not cpu_md.exists():
            pytest.skip("CPU analysis markdown file not found")

        skill = MarkdownSkill(str(cpu_md))
        sop = skill.get_sop()

        assert sop.skill_type == SkillType.CPU_ANALYSIS
        assert len(sop.steps) == 9

    def test_skill_decision_points(self):
        """测试决策点"""
        skills_dir = Path(__file__).parent.parent.parent / "src" / "rds_agent" / "skills" / "docs"
        cpu_md = skills_dir / "cpu_analysis.md"

        if not cpu_md.exists():
            pytest.skip("CPU analysis markdown file not found")

        skill = MarkdownSkill(str(cpu_md))

        assert "check_session_change" in skill.sop.decision_points
        assert "session_spike" in skill.sop.decision_points["check_session_change"]


class TestEvaluateTemplateCondition:
    """模板条件评估测试"""

    def test_greater_than(self):
        """测试大于条件"""
        parser = MarkdownSkillParser()
        result = parser._evaluate_template_condition("cpu_usage > 90", {"cpu_usage": 95})
        assert result == True

        result = parser._evaluate_template_condition("cpu_usage > 90", {"cpu_usage": 85})
        assert result == False

    def test_less_than(self):
        """测试小于条件"""
        parser = MarkdownSkillParser()
        result = parser._evaluate_template_condition("hit_rate < 90", {"hit_rate": 85})
        assert result == True

        result = parser._evaluate_template_condition("hit_rate < 90", {"hit_rate": 95})
        assert result == False


class TestFormatOutput:
    """输出格式化测试"""

    def test_format_output(self):
        """测试格式化输出"""
        parser = MarkdownSkillParser()

        template = "CPU 使用率：{cpu_usage}%，高峰时段：{peak_time}"
        output = {"cpu_usage": 95, "peak_time": "10:30"}

        result = parser._format_output(template, output)
        assert result == "CPU 使用率：95%，高峰时段：10:30"