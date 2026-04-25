"""Agent 记忆系统 - 存储执行历史、反思和学习内容

记忆系统让 Agent 能够：
1. 记住过去的执行经验
2. 从反思中学习
3. 优化后续执行策略
4. 积累领域知识

参考 Hermes Agent 的记忆架构设计
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from collections import defaultdict

from pydantic import BaseModel, Field

from rds_agent.utils.logger import get_logger

logger = get_logger("agent_memory")


class MemoryType(str, Enum):
    """记忆类型"""

    EXECUTION = "execution"        # 执行记忆：工具调用、响应
    REFLECTION = "reflection"      # 反思记忆：分析、改进建议
    EVALUATION = "evaluation"      # 评估记忆：评分、质量
    CONTEXT = "context"            # 上下文记忆：环境信息
    LEARNING = "learning"          # 学习记忆：提取的模式、规则
    ERROR = "error"                # 错误记忆：错误信息和处理
    SUCCESS = "success"            # 成功记忆：成功的模式


class MemoryPriority(str, Enum):
    """记忆优先级"""

    HIGH = "high"          # 高优先级：关键错误、重要学习
    MEDIUM = "medium"      # 中优先级：常规执行、反思
    LOW = "low"            # 低优先级：一般信息


@dataclass
class MemoryEntry:
    """记忆条目"""

    # 内容
    content: str
    memory_type: MemoryType
    priority: MemoryPriority = MemoryPriority.MEDIUM

    # 元数据
    iteration: int = 0
    timestamp: datetime = field(default_factory=datetime.now)

    # 关联
    query: Optional[str] = None
    response: Optional[str] = None
    tool_name: Optional[str] = None

    # 标签
    tags: Set[str] = field(default_factory=set)

    # 附加数据
    metadata: Dict[str, Any] = field(default_factory=dict)

    # 使用次数
    access_count: int = 0

    def access(self) -> str:
        """访问记忆"""
        self.access_count += 1
        return self.content

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "content": self.content,
            "memory_type": self.memory_type.value,
            "priority": self.priority.value,
            "iteration": self.iteration,
            "timestamp": self.timestamp.isoformat(),
            "query": self.query,
            "tool_name": self.tool_name,
            "tags": list(self.tags),
            "access_count": self.access_count,
        }


class MemoryConfig(BaseModel):
    """记忆配置"""

    # 容量限制
    max_entries: int = Field(default=1000, description="最大记忆条目数")
    max_short_term: int = Field(default=100, description="短期记忆容量")
    max_long_term: int = Field(default=500, description="长期记忆容量")

    # 检索配置
    retrieval_top_k: int = Field(default=10, description="检索返回数量")
    similarity_threshold: float = Field(default=0.7, description="相似度阈值")

    # 衰减配置
    decay_rate: float = Field(default=0.1, description="记忆衰减率")
    importance_boost: float = Field(default=0.2, description="重要性加成")

    # 学习配置
    enable_learning: bool = Field(default=True, description="启用学习提取")
    learning_threshold: int = Field(default=3, description="学习阈值（出现次数")


class MemoryStore:
    """记忆存储 - 管理记忆的存储和检索"""

    def __init__(self, config: Optional[MemoryConfig] = None):
        """初始化记忆存储

        Args:
            config: 记忆配置
        """
        self.config = config or MemoryConfig()

        # 记忆存储
        self._entries: List[MemoryEntry] = []

        # 分类索引
        self._type_index: Dict[MemoryType, List[MemoryEntry]] = defaultdict(list)
        self._tag_index: Dict[str, List[MemoryEntry]] = defaultdict(list)
        self._tool_index: Dict[str, List[MemoryEntry]] = defaultdict(list)

        # 统计
        self._stats = {
            "total_entries": 0,
            "type_counts": defaultdict(int),
            "access_counts": 0,
        }

        logger.info(
            f"MemoryStore initialized: max_entries={self.config.max_entries}"
        )

    def add(self, entry: MemoryEntry) -> bool:
        """添加记忆

        Args:
            entry: 记忆条目

        Returns:
            是否成功添加
        """
        # 检查容量
        if len(self._entries) >= self.config.max_entries:
            self._evict_low_priority()

        # 添加到主存储
        self._entries.append(entry)

        # 更新索引
        self._type_index[entry.memory_type].append(entry)
        for tag in entry.tags:
            self._tag_index[tag].append(entry)
        if entry.tool_name:
            self._tool_index[entry.tool_name].append(entry)

        # 更新统计
        self._stats["total_entries"] += 1
        self._stats["type_counts"][entry.memory_type] += 1

        logger.debug(
            f"Memory added: type={entry.memory_type}, "
            f"priority={entry.priority}, total={len(self._entries)}"
        )

        return True

    def get_by_type(self, memory_type: MemoryType) -> List[MemoryEntry]:
        """按类型获取记忆"""
        return self._type_index.get(memory_type, [])

    def get_by_tag(self, tag: str) -> List[MemoryEntry]:
        """按标签获取记忆"""
        return self._tag_index.get(tag, [])

    def get_by_tool(self, tool_name: str) -> List[MemoryEntry]:
        """按工具获取记忆"""
        return self._tool_index.get(tool_name, [])

    def get_recent(self, limit: int = 10) -> List[MemoryEntry]:
        """获取最近记忆"""
        return sorted(
            self._entries,
            key=lambda e: e.timestamp,
            reverse=True
        )[:limit]

    def get_important(self, limit: int = 10) -> List[MemoryEntry]:
        """获取重要记忆"""
        # 综合考虑优先级和访问次数
        scored_entries = []
        for entry in self._entries:
            score = 0
            if entry.priority == MemoryPriority.HIGH:
                score += 3
            elif entry.priority == MemoryPriority.MEDIUM:
                score += 2
            else:
                score += 1
            score += entry.access_count * 0.1
            # 使用 (score, index) 作为排序键，避免 MemoryEntry 比较
            scored_entries.append((score, len(scored_entries), entry))

        # 按 score 降序排序
        sorted_entries = sorted(scored_entries, key=lambda x: (x[0], x[1]), reverse=True)
        return [e for _, _, e in sorted_entries][:limit]

    def search(self, query: str, top_k: int = 5) -> List[MemoryEntry]:
        """搜索记忆"""
        # 简化的搜索：基于关键词匹配
        query_lower = query.lower()
        scored_entries = []

        for entry in self._entries:
            score = 0
            # 内容匹配
            if query_lower in entry.content.lower():
                score += 2
            # 标签匹配
            for tag in entry.tags:
                if query_lower in tag.lower():
                    score += 1
            # 工具匹配
            if entry.tool_name and query_lower in entry.tool_name.lower():
                score += 1

            if score > 0:
                # 优先级加成
                if entry.priority == MemoryPriority.HIGH:
                    score += 1
                scored_entries.append((score, entry))

        # 排序返回
        return [e for _, e in sorted(scored_entries, reverse=True)][:top_k]

    def _evict_low_priority(self) -> None:
        """淘汰低优先级记忆"""
        # 按优先级和访问次数排序
        sorted_entries = sorted(
            self._entries,
            key=lambda e: (
                e.priority.value,
                e.access_count,
                e.timestamp
            )
        )

        # 移除最不重要的
        evict_count = max(1, int(self.config.decay_rate * len(self._entries)))
        for entry in sorted_entries[:evict_count]:
            self._remove_entry(entry)

        logger.info(f"Evicted {evict_count} low priority memories")

    def _remove_entry(self, entry: MemoryEntry) -> None:
        """移除记忆条目"""
        if entry in self._entries:
            self._entries.remove(entry)
            self._type_index[entry.memory_type].remove(entry)
            for tag in entry.tags:
                if entry in self._tag_index[tag]:
                    self._tag_index[tag].remove(entry)
            if entry.tool_name and entry in self._tool_index[entry.tool_name]:
                self._tool_index[entry.tool_name].remove(entry)

    def clear(self) -> None:
        """清空记忆"""
        self._entries.clear()
        self._type_index.clear()
        self._tag_index.clear()
        self._tool_index.clear()
        self._stats["total_entries"] = 0

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_entries": len(self._entries),
            "type_counts": dict(self._stats["type_counts"]),
            "access_counts": self._stats["access_counts"],
            "top_tags": sorted(
                [(tag, len(entries)) for tag, entries in self._tag_index.items()],
                key=lambda x: x[1],
                reverse=True
            )[:10],
        }


class LearningSystem:
    """学习系统 - 从记忆中提取模式和规则"""

    def __init__(self, config: Optional[MemoryConfig] = None):
        """初始化学习系统

        Args:
            config: 记忆配置
        """
        self.config = config or MemoryConfig()
        self._learned_patterns: Dict[str, Any] = {}
        self._pattern_counts: Dict[str, int] = defaultdict(int)

    def extract_patterns(self, memories: List[MemoryEntry]) -> Dict[str, Any]:
        """从记忆中提取模式

        Args:
            memories: 记忆列表

        Returns:
            提取的模式
        """
        patterns = {}

        # 提取工具使用模式
        tool_sequences = self._extract_tool_sequences(memories)
        if tool_sequences:
            patterns["tool_sequences"] = tool_sequences

        # 提取错误模式
        error_patterns = self._extract_error_patterns(memories)
        if error_patterns:
            patterns["error_patterns"] = error_patterns

        # 提取成功模式
        success_patterns = self._extract_success_patterns(memories)
        if success_patterns:
            patterns["success_patterns"] = success_patterns

        # 更新学习记录
        for key, value in patterns.items():
            self._learned_patterns[key] = value
            self._pattern_counts[key] += 1

        return patterns

    def _extract_tool_sequences(self, memories: List[MemoryEntry]) -> List[List[str]]:
        """提取工具调用序列"""
        sequences = []
        current_sequence = []

        for memory in memories:
            if memory.memory_type == MemoryType.EXECUTION and memory.tool_name:
                current_sequence.append(memory.tool_name)
            else:
                if len(current_sequence) >= 2:
                    sequences.append(current_sequence)
                current_sequence = []

        if len(current_sequence) >= 2:
            sequences.append(current_sequence)

        # 统计重复序列
        sequence_counts = defaultdict(int)
        for seq in sequences:
            seq_key = "->".join(seq)
            sequence_counts[seq_key] += 1

        # 返回高频序列
        return [seq for seq, count in sequence_counts.items()
                if count >= self.config.learning_threshold]

    def _extract_error_patterns(self, memories: List[MemoryEntry]) -> Dict[str, List[str]]:
        """提取错误模式"""
        error_patterns = {}

        for memory in memories:
            if memory.memory_type == MemoryType.ERROR:
                error_type = memory.metadata.get("error_type", "unknown")
                if error_type not in error_patterns:
                    error_patterns[error_type] = []

                # 记录错误处理方式
                if memory.metadata.get("resolution"):
                    error_patterns[error_type].append(memory.metadata["resolution"])

        return error_patterns

    def _extract_success_patterns(self, memories: List[MemoryEntry]) -> Dict[str, Any]:
        """提取成功模式"""
        success_patterns = {}

        for memory in memories:
            if memory.memory_type == MemoryType.SUCCESS:
                query_type = memory.metadata.get("query_type", "general")
                if query_type not in success_patterns:
                    success_patterns[query_type] = {
                        "tools": [],
                        "strategies": [],
                    }

                # 记录成功的工具和策略
                if memory.tool_name:
                    success_patterns[query_type]["tools"].append(memory.tool_name)
                if memory.metadata.get("strategy"):
                    success_patterns[query_type]["strategies"].append(
                        memory.metadata["strategy"]
                    )

        return success_patterns

    def get_learned_patterns(self) -> Dict[str, Any]:
        """获取学习到的模式"""
        return self._learned_patterns

    def get_recommendations(self, query_type: str) -> List[str]:
        """获取推荐"""
        recommendations = []

        # 基于成功模式推荐
        success_patterns = self._learned_patterns.get("success_patterns", {})
        if query_type in success_patterns:
            tools = success_patterns[query_type].get("tools", [])
            if tools:
                recommendations.append(f"推荐工具: {', '.join(tools[:3])}")

        # 基于工具序列推荐
        tool_sequences = self._learned_patterns.get("tool_sequences", [])
        if tool_sequences:
            recommendations.append(f"推荐工具序列: {tool_sequences[0]}")

        return recommendations


class AgentMemory:
    """Agent 记忆系统 - 综合记忆管理

    功能：
    1. 存储执行、反思、评估记忆
    2. 从记忆中学习和提取模式
    3. 提供记忆检索和推荐
    4. 支持记忆衰减和淘汰

    记忆分层：
    - 短期记忆：当前会话相关
    - 长期记忆：历史经验积累
    - 工作记忆：当前任务相关
    """

    def __init__(
        self,
        config: Optional[MemoryConfig] = None,
        enable_learning: bool = True,
    ):
        """初始化记忆系统

        Args:
            config: 记忆配置
            enable_learning: 是否启用学习
        """
        self.config = config or MemoryConfig()
        self.store = MemoryStore(self.config)
        self.learning = LearningSystem(self.config) if enable_learning else None

        # 工作记忆
        self._working_memory: Dict[str, Any] = {}

        logger.info(
            f"AgentMemory initialized: enable_learning={enable_learning}"
        )

    def add_execution_memory(
        self,
        iteration: int,
        tool_name: str,
        tool_result: Any,
        response: str,
        query: str,
    ) -> None:
        """添加执行记忆"""
        entry = MemoryEntry(
            content=f"Tool: {tool_name}, Result: {str(tool_result)[:200]}",
            memory_type=MemoryType.EXECUTION,
            iteration=iteration,
            tool_name=tool_name,
            query=query,
            response=response,
            tags={"execution", tool_name},
            metadata={"result_preview": str(tool_result)[:500]},
        )
        self.store.add(entry)

    def add_reflection_memory(
        self,
        iteration: int,
        analysis: str,
        issues: List[str],
        improvements: List[str],
        query: str,
    ) -> None:
        """添加反思记忆"""
        entry = MemoryEntry(
            content=analysis,
            memory_type=MemoryType.REFLECTION,
            priority=MemoryPriority.HIGH,
            iteration=iteration,
            query=query,
            tags={"reflection"},
            metadata={
                "issues": issues,
                "improvements": improvements,
            },
        )
        self.store.add(entry)

    def add_evaluation_memory(
        self,
        iteration: int,
        score: float,
        passed: bool,
        criteria: Dict[str, float],
        query: str,
    ) -> None:
        """添加评估记忆"""
        entry = MemoryEntry(
            content=f"Score: {score}, Passed: {passed}",
            memory_type=MemoryType.EVALUATION,
            priority=MemoryPriority.HIGH if passed else MemoryPriority.MEDIUM,
            iteration=iteration,
            query=query,
            tags={"evaluation"},
            metadata={
                "score": score,
                "passed": passed,
                "criteria": criteria,
            },
        )
        self.store.add(entry)

    def add_error_memory(
        self,
        iteration: int,
        error: str,
        error_type: str,
        resolution: Optional[str] = None,
        query: str = None,
    ) -> None:
        """添加错误记忆"""
        entry = MemoryEntry(
            content=error,
            memory_type=MemoryType.ERROR,
            priority=MemoryPriority.HIGH,
            iteration=iteration,
            query=query,
            tags={"error", error_type},
            metadata={
                "error_type": error_type,
                "resolution": resolution,
            },
        )
        self.store.add(entry)

    def add_success_memory(
        self,
        iteration: int,
        query: str,
        query_type: str,
        tools: List[str],
        strategy: str,
    ) -> None:
        """添加成功记忆"""
        entry = MemoryEntry(
            content=f"Success: {query_type}",
            memory_type=MemoryType.SUCCESS,
            priority=MemoryPriority.HIGH,
            iteration=iteration,
            query=query,
            tags={"success", query_type},
            metadata={
                "query_type": query_type,
                "tools": tools,
                "strategy": strategy,
            },
        )
        self.store.add(entry)

    def get_relevant_memories(self, query: str) -> List[MemoryEntry]:
        """获取相关记忆"""
        # 搜索相关记忆
        relevant = self.store.search(query, top_k=self.config.retrieval_top_k)

        # 补充最近重要记忆
        important = self.store.get_important(limit=5)
        for entry in important:
            if entry not in relevant:
                relevant.append(entry)

        return relevant

    def get_context_for_iteration(self, iteration: int) -> Dict[str, Any]:
        """为迭代准备上下文"""
        context = {
            "recent_memories": [
                e.to_dict() for e in self.store.get_recent(limit=10)
            ],
            "important_memories": [
                e.to_dict() for e in self.store.get_important(limit=5)
            ],
            "learned_patterns": self.learning.get_learned_patterns() if self.learning else {},
        }

        # 添加工作记忆
        context["working_memory"] = self._working_memory

        # 添加推荐
        if self.learning:
            recommendations = self.learning.get_recommendations("general")
            context["recommendations"] = recommendations

        return context

    def update_working_memory(self, key: str, value: Any) -> None:
        """更新工作记忆"""
        self._working_memory[key] = value

    def get_working_memory(self, key: str) -> Optional[Any]:
        """获取工作记忆"""
        return self._working_memory.get(key)

    def clear_working_memory(self) -> None:
        """清空工作记忆"""
        self._working_memory.clear()

    def learn_from_memories(self) -> Dict[str, Any]:
        """从记忆中学习"""
        if not self.learning:
            return {}

        # 获取所有记忆
        all_memories = self.store.get_recent(limit=self.config.max_entries)

        # 提取模式
        patterns = self.learning.extract_patterns(all_memories)

        logger.info(f"Learning completed: patterns={len(patterns)}")

        return patterns

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = self.store.get_stats()
        if self.learning:
            stats["learned_patterns"] = len(self.learning.get_learned_patterns())
        return stats

    def reset(self) -> None:
        """重置记忆系统"""
        self.store.clear()
        self._working_memory.clear()
        if self.learning:
            self.learning._learned_patterns.clear()
            self.learning._pattern_counts.clear()


def create_memory(
    max_entries: int = 1000,
    enable_learning: bool = True,
) -> AgentMemory:
    """创建记忆系统"""
    config = MemoryConfig(max_entries=max_entries)
    return AgentMemory(config=config, enable_learning=enable_learning)