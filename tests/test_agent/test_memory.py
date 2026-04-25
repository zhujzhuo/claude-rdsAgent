"""Agent 记忆系统测试。"""

import pytest
from unittest.mock import Mock, MagicMock

from rds_agent.agent.memory import (
    AgentMemory,
    MemoryStore,
    MemoryEntry,
    MemoryType,
    MemoryPriority,
    MemoryConfig,
    LearningSystem,
)


class TestAgentMemory:
    """Agent 记忆系统测试"""

    @pytest.fixture
    def memory(self):
        """创建记忆系统"""
        return AgentMemory(enable_learning=True)

    def test_memory_creation(self):
        """测试创建记忆系统"""
        memory = AgentMemory()
        assert memory.store is not None

    def test_add_execution_memory(self, memory):
        """测试添加执行记忆"""
        memory.add_execution_memory(
            iteration=1,
            tool_name="get_monitoring_data",
            tool_result={"cpu": "85%"},
            response="CPU 使用率正常",
            query="检查 CPU",
        )

        stats = memory.get_stats()
        assert stats["total_entries"] >= 1

    def test_add_reflection_memory(self, memory):
        """测试添加反思记忆"""
        memory.add_reflection_memory(
            iteration=1,
            analysis="响应质量良好",
            issues=["缺少细节"],
            improvements=["补充具体数值"],
            query="诊断问题",
        )

        reflections = memory.store.get_by_type(MemoryType.REFLECTION)
        assert len(reflections) >= 1

    def test_add_evaluation_memory(self, memory):
        """测试添加评估记忆"""
        memory.add_evaluation_memory(
            iteration=1,
            score=0.85,
            passed=True,
            criteria={"completeness": 0.9, "accuracy": 0.8},
            query="分析 CPU",
        )

        evaluations = memory.store.get_by_type(MemoryType.EVALUATION)
        assert len(evaluations) >= 1

    def test_add_error_memory(self, memory):
        """测试添加错误记忆"""
        memory.add_error_memory(
            iteration=1,
            error="工具调用超时",
            error_type="timeout",
            resolution="增加超时时间",
            query="检查实例",
        )

        errors = memory.store.get_by_type(MemoryType.ERROR)
        assert len(errors) >= 1

    def test_add_success_memory(self, memory):
        """测试添加成功记忆"""
        memory.add_success_memory(
            iteration=1,
            query="CPU 分析",
            query_type="cpu_analysis",
            tools=["get_cpu_monitoring", "get_slow_queries"],
            strategy="先获取监控数据，再分析慢 SQL",
        )

        successes = memory.store.get_by_type(MemoryType.SUCCESS)
        assert len(successes) >= 1

    def test_get_relevant_memories(self, memory):
        """测试获取相关记忆"""
        memory.add_execution_memory(
            iteration=1,
            tool_name="get_cpu",
            tool_result={"cpu": "85%"},
            response="CPU 高",
            query="CPU 分析",
        )
        memory.add_execution_memory(
            iteration=2,
            tool_name="get_memory",
            tool_result={"mem": "60%"},
            response="内存正常",
            query="内存分析",
        )

        relevant = memory.get_relevant_memories("CPU")
        assert len(relevant) >= 1

    def test_get_context_for_iteration(self, memory):
        """测试获取迭代上下文"""
        memory.add_execution_memory(
            iteration=1,
            tool_name="get_cpu",
            tool_result="85%",
            response="CPU 使用率 85%",
            query="CPU 分析",
        )

        context = memory.get_context_for_iteration(1)
        assert "recent_memories" in context
        assert "working_memory" in context

    def test_update_working_memory(self, memory):
        """测试更新工作记忆"""
        memory.update_working_memory("instance", "db-prod-01")
        memory.update_working_memory("region", "cn-east")

        assert memory.get_working_memory("instance") == "db-prod-01"
        assert memory.get_working_memory("region") == "cn-east"

    def test_clear_working_memory(self, memory):
        """测试清空工作记忆"""
        memory.update_working_memory("key", "value")
        memory.clear_working_memory()

        assert memory.get_working_memory("key") is None

    def test_learn_from_memories(self, memory):
        """测试从记忆学习"""
        memory.add_execution_memory(
            iteration=1,
            tool_name="get_cpu",
            tool_result="85%",
            response="CPU 高",
            query="CPU 分析",
        )
        memory.add_success_memory(
            iteration=1,
            query="CPU 分析",
            query_type="cpu_analysis",
            tools=["get_cpu"],
            strategy="先获取数据",
        )

        patterns = memory.learn_from_memories()
        # 学习后应该有模式（如果记忆足够）
        assert isinstance(patterns, dict)

    def test_memory_reset(self, memory):
        """测试重置记忆"""
        memory.add_execution_memory(
            iteration=1,
            tool_name="get_cpu",
            tool_result="85%",
            response="CPU",
            query="分析",
        )

        memory.reset()
        stats = memory.get_stats()
        assert stats["total_entries"] == 0


class TestMemoryStore:
    """记忆存储测试"""

    @pytest.fixture
    def store(self):
        """创建记忆存储"""
        return MemoryStore()

    def test_store_creation(self):
        """测试创建存储"""
        store = MemoryStore()
        assert len(store._entries) == 0

    def test_add_entry(self, store):
        """测试添加条目"""
        entry = MemoryEntry(
            content="执行结果",
            memory_type=MemoryType.EXECUTION,
            iteration=1,
        )

        store.add(entry)
        assert len(store._entries) == 1

    def test_get_by_type(self, store):
        """测试按类型获取"""
        entry1 = MemoryEntry(content="执行", memory_type=MemoryType.EXECUTION)
        entry2 = MemoryEntry(content="反思", memory_type=MemoryType.REFLECTION)

        store.add(entry1)
        store.add(entry2)

        executions = store.get_by_type(MemoryType.EXECUTION)
        assert len(executions) == 1

    def test_get_by_tag(self, store):
        """测试按标签获取"""
        entry = MemoryEntry(
            content="执行",
            memory_type=MemoryType.EXECUTION,
            tags={"cpu", "monitoring"},
        )

        store.add(entry)

        cpu_memories = store.get_by_tag("cpu")
        assert len(cpu_memories) == 1

    def test_get_recent(self, store):
        """测试获取最近记忆"""
        for i in range(5):
            entry = MemoryEntry(
                content=f"记忆{i}",
                memory_type=MemoryType.EXECUTION,
            )
            store.add(entry)

        recent = store.get_recent(limit=3)
        assert len(recent) == 3

    def test_search(self, store):
        """测试搜索记忆"""
        entry1 = MemoryEntry(content="CPU 使用率分析", memory_type=MemoryType.EXECUTION)
        entry2 = MemoryEntry(content="内存使用情况", memory_type=MemoryType.EXECUTION)

        store.add(entry1)
        store.add(entry2)

        results = store.search("CPU")
        assert len(results) >= 1
        assert "CPU" in results[0].content

    def test_get_stats(self, store):
        """测试获取统计"""
        entry = MemoryEntry(content="执行", memory_type=MemoryType.EXECUTION)
        store.add(entry)

        stats = store.get_stats()
        assert stats["total_entries"] == 1


class TestMemoryEntry:
    """记忆条目测试"""

    def test_entry_creation(self):
        """测试创建条目"""
        entry = MemoryEntry(
            content="执行结果",
            memory_type=MemoryType.EXECUTION,
            priority=MemoryPriority.HIGH,
            iteration=1,
            tags={"cpu", "analysis"},
        )

        assert entry.content == "执行结果"
        assert entry.memory_type == MemoryType.EXECUTION
        assert entry.priority == MemoryPriority.HIGH

    def test_entry_access(self):
        """测试条目访问"""
        entry = MemoryEntry(content="内容", memory_type=MemoryType.EXECUTION)

        content = entry.access()
        assert content == "内容"
        assert entry.access_count == 1

    def test_entry_to_dict(self):
        """测试条目转字典"""
        entry = MemoryEntry(
            content="内容",
            memory_type=MemoryType.EXECUTION,
            iteration=1,
            tags={"test"},
        )

        dict_entry = entry.to_dict()
        assert dict_entry["content"] == "内容"
        assert dict_entry["memory_type"] == "execution"


class TestMemoryConfig:
    """记忆配置测试"""

    def test_config_defaults(self):
        """测试默认配置"""
        config = MemoryConfig()

        assert config.max_entries == 1000
        assert config.max_short_term == 100
        assert config.enable_learning == True

    def test_config_custom(self):
        """测试自定义配置"""
        config = MemoryConfig(
            max_entries=500,
            enable_learning=False,
        )

        assert config.max_entries == 500
        assert config.enable_learning == False


class TestLearningSystem:
    """学习系统测试"""

    @pytest.fixture
    def learning(self):
        """创建学习系统"""
        return LearningSystem()

    def test_learning_creation(self):
        """测试创建学习系统"""
        learning = LearningSystem()
        assert len(learning._learned_patterns) == 0

    def test_extract_tool_sequences(self, learning):
        """测试提取工具序列"""
        memories = [
            MemoryEntry(
                content="执行 get_cpu",
                memory_type=MemoryType.EXECUTION,
                tool_name="get_cpu",
            ),
            MemoryEntry(
                content="执行 analyze_sql",
                memory_type=MemoryType.EXECUTION,
                tool_name="analyze_sql",
            ),
        ]

        patterns = learning.extract_patterns(memories)
        # 应该提取到工具序列模式
        assert isinstance(patterns, dict)

    def test_get_learned_patterns(self, learning):
        """测试获取学习模式"""
        patterns = learning.get_learned_patterns()
        assert isinstance(patterns, dict)


class TestMemoryType:
    """记忆类型枚举测试"""

    def test_memory_types(self):
        """测试记忆类型"""
        assert MemoryType.EXECUTION.value == "execution"
        assert MemoryType.REFLECTION.value == "reflection"
        assert MemoryType.EVALUATION.value == "evaluation"
        assert MemoryType.LEARNING.value == "learning"


class TestMemoryPriority:
    """记忆优先级枚举测试"""

    def test_memory_priorities(self):
        """测试记忆优先级"""
        assert MemoryPriority.HIGH.value == "high"
        assert MemoryPriority.MEDIUM.value == "medium"
        assert MemoryPriority.LOW.value == "low"