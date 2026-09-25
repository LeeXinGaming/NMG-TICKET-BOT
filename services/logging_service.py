"""
Logging Service - Handles Python file/console logging and Discord channel audit logs.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Optional, Union

import discord

from config import BASE_DIR, DEFAULT_LOG_CHANNEL_ID
from database.database import Database, db
from utils.embeds import audit_log_embed
from utils.helpers import utc_now

# Setup application logger
logger = logging.getLogger("ticketbot")
logger.setLevel(logging.INFO)

# Formatter
log_formatter = logging.Formatter(
    "[%(asctime)s] [%(levelname)-7s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Reconfigure stdout/stderr to UTF-8 on Windows platforms if available
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Console handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(log_formatter)
logger.addHandler(console_handler)

# Rotating File handler
file_handler = RotatingFileHandler(
    BASE_DIR / "ticketbot.log",
    maxBytes=5 * 1024 * 1024,  # 5MB
    backupCount=3,
    encoding="utf-8",
)
file_handler.setFormatter(log_formatter)
logger.addHandler(file_handler)


class LoggingService:
    def __init__(self, database: Database = db):
        self.db = database

    async def log_event(
        self,
        guild: discord.Guild,
        action: str,
        actor: Optional[Union[discord.User, discord.Member]],
        ticket_id: Optional[int],
        details: str,
        channel: Optional[Union[discord.TextChannel, discord.Thread]] = None,
    ) -> None:
        """Log event to DB and send an embed to the guild's log channel."""
        logger.info(f"[{guild.name} - #{ticket_id or 'N/A'}] {action}: {details}")

        # 1. Save to Database
        try:
            actor_id = actor.id if actor else None
            now = utc_now().isoformat()
            query = (
                "INSERT INTO ticket_logs (guild_id, ticket_id, action, actor_id, details, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?);"
            )
            await self.db.execute(query, (guild.id, ticket_id, action, actor_id, details, now))
        except Exception as e:
            logger.error(f"Failed to record ticket log in database: {e}", exc_info=True)

        # 2. Dispatch to Discord Log Channel
        try:
            setting = await self.db.fetch_one(
                "SELECT log_channel_id, panel_channel_id FROM settings WHERE guild_id = ?;",
                (guild.id,),
            )
            panel_id = setting["panel_channel_id"] if setting and "panel_channel_id" in setting.keys() else None
            log_channel_id = (
                setting["log_channel_id"] if setting and setting["log_channel_id"] else DEFAULT_LOG_CHANNEL_ID
            ) or 1553102113268047874

            # Strictly prevent sending audit logs into the public ticket panel channel!
            if log_channel_id and (log_channel_id == panel_id or log_channel_id == 1552438033176072352):
                log_channel_id = 1553102113268047874

            if log_channel_id:
                log_channel = guild.get_channel(log_channel_id)
                if not log_channel:
                    try:
                        log_channel = await guild.fetch_channel(log_channel_id)
                    except Exception:
                        log_channel = None
                if log_channel and (isinstance(log_channel, (discord.TextChannel, discord.Thread)) or hasattr(log_channel, "send")):
                    embed = audit_log_embed(action, actor, ticket_id, details, channel)
                    try:
                        await log_channel.send(embed=embed)
                    except Exception as se:
                        logger.warning(f"Could not send Discord audit log message to channel {log_channel_id}: {se}")
        except Exception as e:
            logger.error(f"Failed to process Discord audit log message: {e}", exc_info=True)


log_service = LoggingService()
