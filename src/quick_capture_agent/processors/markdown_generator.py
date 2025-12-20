"""
Markdown Generator - Creates formatted Markdown from processed content.

Generates Obsidian-compatible Markdown with:
- YAML frontmatter
- Consistent formatting
- Wikilinks for related content
- Tag support
"""

from datetime import datetime
from pathlib import Path
from typing import Optional


class MarkdownGenerator:
    """
    Generates formatted Markdown documents from processed content.

    Supports Obsidian-compatible format with:
    - YAML frontmatter for metadata
    - Consistent section structure
    - Wikilinks [[]] for internal links
    - Tag formatting #tag
    """

    def __init__(self, template_path: Optional[Path] = None):
        self.template_path = template_path
        self.templates = self._load_templates()

    def _load_templates(self) -> dict:
        """Load or define Markdown templates."""
        return {
            "default": self._default_template(),
            "article": self._article_template(),
            "concept": self._concept_template(),
            "ai_summary": self._ai_summary_template(),
            "visualization": self._visualization_template(),
            "note": self._note_template(),
        }

    def _default_template(self) -> str:
        return """---
title: "{title}"
source: "{source}"
type: {type}
category: {category}
tags: [{tags}]
created: {created}
---

# {title}

## 📋 摘要

{summary}

## 🎯 核心要点

{key_points}

## 📝 详细内容

{content}

## 💭 我的想法

<!-- 在这里添加你的思考和笔记 -->

---
*Captured via Quick Capture Agent*
"""

    def _article_template(self) -> str:
        return """---
title: "{title}"
source: "{source}"
type: article
category: {category}
tags: [{tags}]
created: {created}
author: "{author}"
---

# {title}

> 🔗 原文链接: {source}

## 📋 摘要

{summary}

## 🎯 核心要点

{key_points}

## 📝 文章内容

{content}

## 📚 相关阅读

<!-- 添加相关的 [[wikilinks]] -->

## 💭 我的想法

<!-- 在这里添加你的思考和笔记 -->

---
*Captured on {created}*
"""

    def _concept_template(self) -> str:
        return """---
title: "{title}"
source: "{source}"
type: concept
category: {category}
tags: [{tags}]
created: {created}
aliases: []
---

# {title}

## 📖 定义

{summary}

## 🔑 关键概念

{key_points}

## 📝 详细解释

{content}

## 🔗 相关概念

<!-- 使用 [[wikilinks]] 链接相关概念 -->

## 💡 应用场景

<!-- 这个概念可以应用在哪些场景？ -->

---
*Captured on {created}*
"""

    def _ai_summary_template(self) -> str:
        return """---
title: "{title}"
source: "{source}"
type: ai_summary
category: {category}
tags: [{tags}]
created: {created}
ai_generated: true
---

# {title}

> 🤖 AI 生成的总结

## 📋 摘要

{summary}

## 🎯 核心要点

{key_points}

## 📝 完整内容

{content}

## ✅ 验证状态

- [ ] 已验证准确性
- [ ] 已添加个人笔记
- [ ] 已关联相关内容

## 💭 我的补充

<!-- 添加你对这个总结的补充和修正 -->

---
*Captured on {created}*
"""

    def _visualization_template(self) -> str:
        return """---
title: "{title}"
source: "{source}"
type: visualization
category: {category}
tags: [{tags}]
created: {created}
image_path: "{image_path}"
---

# {title}

## 🖼️ 图片

![[{image_filename}]]

## 📝 描述

{description}

## 📄 提取的文字

{extracted_text}

## 🎯 关键信息

{key_points}

## 💭 我的理解

<!-- 这个图表/可视化说明了什么？ -->

---
*Captured on {created}*
"""

    def _note_template(self) -> str:
        return """---
title: "{title}"
source: "{source}"
type: note
category: {category}
tags: [{tags}]
created: {created}
---

# {title}

{content}

## 🏷️ 标签

{tag_links}

---
*Captured on {created}*
"""

    def generate(self, content_data: dict) -> str:
        """
        Generate Markdown from processed content data.

        Args:
            content_data: Dictionary with processed content

        Returns:
            Formatted Markdown string
        """
        content_type = content_data.get("type", "default")
        template = self.templates.get(content_type, self.templates["default"])

        # Format key points as bullet list
        key_points = content_data.get("key_points", [])
        if key_points:
            key_points_md = "\n".join(f"- {point}" for point in key_points)
        else:
            key_points_md = "- *暂无要点*"

        # Format tags
        tags = content_data.get("tags", [])
        tags_str = ", ".join(f'"{tag}"' for tag in tags)
        tag_links = " ".join(f"#{tag}" for tag in tags)

        # Get image info for visualizations
        image_path = content_data.get("image_path", "")
        image_filename = Path(image_path).name if image_path else ""

        # Build template variables
        variables = {
            "title": content_data.get("title", "Untitled"),
            "source": content_data.get("source", ""),
            "type": content_type,
            "category": content_data.get("category", "uncategorized"),
            "tags": tags_str,
            "tag_links": tag_links,
            "created": content_data.get("processed_at", datetime.now().isoformat()),
            "summary": content_data.get("summary", ""),
            "key_points": key_points_md,
            "content": content_data.get("content", ""),
            "author": content_data.get("author", "Unknown"),
            "description": content_data.get("description", ""),
            "extracted_text": content_data.get("extracted_text", "*无文字内容*"),
            "image_path": image_path,
            "image_filename": image_filename,
        }

        # Apply template
        try:
            markdown = template.format(**variables)
        except KeyError as e:
            # Fallback to default template if specific template fails
            markdown = self.templates["default"].format(**variables)

        return markdown

    def generate_index(self, items: list[dict], title: str = "知识库索引") -> str:
        """
        Generate an index page for multiple items.

        Args:
            items: List of content data dictionaries
            title: Title for the index page

        Returns:
            Formatted Markdown index
        """
        md = f"# {title}\n\n"
        md += f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n\n"

        # Group by category
        categories: dict[str, list] = {}
        for item in items:
            cat = item.get("category", "uncategorized")
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(item)

        # Generate category sections
        for category, cat_items in sorted(categories.items()):
            md += f"## {category.title()}\n\n"
            for item in cat_items:
                title = item.get("title", "Untitled")
                item_id = item.get("id", "")
                tags = " ".join(f"`{t}`" for t in item.get("tags", [])[:3])
                md += f"- [[{item_id}|{title}]] {tags}\n"
            md += "\n"

        return md

    def generate_daily_note(self, items: list[dict], date: Optional[str] = None) -> str:
        """
        Generate a daily note with captured items.

        Args:
            items: List of items captured today
            date: Date string (defaults to today)

        Returns:
            Formatted Markdown daily note
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        md = f"# Daily Capture - {date}\n\n"
        md += f"📊 今日捕获: {len(items)} 条\n\n"

        if not items:
            md += "*今日暂无捕获内容*\n"
            return md

        md += "## 📋 捕获列表\n\n"

        for item in items:
            title = item.get("title", "Untitled")
            item_type = item.get("type", "unknown")
            summary = item.get("summary", "")[:100]
            item_id = item.get("id", "")

            md += f"### [[{item_id}|{title}]]\n\n"
            md += f"- **类型**: {item_type}\n"
            md += f"- **摘要**: {summary}...\n\n"

        md += "---\n"
        md += f"[[{self._prev_date(date)}|⬅️ 昨天]] | [[{self._next_date(date)}|明天 ➡️]]\n"

        return md

    def _prev_date(self, date_str: str) -> str:
        """Get previous date string."""
        from datetime import timedelta
        date = datetime.strptime(date_str, "%Y-%m-%d")
        prev = date - timedelta(days=1)
        return prev.strftime("%Y-%m-%d")

    def _next_date(self, date_str: str) -> str:
        """Get next date string."""
        from datetime import timedelta
        date = datetime.strptime(date_str, "%Y-%m-%d")
        next_d = date + timedelta(days=1)
        return next_d.strftime("%Y-%m-%d")
