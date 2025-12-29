"""
Knowledge Base module - Persistent storage for collected content and knowledge.
"""

from quick_capture_agent.knowledge_base.store import KnowledgeBase, KnowledgeItem, ContentCategory
from quick_capture_agent.knowledge_base.obsidian import ObsidianVault
from quick_capture_agent.knowledge_base.git_sync import GitSync, get_git_sync

__all__ = [
    "KnowledgeBase",
    "KnowledgeItem",
    "ContentCategory",
    "ObsidianVault",
    "GitSync",
    "get_git_sync",
]
