"""
Auto-Reply and Keyword Auto-Response Service.
Handles automatic greetings per category and smart keyword detection inside ticket channels.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, List, Optional

import discord

from database.database import Database, db
from database.models import AutoReply, Keyword
from utils.helpers import utc_now

logger = logging.getLogger("ticketbot.autoreply")


class AutoReplyService:
    def __init__(self, database: Database = db):
        self.db = database

    # ==========================================
    # Auto-Reply System (Category greetings)
    # ==========================================

    async def get_reply_for_category(self, category_name: str) -> Optional[str]:
        """Fetch active auto-reply greeting for a given category."""
        row = await self.db.fetch_one(
            "SELECT message, enabled FROM auto_replies WHERE LOWER(category_name) = LOWER(?);",
            (category_name,),
        )
        if row and row["enabled"]:
            return row["message"]
        return None

    async def set_reply(self, category_name: str, message: str) -> None:
        """Set or update auto-reply for category."""
        now = utc_now().isoformat()
        existing = await self.db.fetch_one(
            "SELECT id FROM auto_replies WHERE LOWER(category_name) = LOWER(?);",
            (category_name,),
        )
        if existing:
            await self.db.execute(
                "UPDATE auto_replies SET message = ?, enabled = 1, updated_at = ? WHERE id = ?;",
                (message, now, existing["id"]),
            )
        else:
            await self.db.execute(
                "INSERT INTO auto_replies (category_name, message, enabled, updated_at) VALUES (?, ?, 1, ?);",
                (category_name, message, now),
            )

    async def toggle_reply(self, category_name: str, enabled: bool) -> bool:
        """Enable or disable auto-reply for a category."""
        existing = await self.db.fetch_one(
            "SELECT id FROM auto_replies WHERE LOWER(category_name) = LOWER(?);",
            (category_name,),
        )
        if existing:
            val = 1 if enabled else 0
            await self.db.execute(
                "UPDATE auto_replies SET enabled = ? WHERE id = ?;",
                (val, existing["id"]),
            )
            return True
        return False

    async def reset_reply(self, category_name: str) -> bool:
        """Reset auto reply for category to system default."""
        default_map = {
            "General Support": "Hello! 👋\n\nYour ticket has been received.\n\nPlease describe your question or issue in detail. A support representative will be with you shortly.",
            "Payment Support": "Hello! 👋\n\nFor payment support, please provide:\n• Your Transaction / Order ID\n• Payment method used\n• Screenshot of proof (if applicable)\n\nOur billing team will review it soon.",
            "Purchase Support": "Hello! 👋\n\nThank you for your interest! Please tell us which product or service you want to purchase or have questions about.",
            "Report Problem": "Hello! 👋\n\nThank you for reporting this issue. Please describe the problem, steps to reproduce, and attach screenshots or logs if possible.",
            "Contact Staff": "Hello! 👋\n\nA senior staff member has been notified and will reply as soon as they are available.",
            "Other": "Hello! 👋\n\nYour ticket has been opened. Please describe how we can assist you today.",
        }
        for k, v in default_map.items():
            if k.lower() == category_name.lower():
                await self.set_reply(category_name, v)
                return True
        return False

    async def list_replies(self) -> List[Dict[str, any]]:
        """List all configured category auto-replies."""
        return await self.db.fetch_all("SELECT * FROM auto_replies ORDER BY category_name ASC;")

    # ==========================================
    # Keyword Auto-Response System
    # ==========================================

    async def check_keywords(self, content: str) -> Optional[str]:
        """
        Scan message content for active keywords.
        Returns first matched response or None.
        """
        if not content:
            return None
        content_lower = content.lower()

        keywords = await self.db.fetch_all(
            "SELECT keyword, response, enabled FROM keywords WHERE enabled = 1;"
        )
        for kw in keywords:
            kw_term = kw["keyword"].lower().strip()
            # Match word or phrase boundary
            if kw_term and (kw_term in content_lower):
                return kw["response"]
        return None

    async def add_keyword(self, keyword: str, response: str, created_by: int) -> None:
        """Add or update a keyword response."""
        now = utc_now().isoformat()
        clean_kw = keyword.lower().strip()
        existing = await self.db.fetch_one(
            "SELECT id FROM keywords WHERE LOWER(keyword) = ?;",
            (clean_kw,),
        )
        if existing:
            await self.db.execute(
                "UPDATE keywords SET response = ?, enabled = 1 WHERE id = ?;",
                (response, existing["id"]),
            )
        else:
            await self.db.execute(
                "INSERT INTO keywords (keyword, response, enabled, created_by, created_at) VALUES (?, ?, 1, ?, ?);",
                (clean_kw, response, created_by, now),
            )

    async def remove_keyword(self, keyword: str) -> bool:
        """Remove a keyword response."""
        clean_kw = keyword.lower().strip()
        row = await self.db.fetch_one(
            "SELECT id FROM keywords WHERE LOWER(keyword) = ?;",
            (clean_kw,),
        )
        if row:
            await self.db.execute("DELETE FROM keywords WHERE id = ?;", (row["id"],))
            return True
        return False

    async def list_keywords(self) -> List[Dict[str, any]]:
        """List all configured keyword triggers."""
        return await self.db.fetch_all("SELECT * FROM keywords ORDER BY keyword ASC;")


autoreply_service = AutoReplyService()
