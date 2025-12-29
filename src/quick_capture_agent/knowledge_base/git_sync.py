"""
Git-based sync for Knowledge Base.

Automatically commits and pushes new content to a Git repository,
enabling sync with Obsidian via the Obsidian Git plugin.
"""

import asyncio
import logging
import os
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class GitSync:
    """
    Handles Git synchronization for the knowledge base.

    Usage:
        sync = GitSync(repo_path="/app/data/knowledge")
        await sync.sync_changes("Added new note")
    """

    def __init__(
        self,
        repo_path: Path,
        remote_url: Optional[str] = None,
        branch: str = "main",
        auto_push: bool = True,
    ):
        self.repo_path = Path(repo_path)
        self.remote_url = remote_url or os.getenv("GIT_REMOTE_URL")
        self.branch = branch or os.getenv("GIT_BRANCH", "main")
        self.auto_push = auto_push
        self._initialized = False

    def _run_git(self, *args, check: bool = True) -> subprocess.CompletedProcess:
        """Run a git command in the repo directory."""
        cmd = ["git", "-C", str(self.repo_path)] + list(args)
        logger.debug(f"Running: {' '.join(cmd)}")
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=check,
        )

    def init_repo(self) -> bool:
        """Initialize or clone the git repository."""
        if self._initialized:
            return True

        try:
            # Check if already a git repo
            if (self.repo_path / ".git").exists():
                logger.info(f"Git repo already exists at {self.repo_path}")
                self._initialized = True
                return True

            # Create directory if needed
            self.repo_path.mkdir(parents=True, exist_ok=True)

            # Clone if remote URL provided, otherwise init
            if self.remote_url:
                logger.info(f"Cloning from {self.remote_url}")
                subprocess.run(
                    ["git", "clone", self.remote_url, str(self.repo_path)],
                    capture_output=True,
                    text=True,
                    check=True,
                )
            else:
                logger.info(f"Initializing new repo at {self.repo_path}")
                self._run_git("init")
                self._run_git("checkout", "-b", self.branch)

            # Configure git user if not set
            self._run_git("config", "user.email",
                         os.getenv("GIT_USER_EMAIL", "bot@quick-capture.local"),
                         check=False)
            self._run_git("config", "user.name",
                         os.getenv("GIT_USER_NAME", "Quick Capture Bot"),
                         check=False)

            self._initialized = True
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Git init failed: {e.stderr}")
            return False

    def has_changes(self) -> bool:
        """Check if there are uncommitted changes."""
        result = self._run_git("status", "--porcelain", check=False)
        return bool(result.stdout.strip())

    def commit_changes(self, message: str = "Auto-commit from Quick Capture Bot") -> bool:
        """Stage and commit all changes."""
        try:
            if not self.has_changes():
                logger.debug("No changes to commit")
                return True

            self._run_git("add", "-A")
            self._run_git("commit", "-m", message)
            logger.info(f"Committed: {message}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Commit failed: {e.stderr}")
            return False

    def push_changes(self) -> bool:
        """Push changes to remote."""
        if not self.remote_url:
            logger.debug("No remote URL configured, skipping push")
            return True

        try:
            self._run_git("push", "-u", "origin", self.branch)
            logger.info("Pushed to remote")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Push failed: {e.stderr}")
            return False

    def pull_changes(self) -> bool:
        """Pull latest changes from remote."""
        if not self.remote_url:
            return True

        try:
            self._run_git("pull", "origin", self.branch, "--rebase")
            logger.info("Pulled latest changes")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Pull failed: {e.stderr}")
            return False

    async def sync_changes(self, message: str = "Auto-commit from Quick Capture Bot") -> bool:
        """
        Full sync: commit local changes and push to remote.

        This is async to avoid blocking the event loop.
        """
        loop = asyncio.get_event_loop()

        def _sync():
            if not self.init_repo():
                return False

            # Pull first to avoid conflicts
            if self.remote_url:
                self.pull_changes()

            # Commit local changes
            if not self.commit_changes(message):
                return False

            # Push if configured
            if self.auto_push and self.remote_url:
                return self.push_changes()

            return True

        return await loop.run_in_executor(None, _sync)


# Singleton instance
_git_sync: Optional[GitSync] = None


def get_git_sync(repo_path: Optional[Path] = None) -> Optional[GitSync]:
    """Get or create the GitSync instance."""
    global _git_sync

    if _git_sync is None:
        path = repo_path or Path(os.getenv("KNOWLEDGE_BASE_PATH", "/app/data/knowledge"))
        remote = os.getenv("GIT_REMOTE_URL")

        if remote:
            _git_sync = GitSync(repo_path=path, remote_url=remote)
            logger.info(f"Git sync enabled: {path} -> {remote}")
        else:
            logger.info("Git sync disabled (no GIT_REMOTE_URL)")

    return _git_sync
