"""
Base agent class that all sub-agents inherit from.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, AsyncIterator, Optional
import asyncio

from pydantic import BaseModel


class AgentStatus(str, Enum):
    """Status of an agent execution."""

    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentResult(BaseModel):
    """Result from an agent execution."""

    success: bool
    data: Any = None
    error: Optional[str] = None
    metadata: dict = {}
    execution_time: float = 0.0
    timestamp: datetime = datetime.now()

    class Config:
        arbitrary_types_allowed = True


@dataclass
class AgentConfig:
    """Configuration for an agent."""

    name: str
    description: str
    model: str = "claude-sonnet-4-5-20241022"
    tools: list[str] = field(default_factory=list)
    max_retries: int = 3
    timeout: int = 300
    system_prompt: Optional[str] = None


class BaseAgent(ABC):
    """
    Abstract base class for all agents in the system.

    Each agent should implement the `execute` method to perform its specific task.
    """

    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or self._default_config()
        self.status = AgentStatus.IDLE
        self._start_time: Optional[float] = None

    @abstractmethod
    def _default_config(self) -> AgentConfig:
        """Return the default configuration for this agent."""
        pass

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def description(self) -> str:
        return self.config.description

    def get_system_prompt(self) -> str:
        """Return the system prompt for this agent."""
        if self.config.system_prompt:
            return self.config.system_prompt
        return self._build_system_prompt()

    @abstractmethod
    def _build_system_prompt(self) -> str:
        """Build the default system prompt for this agent."""
        pass

    @abstractmethod
    async def execute(self, task: str, context: Optional[dict] = None) -> AgentResult:
        """
        Execute the agent's main task.

        Args:
            task: The task description or query
            context: Optional additional context

        Returns:
            AgentResult with the execution results
        """
        pass

    async def run(self, task: str, context: Optional[dict] = None) -> AgentResult:
        """
        Run the agent with error handling and timing.

        This is the main entry point for executing an agent.
        """
        import time

        self.status = AgentStatus.RUNNING
        self._start_time = time.time()

        try:
            result = await self.execute(task, context)
            self.status = AgentStatus.COMPLETED
            result.execution_time = time.time() - self._start_time
            return result
        except asyncio.CancelledError:
            self.status = AgentStatus.CANCELLED
            return AgentResult(
                success=False,
                error="Agent execution was cancelled",
                execution_time=time.time() - self._start_time,
            )
        except Exception as e:
            self.status = AgentStatus.FAILED
            return AgentResult(
                success=False,
                error=str(e),
                execution_time=time.time() - self._start_time,
            )

    def to_agent_definition(self) -> dict:
        """Convert this agent to a Claude SDK agent definition."""
        return {
            "name": self.config.name,
            "description": self.config.description,
            "model": self.config.model,
            "tools": self.config.tools,
            "prompt": self.get_system_prompt(),
        }

    async def stream_execute(
        self, task: str, context: Optional[dict] = None
    ) -> AsyncIterator[str]:
        """
        Execute the agent and stream results.

        Override this method to provide streaming support.
        """
        result = await self.run(task, context)
        if result.success:
            yield str(result.data)
        else:
            yield f"Error: {result.error}"
