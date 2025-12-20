"""
Web Research Specialist Agent implementation.

This agent specializes in conducting thorough web research using Firecrawl tools:
- Web searching across multiple sources
- Page scraping for detailed content extraction
- Site mapping for structure discovery
- Information synthesis and analysis
"""

from typing import Optional

from quick_capture_agent.agents.base import BaseAgent, AgentConfig, AgentResult


class ResearchAgent(BaseAgent):
    """
    Expert web researcher with exceptional skills in information discovery,
    synthesis, and analysis.

    This agent uses Firecrawl MCP tools for:
    - firecrawl_search: Search the web for information
    - firecrawl_scrape: Extract content from specific URLs
    - firecrawl_map: Discover website structures
    """

    def _default_config(self) -> AgentConfig:
        return AgentConfig(
            name="web-research-specialist",
            description=(
                "Use this agent when you need to conduct thorough web research, "
                "including searching for information across multiple sources and "
                "extracting relevant details from specific web pages. This agent "
                "excels at formulating effective search queries, evaluating source "
                "credibility, and synthesizing findings into clear, actionable insights."
            ),
            model="claude-sonnet-4-5-20241022",
            tools=[
                "mcp__mcp-server-firecrawl__firecrawl_scrape",
                "mcp__mcp-server-firecrawl__firecrawl_map",
                "mcp__mcp-server-firecrawl__firecrawl_search",
            ],
            max_retries=3,
            timeout=600,
        )

    def _build_system_prompt(self) -> str:
        return """You are an expert web researcher with exceptional skills in information discovery, synthesis, and analysis. Your expertise spans both broad search strategies and precise information extraction from specific sources.

## Core Capabilities

1. **Web Search**: Use `firecrawl_search` to find relevant information across the web
2. **Page Scraping**: Use `firecrawl_scrape` to extract detailed content from specific URLs
3. **Site Mapping**: Use `firecrawl_map` to discover and understand website structures

## Research Methodology

When conducting research, follow this systematic approach:

1. **Understand the Query**: Break down the research question into key components
2. **Search Strategy**: Formulate effective search queries targeting different aspects
3. **Source Discovery**: Find multiple authoritative sources on the topic
4. **Deep Extraction**: Scrape relevant pages for detailed information
5. **Synthesis**: Combine findings into coherent, well-organized insights
6. **Verification**: Cross-reference facts across multiple sources

## Output Guidelines

Structure your research findings as follows:

- **Summary**: 2-3 sentence overview of key findings
- **Key Insights**: Bullet points of the most important discoveries
- **Detailed Analysis**: In-depth discussion organized by subtopic
- **Sources**: List all sources with URLs and credibility assessment
- **Confidence Level**: Rate your confidence (High/Medium/Low) with justification

## Best Practices

- Always cite your sources with URLs
- Distinguish between facts, opinions, and speculation
- Present multiple viewpoints when relevant
- Acknowledge gaps or limitations in available information
- Prioritize recent and authoritative sources
- Use clear, accessible language while maintaining accuracy
"""

    async def execute(self, task: str, context: Optional[dict] = None) -> AgentResult:
        """
        Execute a web research task.

        Args:
            task: The research question or topic to investigate
            context: Optional context with:
                - depth: "quick" | "standard" | "comprehensive"
                - focus_areas: List of specific areas to focus on
                - max_sources: Maximum number of sources to consult

        Returns:
            AgentResult containing the research findings
        """
        try:
            from claude_agent_sdk import query

            depth = context.get("depth", "standard") if context else "standard"
            focus_areas = context.get("focus_areas", []) if context else []

            prompt = self._build_research_prompt(task, depth, focus_areas)

            results = []
            async for message in query(
                prompt=prompt,
                options={
                    "model": self.config.model,
                    "system_prompt": self.get_system_prompt(),
                },
            ):
                results.append(message)

            final_result = "\n".join(str(r) for r in results)

            return AgentResult(
                success=True,
                data={
                    "task": task,
                    "depth": depth,
                    "findings": final_result,
                },
                metadata={
                    "agent": self.name,
                    "model": self.config.model,
                    "tools": self.config.tools,
                },
            )

        except ImportError:
            return await self._execute_mock(task, context)

        except Exception as e:
            return AgentResult(
                success=False,
                error=f"Research failed: {str(e)}",
                metadata={"agent": self.name},
            )

    async def _execute_mock(self, task: str, context: Optional[dict] = None) -> AgentResult:
        """Mock execution for testing without SDK."""
        return AgentResult(
            success=True,
            data={
                "task": task,
                "findings": (
                    f"[Mock Research Result]\n\n"
                    f"Research topic: {task}\n\n"
                    f"This is a placeholder. Install claude-agent-sdk and configure "
                    f"mcp-server-firecrawl for actual web research functionality."
                ),
                "depth": context.get("depth", "standard") if context else "standard",
            },
            metadata={
                "agent": self.name,
                "mock": True,
            },
        )

    def _build_research_prompt(
        self, task: str, depth: str, focus_areas: list[str]
    ) -> str:
        """Build the research prompt based on parameters."""
        depth_instructions = {
            "quick": (
                "Perform a quick search to get an overview. "
                "Use firecrawl_search to find 2-3 key sources, briefly review them."
            ),
            "standard": (
                "Conduct thorough research. Use firecrawl_search to find multiple sources, "
                "then use firecrawl_scrape to extract detailed content from the most "
                "relevant pages. Synthesize findings into a balanced analysis."
            ),
            "comprehensive": (
                "Perform exhaustive research. Use firecrawl_search extensively, "
                "firecrawl_scrape on all relevant pages, and firecrawl_map to explore "
                "site structures when needed. Cover all aspects with detailed analysis."
            ),
        }

        prompt = f"""Research Task: {task}

Research Depth: {depth}
Strategy: {depth_instructions.get(depth, depth_instructions['standard'])}
"""

        if focus_areas:
            prompt += f"\nFocus Areas: {', '.join(focus_areas)}"

        prompt += "\n\nConduct the research using the available Firecrawl tools and provide comprehensive findings."

        return prompt

    async def search(self, query: str, max_results: int = 10) -> AgentResult:
        """Perform a web search on a topic."""
        return await self.run(
            f"Search for: {query}",
            context={"depth": "quick", "max_results": max_results},
        )

    async def scrape_url(self, url: str) -> AgentResult:
        """Scrape and analyze content from a specific URL."""
        return await self.run(
            f"Scrape and analyze this URL: {url}",
            context={"depth": "standard"},
        )

    async def deep_research(self, topic: str, focus_areas: list[str] = None) -> AgentResult:
        """Perform comprehensive research on a topic."""
        return await self.run(
            topic,
            context={
                "depth": "comprehensive",
                "focus_areas": focus_areas or [],
            },
        )

    async def compare(self, items: list[str], criteria: list[str] = None) -> AgentResult:
        """Compare multiple items or options through research."""
        task = f"Research and compare the following: {', '.join(items)}"
        if criteria:
            task += f"\n\nEvaluate based on these criteria: {', '.join(criteria)}"

        return await self.run(task, context={"depth": "standard"})
