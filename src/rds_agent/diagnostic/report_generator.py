"""诊断报告生成器 - 生成结构化的诊断报告。"""

import json
from datetime import datetime
from typing import Optional
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress

from rds_agent.diagnostic.state import (
    DiagnosticResult,
    CheckItem,
    HealthStatus,
    CheckCategory,
)
from rds_agent.utils.logger import get_logger

logger = get_logger("report_generator")
console = Console()


class DiagnosticReportGenerator:
    """诊断报告生成器"""

    def __init__(self, output_dir: Optional[str] = None):
        """初始化报告生成器"""
        self.output_dir = Path(output_dir or "./reports")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_full_report(self, result: DiagnosticResult) -> str:
        """生成完整诊断报告"""
        report_lines = []

        # 标题
        report_lines.append(self._generate_header(result))

        # 概要信息
        report_lines.append(self._generate_summary(result))

        # 各类别详细检查结果
        report_lines.append(self._generate_category_details(result))

        # 问题汇总
        report_lines.append(self._generate_issues_summary(result))

        # 优化建议
        report_lines.append(self._generate_suggestions(result))

        # 结论
        report_lines.append(self._generate_conclusion(result))

        return "\n".join(report_lines)

    def _generate_header(self, result: DiagnosticResult) -> str:
        """生成报告标题"""
        header = f"""
================================================================================
                    MySQL实例诊断报告
================================================================================

实例名称: {result.instance_name}
诊断类型: {result.diagnostic_type}
诊断时间: {result.start_time.strftime('%Y-%m-%d %H:%M:%S')}
完成时间: {result.end_time.strftime('%Y-%m-%d %H:%M:%S') if result.end_time else '未完成'}
"""
        return header

    def _generate_summary(self, result: DiagnosticResult) -> str:
        """生成概要"""
        status_icon = {
            HealthStatus.HEALTHY: "✓",
            HealthStatus.WARNING: "⚠",
            HealthStatus.CRITICAL: "✗",
            HealthStatus.UNKNOWN: "?",
        }

        summary = f"""
--------------------------------------------------------------------------------
                            诊断概要
--------------------------------------------------------------------------------

整体状态: [{status_icon.get(result.overall_status, '?')}] {result.overall_status}
健康分数: {result.overall_score}/100

{result.summary}

检查项统计:
  - 总检查项: {len(result.check_items)}
  - 健康: {len([c for c in result.check_items if c.status == HealthStatus.HEALTHY])}
  - 警告: {len([c for c in result.check_items if c.status == HealthStatus.WARNING])}
  - 严重: {len([c for c in result.check_items if c.status == HealthStatus.CRITICAL])}
"""
        return summary

    def _generate_category_details(self, result: DiagnosticResult) -> str:
        """生成各类别详细结果"""
        details = "\n--------------------------------------------------------------------------------\n"
        details += "                            详细检查结果\n"
        details += "--------------------------------------------------------------------------------\n"

        # 按类别分组
        categories = {}
        for check in result.check_items:
            cat = check.category
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(check)

        for category, checks in categories.items():
            details += f"\n【{category.value}】\n"

            for check in checks:
                status_icon = {
                    HealthStatus.HEALTHY: "✓",
                    HealthStatus.WARNING: "⚠",
                    HealthStatus.CRITICAL: "✗",
                    HealthStatus.UNKNOWN: "?",
                }.get(check.status, "?")

                details += f"\n  [{status_icon}] {check.name} (分数: {check.score})\n"
                details += f"      {check.message}\n"

                if check.suggestion:
                    details += f"      建议: {check.suggestion}\n"

                if check.details:
                    for key, value in check.details.items():
                        if isinstance(value, list) and value:
                            details += f"      - {key}: {len(value)}项\n"
                        elif value:
                            details += f"      - {key}: {value}\n"

        return details

    def _generate_issues_summary(self, result: DiagnosticResult) -> str:
        """生成问题汇总"""
        issues = "\n--------------------------------------------------------------------------------\n"
        issues += "                            问题汇总\n"
        issues += "--------------------------------------------------------------------------------\n"

        if result.critical_issues:
            issues += "\n【严重问题】\n"
            for issue in result.critical_issues:
                issues += f"  ✗ {issue}\n"

        if result.warnings:
            issues += "\n【警告】\n"
            for warning in result.warnings:
                issues += f"  ⚠ {warning}\n"

        if not result.critical_issues and not result.warnings:
            issues += "\n  未发现严重问题或警告\n"

        return issues

    def _generate_suggestions(self, result: DiagnosticResult) -> str:
        """生成优化建议"""
        suggestions = "\n--------------------------------------------------------------------------------\n"
        suggestions += "                            优化建议\n"
        suggestions += "--------------------------------------------------------------------------------\n"

        if result.suggestions:
            for i, suggestion in enumerate(result.suggestions, 1):
                suggestions += f"\n  {i}. {suggestion}\n"
        else:
            suggestions += "\n  当前配置良好，无需优化\n"

        return suggestions

    def _generate_conclusion(self, result: DiagnosticResult) -> str:
        """生成结论"""
        conclusion = f"""
--------------------------------------------------------------------------------
                            结论
--------------------------------------------------------------------------------

本次诊断检查了实例 '{result.instance_name}' 的各项指标。

整体评估: {result.overall_status}
健康分数: {result.overall_score}/100

{result.summary}

建议优先处理严重问题，然后逐步解决警告事项。

================================================================================
                          报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
================================================================================
"""
        return conclusion

    def generate_json_report(self, result: DiagnosticResult) -> str:
        """生成JSON格式报告"""
        return json.dumps(result.model_dump(), ensure_ascii=False, indent=2)

    def save_report(self, result: DiagnosticResult, format: str = "txt") -> Path:
        """保存报告到文件"""
        timestamp = result.start_time.strftime("%Y%m%d_%H%M%S")
        filename = f"diagnostic_{result.instance_name}_{timestamp}.{format}"
        filepath = self.output_dir / filename

        if format == "txt":
            content = self.generate_full_report(result)
        elif format == "json":
            content = self.generate_json_report(result)
        else:
            raise ValueError(f"不支持的格式: {format}")

        filepath.write_text(content, encoding="utf-8")
        logger.info(f"报告已保存: {filepath}")

        return filepath

    def print_console_report(self, result: DiagnosticResult) -> None:
        """在控制台打印报告"""
        # 标题
        console.print(Panel(
            f"[bold]MySQL实例诊断报告[/bold]\n"
            f"实例: {result.instance_name}\n"
            f"时间: {result.start_time.strftime('%Y-%m-%d %H:%M:%S')}",
            border_style="cyan",
        ))

        # 整体状态
        status_color = {
            HealthStatus.HEALTHY: "green",
            HealthStatus.WARNING: "yellow",
            HealthStatus.CRITICAL: "red",
            HealthStatus.UNKNOWN: "grey",
        }
        console.print(
            f"\n[bold]整体状态: [{status_color.get(result.overall_status)}]{result.overall_status}[/]"
            f"  分数: {result.overall_score}/100\n"
        )

        # 检查结果表格
        table = Table(title="检查结果", show_header=True)
        table.add_column("检查项", style="cyan")
        table.add_column("类别", style="blue")
        table.add_column("状态", style="white")
        table.add_column("分数", style="yellow")
        table.add_column("说明", style="white")

        for check in result.check_items:
            status_icon = {
                HealthStatus.HEALTHY: "✓",
                HealthStatus.WARNING: "⚠",
                HealthStatus.CRITICAL: "✗",
                HealthStatus.UNKNOWN: "?",
            }.get(check.status, "?")

            table.add_row(
                check.name,
                check.category.value,
                f"[{status_color.get(check.status)}]{status_icon}[/]",
                str(check.score),
                check.message[:50] if len(check.message) > 50 else check.message,
            )

        console.print(table)

        # 问题汇总
        if result.critical_issues:
            console.print("\n[bold red]严重问题:[/bold red]")
            for issue in result.critical_issues:
                console.print(f"  ✗ {issue}")

        if result.warnings:
            console.print("\n[bold yellow]警告:[/bold yellow]")
            for warning in result.warnings:
                console.print(f"  ⚠ {warning}")

        # 建议
        if result.suggestions:
            console.print("\n[bold cyan]优化建议:[/bold cyan]")
            for i, suggestion in enumerate(result.suggestions, 1):
                console.print(f"  {i}. {suggestion}")


# 全局报告生成器
_report_generator: Optional[DiagnosticReportGenerator] = None


def get_report_generator() -> DiagnosticReportGenerator:
    """获取报告生成器"""
    global _report_generator
    if _report_generator is None:
        _report_generator = DiagnosticReportGenerator()
    return _report_generator