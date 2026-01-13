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
        """
        Suggest a knowledge category for the content.

        Categories:
        - thinking: 思维模型、决策框架、认知偏差
        - technology: AI、编程、工具、产品
        - business: 创业、管理、营销、战略
        - growth: 学习、效率、习惯、职业
        - philosophy: 哲学、心理学、认知科学
        - creative: 设计、写作、艺术
        - finance: 投资、理财、经济
        - wellness: 健康、运动、生活方式
        - inbox: 待分类
        """
        text_lower = text.lower()

        # Knowledge category keywords mapping
        category_keywords = {
            "thinking": [
                "思维模型", "mental model", "决策", "decision", "认知偏差", "cognitive bias",
                "第一性原理", "first principles", "框架", "framework", "思考", "thinking",
                "逻辑", "logic", "推理", "reasoning", "方法论", "methodology"
            ],
            "technology": [
                "ai", "人工智能", "machine learning", "机器学习", "programming", "编程",
                "code", "代码", "software", "软件", "api", "framework", "开发", "developer",
                "python", "javascript", "gpt", "llm", "claude", "算法", "algorithm",
                "产品", "product", "工具", "tool", "技术", "tech"
            ],
            "business": [
                "business", "商业", "startup", "创业", "company", "公司", "market", "市场",
                "营销", "marketing", "管理", "management", "战略", "strategy", "竞争",
                "competition", "商业模式", "business model", "增长", "growth hacking"
            ],
            "growth": [
                "学习", "learning", "效率", "productivity", "习惯", "habit", "职业", "career",
                "成长", "growth", "技能", "skill", "目标", "goal", "时间管理", "time management",
                "自我提升", "self improvement", "复盘", "review"
            ],
            "philosophy": [
                "哲学", "philosophy", "心理", "psychology", "认知", "cognition", "意识",
                "consciousness", "存在", "existence", "伦理", "ethics", "智慧", "wisdom",
                "人生", "life meaning", "斯多葛", "stoic", "佛学", "buddhism", "道家", "taoism"
            ],
            "creative": [
                "设计", "design", "ui", "ux", "写作", "writing", "艺术", "art", "创意",
                "creative", "美学", "aesthetic", "视觉", "visual", "品牌", "brand",
                "故事", "storytelling", "内容", "content creation"
            ],
            "finance": [
                "投资", "investment", "理财", "finance", "经济", "economics", "股票", "stock",
                "基金", "fund", "财务", "financial", "资产", "asset", "收益", "return",
                "风险", "risk", "估值", "valuation", "crypto", "加密货币"
            ],
            "wellness": [
                "健康", "health", "运动", "exercise", "睡眠", "sleep", "饮食", "diet",
                "冥想", "meditation", "压力", "stress", "心理健康", "mental health",
                "生活方式", "lifestyle", "养生", "wellness"
            ],
        }

        # Score each category
        scores = {cat: 0 for cat in category_keywords}
        for category, keywords in category_keywords.items():
            for kw in keywords:
                if kw in text_lower:
                    scores[category] += 1

        # Get best category
        best_category = max(scores, key=scores.get)
        if scores[best_category] > 0:
            return best_category

        # Default to inbox for uncategorized content
        return "inbox"

    def _extract_tags(self, text: str, category: str = None) -> list[str]:
        """
        Extract knowledge-based tags with #kb/ prefix format.

        Format: #kb/category/subcategory
        Example: #kb/thinking/mental-models, #kb/technology/ai
        """
        tags = []
        text_lower = text.lower()

        # Subcategory keywords mapping (category -> subcategory -> keywords)
        subcategory_keywords = {
            "thinking": {
                "mental-models": ["思维模型", "mental model", "心智模型"],
                "decision-making": ["决策", "decision", "选择", "choice"],
                "cognitive-bias": ["认知偏差", "cognitive bias", "偏见"],
                "first-principles": ["第一性原理", "first principles", "本质"],
                "systems-thinking": ["系统思维", "systems thinking", "复杂系统"],
            },
            "technology": {
                "ai": ["ai", "人工智能", "artificial intelligence", "机器学习", "ml"],
                "llm": ["llm", "大语言模型", "gpt", "claude", "chatgpt"],
                "programming": ["编程", "programming", "代码", "code", "开发"],
                "tools": ["工具", "tool", "软件", "software", "app"],
                "product": ["产品", "product", "功能", "feature"],
            },
            "business": {
                "startup": ["创业", "startup", "初创"],
                "strategy": ["战略", "strategy", "竞争", "competition"],
                "marketing": ["营销", "marketing", "增长", "growth"],
                "management": ["管理", "management", "领导", "leadership"],
            },
            "growth": {
                "learning": ["学习", "learning", "教育", "education"],
                "productivity": ["效率", "productivity", "时间管理"],
                "habits": ["习惯", "habit", "行为", "behavior"],
                "career": ["职业", "career", "工作", "job"],
            },
            "philosophy": {
                "psychology": ["心理", "psychology", "行为"],
                "stoicism": ["斯多葛", "stoic", "自律"],
                "eastern": ["禅", "zen", "道", "tao", "佛", "buddhism"],
                "wisdom": ["智慧", "wisdom", "人生", "life"],
            },
            "creative": {
                "design": ["设计", "design", "ui", "ux"],
                "writing": ["写作", "writing", "文案", "copywriting"],
                "art": ["艺术", "art", "美学", "aesthetic"],
            },
            "finance": {
                "investing": ["投资", "investment", "股票", "stock"],
                "personal-finance": ["理财", "finance", "储蓄", "saving"],
                "economics": ["经济", "economics", "宏观"],
                "crypto": ["加密", "crypto", "区块链", "blockchain"],
            },
            "wellness": {
                "fitness": ["运动", "exercise", "健身", "fitness"],
                "nutrition": ["饮食", "diet", "营养", "nutrition"],
                "mental-health": ["心理健康", "mental health", "冥想", "meditation"],
                "sleep": ["睡眠", "sleep", "休息", "rest"],
            },
        }

        # Add primary category tag
        if category and category != "inbox":
            tags.append(f"#kb/{category}")

        # Find matching subcategories
        for cat, subcats in subcategory_keywords.items():
            for subcat, keywords in subcats.items():
                if any(kw in text_lower for kw in keywords):
                    tag = f"#kb/{cat}/{subcat}"
                    if tag not in tags:
                        tags.append(tag)

        # Limit to most relevant tags
        return tags[:8]

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
        category = self._suggest_category(text, content_type)

        return {
            "id": self._generate_id(text),
            "type": content_type.value,
            "title": title,
            "content": text,
            "summary": self._generate_summary(text),
            "key_points": self._extract_key_points(text),
            "category": category,
            "tags": self._extract_tags(text, category),
            "source": "direct_input",
            "source_type": content_type.value,  # Original content type
            "processed_at": datetime.now().isoformat(),
        }

    # Sites that need special handling (JS rendering, anti-bot, etc.)
    RESTRICTED_SITES = [
        "mp.weixin.qq.com",      # WeChat articles
        "weixin.qq.com",
        "zhihu.com",            # Zhihu
        "zhuanlan.zhihu.com",
        "juejin.cn",            # Juejin
        "xiaohongshu.com",      # Xiaohongshu
        "douyin.com",           # Douyin
        "bilibili.com",         # Bilibili
        "twitter.com",          # Twitter/X
        "x.com",
        "linkedin.com",         # LinkedIn
        "medium.com",           # Medium (paywall)
        "notion.so",            # Notion
    ]

    def _extract_title_from_url(self, url: str) -> str:
        """Extract a readable title from URL path."""
        from urllib.parse import urlparse, unquote
        try:
            parsed = urlparse(url)
            # Get the path and remove common extensions
            path = parsed.path.rstrip('/')
            if path:
                # Get last segment of path
                segment = path.split('/')[-1]
                # Remove file extensions
                segment = re.sub(r'\.(html?|php|aspx?)$', '', segment, flags=re.I)
                # URL decode
                segment = unquote(segment)
                # Replace dashes/underscores with spaces
                segment = re.sub(r'[-_]', ' ', segment)
                # Remove numeric IDs at the end (like zhihu's p/1991073922217709984)
                segment = re.sub(r'^\d+$', '', segment)
                if segment and len(segment) > 3:
                    return segment.title()
            # Fallback to domain
            return parsed.netloc
        except Exception:
            return "Untitled"

    async def _fetch_with_jina(self, url: str) -> tuple[str, str]:
        """
        Fetch URL content using Jina Reader API.

        Returns:
            Tuple of (title, content)
        """
        jina_url = f"https://r.jina.ai/{url}"
        headers = {
            "Accept": "text/markdown",
            "X-Return-Format": "markdown",
        }

        timeout = aiohttp.ClientTimeout(total=60)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(jina_url, headers=headers) as response:
                if response.status != 200:
                    raise Exception(f"Jina Reader failed: HTTP {response.status}")
                content = await response.text()

        # Check if content indicates an error (403, blocked, etc.)
        error_indicators = [
            "error 403", "error 401", "forbidden", "blocked",
            "access denied", "please verify", "captcha"
        ]
        content_lower = content.lower()[:500]
        has_error = any(indicator in content_lower for indicator in error_indicators)

        # Parse title from markdown (usually first # heading)
        lines = content.split('\n')
        title = None
        for line in lines[:10]:
            if line.startswith('# '):
                candidate = line[2:].strip()
                # Skip error-like titles or generic site slogans
                if candidate and len(candidate) > 3:
                    if not any(x in candidate.lower() for x in ['error', '403', '验证', '登录']):
                        title = candidate
                        break
            elif line.startswith('Title:'):
                candidate = line[6:].strip()
                if candidate and len(candidate) > 3:
                    title = candidate
                    break

        # If no title found or error detected, try to extract from URL
        if not title or has_error:
            title = self._extract_title_from_url(url)

        return title, content

    def _is_restricted_site(self, url: str) -> bool:
        """Check if URL is from a restricted site that needs Jina Reader."""
        from urllib.parse import urlparse
        try:
            domain = urlparse(url).netloc.lower()
            return any(site in domain for site in self.RESTRICTED_SITES)
        except Exception:
            return False

    async def process_url(self, url: str, force_jina: bool = False) -> dict:
        """
        Process a URL by fetching and analyzing its content.

        Args:
            url: Web page URL
            force_jina: Force using Jina Reader even for normal sites

        Returns:
            Dictionary with processed content data
        """
        use_jina = force_jina or self._is_restricted_site(url)

        if use_jina:
            return await self._process_url_with_jina(url)
        else:
            return await self._process_url_direct(url)

    async def _process_url_with_jina(self, url: str) -> dict:
        """Process URL using Jina Reader API."""
        try:
            title, content = await self._fetch_with_jina(url)

            # Check if content indicates a fetch error (403, blocked, etc.)
            error_indicators = [
                "error 403", "error 401", "forbidden", "blocked",
                "access denied", "please verify", "captcha"
            ]
            content_lower = content.lower()[:500]
            fetch_failed = any(indicator in content_lower for indicator in error_indicators)

            # Process the extracted content (category determined by content)
            result = await self.process_text(content)
            result["title"] = title
            result["source"] = url
            result["type"] = "article"
            result["source_type"] = "article"  # Original source type
            result["original_url"] = url
            result["fetcher"] = "jina_reader"

            # Add warning if fetch was partial/failed
            if fetch_failed:
                result["fetch_warning"] = "内容抓取受限，可能不完整"
                # Update summary to reflect the issue
                if "403" in content or "forbidden" in content_lower:
                    result["summary"] = f"⚠️ 网站返回403错误，内容抓取受限。标题: {title}"

            return result

        except Exception as e:
            error_msg = f"Jina Reader 抓取失败: {str(e)}"
            return {
                "id": self._generate_id(url),
                "type": "article",
                "title": self._extract_title_from_url(url),
                "content": error_msg,
                "summary": error_msg,
                "key_points": [],
                "category": "inbox",
                "tags": ["#kb/inbox"],
                "source": url,
                "source_type": "article",
                "error": str(e),
                "fetcher": "jina_reader",
            }

    async def _process_url_direct(self, url: str) -> dict:
        """Process URL with direct HTTP fetch."""
        # Headers to mimic a real browser request
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }

        try:
            # Fetch content with proper headers
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
                async with session.get(url, allow_redirects=True) as response:
                    if response.status != 200:
                        raise Exception(f"HTTP {response.status}: {response.reason}")
                    html = await response.text()

            # Extract text from HTML
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')

            # Remove scripts and styles
            for element in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
                element.decompose()

            # Get title
            title = "Untitled"
            if soup.title and soup.title.string:
                title = soup.title.string.strip()
            # Try og:title as fallback
            og_title = soup.find("meta", property="og:title")
            if og_title and og_title.get("content"):
                title = og_title["content"]

            # Get main content with priority order
            article = (
                soup.find('article') or
                soup.find(class_=re.compile(r'article|content|post|entry|main', re.I)) or
                soup.find(id=re.compile(r'article|content|post|entry|main', re.I)) or
                soup.find('main') or
                soup.body
            )
            text = article.get_text(separator='\n', strip=True) if article else ""

            # Clean up text
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            text = '\n'.join(lines)

            if not text or len(text) < 100:
                # Fallback: get all text from body
                text = soup.body.get_text(separator='\n', strip=True) if soup.body else ""

            # Process the extracted text (category determined by content)
            result = await self.process_text(text)
            result["title"] = title
            result["source"] = url
            result["type"] = "article"
            result["source_type"] = "article"  # Original source type
            result["original_url"] = url
            result["fetcher"] = "direct"

            return result

        except aiohttp.ClientError as e:
            # Direct fetch failed, try Jina Reader as fallback
            try:
                return await self._process_url_with_jina(url)
            except Exception:
                pass

            error_msg = f"网络请求失败: {str(e)}"
            return {
                "id": self._generate_id(url),
                "type": "article",
                "title": f"抓取失败: {url[:50]}...",
                "content": error_msg,
                "summary": error_msg,
                "key_points": [],
                "category": "inbox",
                "tags": ["#kb/inbox"],
                "source": url,
                "source_type": "article",
                "error": str(e),
                "fetcher": "direct",
            }
        except Exception as e:
            # Direct fetch failed, try Jina Reader as fallback
            try:
                return await self._process_url_with_jina(url)
            except Exception:
                pass

            error_msg = f"处理失败: {str(e)}"
            return {
                "id": self._generate_id(url),
                "type": "article",
                "title": f"处理失败: {url[:50]}...",
                "content": error_msg,
                "summary": error_msg,
                "key_points": [],
                "category": "inbox",
                "tags": ["#kb/inbox"],
                "source": url,
                "source_type": "article",
                "error": str(e),
                "fetcher": "direct",
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
        content_id = self._generate_id(str(image_path))

        # Determine category based on caption if available
        category = "inbox"
        if caption:
            category = self._suggest_category(caption, ContentType.VISUALIZATION)

        tags = self._extract_tags(caption, category) if caption else ["#kb/inbox"]

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
            "category": category,
            "tags": tags,
            "source": str(image_path),
            "source_type": "image",
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
        extraction_method = "none"

        # Handle PDF
        if mime_type == "application/pdf" or doc_path.suffix.lower() == ".pdf":
            content, extraction_method = await self._extract_pdf_content(doc_path)

        # Handle text files
        elif doc_path.suffix.lower() in ['.txt', '.md', '.json', '.csv']:
            try:
                content = doc_path.read_text(encoding='utf-8')
                extraction_method = "text"
            except UnicodeDecodeError:
                try:
                    content = doc_path.read_text(encoding='latin-1')
                    extraction_method = "text_latin1"
                except Exception as e:
                    content = f"[Error reading file: {e}]"

        # Process the extracted content (category determined by content)
        if content and not content.startswith("["):
            result = await self.process_text(content)
            result["title"] = title
            result["source"] = str(doc_path)
            result["type"] = "document"
            result["source_type"] = "document"  # Original source type
            result["extraction_method"] = extraction_method
            result["original_filename"] = doc_path.name
            return result

        return {
            "id": self._generate_id(str(doc_path)),
            "type": "document",
            "title": title,
            "content": content or "[Unable to extract content]",
            "summary": f"Document: {title}" + (f" ({content})" if content.startswith("[") else ""),
            "key_points": [],
            "category": "inbox",
            "tags": ["#kb/inbox"],
            "source": str(doc_path),
            "source_type": "document",
            "extraction_method": extraction_method,
            "original_filename": doc_path.name,
        }

    async def _extract_pdf_content(self, doc_path: Path) -> tuple[str, str]:
        """
        Extract text content from PDF using multiple methods.

        Returns:
            Tuple of (content, extraction_method)
        """
        # Try pypdf first
        try:
            import pypdf
            with open(doc_path, 'rb') as f:
                reader = pypdf.PdfReader(f)
                pages_text = []
                for page in reader.pages:
                    try:
                        text = page.extract_text()
                        if text:
                            pages_text.append(text)
                    except Exception:
                        continue
                if pages_text:
                    return "\n\n".join(pages_text), "pypdf"
        except ImportError:
            pass
        except Exception as e:
            # pypdf failed, try alternatives
            pass

        # Try pdfplumber as fallback
        try:
            import pdfplumber
            with pdfplumber.open(doc_path) as pdf:
                pages_text = []
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        pages_text.append(text)
                if pages_text:
                    return "\n\n".join(pages_text), "pdfplumber"
        except ImportError:
            pass
        except Exception:
            pass

        # Try PyMuPDF (fitz) as another fallback
        try:
            import fitz
            doc = fitz.open(doc_path)
            pages_text = []
            for page in doc:
                text = page.get_text()
                if text:
                    pages_text.append(text)
            doc.close()
            if pages_text:
                return "\n\n".join(pages_text), "pymupdf"
        except ImportError:
            pass
        except Exception:
            pass

        return "[PDF处理失败: 请安装 pypdf, pdfplumber 或 pymupdf]", "failed"
