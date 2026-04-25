# RDS Agent 架构文档

本目录包含 RDS Agent 项目的架构设计文档和图表。

## 架构图索引

### 1. 系统整体架构图
**文件**: [system_architecture.svg](system_architecture.svg)

展示系统的分层架构，包括：
- **用户交互层**: CLI、Django REST API、Celery Beat、Celery Worker、Notification
- **路由层 (RouterAgent)**: 三层问题分类路由
  - SIMPLE_QA → Hermes + 知识库
  - SOP_SKILL → Skills/SOP 标准化流程
  - GENERAL → LangGraph 自主规划
- **Agent核心层 (三架构)**:
  - Hermes Agent: Function Calling Agent (快速问答)
  - LangGraph Agent: 问答Agent、诊断Agent (状态机编排)
  - Skills/SOP: 标准化诊断流程 (精确规划)
- **Agent自我迭代层** (新增):
  - IterationLoop: 迭代循环管理
  - ReflectionEngine: 自我反思机制
  - ResultEvaluator: 结果评估器
  - AgentMemory: 记忆系统
- **Django + Celery 层**: Django ORM、Celery Tasks、Services
- **工具层 (LangChain Tools)**: instance、performance、sql、connection、storage、parameters、knowledge、diagnostic
- **数据存储层**: MySQL (Django)、Redis (Celery Broker)、MySQL Client、Vector Store、Platform API
- **LLM层**: Ollama (Qwen2.5-14B / Hermes 3)、Embeddings (nomic-embed-text)

### 2. 模块依赖关系图
**文件**: [module_dependencies.svg](module_dependencies.svg)

展示各模块之间的依赖关系：
- **django_project** → scheduler, external dependencies
- **scheduler**:
  - models/ (Django ORM) → MySQL
  - api/ (DRF ViewSets) → models, services
  - tasks/ (Celery) → diagnostic, services
  - services/ → models, external
- **router**:
  - agent.py → classifier, skills, hermes, core, diagnostic, **agent (迭代)**
  - classifier.py → skills (SkillType)
- **agent** (新增):
  - base.py → iteration, evaluator, memory
  - iteration.py → evaluator, reflection
  - reflection.py → evaluator
  - evaluator.py → memory
  - memory.py → (独立)
  - tool_executor.py → (独立)
  - state.py → (独立)
- **skills**:
  - executor.py → cpu_skill, storage_skill, sql_skill, connection_skill
  - cpu_skill.py → sops/cpu_sop, base
  - storage_skill.py → base
  - sql_skill.py → base
  - connection_skill.py → base
- **hermes**:
  - agent.py → client, function_schema, tools
  - client.py → Ollama API
  - tools.py → tools (LangChain)
- **diagnostic** → tools, external
- **core** → tools
- **tools** → external dependencies

数据流程: API请求 → RouterAgent分类 → Skill/Hermes/LangGraph执行 → 诊断分析 → 告警检查 → 存储历史 → 发送通知

### 3. 诊断Agent流程图
**文件**: [diagnostic_agent_flow.svg](diagnostic_agent_flow.svg)

展示诊断Agent的LangGraph状态机流程：
- START → initialize_diagnostic
- → connect_instance
- → (决策: 连接成功?)
- → run_checks (13项检查)
- → analyze_results
- → generate_suggestions
- → (决策: 需要参数优化?)
- → generate_report
- → END

### 4. 调度器架构图
**文件**: [scheduler_architecture.svg](scheduler_architecture.svg)

展示调度器模块的内部架构 (Django + Celery):
- **API Layer**: Django REST Framework ViewSets (5个)
- **Celery Tasks Layer**: run_inspection_task, check_alerts, send_notification
- **Services Layer**: TaskService, AlertService, HistoryService, NotificationService
- **Django ORM Models**: 6个模型
- **Celery Beat Scheduler**: django-celery-beat PeriodicTask
- **Notification Channels**: DingTalk, Email, WeChat, Webhook

### 5. 项目目录结构图
**文件**: [project_structure.svg](project_structure.svg)

展示项目的文件目录结构，包含新增的 `router/` 和 `skills/` 模块。

---

## 技术栈概览

| 层级 | 技术 | 说明 |
|------|------|------|
| Web框架 | Django 4.2 + DRF 3.15 | REST API、ORM模型、ViewSet |
| 任务调度 | Celery 5.3 + Redis + django-celery-beat | 分布式任务队列、定时调度 |
| 数据存储 | MySQL + Django ORM | 任务、告警、历史持久化 |
| Agent框架 | RouterAgent + LangGraph + Hermes + **Skills/SOP** | 三层路由 + 三架构支持 |
| LLM | Ollama + Qwen2.5-14B / Hermes 3 | 本地部署，数据安全 |
| Embeddings | nomic-embed-text | 向量嵌入 |
| 向量库 | ChromaDB | 知识库存储 |
| CLI | Rich + Prompt Toolkit | 美化命令行 |

---

## 三层问题分类路由架构

### 问题分类

| 类别 | 处理方式 | 示例 |
|------|----------|------|
| **SIMPLE_QA** | Hermes + Knowledge | "什么是 Buffer Pool？"、"如何优化MySQL？" |
| **SOP_SKILL** | Skills/SOP 执行 | "db-01 的 CPU 使用率过高"、"分析存储增长点" |
| **GENERAL** | LangGraph 自主规划 | "帮我诊断 db-01"、"完整巡检 db-prod" |

### 问题分类规则

**SIMPLE_QA** - 纯知识问答，不涉及实例：
- 关键词："是什么"、"如何"、"为什么"、"原理"、"区别"、"最佳实践"
- 排除：涉及实例名称（db-、inst-）、诊断分析类词汇

**SOP_SKILL** - 专业垂直问题，有明确问题类型 + 实例：
- `CPU_ANALYSIS`: "CPU使用率"、"CPU过高"、"CPU打满"
- `STORAGE_ANALYSIS`: "磁盘空间"、"存储增长"、"增长点"
- `SQL_OPTIMIZATION`: "SQL优化"、"慢SQL优化"、"执行计划"
- `CONNECTION_ANALYSIS`: "连接数过高"、"会话突增"

**GENERAL** - 不满足上述两类的问题

### 路由选择流程

```
用户输入 → QuestionClassifier.classify()
         ↓
    ┌────┴────┬────────────┐
    ↓         ↓            ↓
SIMPLE_QA  SOP_SKILL    GENERAL
    ↓         ↓            ↓
 Hermes    SkillExecutor  LangGraph
    ↓         ↓            ↓
 知识库    SOP执行      自主规划
```

---

## Skills/SOP 模块详解

### SOP（标准操作流程）框架

**核心类**:
- `SOPStep`: 步骤定义（工具名、参数模板、条件、依赖）
- `SOP`: 流程定义（步骤列表、决策点、结论模板）
- `BaseSkill`: Skill 执行基类
- `SkillExecutor`: Skill 执行器（注册、查找、执行）

**关键特性**:
- 参数模板支持 `$变量引用`（如 `$instance_name`）
- 执行条件支持表达式评估（如 `$cpu_usage > 70`）
- 决策点支持条件分支（如会话突增 → 定位根因）
- 步骤依赖检查

### CPU 分析 SOP（9步流程）

| 步骤 | 工具 | 说明 |
|------|------|------|
| 1. get_monitoring_data | get_monitoring_data | 获取 CPU 监控数据 |
| 2. check_session_change | get_monitoring_data | 检查会话数突增（关键） |
| 3. get_profiling | get_profiling | 获取 CPU 高峰 Profiling |
| 4. get_slow_queries | get_slow_queries | 获取慢 SQL |
| 5. analyze_sql_plan | analyze_sql_plan | 分析执行计划 |
| 6. check_lock_status | check_lock_status | 检查锁等待 |
| 7. check_buffer_pool | check_buffer_pool | 检查 Buffer Pool |
| 8. root_cause_analysis | llm_analysis | 综合分析定位根因 |
| 9. generate_recommendations | generate_recommendations | 生成优化建议 |

**关键决策点**:
- `session_change > 50%` → 根因：业务突增导致会话激增
- 无会话突增 → 继续 SQL 层面分析

**避免大模型因果颠倒问题**:
传统大模型自主规划可能遗漏关键信息（如会话突增），导致误判根因。SOP 流程通过决策点强制检查会话变化，确保根因定位准确性。

### 其他 Skills

| Skill | SOP步骤数 | 说明 |
|-------|----------|------|
| StorageAnalysisSkill | 7 | 存储增长点分析 |
| SQLOptimizationSkill | 7 | 慢 SQL 优化 |
| ConnectionAnalysisSkill | 7 | 连接数问题分析 |

---

## Agent 自我迭代模块（新增）

### 架构概述

Agent 自我迭代模块实现了 Hermes Agent 的核心思想：**执行 → 评估 → 反思 → 改进 → 迭代** 循环。

**核心组件**:
- `IterationLoop`: 迭代循环管理
- `ReflectionEngine`: 自我反思机制
- `ResultEvaluator`: 结果评估器
- `AgentMemory`: 记忆系统（学习积累）
- `ToolExecutor`: 工具执行器
- `IterativeRouterAgent`: 支持迭代的 RouterAgent

### 迭代循环流程

```
┌─────────────────────────────────────────────────────┐
│                  Iteration Loop                      │
│                                                      │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐     │
│   │ Execute  │───→│ Evaluate │───→│ Reflect  │     │
│   │   Agent  │    │  Result  │    │  Analyze │     │
│   └──────────┘    └──────────┘    └──────────┘     │
│        ↑              │              │              │
│        │              ↓              ↓              │
│        │         ┌──────────┐  ┌──────────┐        │
│        │         │  Check   │  │ Generate │        │
│        │         │Terminate │  │Improve   │        │
│        │         └──────────┘  └──────────┘        │
│        │              │              │              │
│        └──────────────┴──────────────┘              │
│                                                      │
│   Memory: 存储历史、学习模式                          │
└─────────────────────────────────────────────────────┘
```

### 迭代策略

| 策略 | 说明 | 适用场景 |
|------|------|----------|
| NONE | 不迭代，单次执行 | 简单问题 |
| CONSERVATIVE | 仅当不合格时迭代 | 质量优先 |
| AGGRESSIVE | 总是尝试迭代改进 | 性能优化 |
| BALANCED | 根据评估动态决定 | 通用场景 |
| SKILL_BASED | SOP/Skill 驱动迭代 | 专业诊断 |

### 终止条件

| 终止原因 | 说明 |
|----------|------|
| SUCCESS | 达到目标质量分数 |
| QUALITY_THRESHOLD | 达到最低质量阈值 |
| MAX_ITERATIONS | 达到最大迭代次数 |
| CONVERGENCE | 连续迭代无改进（收敛） |
| TIMEOUT | 执行超时 |
| ERROR | 执行错误 |

### 结果评估维度

| 评估维度 | 权重 | 说明 |
|----------|------|------|
| COMPLETENESS | 0.30 | 响应完整性 |
| ACCURACY | 0.25 | 内容准确性 |
| READABILITY | 0.15 | 结构可读性 |
| EFFECTIVENESS | 0.15 | 工具使用效率 |
| ERROR_FREE | 0.15 | 无执行错误 |

### 反思机制

**反思类型**:
- `QUALITY`: 质量反思（分析输出质量）
- `ERROR`: 错误反思（分析执行错误）
- `STRATEGY`: 策略反思（分析执行策略）
- `SELF`: 自我反思（评估迭代效果）

**反思深度**:
- `SURFACE`: 表层反思（仅分析输出）
- `MODERATE`: 中层反思（分析过程和输出）
- `DEEP`: 深层反思（分析根因和策略）

### 记忆系统

**记忆类型**:
- `EXECUTION`: 执行记忆（工具调用、响应）
- `REFLECTION`: 反思记忆（分析、改进建议）
- `EVALUATION`: 评估记忆（评分、质量）
- `LEARNING`: 学习记忆（提取的模式、规则）
- `ERROR`: 错误记忆（错误信息和处理）
- `SUCCESS`: 成功记忆（成功的模式）

**学习机制**:
- 工具序列模式提取
- 错误模式识别
- 成功策略总结
- 推荐生成

### IterativeRouterAgent

扩展 RouterAgent 支持自我迭代：

```python
class IterativeRouterAgent(RouterAgent):
    def invoke_with_iteration(message) -> Dict:
        """带迭代的执行"""
        # 1. 初始化迭代循环
        # 2. 执行 Agent
        # 3. 评估结果
        # 4. 反思分析
        # 5. 检查终止条件
        # 6. 应用改进（如需继续）
        # 7. 返回最佳结果

    def invoke(message, enable_iteration=False) -> Dict:
        """可选迭代的执行"""
```

### 配置示例

```python
# 迭代配置
config = IterationConfig(
    strategy=IterationStrategy.BALANCED,
    max_iterations=5,
    min_quality_score=0.7,
    target_quality_score=0.9,
    enable_reflection=True,
    enable_memory=True,
)

agent = IterativeRouterAgent(iteration_config=config)
result = agent.invoke(message, enable_iteration=True)
```

### 模块文件

| 文件 | 说明 |
|------|------|
| `agent/base.py` | Agent 基类，迭代策略定义 |
| `agent/iteration.py` | IterationLoop，迭代循环管理 |
| `agent/reflection.py` | ReflectionEngine，反思机制 |
| `agent/evaluator.py` | ResultEvaluator，结果评估 |
| `agent/memory.py` | AgentMemory，记忆系统 |
| `agent/state.py` | AgentState，状态管理 |
| `agent/tool_executor.py` | ToolExecutor，工具执行器 |
| `router/agent.py` | IterativeRouterAgent 集成 |

---

## 三架构 Agent 详解

### 1. Hermes Agent (快速问答)

**适用场景**: 简单常识问答、知识库搜索

**架构特点**:
- 原生 Function Calling
- OpenAI 兼容工具格式
- 自动工具调用循环
- 无需状态机编排

**模块**:
- `hermes/agent.py`: HermesAgent

### 2. LangGraph Agent (自主规划)

**适用场景**: 泛化问题、多步骤分析、报告生成

**架构特点**:
- 状态机模型 (StateGraph)
- 条件路由节点
- 多节点处理流程
- LangChain Tools 集成

**模块**:
- `core/agent.py`: RDSAgent (问答)
- `diagnostic/agent.py`: DiagnosticAgent (诊断)

### 3. Skills/SOP Agent (精确规划)

**适用场景**: 专业垂直问题、根因定位

**架构特点**:
- 标准化诊断流程
- 决策点条件分支
- 步骤依赖管理
- 避免因果颠倒

**模块**:
- `skills/executor.py`: SkillExecutor
- `skills/cpu_skill.py`: CPUAnalysisSkill
- `skills/storage_skill.py`: StorageAnalysisSkill
- `skills/sql_skill.py`: SQLOptimizationSkill
- `skills/connection_skill.py`: ConnectionAnalysisSkill

---

## RouterAgent 模块

### 核心类

```python
class AgentType(str, Enum):
    LANGGRAPH = "langgraph"   # LangGraph Agent 自主规划
    HERMES = "hermes"         # Hermes Agent 快速响应
    DIAGNOSTIC = "diagnostic" # Diagnostic Agent 完整巡检
    SKILL = "skill"           # Skills/SOP 标准化流程
    AUTO = "auto"             # 自动选择

class RouterAgent:
    def select_agent(message) -> Tuple[AgentType, Optional[SkillType]]
    def invoke(message) -> Dict[str, Any]
    def chat(message) -> str
```

### 路由逻辑

```python
def select_agent(message):
    # Step 1: 三层问题分类
    category, skill_type = classifier.classify(message)

    # Step 2: 根据问题分类选择执行路径
    if category == QuestionCategory.SIMPLE_QA:
        return AgentType.HERMES, None

    if category == QuestionCategory.SOP_SKILL:
        return AgentType.SKILL, skill_type

    # GENERAL: 根据复杂度决定
    complexity = evaluate_complexity(message)
    if complexity == ComplexityLevel.COMPLEX:
        return AgentType.DIAGNOSTIC, None

    return AgentType.LANGGRAPH, None
```

---

## 核心模块说明

### Phase 1: 智能问答助手
- **router/agent.py**: RouterAgent 三层路由
- **router/classifier.py**: QuestionClassifier 问题分类
- **core/agent.py**: LangGraph问答Agent
- **hermes/agent.py**: Hermes Function Calling Agent
- **tools/**: 8个核心工具

### Phase 2: 智能运维助手
- **diagnostic/agent.py**: LangGraph诊断Agent (13项检查)
- **diagnostic/state.py**: DiagnosticState状态定义
- **diagnostic/nodes.py**: 检查节点实现
- **diagnostic/checks.py**: 13项诊断检查
- **diagnostic/report_generator.py**: JSON报告生成
- **diagnostic/parameter_optimizer.py**: 参数优化建议

### Phase 3: Skills/SOP 标准化诊断
- **skills/base.py**: SOPStep, SOP, BaseSkill 定义
- **skills/executor.py**: SkillExecutor 执行器
- **skills/cpu_skill.py**: CPU 分析 Skill（9步）
- **skills/storage_skill.py**: 存储分析 Skill
- **skills/sql_skill.py**: SQL 优化 Skill
- **skills/connection_skill.py**: 连接分析 Skill

### Phase 4: Agent 自我迭代模块（新增）
- **agent/base.py**: BaseAgent, IterationStrategy, AgentConfig
- **agent/iteration.py**: IterationLoop, TerminationReason
- **agent/reflection.py**: ReflectionEngine, ReflectionType
- **agent/evaluator.py**: ResultEvaluator, EvaluationCriterion
- **agent/memory.py**: AgentMemory, MemoryType
- **agent/state.py**: AgentState, StateManager
- **agent/tool_executor.py**: ToolExecutor, HermesStyleToolExecutor

### Phase 5: 自动化巡检系统 (Django + Celery)

#### Django ORM Models
| 模型 | 说明 |
|------|------|
| InspectionTask | 巡检任务配置 |
| TaskExecution | 任务执行记录 |
| AlertRule | 告警规则 |
| AlertEvent | 告警事件 |
| HealthHistory | 健康历史 |
| NotificationChannel | 通知渠道 |

#### Celery Tasks
| 任务 | 说明 |
|------|------|
| run_inspection_task | 执行巡检任务 |
| run_single_inspection | 单实例诊断 |
| check_alerts | 检查告警规则 |
| record_health_history | 记录健康历史 |
| send_notification | 发送告警通知 |

#### Services Layer
| 服务 | 说明 |
|------|------|
| TaskService | 任务调度服务 |
| AlertService | 告警检查服务 |
| HistoryService | 历史记录服务 |
| NotificationService | 通知服务 |

#### API Endpoints (DRF)
| 端点 | ViewSet | 操作 |
|------|---------|------|
| /api/scheduler/tasks/ | InspectionTaskViewSet | CRUD + enable/disable/run |
| /api/scheduler/alerts/rules/ | AlertRuleViewSet | CRUD |
| /api/scheduler/alerts/events/ | AlertEventViewSet | List |
| /api/scheduler/history/ | HealthHistoryViewSet | List |
| /api/scheduler/notifications/channels/ | NotificationChannelViewSet | CRUD + test |

---

## 配置选项

### Agent 类型切换
```bash
# 自动选择（推荐）
AGENT_TYPE=auto
ROUTER_AUTO_SELECT=true

# LangGraph Agent
AGENT_TYPE=langgraph
OLLAMA_MODEL=qwen2.5:14b

# Hermes Agent
AGENT_TYPE=hermes
HERMES_ENABLED=True
HERMES_MODEL=hermes3
```

### Hermes 配置
| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| HERMES_ENABLED | 启用 Hermes Agent | False |
| HERMES_MODEL | Hermes 模型 | hermes3 |
| HERMES_MAX_ITERATIONS | 最大工具调用次数 | 10 |
| HERMES_TIMEOUT | 请求超时 | 60.0 |

### Router 配置
| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| ROUTER_AUTO_SELECT | 自动路由选择 | true |
| ROUTER_HERMES_THRESHOLD | Hermes阈值 | 30 |
| ROUTER_DIAGNOSTIC_THRESHOLD | Diagnostic阈值 | 70 |

---

## 启动服务

```bash
# Django Web服务
python manage.py runserver 0.0.0.0:8000

# Celery Worker (任务执行)
celery -A rds_agent worker -l info --concurrency=5

# Celery Beat (定时调度)
celery -A rds_agent beat -l info

# CLI交互模式
rds-agent chat
```

---

## 目录文件统计

- **源文件**: 80+
- **测试文件**: 70+
- **模块**: 12个 (django_project, scheduler, router, skills, agent, hermes, diagnostic, core, tools, utils, memory, api)
- **架构**: Django 4.2 + Celery 5.3 + MySQL + Redis + RouterAgent + Skills/SOP + Agent Self-Iteration