"""
Content Processor - Handles various content types and extracts structured information.

Supports:
- Text (articles, notes, AI summaries)
- URLs (web pages)
- Images (OCR, vision analysis)
- Documents (PDF, files)
"""

import re
import hashlib
from pathlib import Path
from typing import Optional
from datetime import datetime
from enum import Enum
from dataclasses import dataclass

import aiohttp


class ContentType(str, Enum):
    """Types of content that can be processed."""
    ARTICLE = "article"
    AI_SUMMARY = "ai_summary"
    CONCEPT = "concept"
    NOTE = "note"
    VISUALIZATION = "visualization"
    CODE = "code"
    QUOTE = "quote"
    UNKNOWN = "unknown"


@dataclass
class ProcessedContent:
    """Structured result from content processing."""
    id: str
    type: ContentType
    title: str
    content: str
    summary: str
    key_points: list[str]
    category: str
    tags: list[str]
    source: str
    metadata: dict


class ContentProcessor:
    """
    Processes various content types and extracts structured information.

    Uses Claude for intelligent content analysis, classification, and summarization.
    Supports custom prompts per category via PromptManager.
    """

    def __init__(self, use_ai: bool = True):
        self.url_pattern = re.compile(
            r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+'
        )
        self.use_ai = use_ai
        self._prompt_manager = None

    @property
    def prompt_manager(self):
        """Lazy load prompt manager."""
        if self._prompt_manager is None:
            from quick_capture_agent.processors.prompt_manager import get_prompt_manager
            self._prompt_manager = get_prompt_manager()
        return self._prompt_manager

    async def process_with_ai(self, content: str, category: Optional[str] = None) -> dict:
        """
        Process content using AI with category-specific prompts.

        Args:
            content: The content to process
            category: Optional category (auto-detected if not provided)

        Returns:
            AI-processed result dict
        """
        if not self.use_ai:
            return {}

        # Detect or use provided category
        if category:
            detected_category = category
        else:
            detected_category = self.prompt_manager.detect_category(content)

        system_prompt = self.prompt_manager.get_system_prompt(detected_category)
        user_prompt = self.prompt_manager.format_user_prompt(detected_category, content)

        try:
            import anthropic

            client = anthropic.Anthropic()
            response = client.messages.create(
                model="claude-sonnet-4-5-20241022",
                max_tokens=2000,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )

            # Parse AI response
            ai_result = response.content[0].text
            return {
                "ai_analysis": ai_result,
                "detected_category": detected_category,
                "prompt_used": detected_category,
            }

        except Exception as e:
            return {
                "ai_error": str(e),
                "detected_category": detected_category,
            }

    def _generate_id(self, content: str) -> str:
        """Generate unique ID for content."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
        return f"{timestamp}-{content_hash}"

    def _detect_content_type(self, text: str) -> ContentType:
        """Detect the type of text content."""
        text_lower = text.lower()

        # AI Summary indicators
        ai_indicators = [
            "here's a summary", "key points:", "in summary",
            "the main takeaways", "to summarize", "summary:",
            "tl;dr", "概括", "总结", "要点"
        ]
        if any(ind in text_lower for ind in ai_indicators):
            return ContentType.AI_SUMMARY

        # Concept/Definition indicators
        concept_indicators = [
            "is a ", "refers to", "is defined as", "means that",
            "定义", "是指", "概念"
        ]
        if any(ind in text_lower for ind in concept_indicators) and len(text) < 2000:
            return ContentType.CONCEPT

        # Code indicators
        code_indicators = ["```", "def ", "function ", "class ", "import ", "const "]
        if any(ind in text for ind in code_indicators):
            return ContentType.CODE

        # Quote indicators
        if text.startswith('"') and text.endswith('"'):
            return ContentType.QUOTE
        if text.startswith('"') or text.startswith("「"):
            return ContentType.QUOTE

        # Long text is likely an article
        if len(text) > 1500:
            return ContentType.ARTICLE

        # Default to note
        return ContentType.NOTE

    def _extract_title(self, text: str, content_type: ContentType) -> str:
        """Extract or generate a title from content."""
        lines = text.strip().split('\n')
        first_line = lines[0].strip()

        # If first line looks like a title (short, no punctuation at end)
        if len(first_line) < 100 and not first_line.endswith(('.', '。', '!', '?')):
            return first_line[:80]

        # Generate title based on content type
        type_prefixes = {
            ContentType.AI_SUMMARY: "AI 总结",
            ContentType.CONCEPT: "概念",
            ContentType.CODE: "代码片段",
            ContentType.QUOTE: "引用",
            ContentType.ARTICLE: "文章",
            ContentType.NOTE: "笔记",
        }
        prefix = type_prefixes.get(content_type, "内容")

        # Use first few words
        words = text.split()[:10]
        snippet = ' '.join(words)
        if len(snippet) > 50:
            snippet = snippet[:50] + "..."

        return f"{prefix}: {snippet}"

    def _extract_key_points(self, text: str) -> list[str]:
        """Extract key points from text."""
        points = []

        # Look for bullet points
        bullet_patterns = [
            r'^[-•*]\s*(.+)$',
            r'^\d+[.)]\s*(.+)$',
            r'^[一二三四五六七八九十][、.]\s*(.+)$',
        ]

        for line in text.split('\n'):
            line = line.strip()
            for pattern in bullet_patterns:
                match = re.match(pattern, line)
                if match:
                    points.append(match.group(1))
                    break

        # If no bullet points found, extract first sentences
        if not points:
            sentences = re.split(r'[.。!?！？]', text)
            points = [s.strip() for s in sentences[:5] if len(s.strip()) > 20]

        return points[:10]  # Limit to 10 points

    def _generate_summary(self, text: str, max_length: int = 300) -> str:
        """Generate a summary of the content."""
        # Simple extractive summary - take first paragraph
        paragraphs = text.split('\n\n')
        for para in paragraphs:
            para = para.strip()
            if len(para) > 50:
                if len(para) > max_length:
                    return para[:max_length] + "..."
                return para

        # Fallback to first N characters
        if len(text) > max_length:
            return text[:max_length] + "..."
        return text

    def _suggest_category(self, text: str, content_type: ContentType) -> str:
        """Suggest a category for the content."""
        text_lower = text.lower()

        # Category keywords mapping
        category_keywords = {
            "ai": ["ai", "machine learning", "deep learning", "neural", "gpt", "llm", "claude", "人工智能", "机器学习"],
            "tech": ["programming", "code", "software", "api", "framework", "编程", "技术", "开发"],
            "business": ["business", "startup", "company", "market", "商业", "创业", "投资"],
            "productivity": ["productivity", "workflow", "效率", "工具", "方法"],
            "design": ["design", "ui", "ux", "设计", "界面"],
            "life": ["life", "health", "生活", "健康"],
        }

        for category, keywords in category_keywords.items():
            if any(kw in text_lower for kw in keywords):
                return category

        # Default based on content type
        type_categories = {
            ContentType.AI_SUMMARY: "ai",
            ContentType.CONCEPT: "concepts",
            ContentType.CODE: "tech",
            ContentType.VISUALIZATION: "visualizations",
        }

        return type_categories.get(content_type, "uncategorized")

    def _extract_tags(self, text: str) -> list[str]:
        """Extract relevant tags from content."""
        tags = []
        text_lower = text.lower()

        # Common tech/concept tags
        tag_keywords = {
            "python": ["python"],
            "javascript": ["javascript", "js", "node"],
            "ai": ["ai", "artificial intelligence"],
            "ml": ["machine learning", "ml"],
            "llm": ["llm", "large language model", "gpt", "claude"],
            "api": ["api", "rest", "graphql"],
            "database": ["database", "sql", "mongodb"],
            "cloud": ["aws", "azure", "gcp", "cloud"],
            "agent": ["agent", "multi-agent"],
            "prompt": ["prompt", "prompting"],
        }

        for tag, keywords in tag_keywords.items():
            if any(kw in text_lower for kw in keywords):
                tags.append(tag)

        return tags[:10]  # Limit tags

    async def process_text(self, text: str) -> dict:
        """
        Process text content and extract structured information.

        Args:
            text: Raw text content

        Returns:
            Dictionary with processed content data
        """
        content_type = self._detect_content_type(text)
        title = self._extract_title(text, content_type)

        return {
            "id": self._generate_id(text),
            "type": content_type.value,
            "title": title,
            "content": text,
            "summary": self._generate_summary(text),
            "key_points": self._extract_key_points(text),
            "category": self._suggest_category(text, content_type),
            "tags": self._extract_tags(text),
            "source": "direct_input",
            "processed_at": datetime.now().isoformat(),
        }

    async def process_url(self, url: str) -> dict:
        """
        Process a URL by fetching and analyzing its content.

        Args:
            url: Web page URL

        Returns:
            Dictionary with processed content data
        """
        try:
            # Fetch content (simplified - in production use Firecrawl or similar)
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=30) as response:
                    html = await response.text()

            # Extract text from HTML (basic extraction)
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')

            # Remove scripts and styles
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()

            # Get title
            title = soup.title.string if soup.title else "Untitled"

            # Get main content
            article = soup.find('article') or soup.find('main') or soup.body
            text = article.get_text(separator='\n', strip=True) if article else ""

            # Process the extracted text
            result = await self.process_text(text)
            result["title"] = title
            result["source"] = url
            result["type"] = "article"
            result["category"] = "articles"

            return result

        except Exception as e:
            return {
                "id": self._generate_id(url),
                "type": "article",
                "title": f"Failed to fetch: {url}",
                "content": f"Error: {str(e)}",
                "summary": f"Failed to process URL: {str(e)}",
                "key_points": [],
                "category": "articles",
                "tags": [],
                "source": url,
                "error": str(e),
            }

    async def process_image(self, image_path: Path, caption: str = "") -> dict:
        """
        Process an image with OCR and vision analysis.

        Args:
            image_path: Path to the image file
            caption: Optional caption/description

        Returns:
            Dictionary with processed content data
        """
        # Placeholder for actual vision processing
        # In production, this would use Claude Vision API

        content_id = self._generate_id(str(image_path))

        return {
            "id": content_id,
            "type": "visualization",
            "title": caption or f"Image {content_id[:8]}",
            "content": caption,
            "description": "[Image analysis would go here - requires Claude Vision API]",
            "extracted_text": "",  # OCR result would go here
            "has_text": False,
            "summary": caption or "Image captured",
            "key_points": [],
            "category": "visualizations",
            "tags": ["image"],
            "source": str(image_path),
            "image_path": str(image_path),
        }

    async def process_document(self, doc_path: Path, mime_type: str = "") -> dict:
        """
        Process a document (PDF, etc.).

        Args:
            doc_path: Path to the document
            mime_type: MIME type of the document

        Returns:
            Dictionary with processed content data
        """
        content = ""
        title = doc_path.stem

        # Handle PDF
        if mime_type == "application/pdf" or doc_path.suffix.lower() == ".pdf":
            try:
                import pypdf
                with open(doc_path, 'rb') as f:
                    reader = pypdf.PdfReader(f)
                    content = "\n".join(page.extract_text() for page in reader.pages)
            except ImportError:
                content = "[PDF processing requires pypdf library]"
            except Exception as e:
                content = f"[Error reading PDF: {e}]"

        # Handle text files
        elif doc_path.suffix.lower() in ['.txt', '.md', '.json']:
            try:
                content = doc_path.read_text()
            except Exception as e:
                content = f"[Error reading file: {e}]"

        # Process the extracted content
        if content:
            result = await self.process_text(content)
            result["title"] = title
            result["source"] = str(doc_path)
            result["type"] = "document"
            result["category"] = "documents"
            return result

        return {
            "id": self._generate_id(str(doc_path)),
            "type": "document",
            "title": title,
            "content": content or "[Unable to extract content]",
            "summary": f"Document: {title}",
            "key_points": [],
            "category": "documents",
            "tags": [],
            "source": str(doc_path),
        }
