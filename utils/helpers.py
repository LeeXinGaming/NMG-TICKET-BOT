"""
Helper utilities for strings, Discord timestamp formatting, and channel name sanitization.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import List, Optional


def utc_now() -> datetime:
    """Return naive UTC datetime matching database timestamps without deprecation."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def sanitize_channel_name(name: str) -> str:
    """
    Sanitize string to comply with Discord channel name constraints:
    - Lowercase
    - Only alphanumeric characters and hyphens
    - Consecutive hyphens collapsed
    - Stripped of leading/trailing hyphens
    - Max 100 characters
    """
    name = name.lower()
    name = re.sub(r"[^\w\s-]", "", name)
    name = re.sub(r"[\s_]+", "-", name)
    name = re.sub(r"-+", "-", name)
    name = name.strip("-")
    return name[:100] if name else "ticket"


def format_channel_name(format_str: str, ticket_id: int, username: str) -> str:
    """Format channel name using template like ticket-{id:06d} or ticket-{username}."""
    sanitized_user = sanitize_channel_name(username)
    try:
        raw_name = format_str.format(id=ticket_id, username=sanitized_user)
    except Exception:
        raw_name = f"ticket-{ticket_id:06d}"
    return sanitize_channel_name(raw_name)


def discord_timestamp(dt: Optional[datetime] = None, style: str = "f") -> str:
    """Return Discord markdown timestamp e.g. <t:1670000000:f>."""
    if dt is None:
        dt = utc_now()
    unix_time = int(dt.timestamp())
    return f"<t:{unix_time}:{style}>"


def parse_iso(iso_str: Optional[str]) -> Optional[datetime]:
    """Parse ISO 8601 string to datetime."""
    if not iso_str:
        return None
    try:
        return datetime.fromisoformat(iso_str)
    except Exception:
        return None


def format_iso_to_discord(iso_str: Optional[str], style: str = "f") -> str:
    """Convert stored ISO string to Discord timestamp."""
    dt = parse_iso(iso_str)
    if dt:
        return discord_timestamp(dt, style)
    return "N/A"


def chunk_text(text: str, limit: int = 1900) -> List[str]:
    """Split text into chunks that fit Discord message limit."""
    if len(text) <= limit:
        return [text]
    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        split_idx = text.rfind("\n", 0, limit)
        if split_idx == -1:
            split_idx = limit
        chunks.append(text[:split_idx])
        text = text[split_idx:].lstrip()
    return chunks
