"""
Support Ticket Bot - Configuration Manager
Loads environment variables and sets system defaults.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Base paths
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"

# Load environment variables from .env if present
load_dotenv(dotenv_path=ENV_PATH)

# Bot Authentication
DISCORD_TOKEN: str = os.getenv("DISCORD_TOKEN", "").strip()

# Target Guild (Server) for quick slash command sync
_guild_id_raw = os.getenv("GUILD_ID", "").strip()
GUILD_ID: Optional[int] = int(_guild_id_raw) if _guild_id_raw.isdigit() else None

# Default Discord IDs
_support_role_raw = os.getenv("SUPPORT_ROLE_ID", "").strip()
DEFAULT_SUPPORT_ROLE_ID: Optional[int] = (
    int(_support_role_raw) if _support_role_raw.isdigit() else None
)

_ticket_cat_raw = os.getenv("TICKET_CATEGORY_ID", "").strip()
DEFAULT_TICKET_CATEGORY_ID: Optional[int] = (
    int(_ticket_cat_raw) if _ticket_cat_raw.isdigit() else None
)

_log_chan_raw = os.getenv("LOG_CHANNEL_ID", "").strip()
DEFAULT_LOG_CHANNEL_ID: Optional[int] = (
    int(_log_chan_raw) if _log_chan_raw.isdigit() else None
)

_transcript_chan_raw = os.getenv("TRANSCRIPT_CHANNEL_ID", "").strip()
DEFAULT_TRANSCRIPT_CHANNEL_ID: Optional[int] = (
    int(_transcript_chan_raw) if _transcript_chan_raw.isdigit() else None
)

# Database Configuration
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///tickets.db").strip()

# Default Ticket Behavior
_max_tickets_raw = os.getenv("MAX_OPEN_TICKETS", "3").strip()
DEFAULT_MAX_OPEN_TICKETS: int = int(_max_tickets_raw) if _max_tickets_raw.isdigit() else 3

_daily_ticket_limit_raw = os.getenv("DAILY_TICKET_LIMIT", "3").strip()
DEFAULT_DAILY_TICKET_LIMIT: int = int(_daily_ticket_limit_raw) if _daily_ticket_limit_raw.isdigit() else 3

TICKET_NAME_FORMAT: str = os.getenv("TICKET_NAME_FORMAT", "ticket-{id:06d}").strip()
AUTOREPLY_ENABLED: bool = os.getenv("AUTOREPLY_ENABLED", "true").lower() in ("true", "1", "yes")
ENABLE_PRIVILEGED_INTENTS: bool = os.getenv("ENABLE_PRIVILEGED_INTENTS", "false").lower() in ("true", "1", "yes")

# Registration System Defaults (Disabled)
REQUIRE_REGISTRATION: bool = os.getenv("REQUIRE_REGISTRATION", "false").lower() in ("true", "1", "yes")
_reg_role_raw = os.getenv("REGISTERED_ROLE_ID", "").strip()
DEFAULT_REGISTERED_ROLE_ID: Optional[int] = int(_reg_role_raw) if _reg_role_raw.isdigit() else None


# Directories
TRANSCRIPTS_DIR = BASE_DIR / "transcripts"
TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)

# Optional Web Admin Dashboard / Health Server (Render)
ENABLE_DASHBOARD: bool = (
    os.getenv("ENABLE_DASHBOARD", "false").lower() in ("true", "1", "yes")
    or bool(os.getenv("PORT"))
)
DASHBOARD_HOST: str = os.getenv("DASHBOARD_HOST", "0.0.0.0").strip()
_dash_port_raw = os.getenv("PORT", os.getenv("DASHBOARD_PORT", "8080")).strip()
DASHBOARD_PORT: int = int(_dash_port_raw) if _dash_port_raw.isdigit() else 8080
DASHBOARD_ADMIN_USER: str = os.getenv("DASHBOARD_ADMIN_USER", "admin").strip()
DASHBOARD_ADMIN_PASSWORD: str = os.getenv("DASHBOARD_ADMIN_PASSWORD", "admin123").strip()

# Colors (Hex integer constants for Discord Embeds)
COLOR_PRIMARY = 0x5865F2    # Blurple
COLOR_SUCCESS = 0x57F287    # Green
COLOR_WARNING = 0xFEE75C    # Yellow
COLOR_DANGER = 0xED4245     # Red
COLOR_INFO = 0x5865F2       # Blue
COLOR_DARK = 0x2B2D31       # Discord Dark Theme
