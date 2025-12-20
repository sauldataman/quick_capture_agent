"""
Configuration settings for Quick Capture Agent.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


@dataclass
class ModelConfig:
    """Configuration for AI models."""

    default_model: str = "claude-sonnet-4-5-20241022"
    orchestrator_model: str = "claude-opus-4-5-20250514"
    fast_model: str = "claude-haiku-3-5-20241022"

    def __post_init__(self):
        # Override from environment if available
        self.default_model = os.getenv("DEFAULT_MODEL", self.default_model)
        self.orchestrator_model = os.getenv("ORCHESTRATOR_MODEL", self.orchestrator_model)


@dataclass
class PathConfig:
    """Configuration for file paths."""

    base_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent.parent)
    knowledge_base_path: Optional[Path] = None
    cache_path: Optional[Path] = None

    def __post_init__(self):
        if self.knowledge_base_path is None:
            kb_path = os.getenv("KNOWLEDGE_BASE_PATH", "./data/knowledge")
            self.knowledge_base_path = self.base_dir / kb_path

        if self.cache_path is None:
            self.cache_path = self.base_dir / ".cache"

        # Ensure directories exist
        self.knowledge_base_path.mkdir(parents=True, exist_ok=True)
        self.cache_path.mkdir(parents=True, exist_ok=True)


@dataclass
class AgentConfig:
    """Configuration for agent behavior."""

    max_retries: int = 3
    timeout_seconds: int = 300
    max_parallel_agents: int = 5
    verbose: bool = False

    def __post_init__(self):
        self.verbose = os.getenv("VERBOSE", "false").lower() == "true"


@dataclass
class Settings:
    """Main settings container."""

    models: ModelConfig = field(default_factory=ModelConfig)
    paths: PathConfig = field(default_factory=PathConfig)
    agents: AgentConfig = field(default_factory=AgentConfig)

    @property
    def anthropic_api_key(self) -> Optional[str]:
        return os.getenv("ANTHROPIC_API_KEY")


# Global settings instance
settings = Settings()
