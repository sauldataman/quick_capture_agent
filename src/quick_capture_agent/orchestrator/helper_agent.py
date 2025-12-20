"""
Helper Agent - Main orchestrator that coordinates all sub-agents.

This is the primary entry point for the multi-agent system. It analyzes
user requests and delegates tasks to appropriate specialized agents.
"""

from typing import Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import asyncio

from quick_capture_agent.agents.base import BaseAgent, AgentConfig, AgentResult
from quick_capture_agent.agents.research import ResearchAgent
from quick_capture_agent.agents.content_collector import ContentCollectorAgent


class TaskType(str, Enum):
    """Types of tasks the helper can handle."""

    RESEARCH = "research"
    CONTENT_COLLECTION = "content_collection"
    GENERAL = "general"
    MULTI_STEP = "multi_step"


@dataclass
class SubAgentRegistry:
    """Registry of available sub-agents."""

    agents: dict[str, BaseAgent] = field(default_factory=dict)

    def register(self, agent: BaseAgent) -> None:
        """Register a new agent."""
        self.agents[agent.name] = agent

    def get(self, name: str) -> Optional[BaseAgent]:
        """Get an agent by name."""
        return self.agents.get(name)

    def list_agents(self) -> list[str]:
        """List all registered agent names."""
        return list(self.agents.keys())

    def get_agent_descriptions(self) -> dict[str, str]:
        """Get descriptions of all agents."""
        return {name: agent.description for name, agent in self.agents.items()}


class HelperAgent(BaseAgent):
    """
    Main orchestrator agent that coordinates specialized sub-agents.

    The HelperAgent:
    - Analyzes user requests to determine the best approach
    - Delegates tasks to appropriate sub-agents
    - Coordinates multi-step tasks across agents
    - Synthesizes results from multiple agents
    """

    def __init__(self, config: Optional[AgentConfig] = None):
        super().__init__(config)
        self.registry = SubAgentRegistry()
        self._initialize_agents()

    def _default_config(self) -> AgentConfig:
        return AgentConfig(
            name="helper",
            description="Main orchestrator agent that coordinates specialized sub-agents for various tasks",
            model="claude-opus-4-5-20250514",  # Use most capable model for orchestration
            tools=["Read", "Write", "WebSearch", "WebFetch", "Bash", "Grep", "Glob"],
            max_retries=3,
            timeout=1800,  # 30 minutes for complex tasks
        )

    def _initialize_agents(self) -> None:
        """Initialize and register all sub-agents."""
        # Register built-in agents
        self.registry.register(ResearchAgent())
        self.registry.register(ContentCollectorAgent())

    def register_agent(self, agent: BaseAgent) -> None:
        """Register a custom agent."""
        self.registry.register(agent)

    def _build_system_prompt(self) -> str:
        agent_descriptions = self.registry.get_agent_descriptions()
        agents_info = "\n".join(
            f"- **{name}**: {desc}" for name, desc in agent_descriptions.items()
        )

        return f"""You are a helpful AI assistant orchestrating a team of specialized agents.

## Your Role
You are the main coordinator for a multi-agent system. Your job is to:
1. Understand user requests
2. Break down complex tasks into manageable steps
3. Delegate tasks to the most appropriate specialized agents
4. Coordinate multi-step workflows
5. Synthesize and present results to the user

## Available Agents
{agents_info}

## Decision Framework
When receiving a request:
1. **Analyze**: What is the user trying to accomplish?
2. **Plan**: What steps are needed? Which agents can help?
3. **Delegate**: Assign tasks to appropriate agents
4. **Coordinate**: Manage dependencies between tasks
5. **Synthesize**: Combine results into a coherent response

## Task Routing Guidelines
- Research questions, fact-finding, comparisons → **research** agent
- Collecting articles, images, podcasts, storing to knowledge base → **content_collector** agent
- Multi-step tasks requiring multiple capabilities → coordinate multiple agents
- Simple questions you can answer directly → respond directly

## Communication Style
- Be concise but thorough
- Explain your reasoning when delegating tasks
- Provide clear summaries of agent outputs
- Ask clarifying questions when needed
- Proactively suggest related actions

## Output Format
When coordinating agents, structure your response as:
1. Task Understanding: Brief summary of what's being requested
2. Execution Plan: Steps and agents involved
3. Results: Output from each agent
4. Summary: Final synthesized response
"""

    async def execute(self, task: str, context: Optional[dict] = None) -> AgentResult:
        """
        Execute a task by analyzing it and delegating to appropriate agents.

        Args:
            task: The user's request
            context: Optional context with:
                - agent: Specific agent to use
                - parallel: Run agents in parallel if possible
                - verbose: Include detailed execution info

        Returns:
            AgentResult with the combined results
        """
        try:
            # Check if a specific agent was requested
            if context and context.get("agent"):
                return await self._run_specific_agent(
                    context["agent"], task, context
                )

            # Analyze the task to determine the approach
            task_type = self._analyze_task(task)

            # Route to appropriate handler
            if task_type == TaskType.RESEARCH:
                return await self._handle_research(task, context)
            elif task_type == TaskType.CONTENT_COLLECTION:
                return await self._handle_content_collection(task, context)
            elif task_type == TaskType.MULTI_STEP:
                return await self._handle_multi_step(task, context)
            else:
                return await self._handle_general(task, context)

        except Exception as e:
            return AgentResult(
                success=False,
                error=f"Task execution failed: {str(e)}",
                metadata={"agent": self.name},
            )

    def _analyze_task(self, task: str) -> TaskType:
        """Analyze the task to determine its type."""
        task_lower = task.lower()

        # Research indicators
        research_keywords = [
            "research", "investigate", "find out", "what is", "how does",
            "compare", "analyze", "explain", "why", "learn about",
        ]
        if any(kw in task_lower for kw in research_keywords):
            return TaskType.RESEARCH

        # Content collection indicators
        collection_keywords = [
            "collect", "save", "store", "capture", "download", "extract",
            "summarize this", "analyze this image", "this article", "this podcast",
            "http://", "https://", ".jpg", ".png", ".mp3", ".pdf",
        ]
        if any(kw in task_lower for kw in collection_keywords):
            return TaskType.CONTENT_COLLECTION

        # Multi-step indicators
        multi_step_keywords = [
            "and then", "first", "after that", "finally", "step by step",
            "multiple", "several", "list of",
        ]
        if any(kw in task_lower for kw in multi_step_keywords):
            return TaskType.MULTI_STEP

        return TaskType.GENERAL

    async def _run_specific_agent(
        self, agent_name: str, task: str, context: Optional[dict]
    ) -> AgentResult:
        """Run a specific agent by name."""
        agent = self.registry.get(agent_name)
        if not agent:
            return AgentResult(
                success=False,
                error=f"Agent '{agent_name}' not found. Available: {self.registry.list_agents()}",
            )
        return await agent.run(task, context)

    async def _handle_research(self, task: str, context: Optional[dict]) -> AgentResult:
        """Handle research tasks."""
        agent = self.registry.get("research")
        if not agent:
            return AgentResult(
                success=False,
                error="Research agent not available",
            )

        result = await agent.run(task, context)

        return AgentResult(
            success=result.success,
            data={
                "task_type": "research",
                "agent_used": "research",
                "result": result.data,
            },
            error=result.error,
            metadata={
                "orchestrator": self.name,
                "sub_agent": "research",
            },
        )

    async def _handle_content_collection(
        self, task: str, context: Optional[dict]
    ) -> AgentResult:
        """Handle content collection tasks."""
        agent = self.registry.get("content_collector")
        if not agent:
            return AgentResult(
                success=False,
                error="Content collector agent not available",
            )

        result = await agent.run(task, context)

        return AgentResult(
            success=result.success,
            data={
                "task_type": "content_collection",
                "agent_used": "content_collector",
                "result": result.data,
            },
            error=result.error,
            metadata={
                "orchestrator": self.name,
                "sub_agent": "content_collector",
            },
        )

    async def _handle_multi_step(self, task: str, context: Optional[dict]) -> AgentResult:
        """Handle multi-step tasks requiring coordination."""
        # For now, use research agent to break down and handle
        # In a full implementation, this would parse the task and coordinate multiple agents
        research_agent = self.registry.get("research")
        if research_agent:
            result = await research_agent.run(
                f"Break down and execute this multi-step task: {task}",
                context,
            )
            return result

        return AgentResult(
            success=False,
            error="Unable to handle multi-step task",
        )

    async def _handle_general(self, task: str, context: Optional[dict]) -> AgentResult:
        """Handle general tasks that don't fit specific categories."""
        try:
            from claude_agent_sdk import query

            results = []
            async for message in query(
                prompt=task,
                options={
                    "model": self.config.model,
                    "system_prompt": self.get_system_prompt(),
                },
            ):
                results.append(message)

            return AgentResult(
                success=True,
                data={
                    "task_type": "general",
                    "response": "\n".join(str(r) for r in results),
                },
                metadata={"agent": self.name},
            )

        except ImportError:
            return AgentResult(
                success=True,
                data={
                    "task_type": "general",
                    "response": f"[Mock Response] Processed: {task}",
                },
                metadata={"agent": self.name, "mock": True},
            )

    async def run_parallel(self, tasks: list[dict]) -> list[AgentResult]:
        """
        Run multiple tasks in parallel.

        Args:
            tasks: List of dicts with 'task' and optional 'agent' keys

        Returns:
            List of AgentResults
        """
        async def run_single(task_info: dict) -> AgentResult:
            return await self.run(
                task_info["task"],
                context={"agent": task_info.get("agent")},
            )

        return await asyncio.gather(
            *[run_single(t) for t in tasks],
            return_exceptions=True,
        )

    def get_available_agents(self) -> dict[str, str]:
        """Get information about available agents."""
        return self.registry.get_agent_descriptions()
