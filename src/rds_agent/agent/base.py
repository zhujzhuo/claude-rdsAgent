"""Agent 基类 - 支持自我迭代的智能 Agent 核心定义。

基于 Hermes Agent 架构设计，核心特性：
- Function Calling 工具调用
- 自我反思机制（Reflection）
- 迭代改进循环（Iteration Loop）
- 结果评估（Evaluation）
- 记忆系统（Memory）

参考：NousResearch Hermes Agent
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar, Union

from pydantic import BaseModel, Field

from rds_agent.utils.logger import get_logger
from rds_agent.utils.config import get_settings

logger = get_logger("agent_base")


class IterationStrategy(str, Enum):
    """迭代策略"""

    NONE = "none"                    # 不迭代，单次执行
    CONSERVATIVE = "conservative"    # 保守型：仅当评估不合格时迭代
    AGGRESSIVE = "aggressive"        # 激进型：总是尝试迭代改进
    BALANCED = "balanced"            # 平衡型：根据评估结果动态决定
    SKILL_BASED = "skill_based"      # SOP/Skill 驱动迭代


class AgentStatus(str, Enum):
    """Agent 执行状态"""

    IDLE = "idle"                    # 空闲
    EXECUTING = "executing"          # 执行中
    EVALUATING = "evaluating"        # 评估中
    REFLECTING = "reflecting"        # 反思中
    ITERATING = "iterating"          # 迭代中
    COMPLETED = "completed"          # 完成
    FAILED = "failed"                # 失败


@dataclass
class AgentConfig:
    """Agent 配置"""

    # 模型配置
    model: str = "hermes3"
    temperature: float = 0.7
    max_tokens: int = 4096

    # 迭代配置
    iteration_strategy: IterationStrategy = IterationStrategy.BALANCED
    max_iterations: int = 5
    min_quality_score: float = 0.7  # 最低质量阈值

    # 反思配置
    enable_reflection: bool = True
    reflection_depth: int = 2  # 反思深度（分析层级）

    # 工具配置
    max_tool_calls_per_iteration: int = 10
    tool_timeout: float = 30.0

    # 记忆配置
    enable_memory: bool = True
    memory_max_entries: int = 100

    # 调试配置
    debug_mode: bool = False
    log_iterations: bool = True


def get_agent_config() -> AgentConfig:
    """获取默认 Agent 配置"""
    settings = get_settings()

    # 根据配置选择迭代策略
    strategy_str = getattr(settings.agent, "iteration_strategy", "balanced")
    strategy = IterationStrategy(strategy_str)

    return AgentConfig(
        model=settings.hermes.model,
        temperature=0.7,
        iteration_strategy=strategy,
        max_iterations=settings.agent.max_iterations,
        enable_reflection=True,
        enable_memory=True,
        debug_mode=settings.debug,
    )


class AgentResult(BaseModel):
    """Agent 执行结果"""

    # 基本信息
    agent_id: str = Field(default="", description="Agent ID")
    agent_type: str = Field(default="", description="Agent 类型")
    query: str = Field(default="", description="原始查询")

    # 执行结果
    response: str = Field(default="", description="最终响应")
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list, description="工具调用记录")
    tool_results: List[Dict[str, Any]] = Field(default_factory=list, description="工具执行结果")

    # 迭代信息
    iterations: int = Field(default=0, description="迭代次数")
    iteration_history: List[Dict[str, Any]] = Field(default_factory=list, description="迭代历史")
    termination_reason: str = Field(default="", description="终止原因")

    # 评估信息
    quality_score: float = Field(default=0.0, description="质量评分")
    evaluation_details: Dict[str, Any] = Field(default_factory=dict, description="评估详情")

    # 反思信息
    reflections: List[str] = Field(default_factory=list, description="反思内容")
    improvements: List[str] = Field(default_factory=list, description="改进措施")

    # 状态
    success: bool = Field(default=False, description="是否成功")
    error: Optional[str] = Field(default=None, description="错误信息")

    # 时间信息
    start_time: datetime = Field(default_factory=datetime.now, description="开始时间")
    end_time: Optional[datetime] = Field(default=None, description="结束时间")
    duration_ms: float = Field(default=0.0, description="执行时长(ms)")

    def mark_completed(self) -> None:
        """标记完成"""
        self.end_time = datetime.now()
        if self.start_time:
            self.duration_ms = (self.end_time - self.start_time).total_seconds() * 1000
        self.success = not self.error

    def to_summary(self) -> str:
        """生成摘要"""
        lines = [
            f"Agent Result Summary",
            f"- Query: {self.query[:50]}...",
            f"- Response: {self.response[:100]}...",
            f"- Iterations: {self.iterations}",
            f"- Quality Score: {self.quality_score:.2f}",
            f"- Success: {self.success}",
            f"- Duration: {self.duration_ms:.0f}ms",
        ]

        if self.reflections:
            lines.append(f"- Reflections: {len(self.reflections)}")

        if self.tool_calls:
            lines.append(f"- Tool Calls: {len(self.tool_calls)}")

        if self.error:
            lines.append(f"- Error: {self.error}")

        return "\n".join(lines)


T = TypeVar("T")


class BaseAgent(ABC, Generic[T]):
    """Agent 基类 - 支持自我迭代

    核心流程：
    1. 执行 (Execute): 调用工具，生成响应
    2. 评估 (Evaluate): 评估结果质量
    3. 反思 (Reflect): 分析问题，制定改进策略
    4. 迭代 (Iterate): 重新执行，应用改进
    5. 终止 (Terminate): 达到目标或超过迭代次数

    子类需要实现：
    - _execute_iteration(): 执行单次迭代
    - _evaluate_result(): 评估结果质量
    - _reflect(): 反思并制定改进策略
    """

    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        tools_registry: Optional[Dict[str, Callable]] = None,
    ):
        """初始化 Agent

        Args:
            config: Agent 配置
            tools_registry: 工具注册表
        """
        self.config = config or get_agent_config()
        self.tools_registry = tools_registry or {}

        # Agent ID
        self.agent_id = f"agent_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # 状态
        self.status: AgentStatus = AgentStatus.IDLE
        self.current_iteration: int = 0

        # 记忆系统（延迟初始化）
        self._memory: Optional[Any] = None

        # 反思引擎（延迟初始化）
        self._reflection_engine: Optional[Any] = None

        # 评估器（延迟初始化）
        self._evaluator: Optional[Any] = None

        logger.info(
            f"Agent initialized: {self.agent_id}, "
            f"strategy={self.config.iteration_strategy}, "
            f"max_iterations={self.config.max_iterations}"
        )

    @property
    def memory(self):
        """获取记忆系统"""
        if self._memory is None and self.config.enable_memory:
            from .memory import AgentMemory
            self._memory = AgentMemory(max_entries=self.config.memory_max_entries)
        return self._memory

    @property
    def reflection_engine(self):
        """获取反思引擎"""
        if self._reflection_engine is None and self.config.enable_reflection:
            from .reflection import ReflectionEngine
            self._reflection_engine = ReflectionEngine(depth=self.config.reflection_depth)
        return self._reflection_engine

    @property
    def evaluator(self):
        """获取评估器"""
        if self._evaluator is None:
            from .evaluator import ResultEvaluator
            self._evaluator = ResultEvaluator(min_score=self.config.min_quality_score)
        return self._evaluator

    def invoke(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
        iteration_strategy: Optional[IterationStrategy] = None,
    ) -> AgentResult:
        """执行 Agent（支持自我迭代）

        Args:
            query: 用户查询
            context: 执行上下文
            iteration_strategy: 迭代策略（覆盖配置）

        Returns:
            AgentResult 执行结果
        """
        # 初始化结果
        result = AgentResult(
            agent_id=self.agent_id,
            agent_type=self.__class__.__name__,
            query=query,
        )

        # 确定迭代策略
        strategy = iteration_strategy or self.config.iteration_strategy

        logger.info(f"Agent invoke: {query[:50]}..., strategy={strategy}")

        # 根据策略执行
        if strategy == IterationStrategy.NONE:
            # 单次执行
            self._execute_single(query, context, result)
        else:
            # 迭代执行
            self._execute_with_iteration(query, context, result, strategy)

        # 标记完成
        result.mark_completed()

        logger.info(f"Agent completed: iterations={result.iterations}, quality={result.quality_score:.2f}")

        return result

    def _execute_single(
        self,
        query: str,
        context: Optional[Dict[str, Any]],
        result: AgentResult,
    ) -> None:
        """单次执行（无迭代）"""
        self.status = AgentStatus.EXECUTING

        try:
            # 执行
            iteration_result = self._execute_iteration(query, context, iteration=0)
            result.response = iteration_result.get("response", "")
            result.tool_calls = iteration_result.get("tool_calls", [])
            result.tool_results = iteration_result.get("tool_results", [])
            result.iterations = 1

            # 评估
            self.status = AgentStatus.EVALUATING
            eval_result = self._evaluate_result(result.response, query, iteration_result)
            result.quality_score = eval_result.score
            result.evaluation_details = eval_result.details

            # 记录记忆
            if self.memory:
                self.memory.store(
                    MemoryType.EXECUTION,
                    {
                        "query": query,
                        "response": result.response,
                        "quality_score": result.quality_score,
                    }
                )

            self.status = AgentStatus.COMPLETED

        except Exception as e:
            self.status = AgentStatus.FAILED
            result.error = str(e)
            logger.error(f"Agent execution failed: {e}")

    def _execute_with_iteration(
        self,
        query: str,
        context: Optional[Dict[str, Any]],
        result: AgentResult,
        strategy: IterationStrategy,
    ) -> None:
        """带迭代的执行"""
        from .iteration import IterationLoop, TerminationReason

        # 创建迭代循环
        loop = IterationLoop(
            max_iterations=self.config.max_iterations,
            strategy=strategy,
            min_quality_score=self.config.min_quality_score,
        )

        # 初始上下文
        exec_context = context or {}

        # 迭代执行
        for iteration in range(self.config.max_iterations + 1):
            self.current_iteration = iteration
            result.iterations = iteration

            # 执行
            self.status = AgentStatus.EXECUTING
            iteration_result = self._execute_iteration(query, exec_context, iteration)

            # 评估
            self.status = AgentStatus.EVALUATING
            eval_result = self._evaluate_result(
                iteration_result.get("response", ""),
                query,
                iteration_result
            )

            # 记录迭代历史
            result.iteration_history.append({
                "iteration": iteration,
                "response": iteration_result.get("response", ""),
                "quality_score": eval_result.score,
                "tool_calls": iteration_result.get("tool_calls", []),
                "evaluation": eval_result.details,
            })

            # 更新最佳结果
            if iteration == 0 or eval_result.score > result.quality_score:
                result.response = iteration_result.get("response", "")
                result.tool_calls = iteration_result.get("tool_calls", [])
                result.tool_results = iteration_result.get("tool_results", [])
                result.quality_score = eval_result.score
                result.evaluation_details = eval_result.details

            # 检查终止条件
            termination = loop.check_termination(iteration, eval_result)

            if termination.should_terminate:
                result.termination_reason = termination.reason.value
                self.status = AgentStatus.COMPLETED
                break

            # 反思
            if self.config.enable_reflection and self.reflection_engine:
                self.status = AgentStatus.REFLECTING
                reflection = self._reflect(
                    iteration_result,
                    eval_result,
                    query,
                    iteration
                )

                result.reflections.append(reflection.analysis)
                result.improvements.extend(reflection.improvements)

                # 应用改进
                exec_context = reflection.updated_context
                if reflection.new_tools:
                    exec_context["additional_tools"] = reflection.new_tools

            self.status = AgentStatus.ITERATING

        # 记录记忆
        if self.memory:
            self.memory.store(
                MemoryType.ITERATION,
                {
                    "query": query,
                    "iterations": result.iterations,
                    "quality_score": result.quality_score,
                    "reflections": result.reflections,
                }
            )

    @abstractmethod
    def _execute_iteration(
        self,
        query: str,
        context: Dict[str, Any],
        iteration: int,
    ) -> Dict[str, Any]:
        """执行单次迭代

        Args:
            query: 用户查询
            context: 执行上下文
            iteration: 当前迭代次数

        Returns:
            迭代结果，包含 response, tool_calls, tool_results
        """
        pass

    @abstractmethod
    def _evaluate_result(
        self,
        response: str,
        query: str,
        iteration_result: Dict[str, Any],
    ) -> Any:
        """评估结果质量

        Args:
            response: Agent 响应
            query: 用户查询
            iteration_result: 迭代结果

        Returns:
            EvaluationResult
        """
        pass

    def _reflect(
        self,
        iteration_result: Dict[str, Any],
        eval_result: Any,
        query: str,
        iteration: int,
    ) -> Any:
        """反思并制定改进策略

        Args:
            iteration_result: 迭代结果
            eval_result: 评估结果
            query: 用户查询
            iteration: 当前迭代次数

        Returns:
            ReflectionResult
        """
        if self.reflection_engine:
            return self.reflection_engine.reflect(
                query=query,
                response=iteration_result.get("response", ""),
                evaluation=eval_result,
                iteration=iteration,
                context=iteration_result.get("context", {}),
            )

        # 默认反思
        from .reflection import ReflectionResult
        return ReflectionResult(
            analysis="结果质量未达标，需要改进",
            improvements=["重新执行任务"],
            updated_context=iteration_result.get("context", {}),
        )

    def register_tool(self, name: str, handler: Callable) -> None:
        """注册工具"""
        self.tools_registry[name] = handler
        logger.debug(f"Tool registered: {name}")

    def get_tool(self, name: str) -> Optional[Callable]:
        """获取工具"""
        return self.tools_registry.get(name)

    def reset(self) -> None:
        """重置 Agent"""
        self.status = AgentStatus.IDLE
        self.current_iteration = 0

        if self.memory:
            self.memory.clear()

        logger.info(f"Agent reset: {self.agent_id}")

    def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        return {
            "agent_id": self.agent_id,
            "agent_type": self.__class__.__name__,
            "status": self.status.value,
            "current_iteration": self.current_iteration,
            "config": {
                "iteration_strategy": self.config.iteration_strategy.value,
                "max_iterations": self.config.max_iterations,
                "enable_reflection": self.config.enable_reflection,
            },
        }


class HermesStyleAgent(BaseAgent[AgentResult]):
    """Hermes 风格 Agent - 基于 Function Calling 的智能 Agent

    特点：
    - 原生 Function Calling 支持
    - 多轮工具调用自动处理
    - 自我迭代改进
    - 反思驱动的优化
    """

    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        tools_registry: Optional[Dict[str, Callable]] = None,
        llm_client: Optional[Any] = None,
    ):
        """初始化 Hermes 风格 Agent

        Args:
            config: Agent 配置
            tools_registry: 工具注册表
            llm_client: LLM 客户端
        """
        super().__init__(config, tools_registry)

        # LLM 客户端
        self.llm_client = llm_client

        # 对话历史
        self._conversation_history: List[Dict[str, Any]] = []

    def _execute_iteration(
        self,
        query: str,
        context: Dict[str, Any],
        iteration: int,
    ) -> Dict[str, Any]:
        """执行单次迭代"""
        from .tool_executor import ToolExecutor

        # 创建工具执行器
        executor = ToolExecutor(self.tools_registry)

        # 构建消息
        messages = self._build_messages(query, context, iteration)

        # 调用 LLM
        self.status = AgentStatus.EXECUTING

        try:
            # 获取 LLM 响应
            llm_response = self._call_llm(messages, context)

            # 解析工具调用
            tool_calls = self._parse_tool_calls(llm_response)

            # 执行工具
            tool_results = []
            for call in tool_calls:
                result = executor.execute(call["name"], call.get("arguments", {}))
                tool_results.append({
                    "name": call["name"],
                    "arguments": call.get("arguments", {}),
                    "result": result.output if hasattr(result, 'output') else result,
                    "error": result.error if hasattr(result, 'error') else None,
                })

            # 生成响应
            response = self._generate_response(llm_response, tool_results)

            return {
                "response": response,
                "tool_calls": tool_calls,
                "tool_results": tool_results,
                "context": context,
                "llm_response": llm_response,
            }

        except Exception as e:
            logger.error(f"Iteration execution failed: {e}")
            return {
                "response": f"执行失败: {str(e)}",
                "tool_calls": [],
                "tool_results": [],
                "context": context,
                "error": str(e),
            }

    def _evaluate_result(
        self,
        response: str,
        query: str,
        iteration_result: Dict[str, Any],
    ):
        """评估结果"""
        if self.evaluator:
            return self.evaluator.evaluate(
                response=response,
                query=query,
                tool_results=iteration_result.get("tool_results", []),
                iteration=iteration_result.get("iteration", 0),
            )

        # 默认评估
        from .evaluator import EvaluationResult
        score = 0.8 if len(response) > 50 and not iteration_result.get("error") else 0.5
        return EvaluationResult(
            score=score,
            passed=score >= 0.7,
            details={"default_evaluation": True},
        )

    def _build_messages(
        self,
        query: str,
        context: Dict[str, Any],
        iteration: int,
    ) -> List[Dict[str, Any]]:
        """构建消息"""
        messages = self._conversation_history.copy()

        # 添加用户消息
        if iteration == 0:
            messages.append({"role": "user", "content": query})
        else:
            # 迭代消息
            improvements = context.get("improvements", [])
            improvement_str = "\n".join(improvements) if improvements else ""
            messages.append({
                "role": "user",
                "content": f"请根据以下改进建议重新处理: {query}\n改进建议:\n{improvement_str}"
            })

        return messages

    def _call_llm(
        self,
        messages: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> str:
        """调用 LLM"""
        if self.llm_client:
            # 使用配置的客户端
            if hasattr(self.llm_client, "chat"):
                result = self.llm_client.chat(messages)
                return result.get("content", "")
            elif hasattr(self.llm_client, "invoke"):
                result = self.llm_client.invoke(messages)
                return str(result)

        # 默认：返回模拟响应
        return f"处理请求... (模拟响应)"

    def _parse_tool_calls(self, response: str) -> List[Dict[str, Any]]:
        """解析工具调用"""
        import json
        import re

        tool_calls = []

        # 尝试解析 JSON 格式的工具调用
        try:
            if "{" in response and "}" in response:
                # 提取 JSON 块
                json_pattern = r'\{[^{}]*"name"[^{}]*\}'
                matches = re.findall(json_pattern, response)

                for match in matches:
                    try:
                        parsed = json.loads(match)
                        if "name" in parsed:
                            tool_calls.append({
                                "name": parsed.get("name"),
                                "arguments": parsed.get("arguments", {}),
                            })
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.debug(f"Tool call parsing failed: {e}")

        return tool_calls

    def _generate_response(
        self,
        llm_response: str,
        tool_results: List[Dict[str, Any]],
    ) -> str:
        """生成最终响应"""
        if tool_results:
            # 包含工具结果的响应
            results_str = "\n".join([
                f"- {r['name']}: {str(r.get('result', r.get('error', 'unknown')))[:100]}"
                for r in tool_results
            ])
            return f"{llm_response}\n\n工具执行结果:\n{results_str}"

        return llm_response

    def clear_history(self) -> None:
        """清空对话历史"""
        self._conversation_history = []