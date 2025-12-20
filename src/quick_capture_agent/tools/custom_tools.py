"""
Custom tools that can be used by agents.

These tools extend the base capabilities of the Claude Agent SDK
with specialized functionality for content collection and processing.
"""

import asyncio
from pathlib import Path
from typing import Optional
import aiohttp
import aiofiles
from urllib.parse import urlparse


async def download_file(
    url: str,
    output_path: Optional[Path] = None,
    timeout: int = 300,
) -> dict:
    """
    Download a file from a URL.

    Args:
        url: URL to download from
        output_path: Path to save the file (auto-generated if not provided)
        timeout: Download timeout in seconds

    Returns:
        Dict with download status and file path
    """
    try:
        # Generate output path if not provided
        if not output_path:
            parsed = urlparse(url)
            filename = Path(parsed.path).name or "downloaded_file"
            output_path = Path("./data/downloads") / filename
            output_path.parent.mkdir(parents=True, exist_ok=True)

        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                if response.status != 200:
                    return {
                        "success": False,
                        "error": f"HTTP {response.status}: {response.reason}",
                    }

                content_length = response.headers.get("Content-Length")

                async with aiofiles.open(output_path, "wb") as f:
                    async for chunk in response.content.iter_chunked(8192):
                        await f.write(chunk)

                return {
                    "success": True,
                    "path": str(output_path),
                    "size": content_length,
                    "content_type": response.headers.get("Content-Type"),
                }

    except asyncio.TimeoutError:
        return {"success": False, "error": "Download timed out"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def extract_text_from_image(image_path: str) -> dict:
    """
    Extract text from an image using OCR.

    Note: This is a placeholder. In production, you would integrate with
    an OCR service or use a library like pytesseract.

    Args:
        image_path: Path to the image file

    Returns:
        Dict with extracted text
    """
    try:
        path = Path(image_path)
        if not path.exists():
            return {"success": False, "error": f"Image not found: {image_path}"}

        # Placeholder - in production, use actual OCR
        # Example with pytesseract:
        # from PIL import Image
        # import pytesseract
        # text = pytesseract.image_to_string(Image.open(path))

        return {
            "success": True,
            "text": "[OCR placeholder - integrate pytesseract or cloud OCR]",
            "path": str(path),
            "note": "Install pytesseract for actual OCR functionality",
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


async def transcribe_audio(audio_path: str, language: str = "en") -> dict:
    """
    Transcribe audio to text.

    Note: This is a placeholder. In production, you would integrate with
    Whisper or another transcription service.

    Args:
        audio_path: Path to the audio file
        language: Language code

    Returns:
        Dict with transcription
    """
    try:
        path = Path(audio_path)
        if not path.exists():
            return {"success": False, "error": f"Audio file not found: {audio_path}"}

        # Placeholder - in production, use Whisper
        # Example with openai-whisper:
        # import whisper
        # model = whisper.load_model("base")
        # result = model.transcribe(str(path))
        # text = result["text"]

        return {
            "success": True,
            "text": "[Transcription placeholder - integrate Whisper]",
            "path": str(path),
            "language": language,
            "note": "Install openai-whisper for actual transcription",
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


async def fetch_rss_feed(feed_url: str) -> dict:
    """
    Fetch and parse an RSS feed.

    Args:
        feed_url: URL of the RSS feed

    Returns:
        Dict with feed entries
    """
    try:
        import feedparser

        feed = feedparser.parse(feed_url)

        if feed.bozo and not feed.entries:
            return {"success": False, "error": "Failed to parse RSS feed"}

        entries = []
        for entry in feed.entries[:20]:  # Limit to 20 entries
            entries.append({
                "title": entry.get("title", ""),
                "link": entry.get("link", ""),
                "published": entry.get("published", ""),
                "summary": entry.get("summary", "")[:500],
            })

        return {
            "success": True,
            "feed_title": feed.feed.get("title", ""),
            "feed_link": feed.feed.get("link", ""),
            "entries": entries,
        }

    except ImportError:
        return {
            "success": False,
            "error": "feedparser not installed. Run: pip install feedparser",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def extract_youtube_info(url: str) -> dict:
    """
    Extract information from a YouTube video.

    Args:
        url: YouTube video URL

    Returns:
        Dict with video information
    """
    try:
        import yt_dlp

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        return {
            "success": True,
            "title": info.get("title"),
            "description": info.get("description"),
            "duration": info.get("duration"),
            "uploader": info.get("uploader"),
            "upload_date": info.get("upload_date"),
            "view_count": info.get("view_count"),
            "thumbnail": info.get("thumbnail"),
        }

    except ImportError:
        return {
            "success": False,
            "error": "yt-dlp not installed. Run: pip install yt-dlp",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
