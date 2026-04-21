"""Skills 文档管理 CLI - 创建、生成和管理 Markdown Skill 文档"""

import argparse
import sys
from pathlib import Path

from rds_agent.skills.parser import (
    SkillGenerator,
    get_skill_generator,
    generate_all_markdown_skills,
)
from rds_agent.skills.base import SkillType


def create_skill(args):
    """创建 Skill 文档模板"""
    generator = get_skill_generator()

    skill_name = args.name
    skill_type = args.type

    # 验证 Skill 类型
    valid_types = [e.value for e in SkillType]
    if skill_type not in valid_types:
        print(f"错误: 无效的 Skill 类型 '{skill_type}'")
        print(f"有效类型: {', '.join(valid_types)}")
        return 1

    # 创建模板
    file_path = generator.write_skill_template(skill_name, skill_type)
    print(f"创建 Skill 模板: {file_path}")
    print(f"请编辑文件添加 SOP 步骤和分析模板")

    return 0


def list_skills(args):
    """列出所有 Skill 文档"""
    generator = get_skill_generator()

    skill_files = generator.list_available_skills()

    if not skill_files:
        print("未找到 Skill 文档")
        return 0

    print("Skill 文档列表:")
    for name in skill_files:
        print(f"  - {name}")

    return 0


def generate_skills(args):
    """生成所有 Markdown Skill"""
    print("正在生成 Skills...")

    skills = generate_all_markdown_skills()

    if not skills:
        print("未生成任何 Skill")
        return 0

    print(f"生成 {len(skills)} 个 Skill:")
    for skill_type, skill in skills.items():
        print(f"  - {skill_type.value}: {skill.sop.name} ({len(skill.sop.steps)} 步骤)")

    return 0


def validate_skill(args):
    """验证 Skill 文档"""
    generator = get_skill_generator()

    file_path = Path(args.file)

    if not file_path.exists():
        print(f"错误: 文件不存在 {file_path}")
        return 1

    try:
        skill = generator.generate_skill(str(file_path))
        print(f"验证成功: {skill.sop.name}")
        print(f"类型: {skill.skill_type.value}")
        print(f"步骤数: {len(skill.sop.steps)}")
        print(f"决策点: {len(skill.sop.decision_points)}")

        # 显示步骤
        print("\nSOP 步骤:")
        for i, step in enumerate(skill.sop.steps, 1):
            print(f"  {i}. {step.name} ({step.tool_name})")

        return 0
    except Exception as e:
        print(f"验证失败: {e}")
        return 1


def show_skill(args):
    """显示 Skill 详情"""
    generator = get_skill_generator()

    file_path = Path(args.file)

    if not file_path.exists():
        print(f"错误: 文件不存在 {file_path}")
        return 1

    try:
        skill = generator.generate_skill(str(file_path))

        print(f"=== Skill: {skill.sop.name} ===")
        print(f"类型: {skill.skill_type.value}")
        print(f"版本: {skill.sop.version}")
        print(f"描述: {skill.sop.description}")

        print("\n--- SOP 步骤 ---")
        for i, step in enumerate(skill.sop.steps, 1):
            print(f"\n步骤 {i}: {step.name}")
            print(f"  工具: {step.tool_name}")
            print(f"  参数: {step.tool_params}")
            if step.condition:
                print(f"  条件: {step.condition}")
            if step.dependencies:
                print(f"  依赖: {step.dependencies}")

        print("\n--- 决策点 ---")
        for dp_name, rules in skill.sop.decision_points.items():
            print(f"\n{dp_name}:")
            for rule_name, rule in rules.items():
                print(f"  {rule_name}:")
                if rule.get("condition"):
                    print(f"    条件: {rule['condition']}")
                if rule.get("root_cause"):
                    print(f"    根因: {rule['root_cause']}")

        return 0
    except Exception as e:
        print(f"错误: {e}")
        return 1


def main():
    """CLI 入口"""
    parser = argparse.ArgumentParser(
        description="Skills/SOP 文档管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # create 命令
    create_parser = subparsers.add_parser("create", help="创建 Skill 文档模板")
    create_parser.add_argument("name", help="Skill 名称")
    create_parser.add_argument(
        "-t", "--type",
        default="PERFORMANCE_ANALYSIS",
        help="Skill 类型 (默认: PERFORMANCE_ANALYSIS)"
    )
    create_parser.set_defaults(func=create_skill)

    # list 命令
    list_parser = subparsers.add_parser("list", help="列出所有 Skill 文档")
    list_parser.set_defaults(func=list_skills)

    # generate 命令
    generate_parser = subparsers.add_parser("generate", help="生成所有 Markdown Skill")
    generate_parser.set_defaults(func=generate_skills)

    # validate 命令
    validate_parser = subparsers.add_parser("validate", help="验证 Skill 文档")
    validate_parser.add_argument("file", help="Markdown 文件路径")
    validate_parser.set_defaults(func=validate_skill)

    # show 命令
    show_parser = subparsers.add_parser("show", help="显示 Skill 详情")
    show_parser.add_argument("file", help="Markdown 文件路径")
    show_parser.set_defaults(func=show_skill)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())