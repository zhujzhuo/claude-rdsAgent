#!/usr/bin/env python
"""测试运行脚本。"""

import subprocess
import sys
from pathlib import Path


def run_tests(test_type: str = "all", verbose: bool = True):
    """运行测试"""
    project_root = Path(__file__).parent.parent

    cmd = ["pytest"]

    # 测试类型
    if test_type == "unit":
        cmd.extend(["-m", "unit", "tests/test_tools/", "tests/test_agent/"])
    elif test_type == "integration":
        cmd.extend(["-m", "integration", "tests/test_integration.py"])
    elif test_type == "tools":
        cmd.append("tests/test_tools/")
    elif test_type == "agent":
        cmd.append("tests/test_agent/")
    else:
        cmd.append("tests/")

    # 详细输出
    if verbose:
        cmd.append("-v")

    # 覆盖率
    cmd.extend([
        "--cov=src/rds_agent",
        "--cov-report=term-missing",
        "--cov-report=html:htmlcov",
    ])

    print(f"运行命令: {' '.join(cmd)}")
    print("=" * 60)

    result = subprocess.run(cmd, cwd=project_root)
    return result.returncode


def main():
    """主入口"""
    import argparse

    parser = argparse.ArgumentParser(description="运行RDS Agent测试")
    parser.add_argument(
        "--type",
        choices=["all", "unit", "integration", "tools", "agent"],
        default="all",
        help="测试类型"
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="安静模式"
    )

    args = parser.parse_args()

    exit_code = run_tests(args.type, not args.quiet)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()