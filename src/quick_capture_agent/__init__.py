"""
Quick Capture Agent - A multi-agent helper system built with Claude Agent SDK.

This package provides a modular framework for building and orchestrating
multiple AI agents to assist with daily tasks like research, content collection,
and knowledge management.
"""

__version__ = "0.1.0"

from quick_capture_agent.orchestrator.helper_agent import HelperAgent
from quick_capture_agent.agents.research.agent import ResearchAgent
from quick_capture_agent.agents.content_collector.agent import ContentCollectorAgent

__all__ = [
    "HelperAgent",
    "ResearchAgent",
    "ContentCollectorAgent",
]
