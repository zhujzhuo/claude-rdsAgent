"""调度器模块测试配置。"""

import pytest
from unittest.mock import Mock, patch


@pytest.fixture(autouse=True)
def mock_diagnostic_agent():
    """自动模拟诊断Agent"""
    with patch("rds_agent.scheduler.executor.get_diagnostic_agent") as mock:
        mock_result = Mock()
        mock_result.overall_score = 85
        mock_result.overall_status = Mock(value="healthy")
        mock_result.critical_issues = []
        mock_result.warnings = []
        mock_result.suggestions = []
        mock.return_value.run.return_value = mock_result
        yield mock


@pytest.fixture(autouse=True)
def mock_report_generator():
    """自动模拟报告生成器"""
    with patch("rds_agent.scheduler.executor.get_report_generator") as mock:
        mock_report = Mock()
        mock_report.save_report.return_value = Mock()
        mock.return_value = mock_report
        yield mock