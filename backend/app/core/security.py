from __future__ import annotations

import re
import secrets
from pathlib import Path

from fastapi import Header, HTTPException, status

from app.core.config import settings

_ALLOWED_EXTENSIONS = frozenset(settings.ALLOWED_EXTENSIONS)
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]")


def sanitize_filename(filename: str) -> str:
    """Strip path components and replace unsafe characters in a filename."""
    base = Path(filename).name
    base = _SAFE_NAME.sub("_", base).strip("._ ")
    if not base:
        raise ValueError(f"Filename {filename!r} sanitized to empty; refusing.")
    if len(base) > 255:
        raw, ext = Path(base).stem, Path(base).suffix
        base = raw[: 255 - len(ext)] + ext
    return base


def validate_upload_extension(filename: str) -> str:
    """Return the lowercased whitelisted extension or raise HTTP 400."""
    ext = Path(filename).suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(_ALLOWED_EXTENSIONS))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Extension {ext!r} not allowed. Allowed: {allowed}",
        )
    return ext


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Validate the X-API-Key header when an API key is configured."""
    if settings.API_KEY is None:
        return
    if x_api_key is None or not secrets.compare_digest(x_api_key, settings.API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
        )