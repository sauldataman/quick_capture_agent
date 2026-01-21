"""
Obsidian Integration - Manages an Obsidian-compatible vault structure.

Features:
- Obsidian vault initialization
- Markdown file management
- Wikilink support
- Daily notes
- Folder organization
- Git sync support
"""

import json
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, Iterator
import shutil

from quick_capture_agent.processors.markdown_generator import MarkdownGenerator


class ObsidianVault:
    """
    Manages an Obsidian-compatible vault for knowledge storage.

    Directory structure:
    vault/
    ├── _attachments/      # Images and files
    ├── _templates/        # Note templates
    ├── Articles/          # Web articles
    ├── Concepts/          # Concept definitions
    ├── AI-Summaries/      # AI-generated content
    ├── Visualizations/    # Charts, diagrams
    ├── Notes/             # Quick notes
    ├── Daily/             # Daily notes
    └── _index.md          # Main index
    """

    # Category to folder mapping (knowledge-based categories)
    CATEGORY_FOLDERS = {
        "thinking": "Thinking",        # 思维方法
        "technology": "Technology",    # 技术
        "business": "Business",        # 商业
        "growth": "Growth",            # 个人成长
        "philosophy": "Philosophy",    # 哲学心理
        "creative": "Creative",        # 创意设计
        "finance": "Finance",          # 财务投资
        "wellness": "Wellness",        # 健康生活
        "inbox": "Inbox",              # 收件箱
        # Legacy mappings for backward compatibility
        "articles": "Inbox",
        "documents": "Inbox",
        "visualizations": "Inbox",
        "notes": "Inbox",
        "uncategorized": "Inbox",
    }

    def __init__(self, vault_path: Path):
        self.vault_path = Path(vault_path)
        self.md_generator = MarkdownGenerator()
        self._ensure_structure()

    def _ensure_structure(self) -> None:
        """Ensure the vault has the correct directory structure."""
        # Create main directories
        directories = [
            "_attachments",
            "_templates",
            "Articles",
            "Articles/Tech",
            "Articles/AI",
            "Articles/Business",
            "Concepts",
            "AI-Summaries",
            "Visualizations",
            "Notes",
            "Documents",
            "Daily",
            "Inbox",
        ]

        for dir_name in directories:
            (self.vault_path / dir_name).mkdir(parents=True, exist_ok=True)

        # Create .obsidian config if not exists
        obsidian_dir = self.vault_path / ".obsidian"
        if not obsidian_dir.exists():
            obsidian_dir.mkdir()
            self._create_obsidian_config(obsidian_dir)

        # Create index if not exists
        index_path = self.vault_path / "_index.md"
        if not index_path.exists():
            self._create_index()

    def _create_obsidian_config(self, obsidian_dir: Path) -> None:
        """Create basic Obsidian configuration."""
        # app.json - basic settings
        app_config = {
            "alwaysUpdateLinks": True,
            "newFileLocation": "folder",
            "newFileFolderPath": "Inbox",
            "attachmentFolderPath": "_attachments",
        }
        (obsidian_dir / "app.json").write_text(json.dumps(app_config, indent=2))

        # appearance.json
        appearance = {"theme": "system"}
        (obsidian_dir / "appearance.json").write_text(json.dumps(appearance, indent=2))

    def _create_index(self) -> None:
        """Create the main index file."""
        index_content = """# 📚 知识库

欢迎来到你的知识库！

## 📁 目录结构

- [[Articles/|📰 文章]]
- [[Concepts/|💡 概念]]
- [[AI-Summaries/|🤖 AI 总结]]
- [[Visualizations/|📊 可视化]]
- [[Notes/|📝 笔记]]
- [[Daily/|📅 每日笔记]]
- [[Inbox/|📥 收件箱]]

## 🔍 快速访问

### 最近添加
<!-- 这里会自动更新最近添加的内容 -->

### 常用标签
#ai #tech #productivity #concept

---
*使用 Quick Capture Agent 管理*
"""
        (self.vault_path / "_index.md").write_text(index_content)

    def _get_folder_for_category(self, category: str) -> Path:
        """Get the folder path for a category."""
        folder_name = self.CATEGORY_FOLDERS.get(category.lower(), "Inbox")
        return self.vault_path / folder_name

    def _sanitize_filename(self, name: str) -> str:
        """Sanitize a string for use as filename."""
        # Remove or replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            name = name.replace(char, '_')
        # Limit length
        if len(name) > 100:
            name = name[:100]
        return name.strip()

    def save(
        self,
        content_data: dict,
        filename: Optional[str] = None,
    ) -> Path:
        """
        Save content to the vault.

        Args:
            content_data: Processed content data
            filename: Optional custom filename

        Returns:
            Path to the saved file
        """
        # Generate markdown
        markdown = self.md_generator.generate(content_data)

        # Determine folder
        category = content_data.get("category", "uncategorized")
        folder = self._get_folder_for_category(category)
        folder.mkdir(parents=True, exist_ok=True)

        # Generate filename
        if not filename:
            title = content_data.get("title", "Untitled")
            content_id = content_data.get("id", datetime.now().strftime("%Y%m%d%H%M%S"))
            filename = f"{self._sanitize_filename(title)}-{content_id[:8]}.md"

        # Save file
        file_path = folder / filename
        file_path.write_text(markdown, encoding="utf-8")

        return file_path

    def save_attachment(self, source_path: Path, new_name: Optional[str] = None) -> Path:
        """
        Save an attachment (image, file) to the vault.

        Args:
            source_path: Path to the source file
            new_name: Optional new filename

        Returns:
            Path to the saved attachment
        """
        attachments_dir = self.vault_path / "_attachments"
        attachments_dir.mkdir(exist_ok=True)

        if new_name:
            dest_path = attachments_dir / new_name
        else:
            dest_path = attachments_dir / source_path.name

        shutil.copy2(source_path, dest_path)
        return dest_path

    def create_daily_note(self, date: Optional[str] = None) -> Path:
        """
        Create or get today's daily note.

        Args:
            date: Date string (YYYY-MM-DD), defaults to today

        Returns:
            Path to the daily note
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        daily_dir = self.vault_path / "Daily"
        daily_dir.mkdir(exist_ok=True)

        note_path = daily_dir / f"{date}.md"

        if not note_path.exists():
            content = f"""# 📅 {date}

## 📝 今日笔记



## 📥 今日捕获

<!-- 新捕获的内容会自动添加到这里 -->

## ✅ 待办事项

- [ ]

---
[[{self._prev_date(date)}|⬅️ 昨天]] | [[{self._next_date(date)}|明天 ➡️]]
"""
            note_path.write_text(content, encoding="utf-8")

        return note_path

    def _prev_date(self, date_str: str) -> str:
        from datetime import timedelta
        date = datetime.strptime(date_str, "%Y-%m-%d")
        return (date - timedelta(days=1)).strftime("%Y-%m-%d")

    def _next_date(self, date_str: str) -> str:
        from datetime import timedelta
        date = datetime.strptime(date_str, "%Y-%m-%d")
        return (date + timedelta(days=1)).strftime("%Y-%m-%d")

    def append_to_daily(self, content_data: dict, date: Optional[str] = None) -> None:
        """
        Append a capture reference to the daily note.

        Args:
            content_data: The captured content data
            date: Date string, defaults to today
        """
        note_path = self.create_daily_note(date)

        # Read current content
        current = note_path.read_text(encoding="utf-8")

        # Find the "今日捕获" section and append
        title = content_data.get("title", "Untitled")
        content_id = content_data.get("id", "")
        content_type = content_data.get("type", "note")
        time_str = datetime.now().strftime("%H:%M")

        new_entry = f"\n- {time_str} | [[{content_id}|{title}]] `{content_type}`"

        # Insert after "今日捕获" section marker
        marker = "<!-- 新捕获的内容会自动添加到这里 -->"
        if marker in current:
            current = current.replace(marker, marker + new_entry)
        else:
            # Fallback: append to end
            current += new_entry

        note_path.write_text(current, encoding="utf-8")

    def search(self, query: str, limit: int = 20) -> list[dict]:
        """
        Search the vault for content.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of matching file info
        """
        results = []
        query_lower = query.lower()

        for md_file in self.vault_path.rglob("*.md"):
            # Skip templates and hidden files
            if md_file.name.startswith("_") or ".obsidian" in str(md_file):
                continue

            try:
                content = md_file.read_text(encoding="utf-8")
                if query_lower in content.lower():
                    # Extract title from first heading or filename
                    lines = content.split("\n")
                    title = md_file.stem
                    for line in lines:
                        if line.startswith("# "):
                            title = line[2:].strip()
                            break

                    results.append({
                        "path": str(md_file),
                        "title": title,
                        "folder": md_file.parent.name,
                    })

                    if len(results) >= limit:
                        break
            except Exception:
                continue

        return results

    def get_stats(self) -> dict:
        """Get vault statistics."""
        stats = {
            "total_notes": 0,
            "categories": {},
            "attachments": 0,
        }

        # Count notes by category
        for folder in self.vault_path.iterdir():
            if folder.is_dir() and not folder.name.startswith("."):
                count = len(list(folder.rglob("*.md")))
                if count > 0:
                    stats["categories"][folder.name] = count
                    stats["total_notes"] += count

        # Count attachments
        attachments_dir = self.vault_path / "_attachments"
        if attachments_dir.exists():
            stats["attachments"] = len(list(attachments_dir.iterdir()))

        return stats

    def git_sync(self, message: Optional[str] = None) -> bool:
        """
        Sync vault with git (if initialized).

        Args:
            message: Commit message

        Returns:
            True if successful
        """
        git_dir = self.vault_path / ".git"
        if not git_dir.exists():
            return False

        try:
            if message is None:
                message = f"Auto-sync: {datetime.now().strftime('%Y-%m-%d %H:%M')}"

            subprocess.run(
                ["git", "add", "."],
                cwd=self.vault_path,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "commit", "-m", message],
                cwd=self.vault_path,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "push"],
                cwd=self.vault_path,
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError:
            return False

    def iter_notes(self) -> Iterator[Path]:
        """Iterate through all notes in the vault."""
        for md_file in self.vault_path.rglob("*.md"):
            if not md_file.name.startswith("_") and ".obsidian" not in str(md_file):
                yield md_file
