"""初始化向量知识库 - 导入MySQL运维知识文档。"""

import os
from pathlib import Path
import argparse
from rich.console import Console
from rich.progress import Progress

from langchain_core.documents import Document

from rds_agent.data.vector_store import get_knowledge_store
from rds_agent.utils.logger import get_logger

logger = get_logger("init_knowledge")
console = Console()


# 知识文档目录
KNOWLEDGE_DIR = Path(__file__).parent.parent / "knowledge"


def load_markdown_documents(directory: Path) -> list[Document]:
    """加载Markdown文档"""
    documents = []

    for md_file in directory.rglob("*.md"):
        try:
            content = md_file.read_text(encoding="utf-8")
            if content.strip():
                doc = Document(
                    page_content=content,
                    metadata={
                        "source": str(md_file.relative_to(directory)),
                        "file_type": "markdown",
                    }
                )
                documents.append(doc)
                logger.info(f"加载文档: {md_file.name}")
        except Exception as e:
            logger.warning(f"加载文档失败 {md_file}: {e}")

    return documents


def split_documents(documents: list[Document], chunk_size: int = 500) -> list[Document]:
    """分割文档为小块"""
    from langchain.text_splitter import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

    split_docs = []

    for doc in documents:
        try:
            # 先按Markdown标题分割
            header_splitter = MarkdownHeaderTextSplitter(
                headers_to_split_on=[
                    ("#", "header1"),
                    ("##", "header2"),
                    ("###", "header3"),
                ]
            )
            header_splits = header_splitter.split_text(doc.page_content)

            # 再按字符分割（控制大小）
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=50,
                separators=["\n\n", "\n", " ", ""],
            )

            for split in header_splits:
                # 合并metadata
                metadata = {**doc.metadata, **split.metadata}
                small_splits = text_splitter.split_text(split.page_content)
                for small in small_splits:
                    split_docs.append(Document(
                        page_content=small,
                        metadata=metadata
                    ))

        except Exception as e:
            # 如果Markdown分割失败，使用普通分割
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=50,
            )
            splits = text_splitter.split_documents([doc])
            split_docs.extend(splits)

    return split_docs


def init_mysql_knowledge():
    """初始化MySQL知识库"""
    mysql_dir = KNOWLEDGE_DIR / "mysql"

    console.print("[cyan]加载MySQL知识文档...[/cyan]")
    documents = load_markdown_documents(mysql_dir)

    console.print(f"[green]已加载 {len(documents)} 个文档[/green]")

    console.print("[cyan]分割文档...[/cyan]")
    split_docs = split_documents(documents, chunk_size=500)

    console.print(f"[green]分割后共 {len(split_docs)} 个文档块[/green]")

    # 添加到知识库
    console.print("[cyan]添加到向量知识库...[/cyan]")

    store = get_knowledge_store()

    with Progress() as progress:
        task = progress.add_task("添加文档", total=len(split_docs))

        # 分批添加，每批50个
        batch_size = 50
        for i in range(0, len(split_docs), batch_size):
            batch = split_docs[i:i + batch_size]
            store.add_documents(batch)
            progress.update(task, advance=len(batch))

    console.print(f"[bold green]MySQL知识库初始化完成！[/bold green]")
    console.print(f"共添加 {len(split_docs)} 个知识片段")


def init_faq_knowledge():
    """初始化FAQ知识库"""
    faq_dir = KNOWLEDGE_DIR / "faq"

    if not faq_dir.exists():
        console.print("[yellow]FAQ目录不存在，跳过[/yellow]")
        return

    documents = load_markdown_documents(faq_dir)

    if documents:
        split_docs = split_documents(documents, chunk_size=300)
        store = get_knowledge_store()
        store.add_documents(split_docs)
        console.print(f"[green]FAQ知识库: {len(split_docs)} 个片段[/green]")


def init_all_knowledge():
    """初始化所有知识库"""
    console.print("[bold cyan]========== 开始初始化知识库 ==========[/bold cyan]")

    init_mysql_knowledge()
    init_faq_knowledge()

    console.print("[bold green]========== 知识库初始化完成 ==========[/bold green]")

    # 验证
    store = get_knowledge_store()
    test_results = store.search("Buffer Pool", k=3)
    console.print(f"\n[yellow]验证: 搜索 'Buffer Pool' 返回 {len(test_results)} 条结果[/yellow]")


def clear_knowledge():
    """清空知识库"""
    console.print("[yellow]清空知识库...[/yellow]")
    store = get_knowledge_store()
    store.delete_collection()
    console.print("[green]知识库已清空[/green]")


def main():
    """主入口"""
    parser = argparse.ArgumentParser(description="初始化RDS Agent知识库")
    parser.add_argument(
        "--action",
        choices=["init", "clear", "reinit"],
        default="init",
        help="操作类型: init初始化, clear清空, reinit重新初始化"
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=500,
        help="文档分割块大小"
    )

    args = parser.parse_args()

    if args.action == "init":
        init_all_knowledge()
    elif args.action == "clear":
        clear_knowledge()
    elif args.action == "reinit":
        clear_knowledge()
        init_all_knowledge()


if __name__ == "__main__":
    main()