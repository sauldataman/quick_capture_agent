"""
Tests for ContentProcessor - URL fetching, image processing, text analysis.

Run with: pytest tests/test_content_processor.py -v
"""

import pytest
import asyncio
from pathlib import Path

from quick_capture_agent.processors.content_processor import ContentProcessor


class TestRestrictedSites:
    """Test restricted site detection."""

    def setup_method(self):
        self.processor = ContentProcessor()

    @pytest.mark.parametrize("url,expected", [
        # WeChat - should be restricted
        ("https://mp.weixin.qq.com/s/SBTaFv7Y5S2LBb2kB_g-8g", True),
        ("https://mp.weixin.qq.com/s/abc123", True),
        # Zhihu - should be restricted
        ("https://www.zhihu.com/question/123456", True),
        ("https://zhuanlan.zhihu.com/p/123456", True),
        # Juejin - should be restricted
        ("https://juejin.cn/post/123456", True),
        # Twitter/X - should be restricted
        ("https://twitter.com/user/status/123", True),
        ("https://x.com/user/status/123", True),
        # LinkedIn - should be restricted
        ("https://www.linkedin.com/posts/user-123", True),
        # Medium - should be restricted
        ("https://medium.com/@user/article-123", True),
        # Normal sites - should NOT be restricted
        ("https://github.com/user/repo", False),
        ("https://www.google.com/search?q=test", False),
        ("https://example.com/article", False),
        ("https://news.ycombinator.com/item?id=123", False),
    ])
    def test_is_restricted_site(self, url: str, expected: bool):
        """Test that restricted sites are correctly identified."""
        result = self.processor._is_restricted_site(url)
        assert result == expected, f"URL {url} should be restricted={expected}"


class TestURLProcessing:
    """Test URL processing with different sources."""

    def setup_method(self):
        self.processor = ContentProcessor()

    @pytest.mark.asyncio
    async def test_process_normal_url(self):
        """Test processing a normal (non-restricted) URL."""
        # Using a simple, reliable test URL
        url = "https://httpbin.org/html"
        result = await self.processor.process_url(url)

        assert "id" in result
        assert "title" in result
        assert "content" in result
        assert "category" in result
        # Fetcher could be "direct" or "jina_reader" (fallback)
        assert result.get("fetcher") in ["direct", "jina_reader"]
        # Should not have error if either method succeeded
        if result.get("fetcher") == "direct":
            assert "error" not in result or result.get("error") is None

    @pytest.mark.asyncio
    async def test_process_wechat_url(self):
        """Test processing a WeChat article URL (uses Jina Reader)."""
        url = "https://mp.weixin.qq.com/s/SBTaFv7Y5S2LBb2kB_g-8g"
        result = await self.processor.process_url(url)

        assert "id" in result
        assert result.get("fetcher") == "jina_reader"
        # Note: might fail if Jina Reader has issues, but should still return a result
        assert "title" in result

    @pytest.mark.asyncio
    async def test_process_zhihu_url(self):
        """Test processing a Zhihu URL (uses Jina Reader)."""
        # Using a known Zhihu article
        url = "https://zhuanlan.zhihu.com/p/339045722"
        result = await self.processor.process_url(url)

        assert "id" in result
        assert result.get("fetcher") == "jina_reader"
        assert "title" in result

    @pytest.mark.asyncio
    async def test_process_invalid_url(self):
        """Test processing an invalid URL."""
        url = "https://this-domain-definitely-does-not-exist-12345.com/page"
        result = await self.processor.process_url(url)

        # Should return a result with error info, not raise exception
        assert "id" in result
        assert "error" in result or "抓取失败" in result.get("title", "")

    @pytest.mark.asyncio
    async def test_force_jina_reader(self):
        """Test forcing Jina Reader for a normal URL."""
        url = "https://example.com"
        result = await self.processor.process_url(url, force_jina=True)

        assert result.get("fetcher") == "jina_reader"


class TestTextProcessing:
    """Test text content processing."""

    def setup_method(self):
        self.processor = ContentProcessor()

    @pytest.mark.asyncio
    async def test_process_note(self):
        """Test processing a short note."""
        text = "今天学到了一个新概念：RAG是检索增强生成的缩写。"
        result = await self.processor.process_text(text)

        assert "id" in result
        assert "title" in result
        assert "category" in result
        assert "tags" in result
        assert result.get("type") in ["note", "concept"]

    @pytest.mark.asyncio
    async def test_process_ai_summary(self):
        """Test processing an AI summary."""
        text = """
        Summary:
        这篇文章的主要要点如下：
        1. AI正在改变软件开发
        2. 提示工程变得越来越重要
        3. 未来开发者需要学习新技能
        """
        result = await self.processor.process_text(text)

        assert "id" in result
        assert result.get("type") == "ai_summary"

    @pytest.mark.asyncio
    async def test_process_code_snippet(self):
        """Test processing code content."""
        text = """
        ```python
        def hello_world():
            print("Hello, World!")
        ```
        """
        result = await self.processor.process_text(text)

        assert "id" in result
        assert result.get("type") == "code"

    @pytest.mark.asyncio
    async def test_process_long_article(self):
        """Test processing a long article."""
        text = "这是一篇很长的文章。" * 200  # Make it > 1500 chars
        result = await self.processor.process_text(text)

        assert "id" in result
        assert result.get("type") == "article"
        assert len(result.get("summary", "")) < len(text)  # Summary should be shorter

    @pytest.mark.asyncio
    async def test_extract_tags(self):
        """Test tag extraction from technical content."""
        text = "这是一个关于Python和机器学习的教程，使用了TensorFlow和GPT模型。"
        result = await self.processor.process_text(text)

        tags = result.get("tags", [])
        assert "python" in tags or "ml" in tags or "llm" in tags


class TestImageProcessing:
    """Test image processing."""

    def setup_method(self):
        self.processor = ContentProcessor()

    @pytest.mark.asyncio
    async def test_process_image_with_caption(self):
        """Test processing an image with caption."""
        # Create a dummy image file for testing
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            # Write minimal JPEG data
            f.write(b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01')
            temp_path = Path(f.name)

        try:
            caption = "这是一个架构图"
            result = await self.processor.process_image(temp_path, caption)

            assert "id" in result
            assert "title" in result
            assert result.get("category") == "visualizations"
            assert "image" in result.get("tags", [])
        finally:
            temp_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_process_image_without_caption(self):
        """Test processing an image without caption."""
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b'\x89PNG\r\n\x1a\n')
            temp_path = Path(f.name)

        try:
            result = await self.processor.process_image(temp_path, "")

            assert "id" in result
            assert result.get("category") == "visualizations"
        finally:
            temp_path.unlink(missing_ok=True)


class TestDocumentProcessing:
    """Test document processing."""

    def setup_method(self):
        self.processor = ContentProcessor()

    @pytest.mark.asyncio
    async def test_process_text_file(self):
        """Test processing a text file."""
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode='w') as f:
            f.write("这是一个测试文档的内容。\n包含多行文字。")
            temp_path = Path(f.name)

        try:
            result = await self.processor.process_document(temp_path, "text/plain")

            assert "id" in result
            assert result.get("category") == "documents"
        finally:
            temp_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_process_markdown_file(self):
        """Test processing a markdown file."""
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False, mode='w') as f:
            f.write("# 标题\n\n这是正文内容。")
            temp_path = Path(f.name)

        try:
            result = await self.processor.process_document(temp_path, "text/markdown")

            assert "id" in result
            assert "标题" in result.get("title", "") or "标题" in result.get("content", "")
        finally:
            temp_path.unlink(missing_ok=True)


# Integration test - simulates full flow
class TestIntegration:
    """Integration tests simulating real usage."""

    def setup_method(self):
        self.processor = ContentProcessor()

    @pytest.mark.asyncio
    async def test_full_url_flow(self):
        """Test complete URL processing flow."""
        urls_to_test = [
            ("https://httpbin.org/html", ["direct", "jina_reader"]),  # May fallback
            ("https://mp.weixin.qq.com/s/test", ["jina_reader"]),  # Always Jina
        ]

        for url, expected_fetchers in urls_to_test:
            result = await self.processor.process_url(url)
            assert result.get("fetcher") in expected_fetchers, \
                f"URL {url} should use one of {expected_fetchers}, got {result.get('fetcher')}"
            # Should return valid result structure
            assert "id" in result
            assert "title" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
