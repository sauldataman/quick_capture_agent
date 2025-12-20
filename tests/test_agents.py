"""
Tests for agent implementations.
"""

import pytest
from pathlib import Path
import tempfile
import json

from quick_capture_agent.agents.base import BaseAgent, AgentConfig, AgentResult, AgentStatus
from quick_capture_agent.agents.research import ResearchAgent
from quick_capture_agent.agents.content_collector import ContentCollectorAgent, ContentType
from quick_capture_agent.orchestrator import HelperAgent
from quick_capture_agent.knowledge_base import KnowledgeBase, KnowledgeItem, ContentCategory


class TestAgentResult:
    """Tests for AgentResult."""

    def test_success_result(self):
        result = AgentResult(success=True, data={"key": "value"})
        assert result.success is True
        assert result.data == {"key": "value"}
        assert result.error is None

    def test_failure_result(self):
        result = AgentResult(success=False, error="Something went wrong")
        assert result.success is False
        assert result.error == "Something went wrong"


class TestResearchAgent:
    """Tests for ResearchAgent (Web Research Specialist)."""

    def test_initialization(self):
        agent = ResearchAgent()
        assert agent.name == "web-research-specialist"
        assert agent.status == AgentStatus.IDLE
        assert "mcp__mcp-server-firecrawl__firecrawl_search" in agent.config.tools

    def test_default_config(self):
        agent = ResearchAgent()
        config = agent._default_config()
        assert config.name == "web-research-specialist"
        assert config.model == "claude-sonnet-4-5-20241022"
        assert len(config.tools) == 3  # firecrawl_scrape, firecrawl_map, firecrawl_search

    def test_system_prompt(self):
        agent = ResearchAgent()
        prompt = agent.get_system_prompt()
        assert "web researcher" in prompt.lower()
        assert "firecrawl" in prompt.lower()

    @pytest.mark.asyncio
    async def test_mock_execute(self):
        agent = ResearchAgent()
        result = await agent._execute_mock("test topic")
        assert result.success is True
        assert "task" in result.data
        assert result.data["task"] == "test topic"


class TestContentCollectorAgent:
    """Tests for ContentCollectorAgent."""

    def test_initialization(self):
        agent = ContentCollectorAgent()
        assert agent.name == "content_collector"
        assert agent.status == AgentStatus.IDLE

    def test_content_type_detection(self):
        agent = ContentCollectorAgent()

        # Test various content types
        assert agent._detect_content_type("https://example.com/image.jpg", None) == ContentType.IMAGE
        assert agent._detect_content_type("https://spotify.com/episode/abc", None) == ContentType.PODCAST
        assert agent._detect_content_type("https://youtube.com/watch?v=xyz", None) == ContentType.VIDEO
        assert agent._detect_content_type("https://example.com/article", None) == ContentType.ARTICLE
        assert agent._detect_content_type("document.pdf", None) == ContentType.DOCUMENT

    def test_content_type_from_context(self):
        agent = ContentCollectorAgent()
        assert agent._detect_content_type(
            "anything",
            {"content_type": "podcast"}
        ) == ContentType.PODCAST

    @pytest.mark.asyncio
    async def test_mock_execute(self):
        agent = ContentCollectorAgent()
        result = await agent._execute_mock("https://example.com/article")
        assert result.success is True
        assert "id" in result.data
        assert result.metadata.get("mock") is True


class TestHelperAgent:
    """Tests for HelperAgent."""

    def test_initialization(self):
        agent = HelperAgent()
        assert agent.name == "helper"
        assert "web-research-specialist" in agent.registry.list_agents()
        assert "content_collector" in agent.registry.list_agents()

    def test_agent_registration(self):
        agent = HelperAgent()
        initial_count = len(agent.registry.list_agents())

        # Create a simple test agent
        class TestAgent(BaseAgent):
            def _default_config(self):
                return AgentConfig(name="test", description="Test agent")

            def _build_system_prompt(self):
                return "Test prompt"

            async def execute(self, task, context=None):
                return AgentResult(success=True, data="test")

        test_agent = TestAgent()
        agent.register_agent(test_agent)

        assert len(agent.registry.list_agents()) == initial_count + 1
        assert "test" in agent.registry.list_agents()

    def test_task_analysis(self):
        agent = HelperAgent()

        # Test research detection
        from quick_capture_agent.orchestrator.helper_agent import TaskType
        assert agent._analyze_task("research AI trends") == TaskType.RESEARCH
        assert agent._analyze_task("what is machine learning") == TaskType.RESEARCH

        # Test content collection detection
        assert agent._analyze_task("collect this article https://example.com") == TaskType.CONTENT_COLLECTION
        assert agent._analyze_task("save this image.jpg") == TaskType.CONTENT_COLLECTION


class TestKnowledgeBase:
    """Tests for KnowledgeBase."""

    @pytest.fixture
    def temp_kb(self):
        """Create a temporary knowledge base."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield KnowledgeBase(base_path=Path(tmpdir))

    def test_initialization(self, temp_kb):
        assert temp_kb.base_path.exists()
        assert temp_kb.index_path.exists()

    def test_add_item(self, temp_kb):
        item = temp_kb.add(
            title="Test Item",
            content="This is test content",
            source="https://example.com",
            category=ContentCategory.ARTICLES,
            tags=["test", "example"],
        )

        assert item.id is not None
        assert item.title == "Test Item"
        assert item.category == ContentCategory.ARTICLES

    def test_get_item(self, temp_kb):
        item = temp_kb.add(
            title="Get Test",
            content="Content to retrieve",
            category=ContentCategory.NOTES,
        )

        retrieved = temp_kb.get(item.id)
        assert retrieved is not None
        assert retrieved.title == "Get Test"
        assert retrieved.content == "Content to retrieve"

    def test_search(self, temp_kb):
        temp_kb.add(
            title="Python Tutorial",
            content="Learn Python programming",
            category=ContentCategory.ARTICLES,
            tags=["python", "programming"],
        )
        temp_kb.add(
            title="JavaScript Guide",
            content="Learn JavaScript",
            category=ContentCategory.ARTICLES,
            tags=["javascript", "programming"],
        )

        # Search by query
        results = temp_kb.search(query="Python")
        assert len(results) == 1
        assert results[0].title == "Python Tutorial"

        # Search by tag
        results = temp_kb.search(tags=["programming"])
        assert len(results) == 2

    def test_delete_item(self, temp_kb):
        item = temp_kb.add(
            title="To Delete",
            content="This will be deleted",
            category=ContentCategory.NOTES,
        )

        assert temp_kb.delete(item.id) is True
        assert temp_kb.get(item.id) is None

    def test_stats(self, temp_kb):
        temp_kb.add(title="Item 1", content="Content 1", category=ContentCategory.ARTICLES)
        temp_kb.add(title="Item 2", content="Content 2", category=ContentCategory.NOTES)

        stats = temp_kb.get_stats()
        assert stats["total_items"] == 2
        assert "articles" in stats["categories"]
        assert "notes" in stats["categories"]


class TestKnowledgeItem:
    """Tests for KnowledgeItem."""

    def test_to_dict(self):
        item = KnowledgeItem(
            id="test-123",
            title="Test",
            content="Content",
            source="source",
            category=ContentCategory.ARTICLES,
            tags=["tag1"],
        )
        data = item.to_dict()

        assert data["id"] == "test-123"
        assert data["category"] == "articles"
        assert data["tags"] == ["tag1"]

    def test_from_dict(self):
        data = {
            "id": "test-456",
            "title": "From Dict",
            "content": "Content",
            "source": "source",
            "category": "notes",
            "tags": [],
            "metadata": {},
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
        }
        item = KnowledgeItem.from_dict(data)

        assert item.id == "test-456"
        assert item.category == ContentCategory.NOTES

    def test_matches_query(self):
        item = KnowledgeItem(
            id="test",
            title="Python Programming Guide",
            content="Learn Python basics",
            source="",
            category=ContentCategory.ARTICLES,
            tags=["python", "tutorial"],
        )

        assert item.matches_query("python") is True
        assert item.matches_query("Programming") is True
        assert item.matches_query("tutorial") is True
        assert item.matches_query("javascript") is False
