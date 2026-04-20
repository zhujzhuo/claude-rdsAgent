"""CLI交互界面。"""

import uuid
from typing import Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from rds_agent import __version__, settings
from rds_agent.router import get_router_agent, RouterAgent, AgentType
from rds_agent.utils.logger import get_logger

logger = get_logger("cli")

# 样式定义
STYLE = Style.from_dict(
    {
        "prompt": "bold cyan",
        "input": "bold white",
        "output": "green",
    }
)


def create_key_bindings() -> KeyBindings:
    """创建快捷键绑定"""
    kb = KeyBindings()

    @kb.add("c-c")
    def _(event):
        """Ctrl+C退出"""
        event.app.exit()

    @kb.add("c-d")
    def _(event):
        """Ctrl+D退出"""
        event.app.exit()

    @kb.add("c-l")
    def _(event):
        """Ctrl+L清屏"""
        event.app.renderer.clear()

    return kb


def print_welcome(console: Console) -> None:
    """打印欢迎信息"""
    console.clear()
    console.print(
        Panel(
            f"[bold green]RDS Agent v{__version__}[/bold green]\n"
            f"[blue]MySQL智能问答助手[/blue]\n\n"
            f"[yellow]模型: {settings.ollama.model}[/yellow]\n"
            f"[yellow]Ollama: {settings.ollama.host}[/yellow]\n\n"
            f"[white]输入问题开始对话[/white]\n"
            f"[white]Ctrl+C 退出, Ctrl+L 清屏[/white]",
            title="[bold cyan]欢迎使用[/bold cyan]",
            border_style="cyan",
        )
    )


def print_help(console: Console) -> None:
    """打印帮助信息"""
    table = Table(title="可用功能", show_header=True, header_style="bold cyan")
    table.add_column("类型", style="green")
    table.add_column("示例问题", style="white")

    table.add_row("实例查询", "查看实例列表, db-prod-01的规格是多少")
    table.add_row("性能诊断", "db-prod-01的性能情况, 检查慢查询")
    table.add_row("SQL诊断", "获取慢SQL列表, 分析正在执行的语句")
    table.add_row("连接诊断", "检查连接数, 查看锁等待情况")
    table.add_row("存储分析", "空间使用情况, 查看表大小")
    table.add_row("参数查询", "查看innodb参数, 参数配置")
    table.add_row("知识问答", "如何优化慢查询, innodb原理是什么")

    console.print(table)


def run_cli(instance: Optional[str] = None) -> None:
    """运行CLI交互"""
    console = Console()
    session: PromptSession = PromptSession(
        history=InMemoryHistory(),
        key_bindings=create_key_bindings(),
        style=STYLE,
        message="[bold cyan]>>>[/bold cyan] ",
    )

    print_welcome(console)

    # 初始化 RouterAgent（自动选择 Agent）
    try:
        agent = get_router_agent()
        console.print(
            Panel(
                f"[bold green]Agent 路由模式[/bold green]\n"
                f"[blue]自动选择: Hermes(简单) / LangGraph(中等) / Diagnostic(复杂)[/blue]\n"
                f"[yellow]Hermes 启用: {settings.hermes.enabled}[/yellow]",
                title="[bold cyan]路由信息[/bold cyan]",
                border_style="cyan",
            )
        )
    except Exception as e:
        console.print(f"[red]初始化RouterAgent失败: {e}[/red]")
        return

    # 会话ID
    thread_id = str(uuid.uuid4())
    logger.info(f"会话ID: {thread_id}")

    # 如果指定了默认实例
    if instance:
        console.print(f"[yellow]默认实例: {instance}[/yellow]")

    # 对话循环
    console.print("[cyan]开始对话...[/cyan]")

    while True:
        try:
            # 获取用户输入
            user_input = session.prompt().strip()

            if not user_input:
                continue

            # 处理命令
            if user_input.startswith("/"):
                command = user_input.lower()
                if command in ["exit", "quit", "/q"]:
                    console.print("[yellow]再见！[/yellow]")
                    break
                elif command in ["help", "/h"]:
                    print_help(console)
                    continue
                elif command in ["clear", "/c"]:
                    console.clear()
                    continue
                elif command in ["reset", "/r"]:
                    agent.reset(thread_id)
                    thread_id = str(uuid.uuid4())
                    console.print("[yellow]会话已重置[/yellow]")
                    continue

            # 调用Agent
            console.print("[dim]正在处理...[/dim]")

            try:
                response = agent.chat(user_input, thread_id)
                console.print(
                    Panel(
                        response,
                        title="[bold green]Agent响应[/bold green]",
                        border_style="green",
                    )
                )
            except Exception as e:
                console.print(f"[red]处理失败: {e}[/red]")
                logger.error(f"Agent调用失败: {e}")

        except KeyboardInterrupt:
            console.print("\n[yellow]按Ctrl+C退出, 或输入exit[/yellow]")
            continue
        except EOFError:
            console.print("\n[yellow]再见！[/yellow]")
            break


def main() -> None:
    """CLI入口"""
    run_cli()


if __name__ == "__main__":
    main()