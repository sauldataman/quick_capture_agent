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
from quick_capture_agent.knowledge_base.git_sync import get_git_sync
from quick_capture_agent.knowledge_base.gdrive_sync import get_gdrive_sync

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

    async def _sync_to_git(self, title: str = "New capture") -> None:
        """Sync changes to Git repository if configured."""
        git_sync = get_git_sync(self.knowledge_base.base_path)
        if git_sync:
            try:
                await git_sync.sync_changes(f"Add: {title}")
                logger.info(f"Synced to git: {title}")
            except Exception as e:
                logger.error(f"Git sync failed: {e}")

    async def _sync_to_gdrive(
        self,
        content: str,
        category: str,
        filename: str,
        image_path: Optional[Path] = None
    ) -> Optional[str]:
        """
        Sync content to Google Drive if configured.

        Returns the Google Drive link if successful.
        """
        gdrive = get_gdrive_sync()
        if not gdrive:
            return None

        try:
            # Upload markdown content
            remote_path = f"{category}/{filename}"
            result = await gdrive.upload_content(content, remote_path)
            logger.info(f"Synced to Google Drive: {remote_path}")

            # Upload image if present
            if image_path and image_path.exists():
                img_remote = f"_attachments/{image_path.name}"
                await gdrive.upload_file(image_path, img_remote)

            return result.get('webViewLink')

        except Exception as e:
            logger.error(f"Google Drive sync failed: {e}")
            return None

    def _is_authorized(self, user_id: int) -> bool:
        """Check if user is authorized."""
        if not self.allowed_users:
            return True  # Allow all if no restriction
        return user_id in self.allowed_users

    def _safe_category(self, category_str: str) -> ContentCategory:
        """Safely convert category string to ContentCategory enum."""
        try:
            return ContentCategory(category_str)
        except ValueError:
            logger.warning(f"Invalid category '{category_str}', using UNCATEGORIZED")
            return ContentCategory.UNCATEGORIZED

    def _escape_markdown(self, text: str) -> str:
        """Escape special characters for Telegram Markdown."""
        if not text:
            return ""
        # Escape special markdown characters
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        return text

    def _safe_markdown_text(self, text: str, max_length: int = 300) -> str:
        """Make text safe for Telegram markdown, with length limit."""
        if not text:
            return "无"
        # Truncate first, then escape
        if len(text) > max_length:
            text = text[:max_length] + "..."
        return self._escape_markdown(text)

    async def _process_url_message(self, message, url: str) -> None:
        """Process a URL and save to knowledge base."""
        status_msg = await message.reply_text(f"🔄 正在抓取: {url[:50]}...")

        try:
            result = await self.processor.process_url(url)
            markdown_content = self.markdown_gen.generate(result)

            item = self.knowledge_base.add(
                title=result.get("title", "Untitled"),
                content=markdown_content,
                source=url,
                category=self._safe_category(result.get("category", "articles")),
                tags=result.get("tags", []),
                metadata={
                    "original_url": url,
                    "telegram_message_id": message.message_id,
                    "fetcher": result.get("fetcher", "unknown"),
                }
            )

            # Sync to git if configured
            await self._sync_to_git(result.get('title', 'New article'))

            # Sync to Google Drive if configured
            gdrive_link = await self._sync_to_gdrive(
                content=markdown_content,
                category=result.get('category', 'articles'),
                filename=f"{item.id}.md"
            )

            gdrive_info = f"\n☁️ Google Drive: 已同步" if gdrive_link else ""
            fetcher_info = f"\n🔧 抓取方式: {result.get('fetcher', 'unknown')}"

            # Escape special characters for Telegram markdown
            safe_title = self._safe_markdown_text(result.get('title', 'Untitled'), 100)
            safe_summary = self._safe_markdown_text(result.get('summary', '无摘要'), 300)
            safe_tags = ', '.join(result.get('tags', [])[:5]) or '无'

            response = f"""✅ 文章已保存

📌 {safe_title}

📝 摘要:
{safe_summary}

📁 分类: {result.get('category', 'articles')}
🏷️ 标签: {safe_tags}{fetcher_info}{gdrive_info}

🔑 ID: {item.id}"""

            await status_msg.edit_text(response)

        except Exception as e:
            import traceback
            logger.error(f"Error processing URL: {e}")
            logger.error(traceback.format_exc())
            await status_msg.edit_text(f"❌ 抓取失败: {str(e)}")

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        if not self._is_authorized(update.effective_user.id):
            await update.message.reply_text("⛔ Unauthorized")
            return

        welcome = """🚀 Quick Capture Agent

我是你的知识捕获助手！发送以下内容给我：

📝 文字 - 直接粘贴文章或笔记
🔗 链接 - 网页URL，我会自动抓取
🖼️ 图片 - 截图、图表、信息图
📄 文件 - PDF、文档等

命令：
/search <关键词> - 搜索知识库
/get <ID> - 获取指定内容
/recent - 最近捕获
/stats - 查看统计

直接发送内容即可，我会自动处理并存入知识库！"""

        await update.message.reply_text(welcome)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command."""
        if not self._is_authorized(update.effective_user.id):
            return

        help_text = """📖 使用帮助

内容类型支持：
• 文章链接 → 自动抓取、总结、分类
• 纯文本 → 识别类型、提取要点
• 图片 → OCR + 视觉分析
• 文件 → 解析并提取内容

常用命令：
/search <关键词> - 搜索知识库
/get <ID> - 获取指定ID的内容
/recent - 查看最近捕获
/stats - 查看统计信息

提示：
• 发送图片时可以添加说明文字
• 转发的消息会保留来源信息
• 知乎、微信等受限网站会自动使用Jina Reader"""

        await update.message.reply_text(help_text)

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle text messages."""
        if not self._is_authorized(update.effective_user.id):
            return

        message = update.message
        text = message.text

        # Check if text contains URL - if so, process as URL
        import re
        url_pattern = r'https?://[^\s]+'
        urls = re.findall(url_pattern, text)
        if urls:
            # Redirect to URL handler
            logger.info(f"Detected URL in text: {urls[0]}")
            await self._process_url_message(message, urls[0])
            return

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
                category=self._safe_category(result.get("category", "uncategorized")),
                tags=result.get("tags", []),
                metadata={
                    "telegram_message_id": message.message_id,
                    "telegram_user_id": message.from_user.id,
                    "content_type": result.get("type"),
                    "processed_at": datetime.now().isoformat(),
                }
            )

            # Sync to git if configured
            await self._sync_to_git(result.get('title', 'New note'))

            # Sync to Google Drive if configured
            gdrive_link = await self._sync_to_gdrive(
                content=markdown_content,
                category=result.get('category', 'notes'),
                filename=f"{item.id}.md"
            )

            # Send confirmation (plain text to avoid markdown issues)
            gdrive_info = f"\n☁️ Google Drive: 已同步" if gdrive_link else ""
            safe_title = self._safe_markdown_text(result.get('title', 'Untitled'), 80)
            safe_summary = self._safe_markdown_text(result.get('summary', '无摘要'), 200)

            response = f"""✅ 已保存到知识库

📌 标题: {safe_title}
📁 分类: {result.get('category', 'uncategorized')}
🏷️ 标签: {', '.join(result.get('tags', [])) or '无'}{gdrive_info}

📝 摘要:
{safe_summary}

🔑 ID: {item.id}"""

            await status_msg.edit_text(response)

        except Exception as e:
            logger.error(f"Error processing text: {e}")
            await status_msg.edit_text(f"❌ 处理失败: {str(e)}")

    async def handle_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle URL messages (triggered by filters.Entity('url'))."""
        if not self._is_authorized(update.effective_user.id):
            return

        message = update.message
        # Extract URL from message entities
        import re
        urls = []

        # Try from entities first
        if message.entities:
            for entity in message.entities:
                if entity.type == "url":
                    # Extract URL from text using entity offset and length
                    url = message.text[entity.offset:entity.offset + entity.length]
                    urls.append(url)

        # Fallback: find URL in text with regex
        if not urls:
            urls = re.findall(r'https?://[^\s]+', message.text)

        if not urls:
            await message.reply_text("❌ 未找到有效链接")
            return

        logger.info(f"handle_url: found URL {urls[0]}")
        await self._process_url_message(message, urls[0])

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle photo messages."""
        if not self._is_authorized(update.effective_user.id):
            return

        message = update.message
        status_msg = None

        try:
            status_msg = await message.reply_text("🔄 分析图片中...")

            # Get the largest photo
            photo = message.photo[-1]
            logger.info(f"Processing photo: {photo.file_id}")

            file = await context.bot.get_file(photo.file_id)

            # Download to temp location
            temp_path = Path(f"/tmp/tg_photo_{photo.file_id}.jpg")
            await file.download_to_drive(temp_path)
            logger.info(f"Downloaded photo to: {temp_path}")

            # Get caption if any
            caption = message.caption or ""

            # Process the image
            result = await self.processor.process_image(temp_path, caption)
            logger.info(f"Processed image, category: {result.get('category')}")

            markdown_content = self.markdown_gen.generate(result)

            # Save image to knowledge base attachments
            attachment_path = self.knowledge_base.base_path / "_attachments"
            attachment_path.mkdir(exist_ok=True, parents=True)
            final_image_path = attachment_path / f"{result.get('id', photo.file_id)}.jpg"
            # Use shutil.move instead of rename for cross-filesystem support
            import shutil
            shutil.move(str(temp_path), str(final_image_path))
            logger.info(f"Saved image to: {final_image_path}")

            item = self.knowledge_base.add(
                title=result.get("title", "Image Capture"),
                content=markdown_content,
                source="telegram_photo",
                category=self._safe_category(result.get("category", "visualizations")),
                tags=result.get("tags", []),
                metadata={
                    "image_path": str(final_image_path),
                    "has_ocr": result.get("has_text", False),
                }
            )
            logger.info(f"Added to knowledge base: {item.id}")

            # Sync to git if configured
            await self._sync_to_git(result.get('title', 'New image'))

            # Sync to Google Drive if configured (with image)
            gdrive_link = await self._sync_to_gdrive(
                content=markdown_content,
                category=result.get('category', 'visualizations'),
                filename=f"{item.id}.md",
                image_path=final_image_path
            )

            gdrive_info = f"\n☁️ Google Drive: 已同步" if gdrive_link else ""
            safe_title = self._safe_markdown_text(result.get('title', 'Image'), 80)
            safe_desc = self._safe_markdown_text(result.get('description', '无描述'), 200)
            extracted = result.get('extracted_text', '')
            ocr_info = f"\n📄 提取的文字: {self._safe_markdown_text(extracted, 100)}" if extracted else ""

            response = f"""✅ 图片已分析并保存

📌 {safe_title}
📁 分类: {result.get('category', 'visualizations')}{gdrive_info}

📝 内容识别:
{safe_desc}{ocr_info}

🔑 ID: {item.id}"""

            await status_msg.edit_text(response)

        except Exception as e:
            import traceback
            logger.error(f"Error processing photo: {e}")
            logger.error(traceback.format_exc())
            error_msg = f"❌ 图片处理失败: {str(e)}"
            if status_msg:
                await status_msg.edit_text(error_msg)
            else:
                await message.reply_text(error_msg)

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
                category=self._safe_category(result.get("category", "documents")),
                tags=result.get("tags", []),
            )

            # Sync to git if configured
            await self._sync_to_git(result.get('title', doc.file_name))

            # Sync to Google Drive if configured
            gdrive_link = await self._sync_to_gdrive(
                content=markdown_content,
                category=result.get('category', 'documents'),
                filename=f"{item.id}.md"
            )

            gdrive_info = f"\n☁️ Google Drive: 已同步" if gdrive_link else ""
            safe_filename = self._safe_markdown_text(doc.file_name, 50)
            safe_summary = self._safe_markdown_text(result.get('summary', '无摘要'), 300)

            response = f"""✅ 文档已处理

📄 {safe_filename}
📁 分类: {result.get('category', 'documents')}{gdrive_info}

📝 摘要:
{safe_summary}

🔑 ID: {item.id}"""

            await status_msg.edit_text(response)

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

        response = "📋 最近捕获\n\n"
        for item in recent:
            safe_title = self._safe_markdown_text(item.title[:40], 50)
            response += f"📌 {safe_title}\n"
            response += f"   {item.created_at[:10]} | {item.category.value}\n"
            response += f"   🔑 {item.id}\n\n"

        await update.message.reply_text(response)

    async def get_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /get <id> command to retrieve stored content."""
        if not self._is_authorized(update.effective_user.id):
            return

        if not context.args:
            await update.message.reply_text("用法: /get <ID>\n\n例如: /get 20260108163615-adc280b4")
            return

        item_id = context.args[0]
        item = self.knowledge_base.get(item_id)

        if not item:
            await update.message.reply_text(f"❌ 未找到 ID: {item_id}\n\n使用 /search 或 /recent 查看可用内容")
            return

        # Format the content for display
        safe_title = self._safe_markdown_text(item.title, 100)
        safe_content = item.content[:2000] if len(item.content) > 2000 else item.content
        tags_str = ', '.join(item.tags) if item.tags else '无'

        response = f"""📄 内容详情

🔑 ID: {item.id}
📌 标题: {safe_title}
📁 分类: {item.category.value}
🏷️ 标签: {tags_str}
🔗 来源: {item.source or '无'}
📅 创建: {item.created_at[:19]}

📝 内容:
{safe_content}"""

        # Telegram has a 4096 character limit
        if len(response) > 4000:
            response = response[:3997] + "..."

        await update.message.reply_text(response)

    async def test_gdrive_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /test_gdrive command to test Google Drive integration."""
        try:
            if not self._is_authorized(update.effective_user.id):
                return

            await update.message.reply_text("🔄 测试 Google Drive 连接...")

            # Check environment variables first
            import os
            has_creds = bool(os.getenv("GOOGLE_CREDENTIALS_JSON") or os.getenv("GOOGLE_CREDENTIALS_PATH"))
            folder_id = os.getenv("GDRIVE_FOLDER_ID", "未设置")

            if not has_creds:
                await update.message.reply_text(
                    "❌ Google Drive 凭证未配置\n\n"
                    "请在 Railway 设置环境变量:\n"
                    "• GOOGLE_CREDENTIALS_JSON = {整个JSON内容}\n"
                    "• GDRIVE_FOLDER_ID = 文件夹ID (可选)"
                )
                return

            # Try to get gdrive sync
            gdrive = get_gdrive_sync()

            if not gdrive:
                await update.message.reply_text(
                    f"❌ Google Drive 初始化失败\n\n"
                    f"凭证已设置: ✅\n"
                    f"Folder ID: {folder_id}\n\n"
                    f"可能原因:\n"
                    f"• google-api-python-client 未安装\n"
                    f"• 凭证JSON格式错误"
                )
                return

            # Test upload
            test_content = f"""# Google Drive 测试

测试时间: {datetime.now().isoformat()}

如果你能在 Google Drive 看到这个文件，说明集成成功！✅
"""
            result = await gdrive.upload_content(
                content=test_content,
                remote_path="test/connection_test.md"
            )

            response = f"""✅ Google Drive 测试成功!

📄 文件已上传: test/connection_test.md
🔗 链接: {result.get('webViewLink', '无')}

请检查你的 Google Drive 文件夹。"""

            await update.message.reply_text(response)

        except Exception as e:
            import traceback
            logger.error(f"test_gdrive error: {traceback.format_exc()}")
            await update.message.reply_text(f"❌ 测试失败: {str(e)}")

    def run(self) -> None:
        """Start the bot."""
        self.app = Application.builder().token(self.token).build()

        # Command handlers
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("search", self.search_command))
        self.app.add_handler(CommandHandler("stats", self.stats_command))
        self.app.add_handler(CommandHandler("recent", self.recent_command))
        self.app.add_handler(CommandHandler("get", self.get_command))
        self.app.add_handler(CommandHandler("test_gdrive", self.test_gdrive_command))

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
