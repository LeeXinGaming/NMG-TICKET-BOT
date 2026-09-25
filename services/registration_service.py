"""
Registration Service - Manages user registration, role assignment, verification, and audit logs.
Ensures only verified/registered users can create support tickets across the server.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional, Tuple, Union

import discord

from config import REQUIRE_REGISTRATION, DEFAULT_REGISTERED_ROLE_ID
from database.database import Database, db
from utils.embeds import registration_audit_embed
from utils.helpers import utc_now
from utils.permissions import is_support_staff

logger = logging.getLogger("ticketbot.registration")


class RegistrationService:
    def __init__(self, database: Database = db):
        self.db = database

    async def get_guild_settings(self, guild_id: int) -> dict:
        """Fetch guild settings with registration defaults."""
        row = await self.db.fetch_one("SELECT * FROM settings WHERE guild_id = ?;", (guild_id,))
        if not row:
            return {
                "guild_id": guild_id,
                "require_registration": int(REQUIRE_REGISTRATION),
                "registered_role_id": DEFAULT_REGISTERED_ROLE_ID,
                "registration_channel_id": None,
                "log_channel_id": None,
            }
        # Merge fallbacks for newly added columns if None
        settings = dict(row)
        if settings.get("require_registration") is None:
            settings["require_registration"] = int(REQUIRE_REGISTRATION)
        if settings.get("registered_role_id") is None:
            settings["registered_role_id"] = DEFAULT_REGISTERED_ROLE_ID
        return settings


    async def is_registered(
        self,
        guild_id: int,
        user: Union[discord.User, discord.Member],
    ) -> Tuple[bool, Optional[dict]]:
        """
        Check if user is registered and eligible to create tickets.
        Returns (is_registered, registered_data_dict_or_None).
        """
        settings = await self.get_guild_settings(guild_id)

        # 1. If registration is disabled on this server, everyone is permitted
        if not settings.get("require_registration", 1):
            return True, None

        # 2. Administrator & Staff bypass
        support_role_id = settings.get("support_role_id")
        if is_support_staff(user, support_role_id):
            return True, {"full_name": getattr(user, "display_name", str(user)), "phone_or_id": "Staff"}

        # 3. Check database record
        row = await self.db.fetch_one(
            """
            SELECT * FROM registered_users
            WHERE guild_id = ? AND discord_user_id = ? AND status = 'registered';
            """,
            (guild_id, user.id),
        )
        if row:
            return True, dict(row)

        # 4. Check if member already possesses the Registered Role in Discord
        reg_role_id = settings.get("registered_role_id")
        if reg_role_id and isinstance(user, discord.Member):
            if any(r.id == reg_role_id for r in user.roles):
                # Auto-record into DB for consistent tracking
                now = utc_now().isoformat()
                try:
                    await self.db.execute(
                        """
                        INSERT INTO registered_users (guild_id, discord_user_id, username, full_name, phone_or_id, status, registered_at)
                        VALUES (?, ?, ?, ?, ?, 'registered', ?)
                        ON CONFLICT(guild_id, discord_user_id) DO UPDATE SET status = 'registered';
                        """,
                        (guild_id, user.id, user.name, user.display_name, "Role-Verified", now),
                    )
                except Exception:
                    pass
                return True, {"full_name": user.display_name, "phone_or_id": "Role-Verified"}

        return False, None

    async def register_user(
        self,
        guild: discord.Guild,
        user: Union[discord.User, discord.Member],
        full_name: str,
        phone_or_id: str,
        notes: Optional[str] = None,
        registered_by: Optional[int] = None,
    ) -> Tuple[bool, str, Optional[dict]]:
        """
        Register a user with their character name, phone/ID, and optional notes.
        Assigns the registered role and logs the audit event.
        """
        full_name = full_name.strip()
        phone_or_id = phone_or_id.strip()
        notes = notes.strip() if notes else None

        if not full_name:
            return False, "Full Name / Character Name cannot be empty.", None
        if not phone_or_id:
            return False, "Character ID / Phone Number cannot be empty.", None

        now = utc_now().isoformat()
        reg_by = registered_by or user.id

        # Upsert user record into database
        existing = await self.db.fetch_one(
            "SELECT id FROM registered_users WHERE guild_id = ? AND discord_user_id = ?;",
            (guild.id, user.id),
        )
        if existing:
            await self.db.execute(
                """
                UPDATE registered_users
                SET username = ?, full_name = ?, phone_or_id = ?, notes = ?, status = 'registered',
                    registered_at = ?, registered_by = ?
                WHERE guild_id = ? AND discord_user_id = ?;
                """,
                (user.name, full_name, phone_or_id, notes, now, reg_by, guild.id, user.id),
            )
        else:
            await self.db.execute(
                """
                INSERT INTO registered_users (guild_id, discord_user_id, username, full_name, phone_or_id, notes, status, registered_at, registered_by)
                VALUES (?, ?, ?, ?, ?, ?, 'registered', ?, ?);
                """,
                (guild.id, user.id, user.name, full_name, phone_or_id, notes, now, reg_by),
            )

        reg_data = {
            "guild_id": guild.id,
            "discord_user_id": user.id,
            "username": user.name,
            "full_name": full_name,
            "phone_or_id": phone_or_id,
            "notes": notes,
            "status": "registered",
            "registered_at": now,
            "registered_by": reg_by,
        }

        # Attempt to grant registered role if configured
        settings = await self.get_guild_settings(guild.id)
        reg_role_id = settings.get("registered_role_id")
        member = guild.get_member(user.id)
        if reg_role_id and member:
            role = guild.get_role(reg_role_id)
            if role and role not in member.roles:
                try:
                    await member.add_roles(role, reason="User Registration Completed")
                    logger.info(f"Granted registered role {role.name} to {member.name} ({member.id})")
                except discord.Forbidden:
                    logger.warning(f"Bot lacks permission to grant role {role.name} to {member.name}")
                except Exception as e:
                    logger.error(f"Error adding registered role to {member.name}: {e}")

        # Dispatch audit embed to Registration Log or Audit Log channel
        log_channel_id = settings.get("registration_channel_id") or settings.get("log_channel_id")
        if log_channel_id:
            log_chan = guild.get_channel(log_channel_id)
            if log_chan and isinstance(log_chan, discord.TextChannel):
                try:
                    embed = registration_audit_embed(
                        actor=user,
                        full_name=full_name,
                        phone_or_id=phone_or_id,
                        notes=notes,
                        action="User Registered",
                    )
                    await log_chan.send(embed=embed)
                except Exception as e:
                    logger.warning(f"Failed sending registration audit log: {e}")

        return True, "Registration completed successfully.", reg_data

    async def unregister_user(
        self,
        guild: discord.Guild,
        user_id: int,
        actor: Union[discord.User, discord.Member],
    ) -> Tuple[bool, str]:
        """Unregister / revoke registration for a user."""
        row = await self.db.fetch_one(
            "SELECT * FROM registered_users WHERE guild_id = ? AND discord_user_id = ?;",
            (guild.id, user_id),
        )
        if not row or row["status"] != "registered":
            return False, "This user is not currently registered."

        await self.db.execute(
            "UPDATE registered_users SET status = 'unregistered' WHERE guild_id = ? AND discord_user_id = ?;",
            (guild.id, user_id),
        )

        # Remove registered role if user has it
        settings = await self.get_guild_settings(guild.id)
        reg_role_id = settings.get("registered_role_id")
        member = guild.get_member(user_id)
        if reg_role_id and member:
            role = guild.get_role(reg_role_id)
            if role and role in member.roles:
                try:
                    await member.remove_roles(role, reason=f"Registration revoked by {actor.name}")
                except Exception as e:
                    logger.warning(f"Could not remove registered role: {e}")

        # Audit log
        log_channel_id = settings.get("registration_channel_id") or settings.get("log_channel_id")
        if log_channel_id:
            log_chan = guild.get_channel(log_channel_id)
            if log_chan and isinstance(log_chan, discord.TextChannel):
                try:
                    embed = discord.Embed(
                        title="🚫 Member Unregistered",
                        description=f"<@{user_id}> was unregistered by {actor.mention}.",
                        color=0xED4245,
                    )
                    await log_chan.send(embed=embed)
                except Exception:
                    pass

        return True, f"User <@{user_id}> has been unregistered."

    async def get_registered_user(self, guild_id: int, user_id: int) -> Optional[dict]:
        """Fetch registered user profile."""
        row = await self.db.fetch_one(
            "SELECT * FROM registered_users WHERE guild_id = ? AND discord_user_id = ?;",
            (guild_id, user_id),
        )
        return dict(row) if row else None

    async def list_registered_users(
        self,
        guild_id: int,
        limit: int = 20,
        offset: int = 0,
    ) -> List[dict]:
        """List registered users with pagination."""
        rows = await self.db.fetch_all(
            """
            SELECT * FROM registered_users
            WHERE guild_id = ? AND status = 'registered'
            ORDER BY id DESC LIMIT ? OFFSET ?;
            """,
            (guild_id, limit, offset),
        )
        return rows

    async def count_registered_users(self, guild_id: int) -> int:
        """Count active registered users in guild."""
        row = await self.db.fetch_one(
            "SELECT COUNT(*) as count FROM registered_users WHERE guild_id = ? AND status = 'registered';",
            (guild_id,),
        )
        return row["count"] if row else 0


registration_service = RegistrationService()
