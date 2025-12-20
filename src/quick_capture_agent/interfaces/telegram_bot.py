"""
Telegram Bot interface for Quick Capture Agent.

This module provides a Telegram bot that accepts various content types
and processes them through the content collector agent.
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional
from datetime import datetime

from telegram import Update, Message
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from quick_capture_agent.processors.content_processor import ContentProcessor
from quick_capture_agent.processors.markdown_generator import MarkdownGenerator
from quick_capture_agent.knowledge_base import KnowledgeBase, ContentCategory

logger = logging.getLogger(__name__)


class TelegramBot:
    """
    Telegram Bot for capturing and processing content.

    Supports:
    - Text messages (articles, notes, AI summaries)
    - URLs (auto-fetches and processes)
    - Images (OCR, vision analysis)
    - Documents (PDF, files)
    - Forwarded messages
    """

    def __init__(
        self,
        token: Optional[str] = None,
        knowledge_base_path: Optional[Path] = None,
        allowed_users: Optional[list[int]] = None,
    ):
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN")
        if not self.token:
            raise ValueError("Telegram bot token is required")

        self.knowledge_base = KnowledgeBase(knowledge_base_path)
        self.processor = ContentProcessor()
        self.markdown_gen = MarkdownGenerator()
        self.allowed_users = allowed_users or self._get_allowed_users()
        self.app: Optional[Application] = None

    def _get_allowed_users(self) -> list[int]:
        """Get allowed user IDs from environment."""
        users_str = os.getenv("TELEGRAM_ALLOWED_USERS", "")
        if users_str:
            return [int(u.strip()) for u in users_str.split(",") if u.strip()]
        return []  # Empty means allow all

    def _is_authorized(self, user_id: int) -> bool:
        """Check if user is authorized."""
        if not self.allowed_users:
            return True  # Allow all if no restriction
        return user_id in self.allowed_users

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        if not self._is_authorized(update.effective_user.id):
            await update.message.reply_text("⛔ Unauthorized")
            return

        welcome = """🚀 **Quick Capture Agent**

我是你的知识捕获助手！发送以下内容给我：

📝 **文字** - 直接粘贴文章或笔记
🔗 **链接** - 网页URL，我会自动抓取
🖼️ **图片** - 截图、图表、信息图
📄 **文件** - PDF、文档等

**命令：**
/capture - 开始捕获（默认模式）
/category <类别> - 设置分类
/tags <标签> - 添加标签
/search <关键词> - 搜索知识库
/stats - 查看统计
/recent - 最近捕获

直接发送内容即可，我会自动处理并存入知识库！"""

        await update.message.reply_text(welcome, parse_mode="Markdown")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command."""
        if not self._is_authorized(update.effective_user.id):
            return

        help_text = """📖 **使用帮助**

**内容类型支持：**
• 文章链接 → 自动抓取、总结、分类
• 纯文本 → 识别类型、提取要点
• 图片 → OCR + 视觉分析
• 文件 → 解析并提取内容

**分类命令：**
`/category tech` - 设置为技术类
`/category ai` - 设置为AI类
`/category business` - 设置为商业类

**标签命令：**
`/tags python,机器学习` - 添加标签

**搜索：**
`/search transformer` - 搜索知识库

**提示：**
• 发送图片时可以添加说明文字
• 转发的消息会保留来源信息
• AI总结内容会自动识别"""

        await update.message.reply_text(help_text, parse_mode="Markdown")

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle text messages."""
        if not self._is_authorized(update.effective_user.id):
            return

        message = update.message
        text = message.text

        # Send processing indicator
        status_msg = await message.reply_text("🔄 处理中...")

        try:
            # Process the content
            result = await self.processor.process_text(text)

            # Generate markdown
            markdown_content = self.markdown_gen.generate(result)

            # Store in knowledge base
            item = self.knowledge_base.add(
                title=result.get("title", "Untitled"),
                content=markdown_content,
                source=result.get("source", "telegram"),
                category=ContentCategory(result.get("category", "uncategorized")),
                tags=result.get("tags", []),
                metadata={
                    "telegram_message_id": message.message_id,
                    "telegram_user_id": message.from_user.id,
                    "content_type": result.get("type"),
                    "processed_at": datetime.now().isoformat(),
                }
            )

            # Send confirmation
            response = f"""✅ **已保存到知识库**

📌 **标题**: {result.get('title', 'Untitled')}
📁 **分类**: {result.get('category', 'uncategorized')}
🏷️ **标签**: {', '.join(result.get('tags', [])) or '无'}

📝 **摘要**:
{result.get('summary', '无摘要')}

🔑 ID: `{item.id}`"""

            await status_msg.edit_text(response, parse_mode="Markdown")

        except Exception as e:
            logger.error(f"Error processing text: {e}")
            await status_msg.edit_text(f"❌ 处理失败: {str(e)}")

    async def handle_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle URL messages."""
        if not self._is_authorized(update.effective_user.id):
            return

        message = update.message
        # Extract URL from message
        urls = [e.url for e in message.entities if e.type == "url"]
        if not urls:
            # Try to find URL in text
            import re
            urls = re.findall(r'https?://\S+', message.text)

        if not urls:
            await message.reply_text("❌ 未找到有效链接")
            return

        status_msg = await message.reply_text(f"🔄 正在抓取: {urls[0][:50]}...")

        try:
            result = await self.processor.process_url(urls[0])
            markdown_content = self.markdown_gen.generate(result)

            item = self.knowledge_base.add(
                title=result.get("title", "Untitled"),
                content=markdown_content,
                source=urls[0],
                category=ContentCategory(result.get("category", "articles")),
                tags=result.get("tags", []),
                metadata={
                    "original_url": urls[0],
                    "telegram_message_id": message.message_id,
                }
            )

            response = f"""✅ **文章已保存**

📌 **{result.get('title', 'Untitled')}**

📝 **摘要**:
{result.get('summary', '无摘要')[:300]}...

📁 分类: {result.get('category', 'articles')}
🏷️ 标签: {', '.join(result.get('tags', [])[:5])}

🔑 ID: `{item.id}`"""

            await status_msg.edit_text(response, parse_mode="Markdown")

        except Exception as e:
            logger.error(f"Error processing URL: {e}")
            await status_msg.edit_text(f"❌ 抓取失败: {str(e)}")

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle photo messages."""
        if not self._is_authorized(update.effective_user.id):
            return

        message = update.message
        status_msg = await message.reply_text("🔄 分析图片中...")

        try:
            # Get the largest photo
            photo = message.photo[-1]
            file = await context.bot.get_file(photo.file_id)

            # Download to temp location
            temp_path = Path(f"/tmp/tg_photo_{photo.file_id}.jpg")
            await file.download_to_drive(temp_path)

            # Get caption if any
            caption = message.caption or ""

            # Process the image
            result = await self.processor.process_image(temp_path, caption)
            markdown_content = self.markdown_gen.generate(result)

            # Save image to knowledge base attachments
            attachment_path = self.knowledge_base.base_path / "_attachments"
            attachment_path.mkdir(exist_ok=True)
            final_image_path = attachment_path / f"{result.get('id', photo.file_id)}.jpg"
            temp_path.rename(final_image_path)

            item = self.knowledge_base.add(
                title=result.get("title", "Image Capture"),
                content=markdown_content,
                source="telegram_photo",
                category=ContentCategory(result.get("category", "visualizations")),
                tags=result.get("tags", []),
                metadata={
                    "image_path": str(final_image_path),
                    "has_ocr": result.get("has_text", False),
                }
            )

            response = f"""✅ **图片已分析并保存**

📌 **{result.get('title', 'Image')}**
📁 分类: {result.get('category', 'visualizations')}

📝 **内容识别**:
{result.get('description', '无描述')[:200]}

{'📄 **提取的文字**: ' + result.get('extracted_text', '')[:100] + '...' if result.get('extracted_text') else ''}

🔑 ID: `{item.id}`"""

            await status_msg.edit_text(response, parse_mode="Markdown")

        except Exception as e:
            logger.error(f"Error processing photo: {e}")
            await status_msg.edit_text(f"❌ 图片处理失败: {str(e)}")

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle document messages."""
        if not self._is_authorized(update.effective_user.id):
            return

        message = update.message
        doc = message.document

        status_msg = await message.reply_text(f"🔄 处理文件: {doc.file_name}...")

        try:
            file = await context.bot.get_file(doc.file_id)
            temp_path = Path(f"/tmp/{doc.file_name}")
            await file.download_to_drive(temp_path)

            result = await self.processor.process_document(temp_path, doc.mime_type)
            markdown_content = self.markdown_gen.generate(result)

            item = self.knowledge_base.add(
                title=result.get("title", doc.file_name),
                content=markdown_content,
                source=f"telegram_doc:{doc.file_name}",
                category=ContentCategory(result.get("category", "documents")),
                tags=result.get("tags", []),
            )

            response = f"""✅ **文档已处理**

📄 **{doc.file_name}**
📁 分类: {result.get('category', 'documents')}

📝 **摘要**:
{result.get('summary', '无摘要')[:300]}

🔑 ID: `{item.id}`"""

            await status_msg.edit_text(response, parse_mode="Markdown")

            # Clean up
            temp_path.unlink(missing_ok=True)

        except Exception as e:
            logger.error(f"Error processing document: {e}")
            await status_msg.edit_text(f"❌ 文档处理失败: {str(e)}")

    async def search_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /search command."""
        if not self._is_authorized(update.effective_user.id):
            return

        if not context.args:
            await update.message.reply_text("用法: /search <关键词>")
            return

        query = " ".join(context.args)
        results = self.knowledge_base.search(query=query, limit=5)

        if not results:
            await update.message.reply_text(f"🔍 未找到与 '{query}' 相关的内容")
            return

        response = f"🔍 **搜索结果**: {query}\n\n"
        for item in results:
            response += f"📌 **{item.title}**\n"
            response += f"   📁 {item.category.value} | 🏷️ {', '.join(item.tags[:3])}\n"
            response += f"   🔑 `{item.id}`\n\n"

        await update.message.reply_text(response, parse_mode="Markdown")

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /stats command."""
        if not self._is_authorized(update.effective_user.id):
            return

        stats = self.knowledge_base.get_stats()

        response = f"""📊 **知识库统计**

📚 总条目: {stats['total_items']}
🏷️ 标签数: {stats['total_tags']}

**分类分布:**
"""
        for cat, count in stats.get('categories', {}).items():
            response += f"• {cat}: {count}\n"

        await update.message.reply_text(response, parse_mode="Markdown")

    async def recent_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /recent command."""
        if not self._is_authorized(update.effective_user.id):
            return

        items = list(self.knowledge_base.iter_all())
        items.sort(key=lambda x: x.created_at, reverse=True)
        recent = items[:5]

        if not recent:
            await update.message.reply_text("📭 知识库为空")
            return

        response = "📋 **最近捕获**\n\n"
        for item in recent:
            response += f"📌 **{item.title[:40]}**\n"
            response += f"   {item.created_at[:10]} | {item.category.value}\n\n"

        await update.message.reply_text(response, parse_mode="Markdown")

    def run(self) -> None:
        """Start the bot."""
        self.app = Application.builder().token(self.token).build()

        # Command handlers
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("search", self.search_command))
        self.app.add_handler(CommandHandler("stats", self.stats_command))
        self.app.add_handler(CommandHandler("recent", self.recent_command))

        # Message handlers
        self.app.add_handler(MessageHandler(
            filters.TEXT & filters.Entity("url"), self.handle_url
        ))
        self.app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND, self.handle_text
        ))
        self.app.add_handler(MessageHandler(filters.PHOTO, self.handle_photo))
        self.app.add_handler(MessageHandler(filters.Document.ALL, self.handle_document))

        # Start polling
        logger.info("Starting Telegram bot...")
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)
