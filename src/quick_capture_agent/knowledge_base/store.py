"""
Knowledge Base storage system for persisting collected content and knowledge.

Supports Google Drive sync for persistent storage across container restarts.
"""

import json
import hashlib
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Iterator
from dataclasses import dataclass, field, asdict
from enum import Enum
import shutil

logger = logging.getLogger(__name__)


class ContentCategory(str, Enum):
    """Knowledge base categories for organizing content by knowledge domain."""

    # Primary knowledge categories
    THINKING = "thinking"          # 思维方法：思维模型、决策框架、认知偏差
    TECHNOLOGY = "technology"      # 技术：AI、编程、工具、产品
    BUSINESS = "business"          # 商业：创业、管理、营销、战略
    GROWTH = "growth"              # 个人成长：学习、效率、习惯、职业
    PHILOSOPHY = "philosophy"      # 哲学心理：哲学、心理学、认知科学
    CREATIVE = "creative"          # 创意设计：设计、写作、艺术
    FINANCE = "finance"            # 财务投资：投资、理财、经济
    WELLNESS = "wellness"          # 健康生活：健康、运动、生活方式
    INBOX = "inbox"                # 收件箱：待分类

    @classmethod
    def get_description(cls, category: "ContentCategory") -> str:
        """Get Chinese description for category."""
        descriptions = {
            cls.THINKING: "思维方法",
            cls.TECHNOLOGY: "技术",
            cls.BUSINESS: "商业",
            cls.GROWTH: "个人成长",
            cls.PHILOSOPHY: "哲学心理",
            cls.CREATIVE: "创意设计",
            cls.FINANCE: "财务投资",
            cls.WELLNESS: "健康生活",
            cls.INBOX: "收件箱",
        }
        return descriptions.get(category, "未知")


@dataclass
class KnowledgeItem:
    """A single item in the knowledge base."""

    id: str
    title: str
    content: str
    source: str
    category: ContentCategory
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        data = asdict(self)
        data["category"] = self.category.value
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "KnowledgeItem":
        """Create from dictionary."""
        if "category" in data:
            # Migrate old categories to new knowledge-based categories
            old_to_new = {
                "articles": "inbox",
                "documents": "inbox",
                "visualizations": "inbox",
                "notes": "inbox",
                "uncategorized": "inbox",
                "concepts": "thinking",
                "tech": "technology",
                "ai": "technology",
                "productivity": "growth",
            }
            category_str = data["category"]
            if category_str in old_to_new:
                category_str = old_to_new[category_str]
            try:
                data["category"] = ContentCategory(category_str)
            except ValueError:
                # Default to INBOX for any unknown category
                data["category"] = ContentCategory.INBOX
        return cls(**data)

    def matches_query(self, query: str) -> bool:
        """Check if this item matches a search query."""
        query_lower = query.lower()
        return (
            query_lower in self.title.lower()
            or query_lower in self.content.lower()
            or any(query_lower in tag.lower() for tag in self.tags)
        )


class KnowledgeBase:
    """
    Persistent knowledge base for storing and retrieving collected content.

    Features:
    - Category-based organization
    - Tag-based search
    - Full-text search
    - JSON file storage
    - Automatic indexing
    - Google Drive sync for persistence
    """

    def __init__(self, base_path: Optional[Path] = None, enable_gdrive_sync: bool = True):
        self.base_path = base_path or Path("./data/knowledge")
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.index_path = self.base_path / "_index.json"
        self._index: dict = {}
        self._gdrive_sync = None
        self._enable_gdrive_sync = enable_gdrive_sync
        self._load_index()

    @property
    def gdrive_sync(self):
        """Lazy load Google Drive sync."""
        if self._gdrive_sync is None and self._enable_gdrive_sync:
            try:
                from quick_capture_agent.knowledge_base.gdrive_sync import get_gdrive_sync
                self._gdrive_sync = get_gdrive_sync()
            except Exception as e:
                logger.debug(f"Google Drive sync not available: {e}")
        return self._gdrive_sync

    def _load_index_from_gdrive(self) -> Optional[dict]:
        """Try to load index from Google Drive."""
        if not self.gdrive_sync:
            return None

        try:
            # Download _index.json from Google Drive
            import io
            query = "name='_index.json' and trashed=false"
            if self.gdrive_sync.folder_id:
                query += f" and '{self.gdrive_sync.folder_id}' in parents"

            results = self.gdrive_sync.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name, modifiedTime)'
            ).execute()

            files = results.get('files', [])
            if files:
                file_id = files[0]['id']
                request = self.gdrive_sync.service.files().get_media(fileId=file_id)
                content = request.execute()
                index_data = json.loads(content.decode('utf-8'))
                logger.info(f"Loaded index from Google Drive: {len(index_data.get('items', {}))} items")
                return index_data
        except Exception as e:
            logger.warning(f"Failed to load index from Google Drive: {e}")

        return None

    def _save_index_to_gdrive(self) -> None:
        """Save index to Google Drive."""
        if not self.gdrive_sync:
            return

        try:
            index_json = json.dumps(self._index, indent=2, ensure_ascii=False)
            self.gdrive_sync.upload_content_sync(
                content=index_json,
                remote_path="_index.json",
                mime_type="application/json"
            )
            logger.debug("Index synced to Google Drive")
        except Exception as e:
            logger.warning(f"Failed to sync index to Google Drive: {e}")

    def _load_index(self) -> None:
        """Load the index from disk or Google Drive."""
        # First try local
        if self.index_path.exists():
            with open(self.index_path, "r", encoding="utf-8") as f:
                self._index = json.load(f)
                logger.info(f"Loaded local index: {len(self._index.get('items', {}))} items")
                # Also restore items from Google Drive if they don't exist locally
                self._restore_items_from_gdrive()
                return

        # Try Google Drive if local doesn't exist
        gdrive_index = self._load_index_from_gdrive()
        if gdrive_index:
            self._index = gdrive_index
            # Save locally for faster access
            with open(self.index_path, "w", encoding="utf-8") as f:
                json.dump(self._index, f, indent=2, ensure_ascii=False)
            # Restore item files from Google Drive
            self._restore_items_from_gdrive()
            return

        # Create new index
        self._index = {
            "items": {},
            "tags": {},
            "categories": {},
            "created_at": datetime.now().isoformat(),
        }
        self._save_index()

    def _save_index(self) -> None:
        """Save the index to disk and Google Drive."""
        self._index["updated_at"] = datetime.now().isoformat()

        # Save locally
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump(self._index, f, indent=2, ensure_ascii=False)

        # Sync to Google Drive
        self._save_index_to_gdrive()

    def _restore_items_from_gdrive(self) -> None:
        """Restore item JSON files from Google Drive."""
        if not self.gdrive_sync:
            return

        try:
            restored = self.gdrive_sync.restore_items_from_gdrive(self.base_path)
            if restored > 0:
                logger.info(f"Restored {restored} item files from Google Drive")
        except Exception as e:
            logger.warning(f"Failed to restore items from Google Drive: {e}")

    def _save_item_to_gdrive(self, item: "KnowledgeItem") -> None:
        """Save a single item JSON to Google Drive."""
        if not self.gdrive_sync:
            return

        try:
            item_json = json.dumps(item.to_dict(), indent=2, ensure_ascii=False)
            remote_path = f"_data/{item.category.value}/{item.id}.json"
            self.gdrive_sync.upload_content_sync(
                content=item_json,
                remote_path=remote_path,
                mime_type="application/json"
            )
            logger.debug(f"Item synced to Google Drive: {item.id}")
        except Exception as e:
            logger.warning(f"Failed to sync item to Google Drive: {e}")

    def _generate_id(self, content: str) -> str:
        """Generate a unique ID for content."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
        return f"{timestamp}-{content_hash}"

    def _get_item_path(self, item_id: str, category: ContentCategory) -> Path:
        """Get the file path for an item."""
        category_dir = self.base_path / category.value
        category_dir.mkdir(parents=True, exist_ok=True)
        return category_dir / f"{item_id}.json"

    def add(
        self,
        title: str,
        content: str,
        source: str = "",
        category: ContentCategory = ContentCategory.INBOX,
        tags: list[str] = None,
        metadata: dict = None,
    ) -> KnowledgeItem:
        """
        Add a new item to the knowledge base.

        Args:
            title: Title of the item
            content: Main content
            source: Source URL or path
            category: Category for organization
            tags: List of tags
            metadata: Additional metadata

        Returns:
            The created KnowledgeItem
        """
        item_id = self._generate_id(content)
        item = KnowledgeItem(
            id=item_id,
            title=title,
            content=content,
            source=source,
            category=category,
            tags=tags or [],
            metadata=metadata or {},
        )

        # Save item
        item_path = self._get_item_path(item_id, category)
        with open(item_path, "w", encoding="utf-8") as f:
            json.dump(item.to_dict(), f, indent=2, ensure_ascii=False)

        # Update index
        self._index["items"][item_id] = {
            "title": title,
            "category": category.value,
            "tags": tags or [],
            "path": str(item_path.relative_to(self.base_path)),
            "created_at": item.created_at,
        }

        # Update tag index
        for tag in tags or []:
            if tag not in self._index["tags"]:
                self._index["tags"][tag] = []
            self._index["tags"][tag].append(item_id)

        # Update category index
        if category.value not in self._index["categories"]:
            self._index["categories"][category.value] = []
        self._index["categories"][category.value].append(item_id)

        self._save_index()

        # Sync item to Google Drive for persistence
        self._save_item_to_gdrive(item)

        return item

    def get(self, item_id: str) -> Optional[KnowledgeItem]:
        """Get an item by ID."""
        if item_id not in self._index["items"]:
            return None

        item_info = self._index["items"][item_id]
        item_path = self.base_path / item_info["path"]

        if not item_path.exists():
            return None

        with open(item_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return KnowledgeItem.from_dict(data)

    def update(self, item_id: str, **updates) -> Optional[KnowledgeItem]:
        """Update an existing item."""
        item = self.get(item_id)
        if not item:
            return None

        # Apply updates
        for key, value in updates.items():
            if hasattr(item, key):
                setattr(item, key, value)
        item.updated_at = datetime.now().isoformat()

        # Save updated item
        item_path = self._get_item_path(item_id, item.category)
        with open(item_path, "w", encoding="utf-8") as f:
            json.dump(item.to_dict(), f, indent=2, ensure_ascii=False)

        # Update index
        self._index["items"][item_id]["title"] = item.title
        self._index["items"][item_id]["tags"] = item.tags
        self._save_index()

        # Sync updated item to Google Drive
        self._save_item_to_gdrive(item)

        return item

    def delete(self, item_id: str) -> bool:
        """Delete an item from the knowledge base."""
        if item_id not in self._index["items"]:
            return False

        item_info = self._index["items"][item_id]
        item_path = self.base_path / item_info["path"]

        # Delete file
        if item_path.exists():
            item_path.unlink()

        # Remove from indexes
        del self._index["items"][item_id]

        # Remove from tag index
        for tag, ids in self._index["tags"].items():
            if item_id in ids:
                ids.remove(item_id)

        # Remove from category index
        category = item_info["category"]
        if category in self._index["categories"]:
            if item_id in self._index["categories"][category]:
                self._index["categories"][category].remove(item_id)

        self._save_index()
        return True

    def search(
        self,
        query: str = "",
        category: Optional[ContentCategory] = None,
        tags: list[str] = None,
        limit: int = 50,
    ) -> list[KnowledgeItem]:
        """
        Search the knowledge base.

        Args:
            query: Text to search for
            category: Filter by category
            tags: Filter by tags (items must have all specified tags)
            limit: Maximum number of results

        Returns:
            List of matching KnowledgeItems
        """
        results = []

        # Filter by category first if specified
        if category:
            item_ids = self._index["categories"].get(category.value, [])
        else:
            item_ids = list(self._index["items"].keys())

        # Filter by tags
        if tags:
            for tag in tags:
                tag_ids = set(self._index["tags"].get(tag, []))
                item_ids = [id for id in item_ids if id in tag_ids]

        # Search through filtered items
        for item_id in item_ids[:limit * 2]:  # Get more to account for query filtering
            item = self.get(item_id)
            if item:
                if not query or item.matches_query(query):
                    results.append(item)
                    if len(results) >= limit:
                        break

        return results

    def list_by_category(self, category: ContentCategory) -> list[KnowledgeItem]:
        """List all items in a category."""
        return self.search(category=category)

    def list_by_tag(self, tag: str) -> list[KnowledgeItem]:
        """List all items with a specific tag."""
        return self.search(tags=[tag])

    def get_all_tags(self) -> list[str]:
        """Get all tags in the knowledge base."""
        return list(self._index["tags"].keys())

    def get_all_categories(self) -> list[str]:
        """Get all categories that have items."""
        return [cat for cat, ids in self._index["categories"].items() if ids]

    def get_stats(self) -> dict:
        """Get statistics about the knowledge base."""
        return {
            "total_items": len(self._index["items"]),
            "categories": {
                cat: len(ids) for cat, ids in self._index["categories"].items() if ids
            },
            "total_tags": len(self._index["tags"]),
            "created_at": self._index.get("created_at"),
            "updated_at": self._index.get("updated_at"),
        }

    def export(self, output_path: Path) -> None:
        """Export the entire knowledge base to a directory."""
        shutil.copytree(self.base_path, output_path, dirs_exist_ok=True)

    def iter_all(self) -> Iterator[KnowledgeItem]:
        """Iterate through all items in the knowledge base."""
        for item_id in self._index["items"]:
            item = self.get(item_id)
            if item:
                yield item
