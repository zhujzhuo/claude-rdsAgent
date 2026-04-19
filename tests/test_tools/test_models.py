"""数据模型测试。"""

import pytest
from rds_agent.data.models import (
    InstanceInfo,
    ConnectionConfig,
    InstanceStatus,
    ArchitectureType,
    SlowQueryRecord,
    ConnectionStatus,
    PerformanceMetrics,
    StorageUsage,
    TableStats,
    ParameterInfo,
)


class TestInstanceInfo:
    """实例信息模型测试"""

    def test_instance_info_creation(self):
        """测试创建实例信息"""
        instance = InstanceInfo(
            id="inst-001",
            name="db-prod-01",
            host="192.168.1.100",
            port=3306,
            version="8.0.32",
            architecture=ArchitectureType.SINGLE,
            spec="4C8G",
            storage_size=200,
            status=InstanceStatus.RUNNING,
        )
        assert instance.id == "inst-001"
        assert instance.name == "db-prod-01"
        assert instance.port == 3306

    def test_instance_info_defaults(self):
        """测试默认值"""
        instance = InstanceInfo(
            id="inst-002",
            name="db-test-01",
            host="192.168.2.100",
        )
        assert instance.port == 3306
        assert instance.version == ""
        assert instance.architecture == ArchitectureType.SINGLE
        assert instance.status == InstanceStatus.RUNNING
        assert instance.tags == {}

    def test_instance_info_optional_fields(self):
        """测试可选字段"""
        instance = InstanceInfo(
            id="inst-003",
            name="db-dev-01",
            host="localhost",
            region="cn-east-1",
            zone="zone-a",
            create_time="2024-01-01",
        )
        assert instance.region == "cn-east-1"
        assert instance.zone == "zone-a"
        assert instance.create_time == "2024-01-01"

    def test_architecture_types(self):
        """测试架构类型枚举"""
        assert ArchitectureType.SINGLE == "single"
        assert ArchitectureType.MASTER_SLAVE == "master_slave"
        assert ArchitectureType.CLUSTER == "cluster"
        assert ArchitectureType.MGR == "mgr"

    def test_instance_status_types(self):
        """测试实例状态枚举"""
        assert InstanceStatus.RUNNING == "running"
        assert InstanceStatus.STOPPED == "stopped"
        assert InstanceStatus.ABNORMAL == "abnormal"
        assert InstanceStatus.MAINTAINING == "maintaining"


class TestConnectionConfig:
    """连接配置模型测试"""

    def test_connection_config_creation(self):
        """测试创建连接配置"""
        config = ConnectionConfig(
            host="192.168.1.100",
            port=3306,
            user="admin",
            password="secret",
            database="mysql",
        )
        assert config.host == "192.168.1.100"
        assert config.port == 3306
        assert config.user == "admin"

    def test_connection_config_defaults(self):
        """测试默认值"""
        config = ConnectionConfig(host="localhost")
        assert config.port == 3306
        assert config.user == "root"
        assert config.database == "mysql"
        assert config.charset == "utf8mb4"

    def test_connection_string(self):
        """测试连接字符串生成"""
        config = ConnectionConfig(
            host="192.168.1.100",
            port=3306,
            user="admin",
            database="testdb",
        )
        conn_str = config.to_connection_string()
        assert conn_str == "mysql://admin@192.168.1.100:3306/testdb"
        assert "password" not in conn_str  # 不应包含密码


class TestSlowQueryRecord:
    """慢查询记录模型测试"""

    def test_slow_query_creation(self):
        """测试创建慢查询记录"""
        query = SlowQueryRecord(
            query_time=5.0,
            lock_time=0.1,
            rows_sent=10,
            rows_examined=10000,
            sql_text="SELECT * FROM orders WHERE user_id = 123",
            timestamp="2024-01-01 10:00:00",
            user="app_user",
            host="192.168.1.50",
        )
        assert query.query_time == 5.0
        assert query.rows_examined == 10000

    def test_slow_query_defaults(self):
        """测试默认值"""
        query = SlowQueryRecord(
            query_time=2.0,
            sql_text="SELECT 1",
        )
        assert query.lock_time == 0
        assert query.rows_sent == 0
        assert query.rows_examined == 0


class TestConnectionStatus:
    """连接状态模型测试"""

    def test_connection_status_creation(self):
        """测试创建连接状态"""
        status = ConnectionStatus(
            max_connections=1000,
            current_connections=500,
            active_connections=200,
            idle_connections=300,
        )
        assert status.max_connections == 1000
        assert status.current_connections == 500

    def test_connection_usage_ratio(self):
        """测试连接使用率计算"""
        status = ConnectionStatus(
            max_connections=100,
            current_connections=75,
        )
        assert status.connection_usage_ratio == 75.0

    def test_connection_usage_ratio_zero_max(self):
        """测试最大连接数为0的情况"""
        status = ConnectionStatus(
            max_connections=0,
            current_connections=50,
        )
        assert status.connection_usage_ratio == 0.0


class TestPerformanceMetrics:
    """性能指标模型测试"""

    def test_performance_metrics_creation(self):
        """测试创建性能指标"""
        metrics = PerformanceMetrics(
            qps=1200,
            tps=350,
            buffer_pool_hit_rate=99.5,
            thread_running=15,
        )
        assert metrics.qps == 1200
        assert metrics.tps == 350
        assert metrics.buffer_pool_hit_rate == 99.5

    def test_performance_metrics_defaults(self):
        """测试默认值"""
        metrics = PerformanceMetrics()
        assert metrics.qps == 0
        assert metrics.tps == 0
        assert metrics.buffer_pool_hit_rate == 0
        assert metrics.thread_running == 0


class TestStorageUsage:
    """存储使用情况模型测试"""

    def test_storage_usage_creation(self):
        """测试创建存储使用情况"""
        storage = StorageUsage(
            total_size_gb=100,
            used_size_gb=80,
            free_size_gb=20,
            usage_ratio=80.0,
            table_count=500,
            database_count=10,
        )
        assert storage.total_size_gb == 100
        assert storage.used_size_gb == 80

    def test_storage_usage_largest_tables(self):
        """测试最大表列表"""
        storage = StorageUsage(
            total_size_gb=50,
            used_size_gb=40,
            largest_tables=[
                {"schema_name": "prod", "table_name": "orders", "total_size_mb": 5000},
                {"schema_name": "prod", "table_name": "users", "total_size_mb": 2000},
            ],
        )
        assert len(storage.largest_tables) == 2
        assert storage.largest_tables[0]["table_name"] == "orders"


class TestTableStats:
    """表统计信息模型测试"""

    def test_table_stats_creation(self):
        """测试创建表统计信息"""
        stats = TableStats(
            schema_name="prod",
            table_name="orders",
            table_rows=100000,
            data_size_mb=500.0,
            index_size_mb=100.0,
            data_free_mb=50.0,
            engine="InnoDB",
        )
        assert stats.schema_name == "prod"
        assert stats.table_name == "orders"
        assert stats.table_rows == 100000
        assert stats.engine == "InnoDB"

    def test_table_stats_defaults(self):
        """测试默认值"""
        stats = TableStats(
            schema_name="test",
            table_name="test_table",
        )
        assert stats.table_rows == 0
        assert stats.data_size_mb == 0
        assert stats.index_size_mb == 0
        assert stats.engine == "InnoDB"


class TestParameterInfo:
    """参数信息模型测试"""

    def test_parameter_info_creation(self):
        """测试创建参数信息"""
        param = ParameterInfo(
            name="innodb_buffer_pool_size",
            value="8589934592",
            default_value="134217728",
            description="InnoDB缓冲池大小",
            is_dynamic=False,
            is_readonly=False,
            recommended_value="总内存的70-80%",
        )
        assert param.name == "innodb_buffer_pool_size"
        assert param.value == "8589934592"
        assert param.is_dynamic == False

    def test_parameter_info_defaults(self):
        """测试默认值"""
        param = ParameterInfo(
            name="max_connections",
            value="500",
        )
        assert param.default_value is None
        assert param.description is None
        assert param.is_dynamic == False
        assert param.is_readonly == False