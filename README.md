# RDS Agent

MySQL数据库智能问答助手和智能运维助手，基于 Django + Celery 架构，支持三层问题分类路由和 Skills/SOP 标准化诊断流程。

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

### Phase 3: 三层问题分类路由
- **SIMPLE_QA**: 简单常识问答 → Hermes + 知识库
- **SOP_SKILL**: 专业垂直问题 → Skills/SOP 标准化流程
- **GENERAL**: 泛化问题 → LangGraph 自主规划

### Phase 4: Skills/SOP 标准化诊断
- CPU 使用率分析 SOP（9步流程，避免因果颠倒）
- 存储磁盘增长点分析 SOP
- 慢 SQL 优化流程 SOP
- 连接数问题分析 SOP

## 技术架构

### 核心框架
- **Web框架**: Django 4.2 + Django REST Framework
- **任务调度**: Celery 5.3 + Redis + django-celery-beat
- **数据存储**: MySQL (Django ORM)
- **Agent框架**: RouterAgent + LangGraph + Hermes + Skills/SOP
- **LLM**: Qwen2.5-14B / Hermes 3 (via Ollama)

### 三层路由架构

| 问题类型 | 执行路径 | 示例 |
|----------|----------|------|
| **SIMPLE_QA** | Hermes + 知识库 | "什么是 Buffer Pool？" |
| **SOP_SKILL** | Skills/SOP | "db-01 的 CPU 使用率过高" |
| **GENERAL** | LangGraph | "帮我诊断 db-01" |

### 三架构 Agent

| Agent 类型 | 框架 | 模型 | 特点 | 适用场景 |
|-----------|------|------|------|---------|
| **Hermes Agent** | Function Calling | Hermes 3 | 原生工具调用、高效 | 简单问答、知识库 |
| **Skills/SOP Agent** | SOP 流程 | 任意 | 标准化流程、精确规划 | 专业垂直问题、根因定位 |
| **LangGraph Agent** | LangGraph | Qwen2.5-14B | 状态机编排、复杂流程 | 泛化问题、完整诊断 |

### 模块划分
| 模块 | 技术 | 说明 |
|------|------|------|
| `router` | RouterAgent | 三层问题分类路由 |
| `skills` | SOP/SkillExecutor | 标准化诊断流程 |
| `django_project` | Django | Django 项目配置 |
| `scheduler` | Django ORM + Celery | 任务调度、告警、历史 |
| `diagnostic` | LangGraph | 13项诊断检查 |
| `core` | LangGraph | 问答 Agent |
| `hermes` | Function Calling | Hermes Agent |
| `tools` | LangChain Tools | 数据采集工具 |

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

# 下载 Qwen2.5-14B 模型 (LangGraph Agent)
ollama pull qwen2.5:14b

# 下载 Hermes 3 模型 (Function Calling Agent)
ollama pull hermes3

# 下载 embedding 模型
ollama pull nomic-embed-text
```

### 3. 配置环境变量

```bash
cp .env.example .env
# 编辑.env文件
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

# Ollama (LangGraph Agent)
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen2.5:14b

# Hermes Agent (Function Calling)
HERMES_ENABLED=True
HERMES_MODEL=hermes3
HERMES_MAX_ITERATIONS=10

# Agent 类型选择 (推荐 auto)
AGENT_TYPE=auto
ROUTER_AUTO_SELECT=true
```

### 4. 初始化数据库

```bash
mysql -u root -p -e "CREATE DATABASE rds_agent CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
python manage.py migrate
python manage.py shell -c "from scheduler.services.alert_service import AlertService; AlertService._create_default_rules()"
```

### 5. 启动服务

```bash
# Django Web服务
python manage.py runserver 0.0.0.0:8000

# Celery Worker
celery -A rds_agent worker -l info --concurrency=5

# Celery Beat
celery -A rds_agent beat -l info

# CLI交互模式
rds-agent chat
```

## 三层路由使用示例

### SIMPLE_QA (简单问答)

```bash
# CLI
rds-agent chat
> 什么是 Buffer Pool？
> 如何优化 MySQL 性能？
> InnoDB 和 MyISAM 有什么区别？

# 自动路由到 Hermes + 知识库
```

### SOP_SKILL (专业垂直问题)

```bash
# CLI
rds-agent chat
> db-01 的 CPU 使用率过高
> 分析 db-prod 的存储增长点
> 优化 db-01 的慢 SQL
> db-01 连接数过高怎么办

# 自动路由到 Skills/SOP 执行
# CPU 分析 SOP: 9步标准化流程
# - 监控数据 → 会话检查 → Profiling → 慢SQL → 执行计划 → 锁等待 → Buffer Pool → 根因分析 → 建议
# - 决策点: 会话突增 > 50% → 根因定位为业务突增
```

### GENERAL (泛化问题)

```bash
# CLI
rds-agent chat
> 帮我诊断 db-01
> 对 db-prod 做完整巡检
> 检查 db-01 的性能情况

# 自动路由到 LangGraph 或 Diagnostic
```

## RouterAgent 使用

### 基本使用

```python
from rds_agent.router import get_router_agent

# 获取 RouterAgent
router = get_router_agent()

# 三层自动路由
result = router.invoke("db-01 的 CPU 使用率过高")
print(result["response"])
print(f"路由类型: {result['agent_type']}")
print(f"问题分类: {result['question_category']}")

# 简化接口
response = router.chat("什么是 Buffer Pool")
print(response)
```

### 问题分类

```python
from rds_agent.router import classify_question

# 分类问题
category, skill_type = classify_question("db-01 CPU 使用率过高")
print(f"分类: {category}")  # SOP_SKILL
print(f"Skill类型: {skill_type}")  # CPU_ANALYSIS
```

## Skills/SOP 使用

### 执行 Skill

```python
from rds_agent.skills import get_skill_executor, SkillType

# 获取执行器
executor = get_skill_executor()

# 执行 CPU 分析 SOP
result = executor.execute(
    SkillType.CPU_ANALYSIS,
    instance_name="db-prod-01"
)

print(f"根因: {result['root_cause']}")
print(f"进度: {result['progress']}%")
print(f"结论: {result['conclusion']}")
```

### CPU 分析 SOP 流程

```
步骤1: get_monitoring_data    → 获取 CPU 监控数据
步骤2: check_session_change   → 检查会话数突增（关键决策点）
步骤3: get_profiling          → 获取 CPU 高峰 Profiling
步骤4: get_slow_queries       → 获取慢 SQL
步骤5: analyze_sql_plan       → 分析执行计划
步骤6: check_lock_status      → 检查锁等待
步骤7: check_buffer_pool      → 检查 Buffer Pool
步骤8: root_cause_analysis    → 综合分析定位根因
步骤9: generate_recommendations → 生成优化建议

决策点: session_change > 50% → 根因: 业务突增导致会话激增
```

### 注册自定义 Skill

```python
from rds_agent.skills import BaseSkill, SOP, SOPStep, SkillType

class MyCustomSkill(BaseSkill):
    skill_type = SkillType.PERFORMANCE_ANALYSIS
    sop = SOP(
        name="custom_sop",
        skill_type=SkillType.PERFORMANCE_ANALYSIS,
        steps=[
            SOPStep(name="step1", tool_name="my_tool", tool_params={"param": "$instance_name"}),
        ]
    )

    def get_sop(self):
        return self.sop

    def _analyze_output(self, step, output):
        return f"分析结果: {output}"

# 注册
executor = get_skill_executor()
executor.register_skill(MyCustomSkill)
```

## 项目结构

```
rds-agent/
├── src/rds_agent/
│   ├── router/                  # 路由模块 (三层分类)
│   │   ├── agent.py             # RouterAgent
│   │   ├── classifier.py        # QuestionClassifier
│   │
│   ├── skills/                  # Skills/SOP 模块
│   │   ├── base.py              # SOPStep, SOP, BaseSkill
│   │   ├── executor.py          # SkillExecutor
│   │   ├── cpu_skill.py         # CPU 分析 Skill (9步)
│   │   ├── storage_skill.py     # 存储分析 Skill
│   │   ├── sql_skill.py         # SQL 优化 Skill
│   │   ├── connection_skill.py  # 连接分析 Skill
│   │   ├── sops/                # SOP 定义
│   │   │   └── cpu_sop.py       # CPU SOP
│   │
│   ├── hermes/                  # Hermes Agent
│   ├── diagnostic/              # 诊断 Agent
│   ├── core/                    # 问答 Agent
│   ├── tools/                   # 工具层
│   └── utils/                   # 工具函数
│
├── tests/
│   ├── test_router/             # 路由测试
│   ├── test_skills/             # Skills 测试
│   └── ...
│
└── docs/architecture/           # 架构文档
```

## API 端点

| 方法 | 端点 | 说明 |
|------|------|------|
| GET/POST | `/api/scheduler/tasks/` | 任务管理 |
| GET/POST | `/api/scheduler/alerts/rules/` | 告警规则 |
| GET | `/api/scheduler/alerts/events/` | 告警事件 |
| GET | `/api/scheduler/history/` | 健康历史 |
| GET/POST | `/api/scheduler/notifications/channels/` | 通知渠道 |

## 开发

```bash
# 安装开发依赖
uv pip install -e ".[dev]"

# 运行所有测试
pytest

# 运行路由测试
pytest tests/test_router/

# 运行 Skills 测试
pytest tests/test_skills/

# 代码格式化
ruff format .
```

## License

MIT