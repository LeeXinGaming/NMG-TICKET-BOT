"""Data models for Ticket Bot entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any

from utils.helpers import utc_now


@dataclass
class Ticket:
    id: int
    discord_channel_id: int
    guild_id: int
    user_id: int
    category: str
    status: str  # "open", "closed"
    claimed_by: Optional[int] = None
    created_at: str = field(default_factory=lambda: utc_now().isoformat())
    closed_at: Optional[str] = None
    closed_by: Optional[int] = None

    @property
    def is_open(self) -> bool:
        return self.status == "open"

    @property
    def is_claimed(self) -> bool:
        return self.claimed_by is not None


@dataclass
class TicketMessage:
    id: int
    ticket_id: int
    message_id: int
    author_id: int
    author_name: str
    content: str
    attachments: str = ""  # JSON string or comma-separated list of URLs
    created_at: str = field(default_factory=lambda: utc_now().isoformat())


@dataclass
class TicketClaim:
    id: int
    ticket_id: int
    staff_id: int
    staff_name: str
    claimed_at: str
    released_at: Optional[str] = None


@dataclass
class TicketCategory:
    id: int
    name: str
    emoji: str
    description: str
    role_id: Optional[int] = None
    auto_reply: Optional[str] = None
    enabled: bool = True
    created_at: str = field(default_factory=lambda: utc_now().isoformat())


@dataclass
class AutoReply:
    id: int
    category_name: str
    message: str
    enabled: bool = True
    updated_at: str = field(default_factory=lambda: utc_now().isoformat())


@dataclass
class Keyword:
    id: int
    keyword: str
    response: str
    enabled: bool = True
    created_by: Optional[int] = None
    created_at: str = field(default_factory=lambda: utc_now().isoformat())


@dataclass
class Setting:
    guild_id: int
    support_role_id: Optional[int] = None
    ticket_category_id: Optional[int] = None
    log_channel_id: Optional[int] = None
    transcript_channel_id: Optional[int] = None
    panel_channel_id: Optional[int] = None
    panel_message_id: Optional[int] = None
    max_tickets: int = 1
    ticket_name_format: str = "ticket-{id:06d}"
    autoreply_enabled: bool = True
    require_registration: bool = True
    registered_role_id: Optional[int] = None
    registration_channel_id: Optional[int] = None


@dataclass
class TicketLog:
    id: int
    guild_id: int
    ticket_id: Optional[int]
    action: str
    actor_id: Optional[int]
    details: str
    created_at: str = field(default_factory=lambda: utc_now().isoformat())


@dataclass
class RegisteredUser:
    id: int
    guild_id: int
    discord_user_id: int
    username: str
    full_name: str
    phone_or_id: str
    notes: Optional[str] = None
    status: str = "registered"
    registered_at: str = field(default_factory=lambda: utc_now().isoformat())
    registered_by: Optional[int] = None

