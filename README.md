# Quick Capture Agent

一个基于 Claude Agent SDK 构建的多代理助手系统，用于日常任务自动化。

## 功能特点

- **智能任务路由**: 主代理自动分析任务并分发给最合适的子代理
- **模块化架构**: 易于添加新的专业代理
- **知识库存储**: 持久化存储收集的内容，支持分类和搜索
- **CLI 界面**: 简洁的命令行工具，支持交互模式

## 架构

```
┌─────────────────────────────────────────────────┐
│                  Helper Agent                    │
│              (主协调器 - claude-opus-4-5)         │
└─────────────────┬───────────────────────────────┘
                  │
        ┌─────────┴─────────┐
        ▼                   ▼
┌───────────────┐   ┌───────────────────┐
│ Research Agent │   │ Content Collector │
│ (调研代理)      │   │   (内容收集代理)   │
└───────────────┘   └───────────────────┘
                            │
                            ▼
                    ┌───────────────┐
                    │ Knowledge Base │
                    │   (知识库)      │
                    └───────────────┘
```

## 安装

```bash
# 克隆项目
git clone <repository-url>
cd quick_capture_agent

# 安装依赖
pip install -e .

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，添加你的 ANTHROPIC_API_KEY
```

## CLI 命令

所有命令都在 `src/quick_capture_agent/main.py` 中使用 [Typer](https://typer.tiangolo.com/) 框架定义。

### 基本用法

```bash
# 查看帮助
qca --help

# 查看可用代理
qca agents
```

### 命令列表

| 命令 | 描述 | 定义位置 |
|------|------|----------|
| `qca run` | 执行任意任务 | `main.py:35-60` |
| `qca research` | 专门做调研任务 | `main.py:63-83` |
| `qca collect` | 收集和处理内容 | `main.py:86-112` |
| `qca kb` | 管理知识库 | `main.py:115-163` |
| `qca agents` | 列出可用代理 | `main.py:166-176` |
| `qca interactive` | 交互式会话 | `main.py:179-218` |

### 详细用法

#### 1. 执行任务 (`run`)

```bash
# 基本用法 - 自动选择代理
qca run "research the latest AI trends"

# 指定使用特定代理
qca run "summarize this article" --agent content_collector

# 详细输出
qca run "compare Python and Rust" --verbose
```

#### 2. 调研 (`research`)

```bash
# 快速调研
qca research "what is Claude Agent SDK" --depth quick

# 标准调研
qca research "machine learning frameworks comparison"

# 深度调研
qca research "AI agent architectures in 2024" --depth comprehensive
```

调研深度选项:
- `quick`: 快速概览，2-3 个来源
- `standard`: 标准调研，多来源分析
- `comprehensive`: 全面调研，深入分析所有方面

#### 3. 收集内容 (`collect`)

```bash
# 收集网页文章
qca collect "https://example.com/blog/article"

# 指定分类
qca collect "https://example.com/tutorial" --category articles

# 不存储到知识库（仅处理）
qca collect "https://example.com/news" --no-store
```

支持的内容类型:
- 文章/博客 (Articles)
- 图片 (Images)
- 播客 (Podcasts)
- 视频 (Videos)
- 文档 (Documents)
- 研究论文 (Research Papers)

#### 4. 知识库管理 (`kb`)

```bash
# 查看统计信息
qca kb stats

# 列出所有内容
qca kb list

# 按分类列出
qca kb list --category articles

# 搜索内容
qca kb search --query "machine learning"

# 获取特定条目
qca kb get --id "20241220123456-abc12345"
```

#### 5. 交互模式 (`interactive`)

```bash
qca interactive
```

在交互模式中:
- 直接输入任务，自动路由到合适的代理
- 使用 `@agent_name` 指定代理，如 `@research what is RAG`
- 输入 `quit` 或 `exit` 退出

## 代理详情

### Helper Agent (主协调器)

- **模型**: claude-opus-4-5
- **职责**: 分析用户请求，选择合适的子代理，协调多步骤任务
- **代码**: `src/quick_capture_agent/orchestrator/helper_agent.py`

### Research Agent (调研代理)

- **模型**: claude-sonnet-4-5
- **职责**: 网络搜索、信息收集、对比分析、生成调研报告
- **工具**: WebSearch, WebFetch, Read, Write, Grep, Glob
- **代码**: `src/quick_capture_agent/agents/research/agent.py`

### Content Collector Agent (内容收集代理)

- **模型**: claude-sonnet-4-5
- **职责**: 处理各类媒体内容，提取信息，分类存储到知识库
- **工具**: WebFetch, Read, Write, Bash
- **代码**: `src/quick_capture_agent/agents/content_collector/agent.py`

## 添加新代理

1. **创建代理目录**
   ```bash
   mkdir -p src/quick_capture_agent/agents/my_agent
   ```

2. **实现代理类** (`agents/my_agent/agent.py`)
   ```python
   from quick_capture_agent.agents.base import BaseAgent, AgentConfig, AgentResult

   class MyAgent(BaseAgent):
       def _default_config(self) -> AgentConfig:
           return AgentConfig(
               name="my_agent",
               description="Description of what this agent does",
               model="claude-sonnet-4-5-20241022",
               tools=["Read", "Write"],
           )

       def _build_system_prompt(self) -> str:
           return "You are an expert at..."

       async def execute(self, task: str, context: dict = None) -> AgentResult:
           # 实现你的逻辑
           return AgentResult(success=True, data={"result": "..."})
   ```

3. **注册代理** (`orchestrator/helper_agent.py`)
   ```python
   def _initialize_agents(self) -> None:
       self.registry.register(ResearchAgent())
       self.registry.register(ContentCollectorAgent())
       self.registry.register(MyAgent())  # 添加这行
   ```

4. **添加代理定义** (`.claude/agents/my_agent.md`)
   ```markdown
   # My Agent

   Description and usage examples...
   ```

## 项目结构

```
quick_capture_agent/
├── src/quick_capture_agent/
│   ├── __init__.py
│   ├── main.py                 # CLI 入口和命令定义
│   ├── orchestrator/
│   │   └── helper_agent.py     # 主协调器
│   ├── agents/
│   │   ├── base.py             # BaseAgent 基类
│   │   ├── research/
│   │   │   └── agent.py        # 调研代理
│   │   └── content_collector/
│   │       └── agent.py        # 内容收集代理
│   ├── knowledge_base/
│   │   └── store.py            # 知识库存储
│   ├── tools/
│   │   └── custom_tools.py     # 自定义工具
│   └── utils/
│       └── helpers.py          # 工具函数
├── .claude/agents/             # 代理 Markdown 定义
├── config/
│   └── settings.py             # 配置管理
├── data/knowledge/             # 知识库存储目录
├── tests/
│   └── test_agents.py          # 测试
├── pyproject.toml              # 项目配置
├── .env.example                # 环境变量模板
└── CLAUDE.md                   # Claude Code 项目上下文
```

## 配置

### 环境变量 (`.env`)

```bash
# 必需
ANTHROPIC_API_KEY=your_api_key_here

# 可选 - 模型设置
DEFAULT_MODEL=claude-sonnet-4-5-20241022
ORCHESTRATOR_MODEL=claude-opus-4-5-20250514

# 可选 - 知识库路径
KNOWLEDGE_BASE_PATH=./data/knowledge
```

## 测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定测试
pytest tests/test_agents.py::TestResearchAgent -v

# 带覆盖率报告
pytest tests/ --cov=quick_capture_agent
```

## 依赖

主要依赖:
- `claude-agent-sdk`: Claude Agent SDK
- `anthropic`: Anthropic API 客户端
- `typer`: CLI 框架
- `rich`: 终端美化输出
- `pydantic`: 数据验证
- `aiohttp`/`aiofiles`: 异步 HTTP 和文件操作

可选依赖 (用于媒体处理):
- `yt-dlp`: YouTube 视频信息提取
- `feedparser`: RSS 订阅解析
- `openai-whisper`: 音频转文字
- `Pillow`: 图片处理

## License

MIT
