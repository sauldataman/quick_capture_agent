"""
Prompt Manager - Manages different prompts for different content types.

Loads prompts from config/prompts.yaml and selects the appropriate prompt
based on content keywords or explicit category.
"""

import os
from pathlib import Path
from typing import Optional
import yaml


class PromptManager:
    """
    Manages prompts for different content types.

    Usage:
        pm = PromptManager()
        prompt_config = pm.get_prompt("tech")  # Get by category
        prompt_config = pm.detect_and_get_prompt(content)  # Auto-detect
    """

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or self._find_config()
        self.prompts = self._load_prompts()

    def _find_config(self) -> Path:
        """Find the prompts.yaml config file."""
        # Try multiple locations
        possible_paths = [
            Path("config/prompts.yaml"),
            Path("./prompts.yaml"),
            Path(__file__).parent.parent.parent.parent / "config" / "prompts.yaml",
            Path.home() / ".config" / "quick_capture_agent" / "prompts.yaml",
        ]

        for path in possible_paths:
            if path.exists():
                return path

        # Return default path (will create default config if needed)
        return possible_paths[0]

    def _load_prompts(self) -> dict:
        """Load prompts from YAML config."""
        if self.config_path.exists():
            with open(self.config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}

        # Return default prompts if file doesn't exist
        return self._default_prompts()

    def _default_prompts(self) -> dict:
        """Return default prompts."""
        return {
            "default": {
                "system": "你是一个知识整理助手。请分析内容并提取关键信息。",
                "user_template": "请分析以下内容：\n\n{content}",
            }
        }

    def reload(self) -> None:
        """Reload prompts from config file."""
        self.prompts = self._load_prompts()

    def get_categories(self) -> list[str]:
        """Get all available categories."""
        return list(self.prompts.keys())

    def get_prompt(self, category: str) -> dict:
        """
        Get prompt configuration for a specific category.

        Args:
            category: The category name

        Returns:
            Dict with 'system' and 'user_template' keys
        """
        if category in self.prompts:
            return self.prompts[category]
        return self.prompts.get("default", self._default_prompts()["default"])

    def detect_category(self, content: str) -> str:
        """
        Detect the most appropriate category based on content keywords.

        Args:
            content: The content to analyze

        Returns:
            The detected category name
        """
        content_lower = content.lower()

        # Score each category based on keyword matches
        scores = {}
        for category, config in self.prompts.items():
            if category == "default":
                continue

            keywords = config.get("keywords", [])
            score = sum(1 for kw in keywords if kw.lower() in content_lower)
            if score > 0:
                scores[category] = score

        # Return the category with highest score, or "default"
        if scores:
            return max(scores, key=scores.get)
        return "default"

    def detect_and_get_prompt(self, content: str) -> tuple[str, dict]:
        """
        Detect category and get corresponding prompt.

        Args:
            content: The content to analyze

        Returns:
            Tuple of (category, prompt_config)
        """
        category = self.detect_category(content)
        return category, self.get_prompt(category)

    def format_user_prompt(
        self,
        category: str,
        content: str,
        **kwargs
    ) -> str:
        """
        Format the user prompt template with content.

        Args:
            category: The category name
            content: The main content
            **kwargs: Additional template variables

        Returns:
            Formatted user prompt
        """
        prompt_config = self.get_prompt(category)
        template = prompt_config.get("user_template", "{content}")

        # Build template variables
        variables = {"content": content, **kwargs}

        try:
            return template.format(**variables)
        except KeyError as e:
            # If a variable is missing, return with the raw template
            return template.replace("{content}", content)

    def get_system_prompt(self, category: str) -> str:
        """Get the system prompt for a category."""
        prompt_config = self.get_prompt(category)
        return prompt_config.get("system", "")

    def save_custom_prompt(
        self,
        category: str,
        system_prompt: str,
        user_template: str,
        keywords: list[str] = None
    ) -> None:
        """
        Save a custom prompt configuration.

        Args:
            category: Category name
            system_prompt: The system prompt
            user_template: The user prompt template
            keywords: Keywords for auto-detection
        """
        self.prompts[category] = {
            "system": system_prompt,
            "user_template": user_template,
        }
        if keywords:
            self.prompts[category]["keywords"] = keywords

        # Save to config file
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.dump(self.prompts, f, allow_unicode=True, default_flow_style=False)


# Singleton instance
_prompt_manager: Optional[PromptManager] = None


def get_prompt_manager() -> PromptManager:
    """Get the global PromptManager instance."""
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager()
    return _prompt_manager
