"""MySQL客户端测试。"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import pymysql

from rds_agent.data.mysql_client import MySQLClient
from rds_agent.data.models import ConnectionConfig


class TestMySQLClient:
    """MySQL客户端测试"""

    @pytest.fixture
    def connection_config(self):
        """连接配置fixture"""
        return ConnectionConfig(
            host="localhost",
            port=3306,
            user="test",
            password="test123",
            database="test_db",
        )

    @pytest.fixture
    def mock_connection(self):
        """Mock连接fixture"""
        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value = cursor
        return conn, cursor

    def test_mysql_client_creation(self, connection_config):
        """测试MySQL客户端创建"""
        client = MySQLClient(connection_config)
        assert client.config == connection_config
        assert client.pool_size == 5

    def test_mysql_client_custom_pool_size(self, connection_config):
        """测试自定义连接池大小"""
        client = MySQLClient(connection_config, pool_size=10)
        assert client.pool_size == 10

    @patch("rds_agent.data.mysql_client.PooledDB")
    def test_create_pool(self, mock_pooled_db, connection_config):
        """测试创建连接池"""
        client = MySQLClient(connection_config)
        pool = client._create_pool()

        mock_pooled_db.assert_called_once()
        call_args = mock_pooled_db.call_args[1]
        assert call_args["host"] == connection_config.host
        assert call_args["port"] == connection_config.port
        assert call_args["user"] == connection_config.user
        assert call_args["database"] == connection_config.database

    def test_execute_query_success(self, connection_config, mock_connection):
        """测试执行查询成功"""
        conn, cursor = mock_connection
        cursor.fetchall.return_value = [{"id": 1, "name": "test"}]

        client = MySQLClient(connection_config)
        client._pool = MagicMock()
        client._pool.connection.return_value = conn

        result = client.execute_query("SELECT * FROM test")
        assert len(result) == 1
        assert result[0]["name"] == "test"

    def test_execute_one(self, connection_config, mock_connection):
        """测试执行单条查询"""
        conn, cursor = mock_connection
        cursor.fetchall.return_value = [{"version": "8.0.32"}]

        client = MySQLClient(connection_config)
        client._pool = MagicMock()
        client._pool.connection.return_value = conn

        result = client.execute_one("SELECT VERSION() as version")
        assert result["version"] == "8.0.32"

    def test_execute_one_empty(self, connection_config, mock_connection):
        """测试空结果"""
        conn, cursor = mock_connection
        cursor.fetchall.return_value = []

        client = MySQLClient(connection_config)
        client._pool = MagicMock()
        client._pool.connection.return_value = conn

        result = client.execute_one("SELECT * FROM empty_table")
        assert result is None

    def test_get_version(self, connection_config, mock_connection):
        """测试获取版本"""
        conn, cursor = mock_connection
        cursor.fetchall.return_value = [{"version": "8.0.32"}]

        client = MySQLClient(connection_config)
        client._pool = MagicMock()
        client._pool.connection.return_value = conn

        version = client.get_version()
        assert version == "8.0.32"

    def test_get_status_variables(self, connection_config, mock_connection):
        """测试获取状态变量"""
        conn, cursor = mock_connection
        cursor.fetchall.return_value = [
            {"Variable_name": "Threads_connected", "Value": "50"},
            {"Variable_name": "Questions", "Value": "10000"},
        ]

        client = MySQLClient(connection_config)
        client._pool = MagicMock()
        client._pool.connection.return_value = conn

        status = client.get_status_variables()
        assert status["Threads_connected"] == "50"
        assert status["Questions"] == "10000"

    def test_get_system_variables(self, connection_config, mock_connection):
        """测试获取系统变量"""
        conn, cursor = mock_connection
        cursor.fetchall.return_value = [
            {"Variable_name": "max_connections", "Value": "1000"},
            {"Variable_name": "innodb_buffer_pool_size", "Value": "8589934592"},
        ]

        client = MySQLClient(connection_config)
        client._pool = MagicMock()
        client._pool.connection.return_value = conn

        variables = client.get_system_variables()
        assert variables["max_connections"] == "1000"
        assert variables["innodb_buffer_pool_size"] == "8589934592"

    def test_get_connection_status(self, connection_config, mock_connection):
        """测试获取连接状态"""
        conn, cursor = mock_connection
        cursor.fetchall.return_value = [
            {"Variable_name": "max_connections", "Value": "1000"},
            {"Variable_name": "Threads_connected", "Value": "500"},
            {"Variable_name": "Threads_running", "Value": "50"},
            {"Variable_name": "Connection_errors_total", "Value": "10"},
            {"Variable_name": "Aborted_connects", "Value": "5"},
        ]

        client = MySQLClient(connection_config)
        client._pool = MagicMock()
        client._pool.connection.return_value = conn

        status = client.get_connection_status()
        assert status.max_connections == 1000
        assert status.current_connections == 500
        assert status.active_connections == 50
        assert status.connection_usage_ratio == 50.0

    def test_get_performance_metrics(self, connection_config, mock_connection):
        """测试获取性能指标"""
        conn, cursor = mock_connection
        cursor.fetchall.return_value = [
            {"Variable_name": "Uptime", "Value": "3600"},
            {"Variable_name": "Questions", "Value": "100000"},
            {"Variable_name": "Com_commit", "Value": "5000"},
            {"Variable_name": "Com_rollback", "Value": "100"},
            {"Variable_name": "Threads_running", "Value": "10"},
            {"Variable_name": "Innodb_buffer_pool_read_requests", "Value": "10000"},
            {"Variable_name": "Innodb_buffer_pool_reads", "Value": "100"},
            {"Variable_name": "Innodb_rows_read", "Value": "50000"},
            {"Variable_name": "Innodb_rows_inserted", "Value": "1000"},
            {"Variable_name": "Innodb_rows_updated", "Value": "500"},
            {"Variable_name": "Innodb_rows_deleted", "Value": "100"},
        ]

        client = MySQLClient(connection_config)
        client._pool = MagicMock()
        client._pool.connection.return_value = conn

        metrics = client.get_performance_metrics()
        assert metrics.qps > 0  # 100000/3600 ≈ 27.78
        assert metrics.tps > 0  # (5000+100)/3600 ≈ 1.42
        assert metrics.buffer_pool_hit_rate > 90  # (10000-100)/10000 * 100 = 99%

    def test_get_storage_usage(self, connection_config, mock_connection):
        """测试获取存储使用"""
        conn, cursor = mock_connection
        # 模拟两次查询：数据库统计和最大表
        cursor.fetchall.side_effect = [
            [
                {"schema_name": "prod", "table_rows": 100000, "total_size_mb": 5000, "data_size_mb": 4000, "index_size_mb": 1000},
                {"schema_name": "test", "table_rows": 50000, "total_size_mb": 2000, "data_size_mb": 1500, "index_size_mb": 500},
            ],
            [
                {"schema_name": "prod", "table_name": "orders", "table_rows": 50000, "total_size_mb": 3000},
                {"schema_name": "prod", "table_name": "users", "table_rows": 20000, "total_size_mb": 1000},
            ],
        ]

        client = MySQLClient(connection_config)
        client._pool = MagicMock()
        client._pool.connection.return_value = conn

        storage = client.get_storage_usage()
        assert storage.total_size_gb > 0
        assert storage.database_count == 2
        assert len(storage.largest_tables) == 2

    def test_get_slow_queries(self, connection_config, mock_connection):
        """测试获取慢查询"""
        conn, cursor = mock_connection
        cursor.fetchall.return_value = [
            {
                "sql_text": "SELECT * FROM orders WHERE user_id = ?",
                "exec_count": 100,
                "avg_time_sec": 2.5,
                "rows_examined": 10000,
                "rows_sent": 10,
                "last_seen": "2024-01-01 10:00:00",
            },
        ]

        client = MySQLClient(connection_config)
        client._pool = MagicMock()
        client._pool.connection.return_value = conn

        slow_queries = client.get_slow_queries(limit=5, min_time=1.0)
        assert len(slow_queries) == 1
        assert slow_queries[0].query_time == 2.5
        assert slow_queries[0].rows_examined == 10000

    def test_get_processlist(self, connection_config, mock_connection):
        """测试获取进程列表"""
        conn, cursor = mock_connection
        cursor.fetchall.return_value = [
            {"Id": 1, "User": "root", "Command": "Query", "Time": 5, "Info": "SELECT 1"},
            {"Id": 2, "User": "app", "Command": "Sleep", "Time": 10, "Info": None},
        ]

        client = MySQLClient(connection_config)
        client._pool = MagicMock()
        client._pool.connection.return_value = conn

        processlist = client.get_processlist()
        assert len(processlist) == 2
        assert processlist[0]["Command"] == "Query"

    def test_get_parameters(self, connection_config, mock_connection):
        """测试获取参数"""
        conn, cursor = mock_connection
        cursor.fetchall.return_value = [
            {"Variable_name": "max_connections", "Value": "1000"},
            {"Variable_name": "innodb_buffer_pool_size", "Value": "8589934592"},
        ]

        client = MySQLClient(connection_config)
        client._pool = MagicMock()
        client._pool.connection.return_value = conn

        params = client.get_parameters()
        assert len(params) == 2
        assert params[0].name == "max_connections"

    def test_get_parameters_with_names(self, connection_config, mock_connection):
        """测试获取指定参数"""
        conn, cursor = mock_connection
        cursor.fetchall.return_value = [
            {"Variable_name": "max_connections", "Value": "500"},
        ]

        client = MySQLClient(connection_config)
        client._pool = MagicMock()
        client._pool.connection.return_value = conn

        params = client.get_parameters(names=["max_connections"])
        assert len(params) == 1

    def test_get_innodb_status(self, connection_config, mock_connection):
        """测试获取InnoDB状态"""
        conn, cursor = mock_connection
        cursor.fetchall.return_value = [
            {"Status": "BUFFER POOL AND MEMORY..."},
        ]

        client = MySQLClient(connection_config)
        client._pool = MagicMock()
        client._pool.connection.return_value = conn

        status = client.get_innodb_status()
        assert "BUFFER POOL" in status

    def test_client_close(self, connection_config):
        """测试关闭客户端"""
        client = MySQLClient(connection_config)
        client._pool = MagicMock()

        client.close()
        client._pool.close.assert_called_once()
        assert client._pool is None


class TestMySQLClientErrorHandling:
    """MySQL客户端错误处理测试"""

    @pytest.fixture
    def connection_config(self):
        return ConnectionConfig(host="localhost", port=3306, user="test", password="test")

    def test_connection_error(self, connection_config):
        """测试连接错误处理"""
        client = MySQLClient(connection_config)

        with patch("rds_agent.data.mysql_client.PooledDB") as mock_pool:
            mock_pool.side_effect = pymysql.Error("Connection failed")
            with pytest.raises(pymysql.Error):
                client._create_pool()

    def test_query_error(self, connection_config):
        """测试查询错误处理"""
        client = MySQLClient(connection_config)
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = pymysql.Error("Query failed")
        mock_conn.cursor.return_value = mock_cursor
        mock_pool.connection.return_value = mock_conn
        client._pool = mock_pool

        with pytest.raises(pymysql.Error):
            client.execute_query("SELECT * FROM test")

    def test_get_lock_info_empty(self, connection_config):
        """测试锁信息表不存在的情况"""
        client = MySQLClient(connection_config)
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = pymysql.Error("Table doesn't exist")
        mock_conn.cursor.return_value = mock_cursor
        mock_pool.connection.return_value = mock_conn
        client._pool = mock_pool

        # 应返回空列表而非抛出异常
        result = client.get_lock_info()
        assert result == []