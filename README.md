# RDS Agent

MySQL数据库智能问答助手和智能运维助手。

## 功能特性

### Phase 1: 智能问答助手
- 实例基本信息查询（规格、版本、部署架构）
- 容量使用情况分析（存储空间、表大小、增长趋势）
- 性能诊断（慢SQL、连接数、IO问题）
- 参数查询（关键参数配置、优化建议）
- 空间分析（表空间、索引大小、碎片）
- 连接诊断（连接数、活跃会话、锁等待）

### Phase 2: 智能运维助手（规划中）
- 自动化诊断流程
- 异常检测与告警
- 实例巡检报告
- 参数优化建议

## 技术架构

- **Agent框架**: LangChain + LangGraph
- **LLM**: 本地模型 (Qwen2.5-14B via Ollama)
- **数据访问**: 实例管理平台API + MySQL直连
- **用户界面**: CLI + FastAPI Web API

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
# 编辑.env文件，配置你的实例管理平台地址和Token
```

### 4. 启动服务

```bash
# CLI交互模式
rds-agent chat

# Web API服务
rds-agent api --host 127.0.0.1 --port 8000

# 查看帮助
rds-agent --help
```

## 项目结构

```
rds-agent/
├── src/rds_agent/
│   ├── core/           # Agent核心 (LangGraph)
│   ├── tools/          # 工具层 (诊断工具)
│   ├── data/           # 数据访问层
│   ├── memory/         # 记忆系统
│   └── utils/          # 工具函数
├── knowledge/          # 知识库文档
├── tests/              # 测试
└── scripts/            # 脚本
```

## 开发

```bash
# 安装开发依赖
uv pip install -e ".[dev]"

# 运行所有测试
pytest

# 运行单元测试
pytest -m unit tests/test_tools/ tests/test_agent/

# 运行集成测试
pytest -m integration tests/test_integration.py

# 运行测试并生成覆盖率报告
pytest --cov=src/rds_agent --cov-report=html

# 使用测试脚本
python scripts/run_tests.py --type unit

# 代码格式化
ruff format .

# 类型检查
mypy src/
```

## 测试结构

```
tests/
├── conftest.py           # pytest配置和fixtures
├── test_tools/           # 工具层测试
│   ├── test_tools.py     # 工具函数测试
│   ├── test_models.py    # 数据模型测试
│   ├── test_mysql_client.py    # MySQL客户端测试
│   ├── test_instance_platform.py  # 平台API测试
│   └── test_vector_store.py    # 向量库测试
├── test_agent/           # Agent核心测试
│   ├── test_state.py     # 状态定义测试
│   ├── test_nodes.py     # 节点函数测试
│   └── test_agent.py     # Agent主类测试
└── test_integration.py   # 集成测试
```

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