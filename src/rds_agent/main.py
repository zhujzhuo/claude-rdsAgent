"""RDS Agent入口文件。"""

import argparse
import sys

from rich.console import Console

from rds_agent import __version__, logger
from rds_agent.utils.config import settings


def main() -> None:
    """主入口函数"""
    parser = argparse.ArgumentParser(
        prog="rds-agent",
        description="RDS智能问答助手 - MySQL数据库智能Agent",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=".env",
        help="配置文件路径",
    )

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # chat子命令 - CLI交互模式
    chat_parser = subparsers.add_parser("chat", help="启动CLI交互模式")
    chat_parser.add_argument(
        "--instance",
        type=str,
        help="指定默认实例名称",
    )

    # api子命令 - Web API服务
    api_parser = subparsers.add_parser("api", help="启动Web API服务")
    api_parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="API服务主机",
    )
    api_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="API服务端口",
    )

    # demo子命令 - 演示模式
    demo_parser = subparsers.add_parser("demo", help="运行演示脚本")

    args = parser.parse_args()

    console = Console()
    console.print(f"[bold green]RDS Agent v{__version__}[/bold green]")
    console.print(f"[blue]模型: {settings.ollama.model}[/blue]")
    console.print(f"[blue]Ollama地址: {settings.ollama.host}[/blue]")

    if args.command == "chat":
        # CLI交互模式
        from rds_agent.cli import run_cli
        run_cli(instance=args.instance)
    elif args.command == "api":
        # Web API服务
        import uvicorn
        from rds_agent.api.app import app
        logger.info(f"启动Web API服务: {args.host}:{args.port}")
        uvicorn.run(app, host=args.host, port=args.port)
    elif args.command == "demo":
        # 演示模式
        from scripts.demo import run_demo
        run_demo()
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()