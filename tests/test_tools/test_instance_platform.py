"""实例管理平台API客户端测试。"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import httpx

from rds_agent.data.instance_platform import (
    InstancePlatformClient,
    MockInstancePlatformClient,
    get_platform_client,
)
from rds_agent.data.models import InstanceInfo, InstanceStatus, ArchitectureType


class TestInstancePlatformClient:
    """实例管理平台API客户端测试"""

    @pytest.fixture
    def client_config(self):
        """客户端配置"""
        return {
            "base_url": "http://test-platform.example.com",
            "token": "test-token",
            "timeout": 30.0,
        }

    @pytest.fixture
    def mock_httpx_client(self):
        """Mock HTTP客户端"""
        client = MagicMock()
        return client

    def test_client_creation(self, client_config):
        """测试客户端创建"""
        client = InstancePlatformClient(**client_config)
        assert client.base_url == "http://test-platform.example.com"
        assert client.token == "test-token"
        assert client.timeout == 30.0

    def test_client_creation_from_settings(self):
        """测试从设置创建客户端"""
        with patch("rds_agent.data.instance_platform.settings") as mock_settings:
            mock_settings.instance_platform.url = "http://settings-platform.com"
            mock_settings.instance_platform.token = "settings-token"

            client = InstancePlatformClient()
            assert client.base_url == "http://settings-platform.com"

    @patch("httpx.Client")
    def test_list_instances_success(self, mock_httpx, client_config):
        """测试获取实例列表成功"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "inst-001",
                    "name": "db-prod-01",
                    "host": "192.168.1.100",
                    "port": 3306,
                    "version": "8.0.32",
                    "architecture": "master_slave",
                    "spec": "8C16G",
                    "storage_size": 500,
                    "status": "running",
                    "region": "cn-east-1",
                    "zone": "zone-a",
                },
            ]
        }
        mock_response.raise_for_status = Mock()

        mock_client_instance = MagicMock()
        mock_client_instance.request.return_value = mock_response
        mock_httpx.return_value = mock_client_instance

        client = InstancePlatformClient(**client_config)
        instances = client.list_instances()

        assert len(instances) == 1
        assert instances[0].id == "inst-001"
        assert instances[0].name == "db-prod-01"

    @patch("httpx.Client")
    def test_list_instances_empty(self, mock_httpx, client_config):
        """测试空实例列表"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": []}
        mock_response.raise_for_status = Mock()

        mock_client_instance = MagicMock()
        mock_client_instance.request.return_value = mock_response
        mock_httpx.return_value = mock_client_instance

        client = InstancePlatformClient(**client_config)
        instances = client.list_instances()

        assert len(instances) == 0

    @patch("httpx.Client")
    def test_list_instances_error(self, mock_httpx, client_config):
        """测试获取实例列表失败"""
        mock_client_instance = MagicMock()
        mock_client_instance.request.side_effect = httpx.HTTPError("Network error")
        mock_httpx.return_value = mock_client_instance

        client = InstancePlatformClient(**client_config)
        instances = client.list_instances()

        assert len(instances) == 0  # 错误时返回空列表

    @patch("httpx.Client")
    def test_get_instance_detail_success(self, mock_httpx, client_config):
        """测试获取实例详情成功"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": {
                "id": "inst-001",
                "name": "db-prod-01",
                "host": "192.168.1.100",
                "port": 3306,
                "version": "8.0.32",
                "architecture": "single",
                "spec": "4C8G",
                "status": "running",
            }
        }
        mock_response.raise_for_status = Mock()

        mock_client_instance = MagicMock()
        mock_client_instance.request.return_value = mock_response
        mock_httpx.return_value = mock_client_instance

        client = InstancePlatformClient(**client_config)
        instance = client.get_instance_detail("inst-001")

        assert instance is not None
        assert instance.id == "inst-001"

    @patch("httpx.Client")
    def test_get_instance_detail_not_found(self, mock_httpx, client_config):
        """测试实例不存在"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": {}}
        mock_response.raise_for_status = Mock()

        mock_client_instance = MagicMock()
        mock_client_instance.request.return_value = mock_response
        mock_httpx.return_value = mock_client_instance

        client = InstancePlatformClient(**client_config)
        instance = client.get_instance_detail("nonexistent")

        assert instance is None

    @patch("httpx.Client")
    def test_get_instance_connection_success(self, mock_httpx, client_config):
        """测试获取实例连接配置成功"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": {
                "host": "192.168.1.100",
                "port": 3306,
                "user": "admin",
                "password": "secret",
                "database": "mysql",
            }
        }
        mock_response.raise_for_status = Mock()

        mock_client_instance = MagicMock()
        mock_client_instance.request.return_value = mock_response
        mock_httpx.return_value = mock_client_instance

        client = InstancePlatformClient(**client_config)
        conn_config = client.get_instance_connection("inst-001")

        assert conn_config is not None
        assert conn_config.host == "192.168.1.100"
        assert conn_config.user == "admin"

    @patch("httpx.Client")
    def test_get_instance_metrics_success(self, mock_httpx, client_config):
        """测试获取实例监控指标成功"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": {
                "cpu_usage": 45.2,
                "memory_usage": 62.5,
                "disk_usage": 78.3,
                "qps": 1200,
                "tps": 350,
            }
        }
        mock_response.raise_for_status = Mock()

        mock_client_instance = MagicMock()
        mock_client_instance.request.return_value = mock_response
        mock_httpx.return_value = mock_client_instance

        client = InstancePlatformClient(**client_config)
        metrics = client.get_instance_metrics("inst-001")

        assert metrics["cpu_usage"] == 45.2
        assert metrics["qps"] == 1200

    def test_search_instance_by_name_exact(self, client_config):
        """测试精确匹配实例名称"""
        client = InstancePlatformClient(**client_config)

        with patch.object(client, "list_instances") as mock_list:
            mock_list.return_value = [
                InstanceInfo(id="1", name="db-prod-01", host="192.168.1.100"),
                InstanceInfo(id="2", name="db-prod-02", host="192.168.1.101"),
            ]

            result = client.search_instance_by_name("db-prod-01")
            assert result is not None
            assert result.name == "db-prod-01"

    def test_search_instance_by_name_fuzzy(self, client_config):
        """测试模糊匹配实例名称"""
        client = InstancePlatformClient(**client_config)

        with patch.object(client, "list_instances") as mock_list:
            mock_list.return_value = [
                InstanceInfo(id="1", name="db-prod-01", host="192.168.1.100"),
                InstanceInfo(id="2", name="db-test-01", host="192.168.2.100"),
            ]

            result = client.search_instance_by_name("prod")
            assert result is not None
            assert result.name == "db-prod-01"

    def test_search_instance_by_name_not_found(self, client_config):
        """测试未找到实例"""
        client = InstancePlatformClient(**client_config)

        with patch.object(client, "list_instances") as mock_list:
            mock_list.return_value = [
                InstanceInfo(id="1", name="db-prod-01", host="192.168.1.100"),
            ]

            result = client.search_instance_by_name("nonexistent")
            assert result is None

    def test_client_close(self, client_config):
        """测试关闭客户端"""
        client = InstancePlatformClient(**client_config)
        client._client = MagicMock()

        client.close()
        client._client.close.assert_called_once()
        assert client._client is None


class TestMockInstancePlatformClient:
    """Mock实例管理平台客户端测试"""

    @pytest.fixture
    def mock_client(self):
        """Mock客户端fixture"""
        return MockInstancePlatformClient()

    def test_mock_client_creation(self, mock_client):
        """测试Mock客户端创建"""
        assert mock_client is not None

    def test_list_instances(self, mock_client):
        """测试获取Mock实例列表"""
        instances = mock_client.list_instances()
        assert len(instances) == 3
        assert instances[0].name == "db-prod-01"
        assert instances[1].name == "db-prod-02"
        assert instances[2].name == "db-test-01"

    def test_get_instance_detail_found(self, mock_client):
        """测试获取Mock实例详情"""
        instance = mock_client.get_instance_detail("inst-001")
        assert instance is not None
        assert instance.name == "db-prod-01"

    def test_get_instance_detail_not_found(self, mock_client):
        """测试Mock实例不存在"""
        instance = mock_client.get_instance_detail("nonexistent")
        assert instance is None

    def test_get_instance_connection_found(self, mock_client):
        """测试获取Mock连接配置"""
        conn = mock_client.get_instance_connection("inst-001")
        assert conn is not None
        assert conn.host == "192.168.1.100"
        assert conn.user == "admin"

    def test_get_instance_connection_not_found(self, mock_client):
        """测试Mock连接配置不存在"""
        conn = mock_client.get_instance_connection("nonexistent")
        assert conn is None

    def test_get_instance_metrics(self, mock_client):
        """测试获取Mock监控指标"""
        metrics = mock_client.get_instance_metrics("inst-001")
        assert "cpu_usage" in metrics
        assert "qps" in metrics

    def test_search_instance_exact(self, mock_client):
        """测试Mock精确搜索"""
        instance = mock_client.search_instance_by_name("db-prod-01")
        assert instance is not None
        assert instance.name == "db-prod-01"

    def test_search_instance_by_id(self, mock_client):
        """测试Mock通过ID搜索"""
        instance = mock_client.search_instance_by_name("inst-001")
        assert instance is not None
        assert instance.id == "inst-001"

    def test_search_instance_fuzzy(self, mock_client):
        """测试Mock模糊搜索"""
        instance = mock_client.search_instance_by_name("prod")
        assert instance is not None
        # 返回第一个匹配的
        assert "prod" in instance.name.lower()

    def test_mock_close(self, mock_client):
        """测试Mock客户端关闭"""
        mock_client.close()  # 无操作，不应抛出异常


class TestGetPlatformClient:
    """获取平台客户端函数测试"""

    def test_get_platform_client_with_mock(self):
        """测试使用Mock客户端"""
        client = get_platform_client(use_mock=True)
        assert isinstance(client, MockInstancePlatformClient)

    def test_get_platform_client_without_url(self):
        """测试无URL时使用Mock"""
        with patch("rds_agent.data.instance_platform.settings") as mock_settings:
            mock_settings.instance_platform.url = ""
            client = get_platform_client()
            assert isinstance(client, MockInstancePlatformClient)

    def test_get_platform_client_with_url(self):
        """测试有URL时使用真实客户端"""
        with patch("rds_agent.data.instance_platform.settings") as mock_settings:
            mock_settings.instance_platform.url = "http://test-platform.com"
            client = get_platform_client()
            assert isinstance(client, InstancePlatformClient)