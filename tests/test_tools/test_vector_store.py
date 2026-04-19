"""向量知识库测试。"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path

from rds_agent.data.vector_store import VectorKnowledgeStore, get_knowledge_store


class TestVectorKnowledgeStore:
    """向量知识库测试"""

    @pytest.fixture
    def store_config(self):
        """知识库配置"""
        return {
            "persist_directory": "/tmp/test_vector_store",
            "collection_name": "test_collection",
            "embedding_model": "nomic-embed-text",
        }

    @pytest.fixture
    def mock_embeddings(self):
        """Mock Embedding模型"""
        return MagicMock()

    @pytest.fixture
    def mock_vectorstore(self):
        """Mock向量存储"""
        vs = MagicMock()
        return vs

    def test_store_creation(self, store_config):
        """测试知识库创建"""
        store = VectorKnowledgeStore(**store_config)
        assert store.persist_directory == "/tmp/test_vector_store"
        assert store.collection_name == "test_collection"
        assert store.embedding_model == "nomic-embed-text"

    def test_store_creation_defaults(self):
        """测试默认配置"""
        with patch("rds_agent.data.vector_store.settings") as mock_settings:
            mock_settings.vector_store.path = "./data/vector_store"
            mock_settings.vector_store.chroma_collection_name = "rds_knowledge"
            mock_settings.ollama.embed_model = "nomic-embed-text"

            store = VectorKnowledgeStore()
            assert store.persist_directory == "./data/vector_store"
            assert store.collection_name == "rds_knowledge"

    @patch("rds_agent.data.vector_store.OllamaEmbeddings")
    def test_get_embeddings(self, mock_embeddings_class, store_config):
        """测试获取Embedding模型"""
        with patch("rds_agent.data.vector_store.settings") as mock_settings:
            mock_settings.ollama.host = "http://localhost:11434"

            store = VectorKnowledgeStore(**store_config)
            embeddings = store._get_embeddings()

            mock_embeddings_class.assert_called_once()
            assert embeddings is not None

    @patch("rds_agent.data.vector_store.Chroma")
    @patch("rds_agent.data.vector_store.os.path.exists")
    def test_get_vectorstore_existing(self, mock_exists, mock_chroma, store_config):
        """测试加载已有向量库"""
        mock_exists.return_value = True

        store = VectorKnowledgeStore(**store_config)
        store._embeddings = MagicMock()

        vs = store.get_vectorstore()

        # 应使用persist_directory加载
        mock_chroma.assert_called()

    @patch("rds_agent.data.vector_store.Chroma")
    @patch("rds_agent.data.vector_store.os.path.exists")
    def test_get_vectorstore_new(self, mock_exists, mock_chroma, store_config):
        """测试创建新向量库"""
        mock_exists.return_value = False

        store = VectorKnowledgeStore(**store_config)
        store._embeddings = MagicMock()

        vs = store.get_vectorstore()

        mock_chroma.assert_called()

    def test_add_documents(self, store_config):
        """测试添加文档"""
        from langchain_core.documents import Document

        store = VectorKnowledgeStore(**store_config)
        store._vectorstore = MagicMock()

        docs = [
            Document(page_content="MySQL Buffer Pool缓存数据", metadata={"source": "test"}),
            Document(page_content="InnoDB是默认存储引擎", metadata={"source": "test"}),
        ]

        store.add_documents(docs)
        store._vectorstore.add_documents.assert_called_once_with(docs)

    def test_add_texts(self, store_config):
        """测试添加文本"""
        store = VectorKnowledgeStore(**store_config)
        store._vectorstore = MagicMock()

        texts = ["文本1", "文本2"]
        metadatas = [{"source": "a"}, {"source": "b"}]

        store.add_texts(texts, metadatas)
        store._vectorstore.add_texts.assert_called_once_with(texts, metadatas=metadatas)

    def test_search(self, store_config):
        """测试搜索"""
        from langchain_core.documents import Document

        store = VectorKnowledgeStore(**store_config)
        mock_vs = MagicMock()
        mock_vs.similarity_search.return_value = [
            Document(page_content="相关内容1", metadata={"source": "a"}),
            Document(page_content="相关内容2", metadata={"source": "b"}),
        ]
        store._vectorstore = mock_vs

        results = store.search("Buffer Pool", k=3)
        assert len(results) == 2
        mock_vs.similarity_search.assert_called_once_with("Buffer Pool", k=3, filter=None)

    def test_search_with_filter(self, store_config):
        """测试带过滤条件搜索"""
        store = VectorKnowledgeStore(**store_config)
        mock_vs = MagicMock()
        store._vectorstore = mock_vs

        filter_dict = {"source": "architecture.md"}
        store.search("Buffer Pool", k=5, filter=filter_dict)

        mock_vs.similarity_search.assert_called_once_with(
            "Buffer Pool", k=5, filter=filter_dict
        )

    def test_search_with_score(self, store_config):
        """测试带分数搜索"""
        from langchain_core.documents import Document

        store = VectorKnowledgeStore(**store_config)
        mock_vs = MagicMock()
        mock_vs.similarity_search_with_score.return_value = [
            (Document(page_content="内容1"), 0.8),
            (Document(page_content="内容2"), 0.6),
        ]
        store._vectorstore = mock_vs

        results = store.search_with_score("Buffer Pool", k=3)
        assert len(results) == 2
        assert results[0][1] == 0.8  # 分数

    def test_get_retriever(self, store_config):
        """测试获取检索器"""
        store = VectorKnowledgeStore(**store_config)
        mock_vs = MagicMock()
        mock_vs.as_retriever.return_value = MagicMock()
        store._vectorstore = mock_vs

        retriever = store.get_retriever(k=5)
        mock_vs.as_retriever.assert_called_once_with(search_kwargs={"k": 5})

    def test_delete_collection(self, store_config):
        """测试删除集合"""
        store = VectorKnowledgeStore(**store_config)
        mock_vs = MagicMock()
        store._vectorstore = mock_vs

        store.delete_collection()
        mock_vs.delete_collection.assert_called_once()
        assert store._vectorstore is None


class TestGetKnowledgeStore:
    """获取知识库实例测试"""

    def test_get_knowledge_store_singleton(self):
        """测试单例模式"""
        # 清除全局实例
        import rds_agent.data.vector_store as vs_module
        vs_module._knowledge_store = None

        with patch("rds_agent.data.vector_store.VectorKnowledgeStore") as mock_store_class:
            mock_store = MagicMock()
            mock_store_class.return_value = mock_store

            store1 = get_knowledge_store()
            store2 = get_knowledge_store()

            # 单例，只创建一次
            assert store1 == store2
            mock_store_class.assert_called_once()

    def test_get_knowledge_store_existing(self):
        """测试已有实例"""
        import rds_agent.data.vector_store as vs_module
        mock_store = MagicMock()
        vs_module._knowledge_store = mock_store

        store = get_knowledge_store()
        assert store == mock_store