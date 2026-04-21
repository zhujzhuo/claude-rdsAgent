"""Skills/SOP 文档解析器 - 从 Markdown 文档生成 Skill 定义"""

import os
import re
import yaml
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

from rds_agent.skills.base import (
    BaseSkill,
    SkillState,
    SkillType,
    SOP,
    SOPStep,
    StepStatus,
    StepResult,
)
from rds_agent.utils.logger import get_logger

logger = get_logger("skill_parser")


class MarkdownSkillParser:
    """Markdown Skill 文档解析器

    解析格式:
    - YAML Front Matter: 元数据
    - SOP 步骤表格: 步骤定义
    - 决策点表格: 决策规则
    - 分析模板: 分析逻辑
    - 优化建议: 建议模板

    示例文档见 skills/docs/cpu_analysis.md
    """

    def __init__(self):
        """初始化解析器"""
        self.skills_dir = Path(__file__).parent / "docs"

    def parse_file(self, file_path: str) -> Dict[str, Any]:
        """解析 Skill Markdown 文件

        Args:
            file_path: Markdown 文件路径

        Returns:
            解析结果字典，包含 metadata, steps, decision_points, analysis_templates, recommendations
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Skill 文件不存在: {file_path}")

        content = path.read_text(encoding="utf-8")

        # 解析各部分
        result = {
            "metadata": self._parse_front_matter(content),
            "steps": self._parse_sop_steps(content),
            "decision_points": self._parse_decision_points(content),
            "analysis_templates": self._parse_analysis_templates(content),
            "recommendations": self._parse_recommendations(content),
            "conclusion_template": self._parse_conclusion_template(content),
        }

        logger.info(f"解析 Skill 文件: {file_path}")
        return result

    def _parse_front_matter(self, content: str) -> Dict[str, Any]:
        """解析 YAML Front Matter

        Args:
            content: 文件内容

        Returns:
            元数据字典
        """
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
        if match:
            yaml_content = match.group(1)
            try:
                metadata = yaml.safe_load(yaml_content)
                return metadata or {}
            except yaml.YAMLError as e:
                logger.warning(f"YAML 解析错误: {e}")
                return {}

        return {}

    def _parse_sop_steps(self, content: str) -> List[Dict[str, Any]]:
        """解析 SOP 步骤表格

        Args:
            content: 文件内容

        Returns:
            步骤列表
        """
        steps = []

        # 匹配 SOP 步骤表格
        pattern = r"## SOP 步骤\s*\n\n.*?\n\|.*?\n\|.*?\n((?:\|.*?\n)+)"
        match = re.search(pattern, content, re.DOTALL)

        if not match:
            # 尝试另一种格式
            pattern = r"## SOP 步骤\s*\n\n((?:\|.*?\n)+)"
            match = re.search(pattern, content, re.DOTALL)

        if match:
            table_content = match.group(1)
            rows = table_content.strip().split("\n")

            for row in rows:
                if row.startswith("|"):
                    cells = [c.strip() for c in row.split("|")[1:-1]]
                    if len(cells) >= 6 and cells[0].isdigit():
                        step = {
                            "sequence": int(cells[0]),
                            "name": cells[1],
                            "tool_name": cells[2],
                            "tool_params": self._parse_params(cells[3]),
                            "condition": cells[4] if cells[4] != "-" else None,
                            "dependencies": self._parse_dependencies(cells[5]),
                            "analysis_prompt": cells[6] if len(cells) > 6 else "",
                            "timeout": int(cells[7].replace("s", "")) if len(cells) > 7 and cells[7] else 30,
                        }
                        steps.append(step)

        return steps

    def _parse_params(self, params_str: str) -> Dict[str, Any]:
        """解析参数字符串

        Args:
            params_str: 参数字符串，如 "instance_name=$instance_name, metric_type=cpu_usage"

        Returns:
            参数字典
        """
        params = {}
        if params_str and params_str != "-":
            for part in params_str.split(","):
                if "=" in part:
                    key, value = part.split("=", 1)
                    key = key.strip()
                    value = value.strip()
                    # 处理 $变量引用
                    if value.startswith("$"):
                        params[key] = value
                    else:
                        params[key] = value

        return params

    def _parse_dependencies(self, deps_str: str) -> List[str]:
        """解析依赖字符串

        Args:
            deps_str: 依赖字符串，如 "1,2,3" 或步骤名列表

        Returns:
            依赖列表（步骤名）
        """
        if deps_str and deps_str != "-":
            # 数字序列号需要转换为步骤名
            deps = []
            for part in deps_str.split(","):
                part = part.strip()
                if part.isdigit():
                    # 序列号，暂时保留
                    deps.append(f"step_{part}")
                else:
                    deps.append(part)
            return deps

        return []

    def _parse_decision_points(self, content: str) -> Dict[str, Dict[str, Any]]:
        """解析决策点定义

        Args:
            content: 文件内容

        Returns:
            决策点字典
        """
        decision_points = {}

        # 匹配决策点部分
        pattern = r"## 决策点\s*\n\n((?:###.*?\n(?:\|.*?\n)+)+)"
        match = re.search(pattern, content, re.DOTALL)

        if match:
            decision_section = match.group(1)

            # 解析每个决策点
            dp_pattern = r"### (\w+).*?\n(?:\|.*?\n)*\|.*?\n\|.*?\n((?:\|.*?\n)+)"
            dp_matches = re.finditer(dp_pattern, decision_section, re.DOTALL)

            for dp_match in dp_matches:
                dp_name = dp_match.group(1)
                table_content = dp_match.group(2)

                rules = {}
                rows = table_content.strip().split("\n")

                for row in rows:
                    if row.startswith("|"):
                        cells = [c.strip() for c in row.split("|")[1:-1]]
                        if len(cells) >= 2 and cells[0] != "规则名":
                            rule = {
                                "condition": cells[1] if cells[1] != "-" else None,
                                "root_cause": cells[2] if len(cells) > 2 and cells[2] != "-" else None,
                                "action": self._parse_action(cells[3]) if len(cells) > 3 else None,
                            }
                            rules[cells[0]] = rule

                if rules:
                    decision_points[dp_name] = rules

        return decision_points

    def _parse_action(self, action_str: str) -> Dict[str, Any]:
        """解析动作字符串

        Args:
            action_str: 动作字符串，如 "skip_steps=[3,5], end_analysis=true"

        Returns:
            动作字典
        """
        action = {}
        if action_str and action_str != "-":
            for part in action_str.split(","):
                if "=" in part:
                    key, value = part.split("=", 1)
                    key = key.strip()
                    value = value.strip()

                    # 解析数组
                    if value.startswith("[") and value.endswith("]"):
                        value = [int(v.strip()) for v in value[1:-1].split(",")]
                    elif value == "true":
                        value = True
                    elif value == "false":
                        value = False

                    action[key] = value

        return action

    def _parse_analysis_templates(self, content: str) -> Dict[str, Any]:
        """解析分析模板

        Args:
            content: 文件内容

        Returns:
            分析模板字典
        """
        templates = {}

        # 匹配分析模板部分
        pattern = r"## 分析模板\s*\n\n((?:###.*?\n(?:```.*?```|.*?\n)+)+)"
        match = re.search(pattern, content, re.DOTALL)

        if match:
            template_section = match.group(1)

            # 解析每个模板
            tmpl_pattern = r"### (\w+).*?\n```(.*?)```"
            tmpl_matches = re.finditer(tmpl_pattern, template_section, re.DOTALL)

            for tmpl_match in tmpl_matches:
                tmpl_name = tmpl_match.group(1)
                tmpl_content = tmpl_match.group(2)
                templates[tmpl_name] = tmpl_content.strip()

        return templates

    def _parse_recommendations(self, content: str) -> Dict[str, List[str]]:
        """解析优化建议

        Args:
            content: 文件内容

        Returns:
            建议字典
        """
        recommendations = {}

        # 匹配优化建议部分
        pattern = r"## 优化建议\s*\n\n((?:###.*?\n(?:-.*?\n)+)+)"
        match = re.search(pattern, content, re.DOTALL)

        if match:
            rec_section = match.group(1)

            # 解析每个建议类别
            rec_pattern = r"### ([\w\s]+).*?\n((?:-.*?\n)+)"
            rec_matches = re.finditer(rec_pattern, rec_section, re.DOTALL)

            for rec_match in rec_matches:
                category = rec_match.group(1).strip()
                items_content = rec_match.group(2)

                items = []
                for line in items_content.split("\n"):
                    if line.startswith("-"):
                        items.append(line[1:].strip())

                if items:
                    recommendations[category] = items

        return recommendations

    def _parse_conclusion_template(self, content: str) -> str:
        """解析结论模板

        Args:
            content: 文件内容

        Returns:
            结论模板字符串
        """
        pattern = r"## 结论模板\s*\n\n```markdown\n(.*?)\n```"
        match = re.search(pattern, content, re.DOTALL)

        if match:
            return match.group(1).strip()

        return ""

    def build_sop(self, parsed_data: Dict[str, Any]) -> SOP:
        """从解析数据构建 SOP 对象

        Args:
            parsed_data: 解析后的数据

        Returns:
            SOP 对象
        """
        metadata = parsed_data.get("metadata", {})
        steps_data = parsed_data.get("steps", [])

        # 构建步骤
        steps = []
        for step_data in steps_data:
            step = SOPStep(
                name=step_data["name"],
                description=step_data.get("analysis_prompt", ""),
                tool_name=step_data["tool_name"],
                tool_params=step_data["tool_params"],
                condition=step_data.get("condition"),
                dependencies=step_data.get("dependencies", []),
                analysis_prompt=step_data.get("analysis_prompt", ""),
                timeout=step_data.get("timeout", 30),
            )
            steps.append(step)

        # 构建 SOP
        skill_type_str = metadata.get("skill_type", "PERFORMANCE_ANALYSIS")
        skill_type = SkillType(skill_type_str) if skill_type_str in [e.value for e in SkillType] else SkillType.PERFORMANCE_ANALYSIS

        sop = SOP(
            name=metadata.get("name", "unknown"),
            skill_type=skill_type,
            description=metadata.get("description", ""),
            version=metadata.get("version", "1.0"),
            steps=steps,
            decision_points=parsed_data.get("decision_points", {}),
            conclusion_template=parsed_data.get("conclusion_template", ""),
        )

        return sop

    def list_skill_files(self) -> List[Path]:
        """列出所有 Skill Markdown 文件

        Returns:
            文件路径列表
        """
        if not self.skills_dir.exists():
            return []

        return list(self.skills_dir.glob("*.md"))


class MarkdownSkill(BaseSkill):
    """基于 Markdown 文档生成的 Skill

    从 Markdown 文件动态生成 Skill 定义
    """

    def __init__(
        self,
        markdown_path: str,
        mysql_client=None,
        tools_registry: Dict[str, Callable] = None,
    ):
        """初始化 Markdown Skill

        Args:
            markdown_path: Markdown 文档路径
            mysql_client: MySQL 客户端
            tools_registry: 工具注册表
        """
        self.markdown_path = markdown_path
        self.parser = MarkdownSkillParser()

        # 解析文档
        parsed_data = self.parser.parse_file(markdown_path)
        self._parsed_data = parsed_data

        # 构建 SOP
        self.sop = self.parser.build_sop(parsed_data)

        # 设置 skill_type
        self.skill_type = self.sop.skill_type

        # 初始化基类
        super().__init__(mysql_client, tools_registry)

        # 存储分析模板和建议
        self._analysis_templates = parsed_data.get("analysis_templates", {})
        self._recommendations = parsed_data.get("recommendations", {})

    def get_sop(self) -> SOP:
        """获取 SOP"""
        return self.sop

    def _analyze_output(self, step: SOPStep, output: Any) -> str:
        """分析步骤输出

        Args:
            step: SOP 步骤
            output: 输出数据

        Returns:
            分析结果
        """
        # 检查是否有预定义模板
        template = self._analysis_templates.get(step.name)

        if template:
            return self._apply_template(template, output)

        # 默认分析
        return self._default_analysis(step.name, output)

    def _apply_template(self, template: str, output: Any) -> str:
        """应用分析模板

        Args:
            template: 模板字符串
            output: 输出数据

        Returns:
            分析结果
        """
        if not isinstance(output, dict):
            return f"输出数据：{str(output)[:100]}"

        # 解析模板中的条件分支
        lines = template.split("\n")
        result = ""

        for line in lines:
            # 条件判断
            if ":" in line and not line.startswith("-"):
                # 格式: "condition: output_template"
                parts = line.split(":", 1)
                condition_str = parts[0].strip()
                output_template = parts[1].strip() if len(parts) > 1 else ""

                if self._evaluate_template_condition(condition_str, output):
                    result = output_template
                    # 替换变量
                    result = self._format_output(result, output)
                    break

        if not result:
            result = f"分析结果：{str(output)[:100]}"

        return result

    def _evaluate_template_condition(self, condition: str, output: Dict) -> bool:
        """评估模板条件

        Args:
            condition: 条件字符串，如 "cpu_usage > 90"
            output: 输出数据

        Returns:
            是否满足条件
        """
        # 提取变量名和阈值
        match = re.match(r"(\w+)\s*([><=!]+)\s*(\d+)", condition)
        if match:
            var_name = match.group(1)
            operator = match.group(2)
            threshold = float(match.group(3))

            value = output.get(var_name, 0)

            if operator == ">":
                return value > threshold
            elif operator == ">=":
                return value >= threshold
            elif operator == "<":
                return value < threshold
            elif operator == "<=":
                return value <= threshold
            elif operator == "==":
                return value == threshold

        return False

    def _format_output(self, template: str, output: Dict) -> str:
        """格式化输出

        Args:
            template: 模板字符串
            output: 输出数据

        Returns:
            格式化后的字符串
        """
        # 替换 {变量}
        for key, value in output.items():
            template = template.replace(f"{{{key}}}", str(value))

        return template

    def _default_analysis(self, step_name: str, output: Any) -> str:
        """默认分析"""
        if isinstance(output, dict):
            # 提取关键指标
            key_values = []
            for key, value in output.items():
                if isinstance(value, (int, float, str)):
                    key_values.append(f"{key}={value}")

            return f"{step_name}: {', '.join(key_values[:3])}"

        return f"{step_name}: {str(output)[:100]}"

    def _generate_recommendations(self) -> List[str]:
        """生成优化建议"""
        root_cause = self.state.get("root_cause", "")

        recommendations = []

        # 根据根因匹配建议
        for category, items in self._recommendations.items():
            if root_cause and category.lower() in root_cause.lower():
                recommendations.extend(items)

        # 添加通用建议
        if "通用建议" in self._recommendations:
            recommendations.extend(self._recommendations["通用建议"])

        # 如果没有匹配，添加默认建议
        if not recommendations:
            recommendations.append("持续监控相关指标")
            if root_cause:
                recommendations.append(f"针对根因({root_cause})制定优化方案")

        return recommendations


class SkillGenerator:
    """Skill 生成器 - 从 Markdown 文档动态生成并注册 Skill"""

    def __init__(self, skills_dir: Optional[str] = None):
        """初始化生成器

        Args:
            skills_dir: Skills 文档目录路径
        """
        self.skills_dir = Path(skills_dir) if skills_dir else Path(__file__).parent / "docs"
        self.parser = MarkdownSkillParser()
        self._generated_skills: Dict[SkillType, MarkdownSkill] = {}

    def generate_skill(self, markdown_path: str) -> MarkdownSkill:
        """从 Markdown 文件生成 Skill

        Args:
            markdown_path: Markdown 文件路径

        Returns:
            MarkdownSkill 实例
        """
        skill = MarkdownSkill(markdown_path)
        skill_type = skill.skill_type
        self._generated_skills[skill_type] = skill

        logger.info(f"生成 Skill: {skill_type.value} from {markdown_path}")
        return skill

    def generate_all(self) -> Dict[SkillType, MarkdownSkill]:
        """生成所有 Markdown Skill

        Returns:
            Skill 字典
        """
        skill_files = self.parser.list_skill_files()

        for file_path in skill_files:
            if file_path.name != "README.md":
                try:
                    self.generate_skill(str(file_path))
                except Exception as e:
                    logger.error(f"生成 Skill 失败: {file_path} - {e}")

        return self._generated_skills

    def get_skill(self, skill_type: SkillType) -> Optional[MarkdownSkill]:
        """获取生成的 Skill

        Args:
            skill_type: Skill 类型

        Returns:
            MarkdownSkill 实例
        """
        return self._generated_skills.get(skill_type)

    def list_available_skills(self) -> List[str]:
        """列出可用的 Skill 文件名

        Returns:
            文件名列表
        """
        skill_files = self.parser.list_skill_files()
        return [f.name for f in skill_files if f.name != "README.md"]

    def create_skill_template(self, skill_name: str, skill_type: str) -> str:
        """创建 Skill 文档模板

        Args:
            skill_name: Skill 名称
            skill_type: Skill 类型

        Returns:
            模板内容
        """
        template = f'''---
name: {skill_name}
skill_type: {skill_type}
description: {skill_name} 标准化诊断流程
version: 1.0
author: system
tags: [{skill_type.lower()}]
---

# {skill_name} Skill

标准化诊断流程说明。

## SOP 步骤

| 序号 | 名称 | 工具 | 参数 | 条件 | 依赖 | 分析说明 | 超时 |
|------|------|------|------|------|------|----------|------|
| 1 | step1 | tool_name | param=value | - | - | 步骤描述 | 30s |
| 2 | step2 | tool_name | param=$var | - | 1 | 步骤描述 | 30s |

## 决策点

### step2

| 规则名 | 条件 | 根因 | 动作 |
|--------|------|------|------|
| rule1 | `$value > threshold` | 根因描述 | skip_steps=[3] |
| rule2 | `$value <= threshold` | - | continue |

## 分析模板

### step1

```
输入: {value}

条件分支:
  - value > threshold: "描述: {value}"
  - value <= threshold: "描述: {value}"
```

## 优化建议

### 类别1

- 建议1
- 建议2

### 通用建议

- 持续监控
- 定期巡检

## 结论模板

```markdown
## 分析报告

**实例**: {instance_name}

### 根因定位
{root_cause}

### 关键发现
{key_findings}

### 优化建议
{recommendations}
```
'''
        return template

    def write_skill_template(self, skill_name: str, skill_type: str) -> Path:
        """写入 Skill 模板文件

        Args:
            skill_name: Skill 名称
            skill_type: Skill 类型

        Returns:
            文件路径
        """
        template = self.create_skill_template(skill_name, skill_type)
        file_path = self.skills_dir / f"{skill_name}.md"

        file_path.write_text(template, encoding="utf-8")
        logger.info(f"创建 Skill 模板: {file_path}")

        return file_path


# 全局生成器
_skill_generator: Optional[SkillGenerator] = None


def get_skill_generator(skills_dir: Optional[str] = None) -> SkillGenerator:
    """获取 Skill 生成器单例"""
    global _skill_generator
    if _skill_generator is None:
        _skill_generator = SkillGenerator(skills_dir)
    return _skill_generator


def generate_skill_from_markdown(markdown_path: str) -> MarkdownSkill:
    """从 Markdown 文件生成 Skill"""
    generator = get_skill_generator()
    return generator.generate_skill(markdown_path)


def generate_all_markdown_skills() -> Dict[SkillType, MarkdownSkill]:
    """生成所有 Markdown Skill"""
    generator = get_skill_generator()
    return generator.generate_all()