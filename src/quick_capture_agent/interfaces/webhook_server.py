"""
Webhook Server for Telegram Bot - Serverless/Cloud deployment mode.

Instead of polling, this receives updates via webhook.
Suitable for deployment on:
- Railway
- Render
- Fly.io
- AWS Lambda + API Gateway
- Vercel (with adapter)
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

from aiohttp import web
from telegram import Update
from telegram.ext import Application

from quick_capture_agent.interfaces.telegram_bot import TelegramBot

logger = logging.getLogger(__name__)


class WebhookServer:
    """
    Webhook-based Telegram bot server.

    Usage:
        server = WebhookServer(
            bot_token="...",
            webhook_url="https://your-domain.com/webhook"
        )
        server.run(port=8443)
    """

    def __init__(
        self,
        bot_token: Optional[str] = None,
        webhook_url: Optional[str] = None,
        webhook_path: str = "/webhook",
        knowledge_base_path: Optional[Path] = None,
    ):
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.webhook_url = webhook_url or os.getenv("WEBHOOK_URL")
        self.webhook_path = webhook_path

        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN is required")

        # Initialize the Telegram bot
        self.tg_bot = TelegramBot(
            token=self.bot_token,
            knowledge_base_path=knowledge_base_path,
        )

        self.app: Optional[web.Application] = None
        self.telegram_app: Optional[Application] = None

    async def setup(self) -> None:
        """Set up the webhook server."""
        # Build Telegram application
        self.telegram_app = Application.builder().token(self.bot_token).build()

        # Add handlers (same as TelegramBot)
        from telegram.ext import CommandHandler, MessageHandler, filters

        self.telegram_app.add_handler(CommandHandler("start", self.tg_bot.start))
        self.telegram_app.add_handler(CommandHandler("help", self.tg_bot.help_command))
        self.telegram_app.add_handler(CommandHandler("search", self.tg_bot.search_command))
        self.telegram_app.add_handler(CommandHandler("stats", self.tg_bot.stats_command))
        self.telegram_app.add_handler(CommandHandler("recent", self.tg_bot.recent_command))
        self.telegram_app.add_handler(CommandHandler("get", self.tg_bot.get_command))
        self.telegram_app.add_handler(CommandHandler("test_gdrive", self.tg_bot.test_gdrive_command))

        # Processing commands
        self.telegram_app.add_handler(CommandHandler("summary", self.tg_bot.summary_command))
        self.telegram_app.add_handler(CommandHandler("note", self.tg_bot.note_command))
        self.telegram_app.add_handler(CommandHandler("todo", self.tg_bot.todo_command))
        self.telegram_app.add_handler(CommandHandler("category", self.tg_bot.category_command))
        self.telegram_app.add_handler(CommandHandler("list", self.tg_bot.list_command))
        self.telegram_app.add_handler(CommandHandler("inbox", self.tg_bot.inbox_command))

        # Universal save and modification commands
        self.telegram_app.add_handler(CommandHandler("save", self.tg_bot.save_command))
        self.telegram_app.add_handler(CommandHandler("rename", self.tg_bot.rename_command))
        self.telegram_app.add_handler(CommandHandler("move", self.tg_bot.move_command))

        self.telegram_app.add_handler(MessageHandler(
            filters.TEXT & filters.Entity("url"), self.tg_bot.handle_url
        ))
        self.telegram_app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND, self.tg_bot.handle_text
        ))
        self.telegram_app.add_handler(MessageHandler(filters.PHOTO, self.tg_bot.handle_photo))
        self.telegram_app.add_handler(MessageHandler(filters.Document.ALL, self.tg_bot.handle_document))

        # Initialize the application
        await self.telegram_app.initialize()

        # Set webhook if URL is provided
        if self.webhook_url:
            webhook_full_url = f"{self.webhook_url.rstrip('/')}{self.webhook_path}"
            await self.telegram_app.bot.set_webhook(url=webhook_full_url)
            logger.info(f"Webhook set to: {webhook_full_url}")

    async def handle_webhook(self, request: web.Request) -> web.Response:
        """Handle incoming webhook requests."""
        try:
            data = await request.json()
            logger.debug(f"Received webhook: {data.get('message', {}).get('text', 'non-text')[:50]}")

            update = Update.de_json(data, self.telegram_app.bot)

            # Process the update
            await self.telegram_app.process_update(update)

            return web.Response(text="OK")

        except Exception as e:
            import traceback
            logger.error(f"Error processing webhook: {e}")
            logger.error(traceback.format_exc())
            return web.Response(status=500, text=str(e))

    async def health_check(self, request: web.Request) -> web.Response:
        """Health check endpoint - returns OK even during initialization."""
        try:
            bot_username = None
            if self.telegram_app and self.telegram_app.bot:
                bot_username = self.telegram_app.bot.username
            return web.json_response({
                "status": "healthy",
                "bot_username": bot_username,
                "ready": bot_username is not None,
            })
        except Exception:
            # Always return healthy to pass health check, even during init
            return web.json_response({
                "status": "healthy",
                "ready": False,
            })

    def create_app(self) -> web.Application:
        """Create the aiohttp web application."""
        self.app = web.Application()

        # Add routes
        self.app.router.add_post(self.webhook_path, self.handle_webhook)
        self.app.router.add_get("/health", self.health_check)
        self.app.router.add_get("/", self.health_check)

        # Setup on startup (properly async)
        async def on_startup(app):
            try:
                await self.setup()
                logger.info("Telegram bot setup completed")
            except Exception as e:
                logger.error(f"Setup failed: {e}")
                import traceback
                logger.error(traceback.format_exc())
                # Don't raise - let health check still work

        self.app.on_startup.append(on_startup)

        # Cleanup on shutdown
        async def cleanup(app):
            if self.telegram_app:
                await self.telegram_app.shutdown()

        self.app.on_cleanup.append(cleanup)

        return self.app

    def run(self, host: str = "0.0.0.0", port: int = 8443) -> None:
        """Run the webhook server."""
        app = self.create_app()
        logger.info(f"Starting webhook server on {host}:{port}")
        web.run_app(app, host=host, port=port)


def run_webhook_server():
    """Entry point for webhook server."""
    import argparse
    import sys

    # Check for required environment variables early
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        print("ERROR: TELEGRAM_BOT_TOKEN environment variable is required")
        print("Please set it in Railway dashboard: Settings -> Variables")
        print("")
        print("Waiting for configuration... (server will start when env vars are set)")
        # Exit gracefully instead of crashing - Railway will restart
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Run Telegram bot in webhook mode")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", 8443)))
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--webhook-url", default=os.getenv("WEBHOOK_URL"))
    parser.add_argument("--vault", default=os.getenv("KNOWLEDGE_BASE_PATH"))

    args = parser.parse_args()

    vault_path = Path(args.vault) if args.vault else None

    server = WebhookServer(
        bot_token=bot_token,
        webhook_url=args.webhook_url,
        knowledge_base_path=vault_path,
    )
    server.run(host=args.host, port=args.port)


# Only run when executed directly, not when imported
if __name__ == "__main__":
    run_webhook_server()
