# RDS Agent 架构文档

本目录包含 RDS Agent 项目的架构设计文档和图表。

## 架构图索引

### 1. 系统整体架构图
**文件**: [system_architecture.svg](system_architecture.svg)

展示系统的分层架构，包括：
- **用户交互层**: CLI、Django REST API、Celery Beat、Celery Worker、Notification
- **Agent核心层 (LangGraph)**: 问答Agent、诊断Agent
- **Django + Celery 层**: Django ORM、Celery Tasks、Services
- **工具层 (LangChain Tools)**: instance、performance、sql、connection、storage、parameters、knowledge、diagnostic
- **数据存储层**: MySQL (Django)、Redis (Celery Broker)、MySQL Client、Vector Store、Platform API
- **LLM层**: Ollama (Qwen2.5-14B)、Embeddings (nomic-embed-text)

### 2. 模块依赖关系图
**文件**: [module_dependencies.svg](module_dependencies.svg)

展示各模块之间的依赖关系：
- **django_project** → scheduler, external dependencies
- **scheduler**:
  - models/ (Django ORM) → MySQL
  - api/ (DRF ViewSets) → models, services
  - tasks/ (Celery) → diagnostic, services
  - services/ → models, external
- **diagnostic** → tools, external
- **core** → tools
- **tools** → external dependencies
- **Celery Beat** → scheduler
- **Notifications** → scheduler services

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
  - InspectionTask, TaskExecution, AlertRule, AlertEvent, HealthHistory, NotificationChannel
- **Celery Tasks Layer**:
  - run_inspection_task, run_single_inspection, check_alerts, send_notification
- **Services Layer**:
  - TaskService, AlertService, HistoryService, NotificationService
- **Django ORM Models**:
  - InspectionTask, TaskExecution, AlertRule, AlertEvent, HealthHistory, NotificationChannel
- **Celery Beat Scheduler**:
  - django-celery-beat PeriodicTask
  - Schedule Types: INTERVAL, CRON, ONCE
- **Notification Channels**: DingTalk, Email, WeChat, Webhook

### 5. 项目目录结构图
**文件**: [project_structure.svg](project_structure.svg)

展示项目的文件目录结构：
- **src/rds_agent/**:
  - django_project/ (Django配置)
  - scheduler/ (调度模块)
    - models/ (Django ORM)
    - api/ (DRF ViewSets)
    - tasks/ (Celery Tasks)
    - services/ (业务逻辑)
  - diagnostic/ (诊断Agent)
  - core/ (问答Agent)
  - tools/ (LangChain Tools)
  - utils/ (配置管理)
  - memory/ (记忆系统)
- **tests/**:
  - test_django/ (Django测试)
  - test_integration/ (集成测试)
  - test_agent/ (Agent测试)
  - test_tools/ (工具测试)
- **docs/**: 架构文档
- **knowledge/**: MySQL运维知识库

---

## 技术栈概览

| 层级 | 技术 | 说明 |
|------|------|------|
| Web框架 | Django 4.2 + DRF 3.15 | REST API、ORM模型、ViewSet |
| 任务调度 | Celery 5.3 + Redis + django-celery-beat | 分布式任务队列、定时调度 |
| 数据存储 | MySQL + Django ORM | 任务、告警、历史持久化 |
| Agent框架 | LangChain + LangGraph | 状态机模型，复杂任务编排 |
| LLM | Ollama + Qwen2.5-14B | 本地部署，数据安全 |
| Embeddings | nomic-embed-text | 向量嵌入 |
| 向量库 | ChromaDB | 知识库存储 |
| CLI | Rich + Prompt Toolkit | 美化命令行 |

---

## 核心模块说明

### Phase 1: 智能问答助手
- **core/agent.py**: LangGraph问答Agent
- **tools/**: 8个核心工具 (instance/performance/sql/connection/storage/parameters/knowledge/diagnostic)
- **utils/config.py**: pydantic-settings配置管理

### Phase 2: 智能运维助手
- **diagnostic/agent.py**: LangGraph诊断Agent
- **diagnostic/state.py**: DiagnosticState状态定义
- **diagnostic/nodes.py**: 检查节点实现
- **diagnostic/checks.py**: 13项诊断检查
- **diagnostic/report_generator.py**: JSON报告生成
- **diagnostic/parameter_optimizer.py**: 参数优化建议

### Phase 3: 自动化巡检系统 (Django + Celery)

#### Django ORM Models
| 模型 | 说明 |
|------|------|
| InspectionTask | 巡检任务配置 (目标实例、调度类型、告警配置) |
| TaskExecution | 任务执行记录 (分数、状态、结果数据) |
| AlertRule | 告警规则 (指标、阈值、级别) |
| AlertEvent | 告警事件 (触发、状态、通知) |
| HealthHistory | 健康历史 (分数、趋势) |
| NotificationChannel | 通知渠道 (类型、配置) |

#### Celery Tasks
| 任务 | 说明 |
|------|------|
| run_inspection_task | 执行巡检任务，遍历目标实例 |
| run_single_inspection | 单实例诊断，调用DiagnosticAgent |
| check_alerts | 检查告警规则，触发AlertService |
| record_health_history | 记录健康历史，调用HistoryService |
| send_notification | 发送告警通知，支持多渠道 |

#### Services Layer
| 服务 | 说明 |
|------|------|
| TaskService | schedule_task, run_task_now, cancel_task, update_statistics |
| AlertService | check_and_trigger_alerts, _should_trigger_alert, _is_suppressed |
| HistoryService | record_health, get_health_trend, get_instance_history |
| NotificationService | send_to_channels, test_channel |

#### API Endpoints (DRF)
| 端点 | ViewSet | 操作 |
|------|---------|------|
| /api/scheduler/tasks/ | InspectionTaskViewSet | CRUD + enable/disable/run |
| /api/scheduler/alerts/rules/ | AlertRuleViewSet | CRUD |
| /api/scheduler/alerts/events/ | AlertEventViewSet | List |
| /api/scheduler/history/ | HealthHistoryViewSet | List |
| /api/scheduler/notifications/channels/ | NotificationChannelViewSet | CRUD + test |

---

## 默认告警规则

| 规则 | 指标 | 条件 | 级别 |
|------|------|------|------|
| 健康分数过低 | overall_score | < 60 | critical |
| 健康分数偏低 | overall_score | < 80 | warning |
| 严重问题检测 | critical_count | > 0 | critical |
| 警告数量过多 | warning_count | > 5 | warning |

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

- **源文件**: 50+
- **测试文件**: 40+
- **模块**: 8个 (django_project, scheduler, diagnostic, core, tools, utils, memory, api)
- **架构**: Django 4.2 + Celery 5.3 + MySQL + Redis