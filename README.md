# RDS Agent

MySQL数据库智能问答助手和智能运维助手，基于 Django + Celery 架构。

## 功能特性

### Phase 1: 智能问答助手
- 实例基本信息查询（规格、版本、部署架构）
- 容量使用情况分析（存储空间、表大小、增长趋势）
- 性能诊断（慢SQL、连接数、IO问题）
- 参数查询（关键参数配置、优化建议）
- 空间分析（表空间、索引大小、碎片）
- 连接诊断（连接数、活跃会话、锁等待）

### Phase 2: 智能运维助手
- 自动化诊断流程 (DiagnosticAgent)
- 异常检测与告警 (AlertService)
- 定时巡检任务调度 (Celery + django-celery-beat)
- 实例巡检报告生成 (ReportGenerator)
- 参数优化建议 (ParameterOptimizer)
- 健康趋势分析 (HistoryService)
- 多渠道通知 (DingTalk/Email/WeChat/Webhook)

## 技术架构

### 核心框架
- **Web框架**: Django 4.2 + Django REST Framework
- **任务调度**: Celery 5.3 + Redis + django-celery-beat
- **数据存储**: MySQL (Django ORM)
- **Agent框架**: LangChain + LangGraph
- **LLM**: 本地模型 (Qwen2.5-14B via Ollama)

### 模块划分
| 模块 | 技术 | 说明 |
|------|------|------|
| `django_project` | Django | Django 项目配置、Celery 配置 |
| `scheduler` | Django ORM + Celery | 任务调度、告警、历史、通知 |
| `diagnostic` | LangGraph | 13项诊断检查、报告生成 |
| `core` | LangGraph | 问答 Agent、意图识别 |
| `tools` | LangChain Tools | 数据采集工具层 |
| `utils` | pydantic-settings | 配置管理 |

## 快速开始

### 1. 安装依赖

```bash
# 使用uv安装
uv pip install -e .

# 或使用pip
pip install -e .
```

### 2. 安装Ollama并下载模型

```bash
# 安装Ollama (macOS/Linux)
curl -fsSL https://ollama.com/install.sh | sh

# 下载Qwen2.5-14B模型
ollama pull qwen2.5:14b

# 下载embedding模型
ollama pull nomic-embed-text
```

### 3. 配置环境变量

```bash
cp .env.example .env
# 编辑.env文件，配置数据库、Redis、Ollama等
```

关键配置项:
```bash
# Django
DJANGO_SECRET_KEY=your-secret-key
DJANGO_DEBUG=True

# MySQL Database
DB_NAME=rds_agent
DB_USER=root
DB_PASSWORD=your-password
DB_HOST=localhost
DB_PORT=3306

# Redis (Celery Broker)
REDIS_URL=redis://localhost:6379/0

# Ollama
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen2.5:14b
```

### 4. 初始化数据库

```bash
# 创建数据库
mysql -u root -p -e "CREATE DATABASE rds_agent CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 运行迁移
python manage.py migrate

# 创建默认告警规则
python manage.py shell -c "from scheduler.services.alert_service import AlertService; AlertService._create_default_rules()"
```

### 5. 启动服务

```bash
# Django Web服务
python manage.py runserver 0.0.0.0:8000

# Celery Worker (任务执行)
celery -A rds_agent worker -l info --concurrency=5

# Celery Beat (定时调度)
celery -A rds_agent beat -l info

# CLI交互模式
rds-agent chat

# 查看帮助
rds-agent --help
```

## 项目结构

```
rds-agent/
├── manage.py                    # Django 入口脚本
├── pyproject.toml               # 项目配置和依赖
├── pytest.ini                   # pytest 配置
├── .env.example                 # 环境变量模板
│
├── src/rds_agent/
│   ├── django_project/          # Django 项目配置
│   │   ├── settings.py          # Django settings (MySQL, Celery, DRF)
│   │   ├── urls.py              # URL routing
│   │   ├── celery.py            # Celery app 配置
│   │   └── wsgi.py              # WSGI 入口
│   │
│   ├── scheduler/               # 调度模块 (Django App)
│   │   ├── models/              # Django ORM 模型
│   │   │   ├── task.py          # InspectionTask (任务)
│   │   │   ├── execution.py     # TaskExecution (执行记录)
│   │   │   ├── alert.py         # AlertRule, AlertEvent (告警)
│   │   │   ├── history.py       # HealthHistory (历史)
│   │   │   └── notification.py  # NotificationChannel (通知渠道)
│   │   │
│   │   ├── api/                 # DRF API 层
│   │   │   ├── views.py         # ViewSets (5个)
│   │   │   ├── serializers.py   # Serializers
│   │   │   └── urls.py          # API路由
│   │   │
│   │   ├── tasks/               # Celery 任务
│   │   │   ├── inspection.py    # run_inspection_task, check_alerts
│   │   │   └── notification.py  # send_notification
│   │   │
│   │   ├── services/            # 业务逻辑层
│   │   │   ├── task_service.py  # 任务调度服务
│   │   │   ├── alert_service.py # 告警检查服务
│   │   │   ├── history_service.py # 历史记录服务
│   │   │   └── notification_service.py # 通知服务
│   │   │
│   │   └── apps.py              # Django App配置
│   │
│   ├── diagnostic/              # 诊断 Agent (LangGraph)
│   │   ├── agent.py             # DiagnosticAgent
│   │   ├── state.py             # DiagnosticState
│   │   ├── nodes.py             # 检查节点
│   │   ├── checks.py            # 13项检查实现
│   │   ├── report_generator.py  # 报告生成
│   │   └── parameter_optimizer.py # 参数优化
│   │
│   ├── core/                    # 问答 Agent (LangGraph)
│   │   ├── agent.py             # Agent 主类
│   │   ├── state.py             # AgentState
│   │   ├── nodes.py             # 处理节点
│   │   └── prompts.py           # Prompt模板
│   │
│   ├── tools/                   # 工具层 (LangChain Tools)
│   │   ├── instance.py          # 实例信息
│   │   ├── performance.py       # 性能监控
│   │   ├── sql.py               # SQL诊断
│   │   ├── connection.py        # 连接诊断
│   │   ├── storage.py           # 存储分析
│   │   ├── parameters.py        # 参数查询
│   │   ├── knowledge.py         # 知识检索
│   │   └── diagnostic.py        # 诊断工具
│   │
│   └── utils/                   # 工具函数
│       ├── config.py            # 配置管理 (pydantic-settings)
│       └── logger.py            # 日志配置
│
├── tests/                       # 测试目录
│   ├── test_django/             # Django 测试
│   │   ├── test_models/         # 模型测试
│   │   ├── test_api/            # API测试
│   │   ├── test_tasks/          # Celery任务测试
│   │   └── test_services/       # 服务测试
│   │
│   ├── test_integration/        # 集成测试
│   │   └── test_full_flow.py    # 全流程测试
│   │
│   ├── test_agent/              # Agent测试
│   ├── test_tools/              # 工具测试
│   └── test_scheduler/          # 调度测试
│
├── knowledge/                   # 知识库文档
│   └── mysql/                   # MySQL运维知识
│       ├── architecture.md
│       ├── parameters.md
│       ├── performance.md
│       └── troubleshooting.md
│
├── docs/                        # 文档
│   └── architecture/            # 架构图
│       ├── system_architecture.svg
│       ├── scheduler_architecture.svg
│       ├── module_dependencies.svg
│       └── project_structure.svg
│
└── scripts/                     # 脚本
    ├── demo.py                  # 演示脚本
    ├── init_knowledge.py        # 初始化知识库
    └── run_tests.py             # 测试脚本
```

## API 端点

### 任务管理
| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/scheduler/tasks/` | 任务列表 |
| POST | `/api/scheduler/tasks/` | 创建任务 |
| GET | `/api/scheduler/tasks/{id}/` | 任务详情 |
| PATCH | `/api/scheduler/tasks/{id}/` | 更新任务 |
| DELETE | `/api/scheduler/tasks/{id}/` | 删除任务 |
| POST | `/api/scheduler/tasks/{id}/enable/` | 启用任务 |
| POST | `/api/scheduler/tasks/{id}/disable/` | 禁用任务 |
| POST | `/api/scheduler/tasks/{id}/run/` | 立即执行 |

### 告警管理
| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/scheduler/alerts/rules/` | 告警规则列表 |
| POST | `/api/scheduler/alerts/rules/` | 创建规则 |
| GET | `/api/scheduler/alerts/events/` | 告警事件列表 |

### 历史与通知
| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/scheduler/history/` | 健康历史列表 |
| GET | `/api/scheduler/notifications/channels/` | 通知渠道列表 |
| POST | `/api/scheduler/notifications/channels/` | 创建渠道 |
| POST | `/api/scheduler/notifications/channels/{id}/test/` | 测试渠道 |

### 系统信息
| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/` | 项目信息 |
| GET | `/health/` | 健康检查 |
| GET | `/config/` | 配置信息 |

## 开发

```bash
# 安装开发依赖
uv pip install -e ".[dev]"

# 运行所有测试
pytest

# 运行 Django 测试
pytest tests/test_django/

# 运行集成测试
pytest tests/test_integration/

# 运行测试并生成覆盖率报告
pytest --cov=src/rds_agent --cov-report=html

# 代码格式化
ruff format .

# 类型检查
mypy src/
```

## Celery 任务

### 任务类型
- `run_inspection_task` - 执行巡检任务（遍历目标实例）
- `run_single_inspection` - 单实例诊断
- `check_alerts` - 检查告警规则
- `record_health_history` - 记录健康历史
- `send_notification` - 发送通知

### 调度类型
- `INTERVAL` - 间隔调度（秒）
- `CRON` - Cron表达式调度
- `ONCE` - 立即执行一次

### 告警规则 (默认)
| 规则 | 条件 | 级别 |
|------|------|------|
| 健康分数过低 | overall_score < 60 | critical |
| 健康分数偏低 | overall_score < 80 | warning |
| 严重问题检测 | critical_count > 0 | critical |
| 警告数量过多 | warning_count > 5 | warning |

### 通知渠道
- DingTalk (钉钉机器人)
- Email (邮件)
- WeChat (企业微信)
- Webhook (自定义HTTP回调)

## 初始化知识库

```bash
# 初始化MySQL运维知识库
python scripts/init_knowledge.py --action init

# 清空并重新初始化
python scripts/init_knowledge.py --action reinit

# 清空知识库
python scripts/init_knowledge.py --action clear
```

## License

MIT