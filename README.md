# Quick Capture Agent

一个基于 Claude Agent SDK 构建的多代理助手系统，用于日常任务自动化和知识管理。

## 功能特点

- **智能内容捕获**: 支持文章链接、文字、图片、文档等多种输入
- **Telegram Bot**: 随时随地通过 Telegram 捕获内容
- **Obsidian 集成**: 自动生成 Markdown 并存入 Obsidian 知识库
- **智能分类**: AI 自动分析内容类型、提取要点、打标签
- **多代理架构**: 模块化设计，易于扩展

## 架构

```
┌─────────────────────────────────────────────────────────────┐
│                        输入渠道                              │
├──────────┬──────────┬──────────┬──────────────────────────┤
│ Telegram │   CLI    │  文件     │        URL              │
│   Bot    │  命令行   │  上传     │        链接             │
└────┬─────┴────┬─────┴────┬─────┴────────────┬─────────────┘
     │          │          │                  │
     └──────────┴──────────┴─────────┬────────┘
                                     │
                    ┌────────────────▼────────────────┐
                    │       Content Processor         │
                    │  • 类型识别  • 内容提取           │
                    │  • AI 分析   • 自动分类           │
                    └────────────────┬────────────────┘
                                     │
                    ┌────────────────▼────────────────┐
                    │     Markdown Generator          │
                    │  • 统一模板  • YAML frontmatter  │
                    └────────────────┬────────────────┘
                                     │
                    ┌────────────────▼────────────────┐
                    │    Obsidian Vault (知识库)       │
                    │  📁 Articles/  📁 Concepts/     │
                    │  📁 AI-Summaries/  📁 Daily/    │
                    └─────────────────────────────────┘
```

## 快速开始

### 安装

```bash
# 克隆项目
git clone <repository-url>
cd quick_capture_agent

# 安装依赖
pip install -e .

# 安装完整功能（包括音频转写等）
pip install -e ".[full]"

# 配置环境变量
cp .env.example .env
```

### 初始化知识库

```bash
# 创建 Obsidian 兼容的知识库
qca init-vault ./my-knowledge-base
```

### 捕获内容

```bash
# 捕获文章链接
qca capture "https://example.com/article"

# 捕获文字内容
qca capture "这是一段要保存的笔记..."

# 指定分类和标签
qca capture "内容..." --category ai --tags "llm,agent"
```

### 启动 Telegram Bot

```bash
# 设置环境变量
export TELEGRAM_BOT_TOKEN=your_bot_token

# 启动 bot
qca bot
```

## CLI 命令

| 命令 | 描述 |
|------|------|
| `qca capture` | 快速捕获内容到知识库 |
| `qca bot` | 启动 Telegram Bot |
| `qca init-vault` | 初始化 Obsidian 知识库 |
| `qca run` | 执行任意任务 |
| `qca research` | 调研任务 |
| `qca collect` | 收集处理内容 |
| `qca kb` | 管理知识库 |
| `qca agents` | 列出可用代理 |
| `qca interactive` | 交互式会话 |

## Telegram Bot 使用

发送以下类型的内容到 Bot：

| 类型 | 说明 |
|------|------|
| 📝 文字 | 直接粘贴文章、笔记、AI 总结 |
| 🔗 链接 | 网页 URL，自动抓取并总结 |
| 🖼️ 图片 | 截图、图表、信息图 |
| 📄 文件 | PDF、文档等 |

### Bot 命令

- `/start` - 开始使用
- `/search <关键词>` - 搜索知识库
- `/stats` - 查看统计
- `/recent` - 最近捕获

## 知识库结构

```
knowledge-base/
├── _attachments/       # 图片附件
├── Articles/           # 文章
│   ├── Tech/
│   ├── AI/
│   └── Business/
├── Concepts/           # 概念定义
├── AI-Summaries/       # AI 生成的总结
├── Visualizations/     # 图表、架构图
├── Notes/              # 快速笔记
├── Documents/          # 文档
├── Daily/              # 每日笔记
├── Inbox/              # 待整理
└── _index.md           # 索引
```

## Markdown 模板

捕获的内容会自动生成带 YAML frontmatter 的 Markdown：

```markdown
---
title: "文章标题"
source: "https://example.com/article"
type: article
category: tech
tags: ["ai", "agent"]
created: 2024-12-20T10:00:00
---

# 文章标题

## 📋 摘要
AI 生成的摘要...

## 🎯 核心要点
- 要点 1
- 要点 2

## 📝 详细内容
完整内容...

## 💭 我的想法
<!-- 留空供后续补充 -->
```

## 配置

### 环境变量 (`.env`)

```bash
# Anthropic API (用于 AI 分析)
ANTHROPIC_API_KEY=your_api_key

# Telegram Bot
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_ALLOWED_USERS=123456,789012  # 可选，限制用户

# 知识库路径
KNOWLEDGE_BASE_PATH=./data/knowledge
```

## 项目结构

```
quick_capture_agent/
├── src/quick_capture_agent/
│   ├── interfaces/           # 输入接口
│   │   └── telegram_bot.py   # Telegram Bot
│   ├── processors/           # 内容处理
│   │   ├── content_processor.py
│   │   └── markdown_generator.py
│   ├── knowledge_base/       # 知识库
│   │   ├── store.py
│   │   └── obsidian.py       # Obsidian 集成
│   ├── orchestrator/         # 主协调器
│   ├── agents/               # 子代理
│   │   ├── research/
│   │   └── content_collector/
│   └── main.py               # CLI 入口
├── .claude/agents/           # 代理定义
└── tests/
```

## 添加新代理

1. 在 `agents/` 下创建新目录
2. 继承 `BaseAgent` 实现
3. 在 `HelperAgent` 中注册
4. 添加 `.claude/agents/` 定义

## License

MIT
