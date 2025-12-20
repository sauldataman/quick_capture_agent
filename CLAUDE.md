# Quick Capture Agent

A multi-agent helper system built with Claude Agent SDK for daily task automation.

## Project Overview

This project implements a modular multi-agent framework with:
- **Helper Agent** (Orchestrator): Main coordinator that routes tasks to specialized agents
- **Research Agent**: Conducts research, web searches, and comparative analysis
- **Content Collector Agent**: Collects and processes articles, images, podcasts, and stores to knowledge base

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  Helper Agent                    │
│              (Main Orchestrator)                 │
└─────────────────┬───────────────────────────────┘
                  │
        ┌─────────┴─────────┐
        ▼                   ▼
┌───────────────┐   ┌───────────────────┐
│ Research Agent │   │ Content Collector │
│                │   │      Agent        │
└───────────────┘   └───────────────────┘
                            │
                            ▼
                    ┌───────────────┐
                    │ Knowledge Base │
                    └───────────────┘
```

## Directory Structure

```
quick_capture_agent/
├── src/quick_capture_agent/
│   ├── orchestrator/       # Main helper agent
│   ├── agents/             # Sub-agents
│   │   ├── research/       # Research agent
│   │   └── content_collector/  # Content collection agent
│   ├── knowledge_base/     # Knowledge storage
│   ├── tools/              # Custom tools
│   └── utils/              # Utilities
├── config/                 # Configuration
├── data/knowledge/         # Knowledge base storage
└── tests/                  # Tests
```

## Quick Start

```bash
# Install dependencies
pip install -e .

# Run a task
qca run "research the latest AI trends"

# Research a topic
qca research "machine learning frameworks" --depth comprehensive

# Collect content
qca collect "https://example.com/article" --category articles

# Interactive mode
qca interactive
```

## Adding New Agents

1. Create a new directory under `src/quick_capture_agent/agents/`
2. Implement the agent by extending `BaseAgent`
3. Register the agent in `HelperAgent._initialize_agents()`
4. Add agent definition in `.claude/agents/`

## Testing

```bash
pytest tests/ -v
```

## Models Used

- **Orchestrator**: claude-opus-4-5 (most capable, for complex coordination)
- **Sub-agents**: claude-sonnet-4-5 (balanced performance/cost)
- **Quick tasks**: claude-haiku-3-5 (fast, cost-effective)

## Key Conventions

- All agents inherit from `BaseAgent`
- Results use `AgentResult` dataclass
- Knowledge stored as JSON in category directories
- Async/await pattern throughout
