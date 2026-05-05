# RDS Agent 使用指南

本文档详细介绍 RDS Agent 的核心能力及其使用方法。

---

## 目录

1. [快速开始](#快速开始)
2. [三层问题分类路由](#三层问题分类路由)
3. [RouterAgent 基本使用](#routeragent-基本使用)
4. [IterativeRouterAgent 自我迭代](#iterativerouteragent-自我迭代)
5. [独立组件使用](#独立组件使用)
6. [Skills/SOP 标准化诊断](#skills-sop-标准化诊断)
7. [问题示例参考](#问题示例参考)
8. [配置说明](#配置说明)
9. [常见问题](#常见问题)

---

## 快速开始

### CLI 交互模式

```bash
# 启动 CLI
rds-agent chat

# 指定默认实例
rds-agent chat --instance db-prod-01
```

CLI 内命令：
- `/help` - 显示帮助
- `/reset` - 重置会话
- `/clear` - 清屏
- `/exit` - 退出

### Python API

```python
from rds_agent.router import get_router_agent

# 获取 Agent
agent = get_router_agent()

# 简化调用
response = agent.chat("db-01 的性能情况怎么样？")

# 详细调用
result = agent.invoke("db-01 的 CPU 使用率过高", instance="db-01")
```

---

## 三层问题分类路由

RouterAgent 根据问题类型自动选择最优执行路径：

| 问题类型 | 执行路径 | 特点 | 示例问题 |
|----------|----------|------|----------|
| **SIMPLE_QA** | Hermes + 知识库 | 快速响应、精准回答 | "什么是 Buffer Pool？" |
| **SOP_SKILL** | Skills/SOP 流程 | 标准化步骤、根因定位 | "db-01 CPU 使用率过高" |
| **GENERAL** | LangGraph/Diagnostic | 自主规划、完整诊断 | "帮我诊断 db-01" |

### 分类原理

```
用户问题
    │
    ▼
QuestionClassifier
    │
    ├─ 包含常识关键词？ ────────────► SIMPLE_QA (Hermes + 知识库)
    │   ["是什么", "为什么", "如何", "原理", ...]
    │
    ├─ 包含专业诊断关键词？ ───────► SOP_SKILL (Skills/SOP)
    │   ["CPU过高", "存储增长", "慢SQL", "连接数", ...]
    │
    └─ 其他 ─────────────────────► GENERAL (LangGraph)
```

---

## RouterAgent 基本使用

### 1. 获取实例

```python
from rds_agent.router import (
    RouterAgent,
    get_router_agent,
    create_router_agent,
    AgentType,
)

# 方式1: 全局单例（推荐）
agent = get_router_agent()

# 方式2: 创建新实例
agent = create_router_agent(
    agent_type=AgentType.AUTO,
    enable_hermes=True
)

# 方式3: 自定义配置
agent = RouterAgent(
    agent_type=AgentType.LANGGRAPH,  # 强制使用 LangGraph
    enable_hermes=False              # 禁用 Hermes
)
```

### 2. 简化接口

```python
# chat() - 直接返回响应文本
response = agent.chat("什么是 Buffer Pool？")
print(response)
# 输出: "Buffer Pool 是 InnoDB 存储引擎的内存缓存区域..."

response = agent.chat("db-01 的性能情况", thread_id="session-001")
```

### 3. 详细接口

```python
# invoke() - 返回完整结果
result = agent.invoke(
    message="db-01 的 CPU 使用率过高",
    thread_id="session-001",
    instance="db-01"
)

# 返回字段说明
print(result["response"])              # 响应内容
print(result["agent_type"])            # hermes/langgraph/diagnostic/skill
print(result["question_category"])     # simple_qa/sop_skill/general
print(result["complexity"])            # simple/medium/complex

# Skill 执行结果
if result["agent_type"] == "skill":
    print(result["skill_result"]["root_cause"])     # 根因定位
    print(result["skill_result"]["progress"])       # 执行进度

# Diagnostic 执行结果
if result["agent_type"] == "diagnostic":
    print(result["diagnostic_result"]["overall_score"])   # 健康分数
    print(result["diagnostic_result"]["critical_count"])  # 严重问题数
```

### 4. 流式执行

```python
# stream() - 流式返回
for chunk in agent.stream("帮我诊断 db-01"):
    if chunk["agent"] == "hermes":
        print(chunk["chunk"], end="")
    elif chunk["agent"] == "langgraph":
        print(chunk["event"]["content"], end="")
    elif chunk["agent"] == "diagnostic":
        print(f"[检查] {chunk['event']['check_name']}")
    elif chunk["agent"] == "skill":
        print(f"[步骤] {chunk['result']['current_step']}")
```

### 5. 会话管理

```python
# 重置会话
agent.reset(thread_id="session-001")

# 评估复杂度
complexity = agent.evaluate_complexity("对 db-01 做完整巡检")
print(complexity)  # complex

# 选择 Agent
agent_type, skill_type = agent.select_agent("db-01 CPU 使用率过高")
print(agent_type)   # SKILL
print(skill_type)   # CPU_ANALYSIS
```

---

## IterativeRouterAgent 自我迭代

IterativeRouterAgent 在 RouterAgent 基础上增加自我迭代改进机制：

```
执行 → 评估 → 反思 → 改进 → 迭代 → 选择最佳
```

### 1. 创建迭代 Agent

```python
from rds_agent.router import (
    IterativeRouterAgent,
    IterationConfig,
    IterationStrategy,
    get_iterative_router_agent,
)

# 创建迭代配置
config = IterationConfig(
    strategy=IterationStrategy.BALANCED,     # 迭代策略
    max_iterations=5,                        # 最大迭代次数
    min_quality_score=0.7,                   # 最低质量分数
    target_quality_score=0.9,                # 目标质量分数
    enable_reflection=True,                  # 启用反思
    enable_memory=True,                      # 启用记忆
    reflection_depth=2,                      # 反思深度
)

# 创建 Agent
agent = get_iterative_router_agent(iteration_config=config)
```

### 2. 迭代策略选择

| 策略 | 行为 | 适用场景 |
|------|------|----------|
| `NONE` | 不迭代，单次执行 | 简单查询、快速响应 |
| `CONSERVATIVE` | 仅评估未达标时迭代 | 稳定响应、避免过度迭代 |
| `AGGRESSIVE` | 总是迭代改进 | 追求最佳质量、深度分析 |
| `BALANCED` | 动态决策迭代次数 | 通用推荐、平衡效率与质量 |
| `SKILL_BASED` | SOP 流程驱动迭代 | 专业诊断、标准化流程 |

### 3. 启用迭代执行

```python
# 方式1: invoke 启用迭代参数
result = agent.invoke(
    message="分析 db-01 的 CPU 问题根因",
    enable_iteration=True,  # 启用迭代
    instance="db-01"
)

# 方式2: 直接调用迭代方法
result = agent.invoke_with_iteration(
    message="诊断 db-prod 实例性能",
    thread_id="session-001",
    instance="db-prod"
)
```

### 4. 迭代结果分析

```python
# 迭代结果字段
print(result["response"])               # 最佳响应
print(result["best_score"])             # 最高质量分数 (0-1)
print(result["best_iteration"])         # 最佳迭代编号
print(result["total_iterations"])       # 总迭代次数
print(result["termination_reason"])     # 终止原因
print(result["total_duration_ms"])      # 总耗时

# 终止原因说明:
# - SUCCESS: 达到目标分数
# - QUALITY_THRESHOLD: 达到最低分数阈值
# - MAX_ITERATIONS: 达到最大迭代次数
# - CONVERGENCE: 结果收敛（连续迭代分数无提升）
# - TIMEOUT: 超时
# - ERROR: 执行错误

# 查看迭代过程
for iter_info in result["iterations"]:
    print(f"迭代 {iter_info['iteration']}: 分数={iter_info['score']:.2f}")
    print(f"  问题: {iter_info['issues']}")
    print(f"  改进: {iter_info['improvements']}")
```

### 5. 迭代统计

```python
# 获取迭代统计
stats = agent.get_iteration_stats()
print(stats["evaluation"]["total_evaluations"])  # 评估次数
print(stats["memory"]["total_memories"])         # 记忆条数

# 重置迭代状态
agent.reset_iteration()
```

---

## 独立组件使用

### 1. IterationLoop - 迭代循环管理

```python
from rds_agent.agent import (
    IterationLoop,
    IterationStrategy,
    TerminationReason,
)

# 创建迭代循环
loop = IterationLoop(
    max_iterations=5,
    strategy=IterationStrategy.BALANCED,
    min_quality_score=0.7
)

# 记录迭代
loop.record_iteration(
    iteration=0,
    score=0.75,
    response="初步分析结果...",
    time_ms=500
)

# 检查终止条件
check = loop.check_termination(iteration=0, evaluation=evaluation)
if check.should_terminate:
    print(f"终止原因: {check.reason}")
else:
    print(f"继续迭代，当前分数: {check.score}")

# 获取最终结果
result = loop.get_result(TerminationReason.SUCCESS)
print(result.best_response)
print(result.best_score)
```

### 2. ResultEvaluator - 结果评估器

```python
from rds_agent.agent import ResultEvaluator, EvaluationCriteria

# 创建评估器
evaluator = ResultEvaluator()

# 设置评估标准（可选）
criteria = EvaluationCriteria(
    completeness_weight=0.30,     # 完整性权重
    accuracy_weight=0.25,         # 准确性权重
    readability_weight=0.15,      # 可读性权重
    effectiveness_weight=0.15,    # 有效性权重
    error_free_weight=0.15,       # 无错误权重
    min_score=0.7,                # 最低分数
    target_score=0.9,             # 目标分数
)

# 评估响应
evaluation = evaluator.evaluate(
    response="CPU 使用率 85%，建议优化慢 SQL...",
    query="分析 db-01 的 CPU 问题",
    tool_results=["get_cpu", "analyze_sql"],
    iteration=0,
    criteria=criteria
)

# 评估结果
print(f"总分: {evaluation.score:.2f}")        # 0-1
print(f"达标: {evaluation.passed}")           # True/False
print(f"问题: {evaluation.issues}")           # 发现的问题
print(f"建议: {evaluation.suggestions}")      # 改进建议

# 各维度分数
for cs in evaluation.criterion_scores:
    print(f"{cs.criterion.value}: {cs.score:.2f}")
# 输出:
# completeness: 0.80
# accuracy: 0.75
# readability: 0.90
# effectiveness: 0.70
# error_free: 0.85
```

### 3. ReflectionEngine - 反思引擎

```python
from rds_agent.agent import ReflectionEngine, ReflectionType

# 创建反思引擎
engine = ReflectionEngine(depth=2)  # 反思深度

# 执行反思
reflection = engine.reflect(
    query="分析 CPU 问题",
    response="CPU 使用率较高...",
    evaluation=evaluation,  # 评估结果
    iteration=0,
    context={}              # 可选上下文
)

# 反思结果
print(f"分析: {reflection.analysis}")
print(f"问题: {reflection.issues}")           # ["响应缺少具体数值", "未分析根因"]
print(f"改进: {reflection.improvements}")     # ["添加 CPU 具体数值", "深入分析根因"]
print(f"深度: {reflection.depth}")
print(f"类型: {reflection.type}")             # QUALITY/ERROR/STRATEGY/SELF

# 生成改进提示
prompt_context = reflection.to_prompt_context()
# 用于指导下一次迭代
```

### 4. AgentMemory - 记忆系统

```python
from rds_agent.agent import AgentMemory, MemoryType

# 创建记忆系统
memory = AgentMemory(enable_learning=True)

# 添加执行记忆
memory.add_execution_memory(
    iteration=0,
    tool_name="get_cpu",
    tool_result={"cpu_usage": 85},
    response="CPU 使用率 85%",
    query="分析 CPU"
)

# 添加反思记忆
memory.add_reflection_memory(
    iteration=0,
    analysis="响应缺少根因分析",
    issues=["缺少根因"],
    improvements=["深入分析根因"],
    query="分析 CPU"
)

# 添加评估记忆
memory.add_evaluation_memory(
    iteration=0,
    score=0.75,
    passed=False,
    criteria={"completeness": 0.80},
    query="分析 CPU"
)

# 获取相关记忆
memories = memory.get_relevant_memories("CPU 分析")
for m in memories:
    print(f"{m.memory_type}: {m.content}")

# 学习模式
patterns = memory.learn_from_memories()
print(patterns["successful_patterns"])
print(patterns["failed_patterns"])
print(patterns["improvement_suggestions"])

# 统计信息
stats = memory.get_stats()
print(f"总记忆数: {stats['total_memories']}")
print(f"成功率: {stats['success_rate']}")
```

### 5. ToolExecutor - 工具执行器

```python
from rds_agent.agent import ToolExecutor, ToolResult

# 创建执行器
executor = ToolExecutor()

# 执行单个工具
result = executor.execute(
    tool_name="get_cpu_usage",
    arguments={"instance": "db-01"},
    iteration=0,
    timeout_ms=5000
)

print(result.success)      # True/False
print(result.output)       # {"cpu_usage": 85}
print(result.error)        # None 或错误信息
print(result.execution_time_ms)

# 执行批量工具
results = executor.execute_batch(
    tool_calls=[
        {"tool_name": "get_cpu", "arguments": {"instance": "db-01"}},
        {"tool_name": "get_memory", "arguments": {"instance": "db-01"}},
    ],
    iteration=0,
    parallel=True  # 并行执行
)
```

---

## Skills/SOP 标准化诊断

### 1. 执行 Skill

```python
from rds_agent.skills import get_skill_executor, SkillType

# 获取执行器
executor = get_skill_executor()

# 执行 CPU 分析
result = executor.execute(
    SkillType.CPU_ANALYSIS,
    instance_name="db-prod-01"
)

# 执行结果
print(f"根因: {result['root_cause']}")
print(f"关键发现: {result['key_findings']}")
print(f"建议: {result['recommendations']}")
print(f"进度: {result['progress']}%")
print(f"SOP: {result['sop_name']}")
```

### 2. 可用 Skill 类型

| SkillType | SOP 流程 | 步骤数 | 适用问题 |
|-----------|----------|--------|----------|
| `CPU_ANALYSIS` | CPU 使用率分析 SOP | 9 | CPU 使用率过高 |
| `STORAGE_ANALYSIS` | 存储增长点分析 SOP | 6 | 存储空间增长快 |
| `SQL_OPTIMIZATION` | 慢 SQL 优化 SOP | 5 | 慢 SQL 优化 |
| `CONNECTION_ANALYSIS` | 连接数分析 SOP | 4 | 连接数过高 |

### 3. CPU 分析 SOP 流程详解

```
步骤1: get_monitoring_data
       ↓ 获取 CPU 使用率趋势、高峰时段
步骤2: check_session_change 【关键决策点】
       ↓ 检查会话数是否突增 > 50%
       ├─ 是 → 根因: 业务突增导致会话激增
       └─ 否 → 继续
步骤3: get_profiling
       ↓ 获取 CPU 高峰时段的 Profiling 数据
步骤4: get_slow_queries
       ↓ 获取高峰时段的慢 SQL
步骤5: analyze_sql_plan
       ↓ 分析慢 SQL 执行计划
步骤6: check_lock_status
       ↓ 检查是否有锁等待
步骤7: check_buffer_pool
       ↓ 检查 Buffer Pool 命中率
步骤8: root_cause_analysis
       ↓ 综合分析定位根因
步骤9: generate_recommendations
       ↓ 生成优化建议
```

### 4. 注册自定义 Skill

```python
from rds_agent.skills import BaseSkill, SOP, SOPStep, SkillType, SkillState

class MyCustomSkill(BaseSkill):
    """自定义 Skill 示例"""

    skill_type = SkillType.PERFORMANCE_ANALYSIS

    def __init__(self):
        super().__init__()
        self.sop = SOP(
            name="my_performance_sop",
            skill_type=SkillType.PERFORMANCE_ANALYSIS,
            description="自定义性能分析 SOP",
            steps=[
                SOPStep(
                    name="获取监控数据",
                    tool_name="get_monitoring",
                    tool_params={"instance": "$instance_name"},
                    description="获取实例监控指标"
                ),
                SOPStep(
                    name="分析慢 SQL",
                    tool_name="get_slow_queries",
                    tool_params={"instance": "$instance_name", "limit": 10},
                    description="获取 Top10 慢 SQL"
                ),
                SOPStep(
                    name="生成建议",
                    tool_name=None,  # 无工具，纯分析步骤
                    description="综合分析生成优化建议",
                    is_decision_point=True
                ),
            ],
            decision_points=["step_3"],  # 决策点步骤
        )

    def get_sop(self) -> SOP:
        return self.sop

    def _analyze_output(self, step: SOPStep, output: Any) -> str:
        """分析步骤输出"""
        if step.name == "获取监控数据":
            return f"CPU 使用率: {output.get('cpu_usage', 'N/A')}%"
        elif step.name == "分析慢 SQL":
            return f"发现 {len(output)} 条慢 SQL"
        return str(output)

    def _make_decision(self, state: SkillState) -> Optional[str]:
        """决策点判断"""
        if state["current_step"] == 2:
            # 根据前两步结果决定下一步
            cpu = state["context"].get("cpu_usage", 0)
            if cpu > 80:
                return "CPU 确实过高，需要深入分析"
            else:
                return "CPU 正常，无需深入分析"
        return None

# 注册 Skill
executor = get_skill_executor()
executor.register_skill(MyCustomSkill)

# 使用自定义 Skill
result = executor.execute(SkillType.PERFORMANCE_ANALYSIS, "db-01")
```

---

## 问题示例参考

### SIMPLE_QA 示例（Hermes + 知识库）

```python
# 常识问答
agent.chat("什么是 Buffer Pool？")
agent.chat("InnoDB 和 MyISAM 有什么区别？")
agent.chat("如何优化 MySQL 查询性能？")
agent.chat("为什么需要索引？")
agent.chat("什么是事务隔离级别？")
agent.chat("MVCC 是什么原理？")
agent.chat("Binlog 和 Redolog 的区别？")
agent.chat("如何设计合理的索引？")
```

### SOP_SKILL 示例（Skills/SOP）

```python
# CPU 分析
agent.chat("db-01 的 CPU 使用率过高怎么办")
agent.chat("分析 db-prod 的 CPU 峰值原因")
agent.chat("db-01 CPU 占用率持续 85% 以上")

# 存储分析
agent.chat("db-01 的存储增长点在哪")
agent.chat("分析 db-prod 的空间增长趋势")
agent.chat("db-01 磁盘空间快满了")

# SQL 优化
agent.chat("优化 db-01 的慢 SQL")
agent.chat("db-01 的慢查询需要优化")
agent.chat("分析 db-prod 的 Top10 慢 SQL")

# 连接分析
agent.chat("db-01 的连接数过高")
agent.chat("db-prod 连接池满了怎么办")
agent.chat("db-01 活跃连接数异常")
```

### GENERAL 示例（LangGraph/Diagnostic）

```python
# 完整诊断
agent.chat("帮我诊断 db-01")
agent.chat("对 db-prod 做完整巡检")
agent.chat("检查 db-01 的健康状态")
agent.chat("db-01 全面性能分析")

# 复杂问题
agent.chat("db-01 最近性能变差了，帮忙分析一下")
agent.chat("db-prod 响应延迟增加，可能是什么原因")
agent.chat("db-01 的 QPS 突然下降了")
```

---

## 配置说明

### 环境变量配置 (.env)

```bash
# Agent 类型选择
AGENT_TYPE=auto                    # auto/hermes/langgraph/diagnostic
ROUTER_AUTO_SELECT=true            # 自动选择 Agent

# Hermes Agent 配置
HERMES_ENABLED=true                # 是否启用 Hermes
HERMES_MODEL=hermes3               # Hermes 模型
HERMES_HOST=http://localhost:11434 # Ollama 地址
HERMES_MAX_ITERATIONS=10           # 工具调用最大迭代

# LangGraph Agent 配置
OLLAMA_HOST=http://localhost:11434 # Ollama 地址
OLLAMA_MODEL=qwen2.5:14b           # LangGraph 模型

# 迭代配置 (IterativeRouterAgent)
ITERATION_STRATEGY=BALANCED        # NONE/CONSERVATIVE/AGGRESSIVE/BALANCED
MAX_ITERATIONS=5                   # 最大迭代次数
MIN_QUALITY_SCORE=0.7              # 最低质量分数
TARGET_QUALITY_SCORE=0.9           # 目标质量分数
ENABLE_REFLECTION=true             # 启用反思
ENABLE_MEMORY=true                 # 启用记忆
REFLECTION_DEPTH=2                 # 反思深度

# 知识库配置
KNOWLEDGE_BASE_PATH=./knowledge    # 知识库路径
EMBEDDING_MODEL=nomic-embed-text   # Embedding 模型
```

### AgentType 枚举

```python
from rds_agent.router import AgentType

AgentType.AUTO        # 自动选择（推荐）
AgentType.HERMES      # 强制使用 Hermes
AgentType.LANGGRAPH   # 强制使用 LangGraph
AgentType.DIAGNOSTIC  # 强制使用 Diagnostic
AgentType.SKILL       # 强制使用 Skill
```

---

## 常见问题

### Q1: 如何判断问题会被路由到哪个 Agent？

使用分类器预判：

```python
from rds_agent.router import classify_question

category, skill_type = classify_question("db-01 CPU 使用率过高")
print(f"分类: {category.value}")      # sop_skill
print(f"Skill: {skill_type.value}")   # cpu_analysis
```

### Q2: 迭代执行耗时太长怎么办？

调整迭代配置：

```python
# 减少迭代次数
config = IterationConfig(
    strategy=IterationStrategy.CONSERVATIVE,  # 仅失败时迭代
    max_iterations=3,                         # 减少次数
    min_quality_score=0.6,                    # 降低阈值
)
```

### Q3: 如何获取更详细的诊断结果？

使用详细接口：

```python
result = agent.invoke("完整巡检 db-01", instance="db-01")

if result["agent_type"] == "diagnostic":
    diag = result["diagnostic_result"]
    print(f"健康分数: {diag['overall_score']}")
    print(f"严重问题: {diag['critical_count']}")
    print(f"警告: {diag['warning_count']}")
```

### Q4: 如何自定义评估标准？

```python
from rds_agent.agent import EvaluationCriteria

criteria = EvaluationCriteria(
    completeness_weight=0.40,  # 提高完整性权重
    accuracy_weight=0.30,      # 提高准确性权重
    min_score=0.8,             # 提高最低分数
)

evaluation = evaluator.evaluate(..., criteria=criteria)
```

### Q5: 如何禁用迭代功能？

```python
# 方式1: 使用普通 RouterAgent
from rds_agent.router import get_router_agent
agent = get_router_agent()

# 方式2: IterativeRouterAgent 关闭迭代
result = agent.invoke(..., enable_iteration=False)

# 方式3: 配置 NONE 策略
config = IterationConfig(strategy=IterationStrategy.NONE)
```

### Q6: 如何查看迭代过程日志？

```python
result = agent.invoke_with_iteration(...)

for iter_info in result["iterations"]:
    print(f"迭代 {iter_info['iteration']}:")
    print(f"  分数: {iter_info['score']:.2f}")
    print(f"  Agent: {iter_info['agent_type']}")
    print(f"  问题: {iter_info['issues']}")
    print(f"  改进: {iter_info['improvements']}")
    print(f"  响应预览: {iter_info['response_preview'][:100]}")
```

---

## 附录：API 快速参考

### RouterAgent

| 方法 | 参数 | 返回 |
|------|------|------|
| `chat(message, thread_id)` | 消息、会话ID | 响应字符串 |
| `invoke(message, thread_id, instance)` | 消息、会话ID、实例 | 完整结果字典 |
| `stream(message, thread_id)` | 消息、会话ID | 流式迭代器 |
| `reset(thread_id)` | 会话ID | None |
| `select_agent(message)` | 消息 | (AgentType, SkillType) |
| `evaluate_complexity(message)` | 消息 | ComplexityLevel |

### IterativeRouterAgent

| 方法 | 参数 | 返回 |
|------|------|------|
| `invoke(..., enable_iteration)` | 同上 + 启用迭代 | 迭代结果字典 |
| `invoke_with_iteration(...)` | 消息、会话ID、实例 | 迭代结果字典 |
| `get_iteration_stats()` | 无 | 统计字典 |
| `reset_iteration()` | 无 | None |

### SkillExecutor

| 方法 | 参数 | 返回 |
|------|------|------|
| `execute(skill_type, instance_name)` | Skill类型、实例名 | SkillState字典 |
| `register_skill(skill_class)` | Skill类 | None |
| `get_available_skills()` | 无 | SkillType列表 |

---

## 版本信息

- 文档版本: 2.0
- 更新日期: 2026-05
- 适用版本: RDS Agent v0.2.0+

---

## MarkdownSkillParser 动态 Skill 生成

### 1. 解析 Markdown 生成 Skill

```python
from rds_agent.skills.parser import MarkdownSkillParser, SkillGenerator, MarkdownSkill

# 解析 Markdown 文件
parser = MarkdownSkillParser()
parsed = parser.parse_file("skills/docs/cpu_analysis.md")
print(parsed["metadata"])      # YAML Front Matter
print(parsed["steps"])          # SOP 步骤
print(parsed["decision_points"]) # 决策点规则
print(parsed["recommendations"]) # 优化建议

# 构建 SOP 对象
sop = parser.build_sop(parsed)
print(sop.name, sop.steps, sop.decision_points)
```

### 2. 使用 SkillGenerator 自动生成

```python
from rds_agent.skills.parser import get_skill_generator, generate_all_markdown_skills

# 生成所有 Markdown Skill
skills = generate_all_markdown_skills()
for skill_type, skill in skills.items():
    print(f"{skill_type.value}: {skill.get_sop().name}")

# 从指定文件生成
generator = get_skill_generator()
skill = generator.generate_skill("skills/docs/cpu_analysis.md")

# 列出可用 Skill 文件
files = generator.list_available_skills()
print(files)  # ['cpu_analysis.md', ...]
```

### 3. Markdown Skill 文档格式

```markdown
---
name: cpu_analysis
skill_type: CPU_ANALYSIS
description: CPU 使用率分析标准诊断流程
version: 1.0
author: system
tags: [cpu, performance]
---

# CPU 分析 Skill

## SOP 步骤

| 序号 | 名称 | 工具 | 参数 | 条件 | 依赖 | 分析说明 | 超时 |
|------|------|------|------|------|------|----------|------|
| 1 | 获取监控数据 | get_monitoring_data | instance_name=$instance_name, metric_type=cpu_usage | - | - | 获取CPU监控 | 30s |
| 2 | 检查会话突增 | check_session_change | instance_name=$instance_name | - | 1 | 关键决策点 | 30s |

## 决策点

### check_session_change

| 规则名 | 条件 | 根因 | 动作 |
|--------|------|------|------|
| session_spike | `$session_change > 50` | 业务突增导致会话激增 | skip_steps=[3,5] |
| no_spike | `$session_change <= 50` | - | continue |

## 分析模板 / 优化建议 / 结论模板
...
```

### 4. 创建新的 Skill 模板

```python
from rds_agent.skills.parser import get_skill_generator

generator = get_skill_generator()
file_path = generator.write_skill_template(
    skill_name="memory_analysis",
    skill_type="PERFORMANCE_ANALYSIS"
)
print(f"模板已创建: {file_path}")
```

### 5. SkillParser 核心类

| 类 | 说明 |
|----|------|
| `MarkdownSkillParser` | 解析 Markdown 文件为结构化数据 |
| `MarkdownSkill` | 基于 Markdown 的动态 Skill 实现 |
| `SkillGenerator` | 批量生成和注册 MarkdownSkill |