"""
Interfaces module - Various input interfaces for content capture.
"""

from quick_capture_agent.interfaces.telegram_bot import TelegramBot
from quick_capture_agent.interfaces.webhook_server import WebhookServer

__all__ = ["TelegramBot", "WebhookServer"]
