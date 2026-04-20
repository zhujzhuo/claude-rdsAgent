# RDS Agent 架构文档

本目录包含 RDS Agent 项目的架构设计文档和图表。

## 架构图索引

### 1. 系统整体架构图
**文件**: [system_architecture.svg](system_architecture.svg)

展示系统的分层架构，包括：
- **用户交互层**: CLI、Django REST API、Celery Beat、Celery Worker、Notification
- **Agent核心层 (双架构)**:
  - LangGraph Agent: 问答Agent、诊断Agent (状态机编排)
  - Hermes Agent: Function Calling Agent (原生工具调用)
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
- **hermes** (新增):
  - agent.py → client, function_schema, tools
  - client.py → Ollama API
  - tools.py → tools (LangChain)
- **diagnostic** → tools, external
- **core** → tools
- **tools** → external dependencies

数据流程: API请求 → 任务调度 → 任务执行 → Agent诊断 → 告警检查 → 存储历史 → 发送通知

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

展示项目的文件目录结构，包含新增的 `hermes/` 模块。

---

## 技术栈概览

| 层级 | 技术 | 说明 |
|------|------|------|
| Web框架 | Django 4.2 + DRF 3.15 | REST API、ORM模型、ViewSet |
| 任务调度 | Celery 5.3 + Redis + django-celery-beat | 分布式任务队列、定时调度 |
| 数据存储 | MySQL + Django ORM | 任务、告警、历史持久化 |
| Agent框架 | LangGraph / **Hermes Function Calling** | 双架构支持 |
| LLM | Ollama + Qwen2.5-14B / **Hermes 3** | 本地部署，数据安全 |
| Embeddings | nomic-embed-text | 向量嵌入 |
| 向量库 | ChromaDB | 知识库存储 |
| CLI | Rich + Prompt Toolkit | 美化命令行 |

---

## 双 Agent 架构详解

### LangGraph Agent (复杂流程)

**适用场景**: 复杂诊断流程、多步骤分析、报告生成

**架构特点**:
- 状态机模型 (StateGraph)
- 条件路由节点
- 多节点处理流程
- LangChain Tools 集成

**流程**:
```
用户输入 → 意图识别 → 实例检查 → 工具选择 → 工具执行 → 响应生成
```

**模块**:
- `core/agent.py`: RDSAgent (问答)
- `diagnostic/agent.py`: DiagnosticAgent (诊断)

### Hermes Agent (快速调用)

**适用场景**: 快速问答、单工具调用、知识库搜索

**架构特点**:
- 原生 Function Calling
- OpenAI 兼容工具格式
- 自动工具调用循环
- 无需状态机编排

**流程**:
```
用户输入 → 工具调用决策 → 自动执行工具 → 返回结果
```

**模块**:
- `hermes/agent.py`: HermesAgent
- `hermes/client.py`: HermesClient (Ollama)
- `hermes/function_schema.py`: FunctionSchema, ToolRegistry
- `hermes/tools.py`: 8个 RDS 工具注册

---

## Hermes Function Calling 工具

| 工具 | 说明 | 参数 |
|------|------|------|
| `get_instance_info` | 获取实例信息 | instance_name |
| `get_performance_metrics` | 获取性能指标 | instance_name, metric_type |
| `analyze_sql` | SQL分析 | instance_name, sql_text |
| `check_connections` | 连接检查 | instance_name |
| `analyze_storage` | 存储分析 | instance_name, analyze_type |
| `get_parameters` | 参数查询 | instance_name, parameter_name |
| `search_knowledge` | 知识库搜索 | query, top_k |
| `run_diagnostic` | 执行诊断 | instance_name, diagnostic_type |

---

## 核心模块说明

### Phase 1: 智能问答助手
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

### Phase 3: 自动化巡检系统 (Django + Celery)

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
# LangGraph Agent
AGENT_TYPE=langgraph
OLLAMA_MODEL=qwen2.5:14b

# Hermes Agent
AGENT_TYPE=hermes
HERMES_ENABLED=True
HERMES_MODEL=hermes3
HERMES_MAX_ITERATIONS=10
```

### Hermes 配置
| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| HERMES_ENABLED | 启用 Hermes Agent | False |
| HERMES_MODEL | Hermes 模型 | hermes3 |
| HERMES_MAX_ITERATIONS | 最大工具调用次数 | 10 |
| HERMES_TIMEOUT | 请求超时 | 60.0 |

---

## 启动服务

```bash
# Django Web服务
python manage.py runserver 0.0.0.0:8000

# Celery Worker (任务执行)
celery -A rds_agent worker -l info --concurrency=5

# Celery Beat (定时调度)
celery -A rds_agent beat -l info
```

---

## 目录文件统计

- **源文件**: 60+
- **测试文件**: 50+
- **模块**: 9个 (django_project, scheduler, hermes, diagnostic, core, tools, utils, memory, api)
- **架构**: Django 4.2 + Celery 5.3 + MySQL + Redis + Hermes