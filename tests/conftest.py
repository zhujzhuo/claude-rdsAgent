"""pytest配置和通用fixtures。"""

import pytest
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# 确保src目录在路径中
src_path = Path(__file__).parent.parent / "src"
if src_path.exists():
    sys.path.insert(0, str(src_path))


@pytest.fixture(autouse=True)
def mock_settings():
    """自动mock设置，避免依赖真实配置"""
    from rds_agent.utils.config import Settings

    mock_settings = Settings()
    mock_settings.ollama.host = "http://localhost:11434"
    mock_settings.ollama.model = "qwen2.5:14b"
    mock_settings.ollama.embed_model = "nomic-embed-text"
    mock_settings.instance_platform.url = ""
    mock_settings.instance_platform.token = ""
    mock_settings.vector_store.path = "/tmp/test_vector_store"
    mock_settings.vector_store.chroma_collection_name = "test_collection"
    mock_settings.agent.max_iterations = 10
    mock_settings.agent.timeout_seconds = 60
    mock_settings.log.level = "DEBUG"
    mock_settings.log.file = ""

    with patch("rds_agent.utils.config.settings", mock_settings):
        with patch("rds_agent.utils.config.get_settings", return_value=mock_settings):
            yield mock_settings


@pytest.fixture
def mock_mysql_connection():
    """Mock MySQL连接"""
    from rds_agent.data.models import ConnectionConfig

    config = ConnectionConfig(
        host="localhost",
        port=3306,
        user="test",
        password="test",
        database="test_db",
    )
    return config


@pytest.fixture
def mock_mysql_client(mock_mysql_connection):
    """Mock MySQL客户端"""
    from rds_agent.data.mysql_client import MySQLClient

    client = MagicMock(spec=MySQLClient)
    client.config = mock_mysql_connection
    client.get_version.return_value = "8.0.32"
    client.get_connection_status.return_value = MagicMock(
        max_connections=1000,
        current_connections=500,
        active_connections=200,
        connection_usage_ratio=50.0,
    )
    client.get_performance_metrics.return_value = MagicMock(
        qps=1200,
        tps=350,
        buffer_pool_hit_rate=99.5,
    )
    client.get_slow_queries.return_value = []
    client.get_storage_usage.return_value = MagicMock(
        total_size_gb=50,
        used_size_gb=40,
    )
    client.get_parameters.return_value = []
    client.close.return_value = None

    return client


@pytest.fixture
def mock_platform_client():
    """Mock实例管理平台客户端"""
    from rds_agent.data.instance_platform import MockInstancePlatformClient

    return MockInstancePlatformClient()


@pytest.fixture
def mock_vector_store():
    """Mock向量知识库"""
    from rds_agent.data.vector_store import VectorKnowledgeStore
    from langchain_core.documents import Document

    store = MagicMock(spec=VectorKnowledgeStore)
    store.search.return_value = [
        Document(page_content="测试内容", metadata={"source": "test.md"})
    ]
    store.add_documents.return_value = None

    return store


@pytest.fixture
def mock_llm():
    """Mock LLM"""
    mock = MagicMock()
    mock.invoke.return_value = "测试响应"
    return mock


@pytest.fixture
def mock_agent_state():
    """Mock Agent状态"""
    from rds_agent.core.state import AgentState, IntentType
    from langchain_core.messages import HumanMessage

    state: AgentState = {
        "messages": [HumanMessage(content="测试问题")],
        "intent": IntentType.UNKNOWN,
        "target_instance": None,
        "tool_calls": [],
        "tool_results": [],
        "context": {},
        "current_node": "",
        "needs_tool_call": False,
        "response": None,
        "error": None,
    }
    return state


@pytest.fixture(scope="session")
def test_knowledge_dir(tmp_path_factory):
    """测试知识库目录"""
    knowledge_dir = tmp_path_factory.mktemp("knowledge")
    mysql_dir = knowledge_dir / "mysql"
    mysql_dir.mkdir()

    # 创建测试文档
    test_doc = mysql_dir / "test.md"
    test_doc.write_text("""# MySQL测试文档

## Buffer Pool
Buffer Pool是InnoDB存储引擎的内存缓存区域。

## 性能优化
使用索引可以提高查询性能。
""")
    return knowledge_dir


# 测试标记
def pytest_configure(config):
    """配置测试标记"""
    config.addinivalue_line("markers", "unit: 单元测试")
    config.addinivalue_line("markers", "integration: 集成测试")
    config.addinivalue_line("markers", "slow: 慢测试")
    config.addinivalue_line("markers", "requires_mysql: 需要真实MySQL连接")
    config.addinivalue_line("markers", "requires_ollama: 需要Ollama服务")


# 跳过需要真实服务的测试
def pytest_collection_modifyitems(config, items):
    """修改测试收集"""
    skip_mysql = pytest.mark.skip(reason="需要真实MySQL连接")
    skip_ollama = pytest.mark.skip(reason="需要Ollama服务")

    for item in items:
        if "requires_mysql" in item.keywords and not os.getenv("MYSQL_TEST_HOST"):
            item.add_marker(skip_mysql)
        if "requires_ollama" in item.keywords and not os.getenv("OLLAMA_TEST_ENABLED"):
            item.add_marker(skip_ollama)