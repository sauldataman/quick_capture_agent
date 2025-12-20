"""
Helper utility functions used across the project.
"""

import asyncio
import re
import unicodedata
from functools import wraps
from typing import Callable, TypeVar, Any
from urllib.parse import urlparse

T = TypeVar("T")


def extract_urls(text: str) -> list[str]:
    """
    Extract all URLs from a text string.

    Args:
        text: The text to extract URLs from

    Returns:
        List of extracted URLs
    """
    url_pattern = re.compile(
        r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
    )
    return url_pattern.findall(text)


def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """
    Sanitize a string to be used as a filename.

    Args:
        filename: The original filename
        max_length: Maximum length of the filename

    Returns:
        Sanitized filename
    """
    # Normalize unicode characters
    filename = unicodedata.normalize("NFKD", filename)
    filename = filename.encode("ascii", "ignore").decode("ascii")

    # Replace problematic characters
    filename = re.sub(r'[<>:"/\\|?*]', "_", filename)
    filename = re.sub(r"\s+", "_", filename)
    filename = re.sub(r"_+", "_", filename)
    filename = filename.strip("_.")

    # Truncate if too long
    if len(filename) > max_length:
        filename = filename[:max_length]

    return filename or "unnamed"


def chunk_text(text: str, chunk_size: int = 4000, overlap: int = 200) -> list[str]:
    """
    Split text into overlapping chunks.

    Args:
        text: The text to split
        chunk_size: Maximum size of each chunk
        overlap: Number of characters to overlap between chunks

    Returns:
        List of text chunks
    """
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        # Try to break at a sentence or paragraph boundary
        if end < len(text):
            # Look for paragraph break
            para_break = text.rfind("\n\n", start, end)
            if para_break > start + chunk_size // 2:
                end = para_break + 2
            else:
                # Look for sentence break
                sentence_break = text.rfind(". ", start, end)
                if sentence_break > start + chunk_size // 2:
                    end = sentence_break + 2

        chunks.append(text[start:end].strip())
        start = end - overlap

    return chunks


def async_retry(
    max_retries: int = 3,
    delay: float = 1.0,
    exponential_backoff: bool = True,
    exceptions: tuple = (Exception,),
) -> Callable:
    """
    Decorator for retrying async functions on failure.

    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        exponential_backoff: Whether to use exponential backoff
        exceptions: Tuple of exceptions to catch and retry

    Returns:
        Decorated function
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception = None
            current_delay = delay

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        await asyncio.sleep(current_delay)
                        if exponential_backoff:
                            current_delay *= 2

            raise last_exception

        return wrapper

    return decorator


def is_valid_url(url: str) -> bool:
    """
    Check if a string is a valid URL.

    Args:
        url: The URL string to validate

    Returns:
        True if valid, False otherwise
    """
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


def get_url_domain(url: str) -> str:
    """
    Extract the domain from a URL.

    Args:
        url: The URL to extract domain from

    Returns:
        The domain name
    """
    try:
        parsed = urlparse(url)
        return parsed.netloc
    except Exception:
        return ""


def format_file_size(size_bytes: int) -> str:
    """
    Format a file size in bytes to a human-readable string.

    Args:
        size_bytes: Size in bytes

    Returns:
        Human-readable size string
    """
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"
