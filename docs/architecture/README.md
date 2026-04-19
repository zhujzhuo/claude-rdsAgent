# RDS Agent 架构文档

本目录包含 RDS Agent 项目的架构设计文档和图表。

## 架构图索引

### 1. 系统整体架构图
**文件**: [system_architecture.svg](system_architecture.svg)

展示系统的分层架构，包括：
- 用户交互层 (CLI/Web API/Scheduler API)
- Agent核心层 (问答Agent/诊断Agent/调度器)
- 工具层 (LangChain Tools)
- 数据访问层 (MySQL Client/Instance Platform/Vector Store)
- LLM层 (Ollama + Qwen2.5-14B)

### 2. 模块依赖关系图
**文件**: [module_dependencies.svg](module_dependencies.svg)

展示各模块之间的依赖关系：
- core → tools, data, utils
- diagnostic → tools, data
- scheduler → diagnostic, data
- api → core, scheduler
- tools → data

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

展示调度器模块的内部架构：
- TaskScheduler (APScheduler)
- AlertEngine (规则引擎 + 抑制机制)
- HistoryStore (趋势分析)
- NotificationManager (多渠道发送)
- 默认告警规则 (4条)

### 5. 项目目录结构图
**文件**: [project_structure.svg](project_structure.svg)

展示项目的文件目录结构：
- src/rds_agent/ (核心代码)
- tests/ (测试代码)
- docs/ (文档)
- knowledge/ (知识库)

---

## 技术栈概览

| 层级 | 技术 | 说明 |
|------|------|------|
| Agent框架 | LangChain + LangGraph | 状态机模型，支持复杂任务编排 |
| LLM | Ollama + Qwen2.5-14B | 本地部署，数据安全 |
| 任务调度 | APScheduler | Cron/Interval/One-time调度 |
| Web API | FastAPI | 高性能异步API |
| 数据库 | MySQL + SQLAlchemy | 直连数据库，连接池 |
| 向量库 | ChromaDB | 知识库存储 |
| CLI | Rich + Prompt Toolkit | 美化命令行 |

---

## 核心模块说明

### Phase 1: 智能问答助手
- **core/agent.py**: LangGraph问答Agent
- **tools/**: 7个核心工具 (实例/性能/SQL/连接/存储/参数/知识)
- **data/**: 数据访问层

### Phase 2: 智能运维助手
- **diagnostic/agent.py**: LangGraph诊断Agent
- **diagnostic/checks.py**: 13项诊断检查
- **diagnostic/report_generator.py**: 报告生成

### Phase 3: 自动化巡检系统
- **scheduler/executor.py**: 任务调度
- **scheduler/alert_engine.py**: 告警规则引擎
- **scheduler/history_store.py**: 健康趋势分析
- **scheduler/notification.py**: 多渠道通知