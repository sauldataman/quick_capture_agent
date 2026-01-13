#!/usr/bin/env python3
"""
Test script for Google Drive integration.

Usage:
    # With environment variables already set:
    python scripts/test_gdrive.py

    # Or with explicit credentials:
    GOOGLE_CREDENTIALS_JSON='{"type":"service_account",...}' python scripts/test_gdrive.py
"""

import os
import sys
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def test_gdrive():
    """Test Google Drive connection and upload."""

    print("=" * 50)
    print("Google Drive Integration Test")
    print("=" * 50)

    # Check environment variables
    print("\n1. Checking environment variables...")

    has_json = bool(os.getenv("GOOGLE_CREDENTIALS_JSON"))
    has_path = bool(os.getenv("GOOGLE_CREDENTIALS_PATH"))
    folder_id = os.getenv("GDRIVE_FOLDER_ID", "Not set (will create QuickCapture folder)")

    print(f"   GOOGLE_CREDENTIALS_JSON: {'✅ Set' if has_json else '❌ Not set'}")
    print(f"   GOOGLE_CREDENTIALS_PATH: {'✅ Set' if has_path else '❌ Not set'}")
    print(f"   GDRIVE_FOLDER_ID: {folder_id}")

    if not has_json and not has_path:
        print("\n❌ Error: No credentials found!")
        print("   Please set GOOGLE_CREDENTIALS_JSON or GOOGLE_CREDENTIALS_PATH")
        return False

    # Try to import and initialize
    print("\n2. Initializing Google Drive sync...")
    try:
        from quick_capture_agent.knowledge_base.gdrive_sync import GoogleDriveSync
        sync = GoogleDriveSync()
        print("   ✅ GoogleDriveSync initialized successfully")
    except ImportError as e:
        print(f"   ❌ Import error: {e}")
        print("   Run: pip install google-api-python-client google-auth")
        return False
    except Exception as e:
        print(f"   ❌ Initialization error: {e}")
        return False

    # Test upload
    print("\n3. Testing file upload...")
    test_content = f"""# Google Drive Test

This is a test file created at {datetime.now().isoformat()}

If you can see this file in your Google Drive, the integration is working!

## Test Details
- Script: test_gdrive.py
- Status: Success ✅
"""

    try:
        result = sync.upload_content_sync(
            content=test_content,
            remote_path="test/gdrive_test.md"
        )
        print(f"   ✅ File uploaded successfully!")
        print(f"   📄 File ID: {result.get('id')}")
        print(f"   🔗 Web Link: {result.get('webViewLink', 'N/A')}")
    except Exception as e:
        print(f"   ❌ Upload failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("\n" + "=" * 50)
    print("✅ All tests passed! Google Drive is working.")
    print("=" * 50)
    print("\nCheck your Google Drive for the test file at:")
    print("   QuickCapture/test/gdrive_test.md")

    return True


if __name__ == "__main__":
    success = test_gdrive()
    sys.exit(0 if success else 1)
