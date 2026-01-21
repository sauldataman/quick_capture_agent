"""
Google Drive sync for Knowledge Base.

Automatically uploads content to Google Drive, enabling seamless
sync with local machines and Obsidian.
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Google API imports - optional dependency
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False
    logger.warning("Google API libraries not installed. Run: pip install google-api-python-client google-auth")


class GoogleDriveSync:
    """
    Google Drive synchronization for knowledge base files.

    Supports two authentication methods:
    1. Service Account with Domain-wide Delegation (recommended for Google Workspace)
    2. Service Account with shared folder access

    Usage:
        sync = GoogleDriveSync(
            credentials_path="/path/to/credentials.json",
            folder_id="your-drive-folder-id",
            delegated_user="user@yourdomain.com"  # For delegation
        )
        await sync.upload_file(local_path, "notes/my-note.md")
    """

    # Full drive access for delegation mode
    SCOPES = ['https://www.googleapis.com/auth/drive']

    def __init__(
        self,
        credentials_path: Optional[str] = None,
        credentials_json: Optional[str] = None,
        folder_id: Optional[str] = None,
        folder_name: str = "QuickCapture",
        delegated_user: Optional[str] = None,
    ):
        """
        Initialize Google Drive sync.

        Args:
            credentials_path: Path to service account JSON file
            credentials_json: Service account JSON as string (for env vars)
            folder_id: Google Drive folder ID to sync to
            folder_name: Folder name to create if folder_id not specified
            delegated_user: Email of user to impersonate (for domain-wide delegation)
        """
        if not GOOGLE_API_AVAILABLE:
            raise ImportError(
                "Google API libraries required. Install with: "
                "pip install google-api-python-client google-auth"
            )

        self.credentials_path = credentials_path or os.getenv("GOOGLE_CREDENTIALS_PATH")
        self.credentials_json = credentials_json or os.getenv("GOOGLE_CREDENTIALS_JSON")
        self.folder_id = folder_id or os.getenv("GDRIVE_FOLDER_ID")
        self.folder_name = folder_name
        self.delegated_user = delegated_user or os.getenv("GDRIVE_DELEGATED_USER")

        self._service = None
        self._folder_cache = {}  # Cache for subfolder IDs

    def _get_credentials(self):
        """Get Google API credentials with optional delegation."""
        if self.credentials_json:
            # Parse JSON from environment variable
            creds_dict = json.loads(self.credentials_json)
            credentials = service_account.Credentials.from_service_account_info(
                creds_dict, scopes=self.SCOPES
            )
        elif self.credentials_path:
            credentials = service_account.Credentials.from_service_account_file(
                self.credentials_path, scopes=self.SCOPES
            )
        else:
            raise ValueError(
                "Google credentials required. Set GOOGLE_CREDENTIALS_JSON or GOOGLE_CREDENTIALS_PATH"
            )

        # Apply domain-wide delegation if user is specified
        if self.delegated_user:
            credentials = credentials.with_subject(self.delegated_user)
            logger.info(f"Using domain-wide delegation as: {self.delegated_user}")

        return credentials

    @property
    def service(self):
        """Get or create the Drive API service."""
        if self._service is None:
            credentials = self._get_credentials()
            self._service = build('drive', 'v3', credentials=credentials)
        return self._service

    def _get_or_create_folder(self, name: str, parent_id: Optional[str] = None) -> str:
        """Get existing folder or create new one."""
        cache_key = f"{parent_id}:{name}"
        if cache_key in self._folder_cache:
            return self._folder_cache[cache_key]

        # Search for existing folder
        query = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        if parent_id:
            query += f" and '{parent_id}' in parents"

        results = self.service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name)'
        ).execute()

        files = results.get('files', [])
        if files:
            folder_id = files[0]['id']
        else:
            # Create new folder
            file_metadata = {
                'name': name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            if parent_id:
                file_metadata['parents'] = [parent_id]

            folder = self.service.files().create(
                body=file_metadata,
                fields='id'
            ).execute()
            folder_id = folder['id']
            logger.info(f"Created folder: {name} ({folder_id})")

        self._folder_cache[cache_key] = folder_id
        return folder_id

    def _ensure_folder_path(self, path: str) -> str:
        """
        Ensure folder path exists and return the final folder ID.

        Args:
            path: Folder path like "notes/tech" or just "articles"

        Returns:
            Folder ID of the deepest folder
        """
        # Start from root folder
        if not self.folder_id:
            self.folder_id = self._get_or_create_folder(self.folder_name)

        current_folder = self.folder_id

        # Create each folder in path
        if path:
            parts = path.strip('/').split('/')
            for part in parts:
                if part:
                    current_folder = self._get_or_create_folder(part, current_folder)

        return current_folder

    def upload_file_sync(
        self,
        local_path: Path,
        remote_path: str,
        mime_type: Optional[str] = None
    ) -> dict:
        """
        Upload a file to Google Drive (synchronous).

        Args:
            local_path: Local file path
            remote_path: Remote path like "notes/my-note.md"
            mime_type: MIME type (auto-detected if not specified)

        Returns:
            Dict with file info including 'id' and 'webViewLink'
        """
        local_path = Path(local_path)
        if not local_path.exists():
            raise FileNotFoundError(f"File not found: {local_path}")

        # Parse remote path
        remote_path = remote_path.lstrip('/')
        if '/' in remote_path:
            folder_path = '/'.join(remote_path.split('/')[:-1])
            file_name = remote_path.split('/')[-1]
        else:
            folder_path = ''
            file_name = remote_path

        # Ensure folder exists
        folder_id = self._ensure_folder_path(folder_path)

        # Detect MIME type
        if mime_type is None:
            mime_type = self._detect_mime_type(local_path)

        # Check if file already exists
        existing_id = self._find_file(file_name, folder_id)

        file_metadata = {'name': file_name}
        media = MediaFileUpload(str(local_path), mimetype=mime_type, resumable=True)

        if existing_id:
            # Update existing file
            file = self.service.files().update(
                fileId=existing_id,
                body=file_metadata,
                media_body=media,
                fields='id, name, webViewLink, size'
            ).execute()
            logger.info(f"Updated: {remote_path}")
        else:
            # Create new file
            file_metadata['parents'] = [folder_id]
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name, webViewLink, size'
            ).execute()
            logger.info(f"Uploaded: {remote_path}")

        return file

    def upload_content_sync(
        self,
        content: str,
        remote_path: str,
        mime_type: str = 'text/markdown'
    ) -> dict:
        """
        Upload content directly to Google Drive without local file.

        Args:
            content: Text content to upload
            remote_path: Remote path like "notes/my-note.md"
            mime_type: MIME type (default: text/markdown)

        Returns:
            Dict with file info
        """
        import io

        # Parse remote path
        remote_path = remote_path.lstrip('/')
        if '/' in remote_path:
            folder_path = '/'.join(remote_path.split('/')[:-1])
            file_name = remote_path.split('/')[-1]
        else:
            folder_path = ''
            file_name = remote_path

        # Ensure folder exists
        folder_id = self._ensure_folder_path(folder_path)

        # Check if file already exists
        existing_id = self._find_file(file_name, folder_id)

        file_metadata = {'name': file_name}
        media = MediaIoBaseUpload(
            io.BytesIO(content.encode('utf-8')),
            mimetype=mime_type,
            resumable=True
        )

        if existing_id:
            file = self.service.files().update(
                fileId=existing_id,
                body=file_metadata,
                media_body=media,
                fields='id, name, webViewLink, size'
            ).execute()
            logger.info(f"Updated: {remote_path}")
        else:
            file_metadata['parents'] = [folder_id]
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name, webViewLink, size'
            ).execute()
            logger.info(f"Uploaded: {remote_path}")

        return file

    def _find_file(self, name: str, parent_id: str) -> Optional[str]:
        """Find a file by name in a folder."""
        query = f"name='{name}' and '{parent_id}' in parents and trashed=false"
        results = self.service.files().list(
            q=query,
            spaces='drive',
            fields='files(id)'
        ).execute()
        files = results.get('files', [])
        return files[0]['id'] if files else None

    def _detect_mime_type(self, path: Path) -> str:
        """Detect MIME type from file extension."""
        mime_types = {
            '.md': 'text/markdown',
            '.txt': 'text/plain',
            '.json': 'application/json',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.pdf': 'application/pdf',
            '.html': 'text/html',
        }
        return mime_types.get(path.suffix.lower(), 'application/octet-stream')

    async def upload_file(
        self,
        local_path: Path,
        remote_path: str,
        mime_type: Optional[str] = None
    ) -> dict:
        """Async wrapper for upload_file_sync."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.upload_file_sync(local_path, remote_path, mime_type)
        )

    async def upload_content(
        self,
        content: str,
        remote_path: str,
        mime_type: str = 'text/markdown'
    ) -> dict:
        """Async wrapper for upload_content_sync."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.upload_content_sync(content, remote_path, mime_type)
        )

    def download_file_content(self, file_id: str) -> bytes:
        """Download file content from Google Drive."""
        request = self.service.files().get_media(fileId=file_id)
        return request.execute()

    def list_files_in_folder(self, folder_path: str = "", file_extension: str = None) -> list:
        """
        List files in a folder.

        Args:
            folder_path: Path relative to root folder (e.g., "_data/inbox")
            file_extension: Filter by extension (e.g., ".json")

        Returns:
            List of dicts with 'id', 'name', 'modifiedTime'
        """
        # Get folder ID
        if folder_path:
            folder_id = self._ensure_folder_path(folder_path)
        else:
            if not self.folder_id:
                self.folder_id = self._get_or_create_folder(self.folder_name)
            folder_id = self.folder_id

        query = f"'{folder_id}' in parents and trashed=false"
        if file_extension:
            query += f" and name contains '{file_extension}'"

        results = self.service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name, modifiedTime)',
            pageSize=1000
        ).execute()

        return results.get('files', [])

    def restore_items_from_gdrive(self, local_base_path: Path) -> int:
        """
        Restore knowledge base items from Google Drive to local storage.

        Args:
            local_base_path: Local base path for knowledge base

        Returns:
            Number of items restored
        """
        restored_count = 0

        try:
            # List all category folders in _data
            data_folder_id = self._ensure_folder_path("_data")

            # Get category folders
            query = f"'{data_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name)'
            ).execute()

            category_folders = results.get('files', [])

            for cat_folder in category_folders:
                category_name = cat_folder['name']
                category_id = cat_folder['id']

                # Create local category directory
                local_cat_dir = local_base_path / category_name
                local_cat_dir.mkdir(parents=True, exist_ok=True)

                # List JSON files in this category
                query = f"'{category_id}' in parents and name contains '.json' and trashed=false"
                files_result = self.service.files().list(
                    q=query,
                    spaces='drive',
                    fields='files(id, name)'
                ).execute()

                json_files = files_result.get('files', [])

                for json_file in json_files:
                    local_file_path = local_cat_dir / json_file['name']

                    # Only download if not exists locally
                    if not local_file_path.exists():
                        try:
                            content = self.download_file_content(json_file['id'])
                            with open(local_file_path, 'wb') as f:
                                f.write(content)
                            restored_count += 1
                            logger.debug(f"Restored: {category_name}/{json_file['name']}")
                        except Exception as e:
                            logger.warning(f"Failed to restore {json_file['name']}: {e}")

            if restored_count > 0:
                logger.info(f"Restored {restored_count} items from Google Drive")

        except Exception as e:
            logger.warning(f"Failed to restore items from Google Drive: {e}")

        return restored_count


# Singleton instance
_gdrive_sync: Optional[GoogleDriveSync] = None


def get_gdrive_sync() -> Optional[GoogleDriveSync]:
    """Get or create the GoogleDriveSync instance."""
    global _gdrive_sync

    if _gdrive_sync is None:
        # Check if credentials are configured
        has_creds = (
            os.getenv("GOOGLE_CREDENTIALS_JSON") or
            os.getenv("GOOGLE_CREDENTIALS_PATH")
        )

        if has_creds and GOOGLE_API_AVAILABLE:
            try:
                _gdrive_sync = GoogleDriveSync()
                logger.info("Google Drive sync enabled")
            except Exception as e:
                logger.error(f"Failed to initialize Google Drive sync: {e}")
        else:
            if not GOOGLE_API_AVAILABLE:
                logger.debug("Google API libraries not installed")
            else:
                logger.debug("Google Drive sync disabled (no credentials)")

    return _gdrive_sync
