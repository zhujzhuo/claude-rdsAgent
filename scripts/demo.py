"""演示脚本 - 展示RDS Agent的基本功能。"""

import json
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from rds_agent import __version__, settings
from rds_agent.tools import (
    get_instance_list,
    get_instance_info,
    get_performance_metrics,
    get_slow_queries,
    get_connection_status,
    get_storage_usage,
    get_parameters,
)
from rds_agent.utils.logger import get_logger

logger = get_logger("demo")
console = Console()


def print_header():
    """打印标题"""
    console.print(
        Panel(
            f"[bold green]RDS Agent v{__version__}[/bold green]\n"
            f"[blue]功能演示[/blue]",
            title="Demo",
            border_style="cyan",
        )
    )
    console.print(f"[yellow]模型: {settings.ollama.model}[/yellow]")
    console.print(f"[yellow]Ollama: {settings.ollama.host}[/yellow]")
    console.print()


def demo_instance_tools():
    """演示实例信息工具"""
    console.print("[bold cyan]=== 实例信息工具演示 ===[/bold cyan]")

    # 获取实例列表
    console.print("[green]1. 获取实例列表[/green]")
    result = get_instance_list.invoke({})
    console.print(result)
    console.print()

    # 获取实例详情
    console.print("[green]2. 获取实例详情 (db-prod-01)[/green]")
    result = get_instance_info.invoke({"instance_name": "db-prod-01"})
    console.print(result)
    console.print()


def demo_performance_tools():
    """演示性能监控工具"""
    console.print("[bold cyan]=== 性能监控工具演示 ===[/bold cyan]")

    # 获取性能指标
    console.print("[green]1. 获取性能指标[/green]")
    result = get_performance_metrics.invoke({"instance_name": "db-prod-01"})
    console.print(result)
    console.print()


def demo_sql_tools():
    """演示SQL诊断工具"""
    console.print("[bold cyan]=== SQL诊断工具演示 ===[/bold cyan]")

    # 获取慢查询
    console.print("[green]1. 获取慢查询列表[/green]")
    result = get_slow_queries.invoke({
        "instance_name": "db-prod-01",
        "limit": 5,
        "min_time": 1.0
    })
    console.print(result)
    console.print()


def demo_connection_tools():
    """演示连接诊断工具"""
    console.print("[bold cyan]=== 连接诊断工具演示 ===[/bold cyan]")

    # 获取连接状态
    console.print("[green]1. 获取连接状态[/green]")
    result = get_connection_status.invoke({"instance_name": "db-prod-01"})
    console.print(result)
    console.print()


def demo_storage_tools():
    """演示存储分析工具"""
    console.print("[bold cyan]=== 存储分析工具演示 ===[/bold cyan]")

    # 获取存储使用情况
    console.print("[green]1. 获取存储使用情况[/green]")
    result = get_storage_usage.invoke({"instance_name": "db-prod-01"})
    console.print(result)
    console.print()


def demo_parameter_tools():
    """演示参数查询工具"""
    console.print("[bold cyan]=== 参数查询工具演示 ===[/bold cyan]")

    # 获取关键参数
    console.print("[green]1. 获取关键参数配置[/green]")
    result = get_parameters.invoke({"instance_name": "db-prod-01"})
    console.print(result)
    console.print()


def demo_tools_table():
    """打印工具清单表格"""
    table = Table(title="可用工具清单", show_header=True, header_style="bold cyan")
    table.add_column("工具名", style="green")
    table.add_column("功能", style="white")
    table.add_column("参数", style="yellow")

    tools_info = [
        ("get_instance_list", "获取实例列表", "无"),
        ("get_instance_info", "获取实例详情", "instance_name"),
        ("get_performance_metrics", "获取性能指标", "instance_name"),
        ("get_slow_queries", "获取慢查询", "instance_name, limit, min_time"),
        ("get_connection_status", "获取连接状态", "instance_name"),
        ("get_lock_info", "获取锁信息", "instance_name"),
        ("get_storage_usage", "获取存储使用", "instance_name"),
        ("get_table_stats", "获取表统计", "instance_name, schema_name"),
        ("get_parameters", "获取参数配置", "instance_name, param_names"),
        ("search_knowledge", "知识库检索", "query, top_k"),
    ]

    for tool_name, func, params in tools_info:
        table.add_row(tool_name, func, params)

    console.print(table)


def run_demo():
    """运行完整演示"""
    print_header()

    console.print("[yellow]注意：演示使用Mock数据，实际运行需要配置真实实例[/yellow]")
    console.print()

    # 演示各工具
    demo_instance_tools()
    demo_performance_tools()
    demo_sql_tools()
    demo_connection_tools()
    demo_storage_tools()
    demo_parameter_tools()

    # 工具清单
    demo_tools_table()

    console.print()
    console.print("[bold green]演示完成！[/bold green]")
    console.print("[cyan]运行 CLI: python -m rds_agent chat[/cyan]")
    console.print("[cyan]运行 API: python -m rds_agent api[/cyan]")


if __name__ == "__main__":
    run_demo()