"""
Research Agent implementation.

This agent specializes in conducting research tasks including:
- Web searches and information gathering
- Document analysis and summarization
- Fact-checking and verification
- Comparative analysis
"""

from typing import Any, Optional
import anyio

from quick_capture_agent.agents.base import BaseAgent, AgentConfig, AgentResult


class ResearchAgent(BaseAgent):
    """
    Agent specialized for research and investigation tasks.

    This agent can:
    - Search the web for information
    - Analyze and summarize documents
    - Compare different sources
    - Generate comprehensive research reports
    """

    def _default_config(self) -> AgentConfig:
        return AgentConfig(
            name="research",
            description="Expert research agent for investigating topics, gathering information, and producing comprehensive analysis",
            model="claude-sonnet-4-5-20241022",
            tools=["WebSearch", "WebFetch", "Read", "Write", "Grep", "Glob"],
            max_retries=3,
            timeout=600,
        )

    def _build_system_prompt(self) -> str:
        return """You are an expert research agent specialized in conducting thorough investigations and analysis.

## Core Capabilities
- Web searching and information gathering from multiple sources
- Document analysis, summarization, and synthesis
- Fact-checking and source verification
- Comparative analysis across different viewpoints

## Research Methodology
1. **Understand the Query**: Break down the research question into sub-questions
2. **Gather Information**: Search multiple sources for relevant information
3. **Verify Facts**: Cross-reference information across sources
4. **Synthesize**: Combine findings into coherent insights
5. **Report**: Present findings in a clear, structured format

## Output Format
When conducting research, provide:
- **Summary**: A brief overview of findings (2-3 sentences)
- **Key Findings**: Bullet points of the most important discoveries
- **Detailed Analysis**: In-depth discussion of the topic
- **Sources**: List of sources consulted
- **Confidence Level**: How confident you are in the findings (High/Medium/Low)

## Guidelines
- Always cite sources when presenting factual information
- Distinguish between facts, opinions, and speculation
- Present multiple viewpoints when relevant
- Acknowledge limitations and gaps in available information
- Use clear, accessible language while maintaining accuracy
"""

    async def execute(self, task: str, context: Optional[dict] = None) -> AgentResult:
        """
        Execute a research task.

        Args:
            task: The research question or topic to investigate
            context: Optional context with:
                - depth: "quick" | "standard" | "comprehensive"
                - focus_areas: List of specific areas to focus on
                - source_types: Types of sources to prioritize

        Returns:
            AgentResult containing the research findings
        """
        try:
            # Import here to avoid circular imports
            from claude_agent_sdk import query

            # Build the research prompt
            depth = context.get("depth", "standard") if context else "standard"
            focus_areas = context.get("focus_areas", []) if context else []

            prompt = self._build_research_prompt(task, depth, focus_areas)

            # Execute using Claude Agent SDK
            results = []
            async for message in query(
                prompt=prompt,
                options={
                    "model": self.config.model,
                    "system_prompt": self.get_system_prompt(),
                },
            ):
                results.append(message)

            # Combine results
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
                },
            )

        except ImportError:
            # Fallback if SDK not available - return mock result for testing
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
                "findings": f"[Mock Research Result]\n\nResearch topic: {task}\n\nThis is a placeholder result. Install claude-agent-sdk for actual functionality.",
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
            "quick": "Provide a brief overview with key points. Limit to 2-3 sources.",
            "standard": "Conduct a thorough investigation with multiple sources. Provide balanced analysis.",
            "comprehensive": "Perform an exhaustive investigation. Cover all aspects, multiple viewpoints, and provide detailed analysis with extensive sources.",
        }

        prompt = f"""Research Task: {task}

Research Depth: {depth}
Instructions: {depth_instructions.get(depth, depth_instructions['standard'])}
"""

        if focus_areas:
            prompt += f"\nFocus Areas: {', '.join(focus_areas)}"

        prompt += "\n\nPlease conduct the research and provide your findings."

        return prompt

    async def quick_search(self, query: str) -> AgentResult:
        """Perform a quick web search on a topic."""
        return await self.run(query, context={"depth": "quick"})

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
        """Compare multiple items or options."""
        task = f"Compare the following: {', '.join(items)}"
        if criteria:
            task += f"\n\nEvaluate based on these criteria: {', '.join(criteria)}"

        return await self.run(task, context={"depth": "standard"})
