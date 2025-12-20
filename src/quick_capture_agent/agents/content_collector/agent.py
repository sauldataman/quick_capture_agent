"""
Content Collector Agent implementation.

This agent specializes in collecting and processing various content types:
- Images and visual content analysis
- Blog posts and articles
- Podcasts and audio content
- Videos and multimedia
- Files and documents

It categorizes content and stores it in a knowledge base.
"""

from enum import Enum
from typing import Any, Optional
from pathlib import Path
from datetime import datetime
import json

from quick_capture_agent.agents.base import BaseAgent, AgentConfig, AgentResult


class ContentType(str, Enum):
    """Types of content that can be collected."""

    IMAGE = "image"
    ARTICLE = "article"
    PODCAST = "podcast"
    VIDEO = "video"
    DOCUMENT = "document"
    SOCIAL_POST = "social_post"
    RESEARCH_PAPER = "research_paper"
    OTHER = "other"


class ContentCollectorAgent(BaseAgent):
    """
    Agent specialized for collecting, analyzing, and storing various content types.

    This agent can:
    - Extract information from images (OCR, visual analysis)
    - Summarize blog posts and articles
    - Transcribe and summarize podcasts
    - Categorize and tag content
    - Store content in a structured knowledge base
    """

    def __init__(self, config: Optional[AgentConfig] = None, knowledge_base_path: Optional[Path] = None):
        super().__init__(config)
        self.knowledge_base_path = knowledge_base_path or Path("./data/knowledge")
        self.knowledge_base_path.mkdir(parents=True, exist_ok=True)

    def _default_config(self) -> AgentConfig:
        return AgentConfig(
            name="content_collector",
            description="Expert content collector for gathering, analyzing, and organizing information from various sources including images, blogs, podcasts, and documents",
            model="claude-sonnet-4-5-20241022",
            tools=["WebFetch", "Read", "Write", "Bash"],
            max_retries=3,
            timeout=900,  # 15 minutes for media processing
        )

    def _build_system_prompt(self) -> str:
        return """You are an expert content collection and knowledge management agent.

## Core Capabilities
- Analyze images and extract information (text, objects, concepts)
- Process and summarize blog posts, articles, and web content
- Handle podcast content (transcription, summarization, key points)
- Categorize and tag content for easy retrieval
- Organize information into a structured knowledge base

## Content Processing Workflow
1. **Identify Content Type**: Determine what kind of content is being processed
2. **Extract Information**: Pull out relevant data, text, and metadata
3. **Analyze & Summarize**: Create concise summaries and key takeaways
4. **Categorize**: Assign appropriate categories and tags
5. **Store**: Save to knowledge base in a structured format

## Output Format for Collected Content
```json
{
  "id": "unique-id",
  "type": "article|image|podcast|video|document",
  "title": "Content title",
  "source": "URL or file path",
  "collected_at": "ISO timestamp",
  "summary": "Brief summary of the content",
  "key_points": ["point 1", "point 2"],
  "categories": ["category1", "category2"],
  "tags": ["tag1", "tag2"],
  "full_content": "Full extracted content or transcript",
  "metadata": {
    "author": "Author name",
    "date": "Original publish date",
    "duration": "For audio/video",
    "word_count": 1234
  }
}
```

## Guidelines
- Always preserve source attribution
- Extract actionable insights when possible
- Use consistent categorization schemes
- Handle various languages appropriately
- Note any content that requires follow-up or action
"""

    async def execute(self, task: str, context: Optional[dict] = None) -> AgentResult:
        """
        Execute a content collection task.

        Args:
            task: Description of what to collect or the URL/path to content
            context: Optional context with:
                - content_type: Specific type of content
                - categories: Suggested categories
                - store: Whether to store in knowledge base (default True)

        Returns:
            AgentResult containing the processed content
        """
        try:
            from claude_agent_sdk import query

            # Detect content type if not specified
            content_type = self._detect_content_type(task, context)

            prompt = self._build_collection_prompt(task, content_type, context)

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

            final_result = "\n".join(str(r) for r in results)

            # Parse and structure the result
            content_data = self._parse_result(final_result, task, content_type)

            # Store in knowledge base if requested
            should_store = context.get("store", True) if context else True
            if should_store:
                stored_path = await self._store_content(content_data)
                content_data["stored_at"] = str(stored_path)

            return AgentResult(
                success=True,
                data=content_data,
                metadata={
                    "agent": self.name,
                    "content_type": content_type.value,
                },
            )

        except ImportError:
            return await self._execute_mock(task, context)

        except Exception as e:
            return AgentResult(
                success=False,
                error=f"Content collection failed: {str(e)}",
                metadata={"agent": self.name},
            )

    async def _execute_mock(self, task: str, context: Optional[dict] = None) -> AgentResult:
        """Mock execution for testing without SDK."""
        content_type = self._detect_content_type(task, context)

        mock_data = {
            "id": f"mock-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "type": content_type.value,
            "title": f"Collected: {task[:50]}...",
            "source": task,
            "collected_at": datetime.now().isoformat(),
            "summary": "[Mock] This is a placeholder summary. Install claude-agent-sdk for actual functionality.",
            "key_points": ["Mock key point 1", "Mock key point 2"],
            "categories": ["uncategorized"],
            "tags": ["mock"],
        }

        return AgentResult(
            success=True,
            data=mock_data,
            metadata={
                "agent": self.name,
                "mock": True,
            },
        )

    def _detect_content_type(self, task: str, context: Optional[dict]) -> ContentType:
        """Detect the type of content from the task description or URL."""
        if context and context.get("content_type"):
            return ContentType(context["content_type"])

        task_lower = task.lower()

        # Check for common patterns
        if any(ext in task_lower for ext in [".jpg", ".png", ".gif", ".webp", "image"]):
            return ContentType.IMAGE
        elif any(word in task_lower for word in ["podcast", ".mp3", "spotify.com/episode", "podcasts.apple"]):
            return ContentType.PODCAST
        elif any(word in task_lower for word in ["youtube.com", "video", ".mp4", "vimeo"]):
            return ContentType.VIDEO
        elif any(word in task_lower for word in [".pdf", ".doc", "document"]):
            return ContentType.DOCUMENT
        elif any(word in task_lower for word in ["arxiv", "paper", "research"]):
            return ContentType.RESEARCH_PAPER
        elif any(word in task_lower for word in ["twitter", "tweet", "x.com", "linkedin.com/post"]):
            return ContentType.SOCIAL_POST
        elif any(word in task_lower for word in ["blog", "article", "http", "https", ".com", ".org"]):
            return ContentType.ARTICLE

        return ContentType.OTHER

    def _build_collection_prompt(
        self, task: str, content_type: ContentType, context: Optional[dict]
    ) -> str:
        """Build the collection prompt based on content type."""
        type_instructions = {
            ContentType.IMAGE: """
Analyze this image:
1. Describe what's in the image
2. Extract any text (OCR)
3. Identify key objects, people, or concepts
4. Note any relevant context or metadata
""",
            ContentType.ARTICLE: """
Process this article/blog post:
1. Extract the full content
2. Summarize the main points (2-3 sentences)
3. List 3-5 key takeaways
4. Identify the author and publication date
5. Suggest relevant categories and tags
""",
            ContentType.PODCAST: """
Process this podcast episode:
1. Get the episode title and show name
2. Provide a summary of the episode
3. List key topics discussed
4. Note any mentioned resources or references
5. Extract notable quotes if available
""",
            ContentType.VIDEO: """
Process this video content:
1. Get the title and creator
2. Summarize the content
3. List main topics covered
4. Note timestamps of key sections if available
5. Extract any important visuals or demonstrations
""",
            ContentType.RESEARCH_PAPER: """
Process this research paper:
1. Extract title, authors, and abstract
2. Summarize key findings
3. Note methodology used
4. List important conclusions
5. Identify cited references of interest
""",
        }

        instructions = type_instructions.get(content_type, "Process this content and extract relevant information.")

        prompt = f"""Content to process: {task}

Content Type: {content_type.value}

{instructions}

Please process this content and provide the structured output as specified in your instructions.
"""

        if context and context.get("categories"):
            prompt += f"\n\nSuggested categories: {', '.join(context['categories'])}"

        return prompt

    def _parse_result(self, result: str, source: str, content_type: ContentType) -> dict:
        """Parse the agent result into structured content data."""
        return {
            "id": f"content-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "type": content_type.value,
            "source": source,
            "collected_at": datetime.now().isoformat(),
            "raw_result": result,
            "processed": True,
        }

    async def _store_content(self, content_data: dict) -> Path:
        """Store content in the knowledge base."""
        # Create category directory
        content_type = content_data.get("type", "other")
        type_dir = self.knowledge_base_path / content_type
        type_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename
        content_id = content_data.get("id", datetime.now().strftime("%Y%m%d%H%M%S"))
        file_path = type_dir / f"{content_id}.json"

        # Write content
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(content_data, f, indent=2, ensure_ascii=False)

        return file_path

    # Convenience methods for specific content types

    async def collect_article(self, url: str, categories: list[str] = None) -> AgentResult:
        """Collect and process a web article."""
        return await self.run(
            url,
            context={
                "content_type": ContentType.ARTICLE.value,
                "categories": categories or [],
            },
        )

    async def analyze_image(self, image_path: str, categories: list[str] = None) -> AgentResult:
        """Analyze an image and extract information."""
        return await self.run(
            image_path,
            context={
                "content_type": ContentType.IMAGE.value,
                "categories": categories or [],
            },
        )

    async def process_podcast(self, podcast_url: str, categories: list[str] = None) -> AgentResult:
        """Process a podcast episode."""
        return await self.run(
            podcast_url,
            context={
                "content_type": ContentType.PODCAST.value,
                "categories": categories or [],
            },
        )

    async def batch_collect(self, sources: list[str]) -> list[AgentResult]:
        """Collect multiple content sources in parallel."""
        import asyncio

        tasks = [self.run(source) for source in sources]
        return await asyncio.gather(*tasks, return_exceptions=True)
