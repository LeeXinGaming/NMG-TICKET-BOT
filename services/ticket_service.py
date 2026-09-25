"""
Ticket Service - Core Lifecycle Manager.
Handles creation, permission overwrites, claiming, closing, reopening, deletion, and member additions.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple, Union

import discord

from config import (
    BASE_DIR,
    DEFAULT_MAX_OPEN_TICKETS,
    DEFAULT_DAILY_TICKET_LIMIT,
    DEFAULT_SUPPORT_ROLE_ID,
    DEFAULT_TICKET_CATEGORY_ID,
    DEFAULT_TRANSCRIPT_CHANNEL_ID,
    DEFAULT_LOG_CHANNEL_ID,
    TICKET_NAME_FORMAT,
)
from database.database import Database, db
from database.models import Ticket
from services.autoreply_service import autoreply_service
from services.logging_service import log_service
from services.transcript_service import transcript_service
from utils.embeds import (
    ticket_welcome_embed,
    ticket_claimed_embed,
    ticket_unclaimed_embed,
    ticket_closed_embed,
    ticket_reopened_embed,
    info_embed,
    success_embed,
    error_embed,
)
from utils.helpers import format_channel_name, sanitize_channel_name, utc_now, parse_iso
from utils.permissions import is_support_staff

logger = logging.getLogger("ticketbot.service")


class TicketService:
    def __init__(self, database: Database = db):
        self.db = database

    async def get_guild_settings(self, guild_id: int) -> dict:
        """Fetch guild settings with fallbacks."""
        row = await self.db.fetch_one("SELECT * FROM settings WHERE guild_id = ?;", (guild_id,))
        if not row:
            return {
                "guild_id": guild_id,
                "support_role_id": DEFAULT_SUPPORT_ROLE_ID,
                "ticket_category_id": DEFAULT_TICKET_CATEGORY_ID,
                "log_channel_id": DEFAULT_LOG_CHANNEL_ID,
                "transcript_channel_id": DEFAULT_TRANSCRIPT_CHANNEL_ID,
                "panel_channel_id": None,
                "panel_message_id": None,
                "max_tickets": DEFAULT_MAX_OPEN_TICKETS,
                "ticket_name_format": TICKET_NAME_FORMAT,
                "autoreply_enabled": 1,
                "require_registration": 1,
                "registered_role_id": None,
                "registration_channel_id": None,
            }
        return row

    async def get_ticket_by_channel(self, channel_id: int) -> Optional[Ticket]:
        """Fetch Ticket object by Discord Channel ID."""
        row = await self.db.fetch_one(
            "SELECT * FROM tickets WHERE discord_channel_id = ?;",
            (channel_id,),
        )
        if row:
            return Ticket(
                id=row["id"],
                discord_channel_id=row["discord_channel_id"],
                guild_id=row["guild_id"],
                user_id=row["user_id"],
                category=row["category"],
                status=row["status"],
                claimed_by=row["claimed_by"],
                created_at=row["created_at"],
                closed_at=row["closed_at"],
                closed_by=row["closed_by"],
            )
        return None

    async def get_ticket_by_id(self, ticket_id: int) -> Optional[Ticket]:
        """Fetch Ticket object by Ticket ID."""
        row = await self.db.fetch_one("SELECT * FROM tickets WHERE id = ?;", (ticket_id,))
        if row:
            return Ticket(
                id=row["id"],
                discord_channel_id=row["discord_channel_id"],
                guild_id=row["guild_id"],
                user_id=row["user_id"],
                category=row["category"],
                status=row["status"],
                claimed_by=row["claimed_by"],
                created_at=row["created_at"],
                closed_at=row["closed_at"],
                closed_by=row["closed_by"],
            )
        return None

    async def _resolve_member_or_user(
        self, guild: discord.Guild, user_id: Optional[int]
    ) -> Optional[Union[discord.Member, discord.User]]:
        """Safely resolve member or user, fetching from API if not cached in memory."""
        if not user_id:
            return None
        member = guild.get_member(user_id)
        if member:
            return member
        try:
            return await guild.fetch_member(user_id)
        except Exception:
            pass
        try:
            state = getattr(guild, "_state", None)
            if state and hasattr(state, "http"):
                user_data = await state.http.get_user(user_id)
                return discord.User(state=state, data=user_data)
        except Exception:
            pass
        return None

    async def count_open_tickets(self, guild_id: int, user_id: int) -> int:
        """Count active open tickets for a given user in a guild."""
        row = await self.db.fetch_one(
            "SELECT COUNT(*) as count FROM tickets WHERE guild_id = ? AND user_id = ? AND status = 'open';",
            (guild_id, user_id),
        )
        return row["count"] if row else 0

    async def create_ticket(
        self,
        guild: discord.Guild,
        user: Union[discord.User, discord.Member],
        category_name: str,
        initial_reason: Optional[str] = None,
    ) -> Tuple[bool, str, Optional[discord.TextChannel]]:
        """
        Creates a new private ticket channel, sets up permissions,
        writes records to database, sends welcome embed, and returns channel.
        """
        settings = await self.get_guild_settings(guild.id)
        max_tickets = settings.get("max_tickets", DEFAULT_MAX_OPEN_TICKETS)

        # 1. Check open ticket limit (Allow up to max_tickets, default 3)
        open_count = await self.count_open_tickets(guild.id, user.id)
        if open_count >= max_tickets:
            return (
                False,
                f"⚠️ **You already have {max_tickets} active open tickets! / អ្នកមាន Ticket កំពុងដំណើរការចំនួន {max_tickets} រួចហើយ**\n\n"
                "Please close an active ticket before opening a new one.\n"
                f"សូមបិទ Ticket ចាស់របស់អ្នកជាមុនសិន ទើបអាចបង្កើត Ticket ថ្មីបាន (អតិបរមា {max_tickets} ក្នុងពេលតែមួយ)។",
                None,
            )

        # 2. Check 3 tickets per day (24-hour limit)
        # Admins and support staff bypass this restriction
        support_role_id = settings.get("support_role_id")
        is_privileged = is_support_staff(user, support_role_id)

        daily_limit = DEFAULT_DAILY_TICKET_LIMIT  # 3 tickets per day
        twenty_four_hours_ago = (utc_now() - timedelta(hours=24)).isoformat()
        recent_tickets = await self.db.fetch_all(
            "SELECT created_at FROM tickets WHERE guild_id = ? AND user_id = ? AND created_at >= ? ORDER BY created_at ASC;",
            (guild.id, user.id, twenty_four_hours_ago),
        )
        daily_count = len(recent_tickets) if recent_tickets else 0

        if not is_privileged:
            if daily_count >= daily_limit:
                rem_hours = 24
                rem_minutes = 0
                try:
                    oldest_created = parse_iso(recent_tickets[0]["created_at"])
                    if oldest_created:
                        if oldest_created.tzinfo is not None:
                            oldest_created = oldest_created.replace(tzinfo=None)
                        elapsed = utc_now() - oldest_created
                        twenty_four_hours = timedelta(hours=24)
                        remaining = twenty_four_hours - elapsed if elapsed < twenty_four_hours else timedelta(0)
                        rem_hours = int(remaining.total_seconds() // 3600)
                        rem_minutes = int((remaining.total_seconds() % 3600) // 60)
                except Exception as e:
                    logger.warning(f"Error calculating remaining daily ticket limit wait time: {e}")

                return (
                    False,
                    f"⏳ **Daily Limit Reached! / ដល់កម្រិតកំណត់បង្កើត Ticket ក្នុង ១ ថ្ងៃ**\n\n"
                    f"You can create a maximum of **{daily_limit} tickets per day (24 hours)**.\n"
                    f"អ្នកអាចបង្កើត Ticket បានត្រឹមតែ **{daily_limit} ដងប៉ុណ្ណោះក្នុងរយៈពេល ២៤ ម៉ោង** (អតិបរមា {daily_limit} ដងក្នុង ១ ថ្ងៃ)។\n\n"
                    f"🕒 Please wait **{rem_hours}h {rem_minutes}m** before creating another ticket.\n"
                    f"*(សូមរង់ចាំ {rem_hours} ម៉ោង {rem_minutes} នាទីទៀត ដើម្បីបង្កើត Ticket បន្ទាប់)*",
                    None,
                )

        # 3. Resolve Category & Support Role
        cat_id = settings.get("ticket_category_id")
        discord_category = None
        for candidate_cat_id in (cat_id, 1552438033176072352):
            if candidate_cat_id and not discord_category:
                target_chan = guild.get_channel(candidate_cat_id)
                if not target_chan:
                    try:
                        target_chan = await guild.fetch_channel(candidate_cat_id)
                    except Exception:
                        target_chan = None
                if target_chan:
                    if isinstance(target_chan, discord.CategoryChannel):
                        discord_category = target_chan
                    elif hasattr(target_chan, "category") and isinstance(target_chan.category, discord.CategoryChannel):
                        # If candidate ID is a text channel (like 1552438033176072352), adopt its parent category!
                        discord_category = target_chan.category

        support_role_id = settings.get("support_role_id")
        support_role = None
        if support_role_id:
            support_role = guild.get_role(support_role_id)
            if not support_role:
                try:
                    roles = await guild.fetch_roles()
                    for r in roles:
                        if r.id == support_role_id:
                            support_role = r
                            break
                except Exception:
                    pass

        special_staff_member = None
        for staff_check_id in (support_role_id, 1552441867499733124, 1552438033176072352):
            if staff_check_id and not special_staff_member:
                special_staff_member = guild.get_member(staff_check_id)
                if not special_staff_member:
                    try:
                        special_staff_member = await guild.fetch_member(staff_check_id)
                    except Exception:
                        special_staff_member = None

        # 3. Create initial DB placeholder to reserve ticket ID
        now = utc_now().isoformat()
        temp_query = (
            "INSERT INTO tickets (discord_channel_id, guild_id, user_id, category, status, created_at) "
            "VALUES (?, ?, ?, ?, 'open', ?);"
        )
        ticket_id = await self.db.execute_returning_id(
            temp_query,
            (0, guild.id, user.id, category_name, now),
        )

        # 4. Save/update user entry
        try:
            await self.db.execute(
                "INSERT INTO users (discord_user_id, username, created_at) VALUES (?, ?, ?) "
                "ON CONFLICT(discord_user_id) DO UPDATE SET username = excluded.username;",
                (user.id, user.name, now),
            )
        except Exception:
            # Fallback if SQLite without ON CONFLICT syntax
            existing_user = await self.db.fetch_one("SELECT id FROM users WHERE discord_user_id = ?;", (user.id,))
            if not existing_user:
                await self.db.execute(
                    "INSERT INTO users (discord_user_id, username, created_at) VALUES (?, ?, ?);",
                    (user.id, user.name, now),
                )

        # 5. Determine channel name
        name_format = settings.get("ticket_name_format", TICKET_NAME_FORMAT)
        channel_name = format_channel_name(name_format, ticket_id, user.name)

        # 6. Configure Channel Permissions
        target_user = await self._resolve_member_or_user(guild, user.id) or user

        # Resolve default_role (@everyone)
        default_role = guild.default_role or guild.get_role(guild.id)
        if not default_role:
            try:
                roles = await guild.fetch_roles()
                for r in roles:
                    if r.id == guild.id:
                        default_role = r
                        break
            except Exception:
                pass
        if not default_role:
            class _EveryoneRoleFallback(discord.Role):
                def __init__(self, gid: int):
                    self.id = gid
                    self.name = "@everyone"
                    self._permissions = 0
                def __str__(self):
                    return self.name
            default_role = _EveryoneRoleFallback(guild.id)

        # Resolve bot user/member in guild
        bot_target = guild.me
        if not bot_target:
            client_user = getattr(getattr(guild, "_state", None), "user", None)
            if client_user:
                bot_target = guild.get_member(client_user.id)
                if not bot_target:
                    try:
                        bot_target = await guild.fetch_member(client_user.id)
                    except Exception:
                        bot_target = client_user
            if not bot_target:
                state = getattr(guild, "_state", None)
                if state and hasattr(state, "client") and getattr(state.client, "user", None):
                    bot_target = state.client.user

        overwrites = {}

        if default_role and getattr(default_role, "id", None) is not None:
            overwrites[default_role] = discord.PermissionOverwrite(
                view_channel=False,
            )

        if bot_target and getattr(bot_target, "id", None) is not None:
            overwrites[bot_target] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                embed_links=True,
                attach_files=True,
            )

        if target_user and getattr(target_user, "id", None) is not None:
            overwrites[target_user] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=False,  # Locked until staff claims!
                read_message_history=True,
                embed_links=False,
                attach_files=False,
            )

        if support_role and getattr(support_role, "id", None) is not None:
            overwrites[support_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                embed_links=True,
                attach_files=True,
            )

        if special_staff_member and getattr(special_staff_member, "id", None) is not None:
            overwrites[special_staff_member] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                embed_links=True,
                attach_files=True,
            )

        # STRICT GUARANTEE: Never include None keys or keys without .id
        clean_overwrites = {
            target: perm
            for target, perm in overwrites.items()
            if target is not None and getattr(target, "id", None) is not None
        }

        # 7. Create Ticket Channel / Thread with Cascading Fallbacks
        channel = None
        creation_error = None

        # Attempt 1: Standard Text Channel with Category and Overwrites
        try:
            channel = await guild.create_text_channel(
                name=channel_name,
                category=discord_category,
                overwrites=clean_overwrites,
                topic=f"Support Ticket #{ticket_id:06d} | User: {user.name} ({user.id}) | Category: {category_name}",
                reason=f"Support ticket created by {user.name}",
            )
        except Exception as e1:
            creation_error = e1
            logger.warning(f"Attempt 1 (Text Channel with Category) failed: {e1}")

        # Attempt 2: Text Channel without Category with Overwrites
        if not channel and discord_category is not None:
            try:
                channel = await guild.create_text_channel(
                    name=channel_name,
                    category=None,
                    overwrites=clean_overwrites,
                    topic=f"Support Ticket #{ticket_id:06d} | User: {user.name} ({user.id}) | Category: {category_name}",
                    reason=f"Support ticket created by {user.name} (no-category fallback)",
                )
            except Exception as e2:
                creation_error = e2
                logger.warning(f"Attempt 2 (Text Channel without Category) failed: {e2}")

        # Attempt 3: Text Channel with Category without initial overwrites
        if not channel:
            try:
                channel = await guild.create_text_channel(
                    name=channel_name,
                    category=discord_category,
                    topic=f"Support Ticket #{ticket_id:06d} | User: {user.name} ({user.id}) | Category: {category_name}",
                    reason=f"Support ticket created by {user.name} (clean category fallback)",
                )
                for target, perm in clean_overwrites.items():
                    try:
                        await channel.set_permissions(target, overwrite=perm)
                    except Exception as pe:
                        logger.warning(f"Could not apply overwrite for {target}: {pe}")
            except Exception as e3:
                creation_error = e3
                logger.warning(f"Attempt 3 (Text Channel with Category, no overwrites) failed: {e3}")

        # Attempt 4: Text Channel without Category and without initial overwrites
        if not channel:
            try:
                channel = await guild.create_text_channel(
                    name=channel_name,
                    category=None,
                    topic=f"Support Ticket #{ticket_id:06d} | User: {user.name} ({user.id}) | Category: {category_name}",
                    reason=f"Support ticket created by {user.name} (bare text channel fallback)",
                )
                for target, perm in clean_overwrites.items():
                    try:
                        await channel.set_permissions(target, overwrite=perm)
                    except Exception as pe:
                        logger.warning(f"Could not apply overwrite for {target}: {pe}")
            except Exception as e4:
                creation_error = e4
                logger.warning(f"Attempt 4 (Bare Text Channel) failed: {e4}")

        # Attempt 5: Create Thread in Host Channel (1552438033176072352 or panel/available channel)
        if not channel:
            candidate_ids = [1552438033176072352, cat_id, settings.get("panel_channel_id")]
            host_channel = None
            for cid in candidate_ids:
                if cid:
                    ch = guild.get_channel(cid)
                    if not ch:
                        try:
                            ch = await guild.fetch_channel(cid)
                        except Exception:
                            ch = None
                    if ch and isinstance(ch, discord.TextChannel):
                        host_channel = ch
                        break

            if not host_channel and hasattr(guild, "text_channels"):
                for tc in guild.text_channels:
                    bot_perms = tc.permissions_for(guild.me) if guild.me else None
                    if not bot_perms or bot_perms.send_messages:
                        host_channel = tc
                        break

            if host_channel:
                try:
                    logger.info(f"Attempting to create ticket thread in {host_channel.name} ({host_channel.id})...")
                    try:
                        channel = await host_channel.create_thread(
                            name=channel_name,
                            type=discord.ChannelType.private_thread,
                            reason=f"Support ticket created by {user.name}",
                        )
                    except Exception as pt_err:
                        logger.warning(f"Private thread creation failed ({pt_err}), attempting public thread...")
                        channel = await host_channel.create_thread(
                            name=channel_name,
                            type=discord.ChannelType.public_thread,
                            reason=f"Support ticket created by {user.name} (fallback public thread)",
                        )
                    if channel:
                        try:
                            await channel.add_user(user)
                        except Exception:
                            pass
                        if special_staff_member:
                            try:
                                await channel.add_user(special_staff_member)
                            except Exception:
                                pass
                except Exception as th_err:
                    creation_error = th_err
                    logger.error(f"Attempt 5 (Thread Creation) failed: {th_err}")

        # If all attempts failed:
        if not channel:
            await self.db.execute("DELETE FROM tickets WHERE id = ?;", (ticket_id,))
            logger.error(f"All channel creation attempts failed: {creation_error}", exc_info=True)
            bot_id = getattr(bot_target, "id", 1552440805187264522)
            invite_link = f"https://discord.com/oauth2/authorize?client_id={bot_id}&permissions=8&scope=bot%20applications.commands"
            return (
                False,
                f"❌ **Bot មិនទាន់មានសិទ្ធិគ្រប់គ្រង Channel ឡើយ (Missing Permissions)**\n\n"
                f"សូមអញ្ជើញ Bot ម្តងទៀត ឬកំណត់សិទ្ធិ:\n"
                f"1. ចូលទៅកាន់ **Server Settings > Roles > Bot Role** ហើយបើក **Administrator** ឬ **Manage Channels**\n"
                f"2. ឬចុច Link នេះដើម្បីផ្តល់សិទ្ធិ Admin ដោយផ្ទាល់: [ចុចទីនេះដើម្បី Invite/Re-authorize Bot]({invite_link})\n\n"
                f"*(Please grant the bot 'Manage Channels' or 'Administrator' in Server Settings)*",
                None,
            )

        # 8. Update DB with real channel ID
        await self.db.execute(
            "UPDATE tickets SET discord_channel_id = ? WHERE id = ?;",
            (channel.id, ticket_id),
        )

        # 9. Send Welcome Embed and Ticket Controls
        from views.ticket_view import TicketControlView

        daily_display = f"{min(daily_count + 1, daily_limit)}/{daily_limit}" if not is_privileged else "Unlimited (Staff)"
        welcome_embed = ticket_welcome_embed(
            ticket_id=ticket_id,
            user=user,
            category_name=category_name,
            created_at_iso=now,
            registered_info=None,
            daily_info=daily_display,
        )
        if initial_reason:
            welcome_embed.add_field(name="📝 Inquiry Details", value=initial_reason[:1024], inline=False)

        view = TicketControlView()
        
        # Ping user and support role
        if support_role:
            support_mention = support_role.mention
        elif special_staff_member:
            support_mention = special_staff_member.mention
        elif support_role_id:
            support_mention = f"<@&{support_role_id}>"
        else:
            support_mention = "Support Staff"
        content_mention = f"{user.mention} | {support_mention}"

        image_path = BASE_DIR / "assets" / "nightmare.png"
        if image_path.exists():
            welcome_embed.set_image(url="attachment://nightmare.png")
            welcome_file = discord.File(str(image_path), filename="nightmare.png")
            welcome_message = await channel.send(
                content=content_mention,
                embed=welcome_embed,
                file=welcome_file,
                view=view,
            )
        else:
            welcome_message = await channel.send(
                content=content_mention,
                embed=welcome_embed,
                view=view,
            )

        # 10. Send Category Auto Reply if enabled
        if settings.get("autoreply_enabled", 1):
            category_reply = await autoreply_service.get_reply_for_category(category_name)
            if category_reply:
                reply_embed = discord.Embed(
                    description=category_reply,
                    color=0x5865F2,
                )
                bot_member = getattr(guild, "me", None)
                bot_avatar = bot_member.display_avatar.url if bot_member and hasattr(bot_member, "display_avatar") else None
                if bot_avatar:
                    reply_embed.set_author(name="Support Assistant", icon_url=bot_avatar)
                else:
                    reply_embed.set_author(name="Support Assistant")
                await channel.send(embed=reply_embed)

        # 11. Log audit event
        await log_service.log_event(
            guild=guild,
            action="Ticket Created",
            actor=user,
            ticket_id=ticket_id,
            details=f"Ticket #{ticket_id:06d} opened by {user.mention} in category '{category_name}'.",
            channel=channel,
        )

        return True, f"Ticket created: {channel.mention}", channel

    async def claim_ticket(
        self,
        channel: Union[discord.TextChannel, discord.Thread],
        staff: discord.Member,
    ) -> Tuple[bool, str]:
        """Claim a ticket for a staff member."""
        ticket = await self.get_ticket_by_channel(channel.id)
        if not ticket:
            return False, "❌ នេះមិនមែនជា Channel Ticket ទេ។ (Not an active ticket channel)"

        if ticket.claimed_by:
            if ticket.claimed_by == staff.id:
                return False, "ℹ️ អ្នកបានទទួលយក (Claim) Ticket នេះរួចហើយ។ (You have already claimed this ticket)"
            return False, f"⚠️ Ticket នេះត្រូវបានទទួលយកដោយ <@{ticket.claimed_by}> រួចហើយ។"

        now = utc_now().isoformat()
        await self.db.execute(
            "UPDATE tickets SET claimed_by = ? WHERE id = ?;",
            (staff.id, ticket.id),
        )
        await self.db.execute(
            "INSERT INTO ticket_claims (ticket_id, staff_id, staff_name, claimed_at) VALUES (?, ?, ?, ?);",
            (ticket.id, staff.id, staff.display_name, now),
        )

        # Unlock chat permissions for ticket creator
        target_user = await self._resolve_member_or_user(channel.guild, ticket.user_id)
        if target_user:
            if isinstance(channel, discord.Thread):
                try:
                    await channel.add_user(target_user)
                except Exception as e:
                    logger.warning(f"Could not add user {ticket.user_id} to thread: {e}")
            else:
                try:
                    await channel.set_permissions(
                        target_user,
                        view_channel=True,
                        send_messages=True,
                        send_messages_in_threads=True,
                        read_message_history=True,
                        embed_links=True,
                        attach_files=True,
                        add_reactions=True,
                        use_external_emojis=True,
                    )
                    logger.info(f"Unlocked chat permissions for {getattr(target_user, 'name', ticket.user_id)} in {channel.name}")
                except Exception as e:
                    logger.warning(f"Could not unlock chat permissions for {ticket.user_id}: {e}")
        else:
            logger.warning(f"Could not resolve member or user for ticket owner ID: {ticket.user_id}")

        # Notify inside channel
        embed = ticket_claimed_embed(staff)
        try:
            await channel.send(embed=embed)
        except Exception:
            pass

        # Audit log
        await log_service.log_event(
            guild=channel.guild,
            action="Ticket Claimed",
            actor=staff,
            ticket_id=ticket.id,
            details=f"Ticket #{ticket.id:06d} was claimed by {staff.mention}.",
            channel=channel,
        )
        return True, f"Ticket ត្រូវបានទទួលយកដោយ {staff.mention}។ (Ticket claimed)"

    async def unclaim_ticket(
        self,
        channel: Union[discord.TextChannel, discord.Thread],
        staff: discord.Member,
    ) -> Tuple[bool, str]:
        """Release claim on a ticket."""
        ticket = await self.get_ticket_by_channel(channel.id)
        if not ticket:
            return False, "❌ នេះមិនមែនជា Channel Ticket ទេ។ (Not an active ticket channel)"

        if not ticket.claimed_by:
            return False, "⚠️ Ticket នេះមិនទាន់មានបុគ្គលិកទទួលយកនៅឡើយទេ។ (Not currently claimed)"

        now = utc_now().isoformat()
        await self.db.execute(
            "UPDATE tickets SET claimed_by = NULL WHERE id = ?;",
            (ticket.id,),
        )
        await self.db.execute(
            "UPDATE ticket_claims SET released_at = ? WHERE ticket_id = ? AND staff_id = ? AND released_at IS NULL;",
            (now, ticket.id, staff.id),
        )

        # Lock chat permissions for ticket creator again until claimed
        target_user = await self._resolve_member_or_user(channel.guild, ticket.user_id)
        if target_user and not isinstance(channel, discord.Thread):
            try:
                await channel.set_permissions(
                    target_user,
                    view_channel=True,
                    send_messages=False,
                    send_messages_in_threads=False,
                    read_message_history=True,
                    embed_links=False,
                    attach_files=False,
                )
            except Exception as e:
                logger.warning(f"Could not lock chat permissions for {ticket.user_id}: {e}")

        embed = ticket_unclaimed_embed(staff)
        try:
            await channel.send(embed=embed)
        except Exception:
            pass

        await log_service.log_event(
            guild=channel.guild,
            action="Ticket Unclaimed",
            actor=staff,
            ticket_id=ticket.id,
            details=f"Ticket #{ticket.id:06d} was released by {staff.mention}.",
            channel=channel,
        )
        return True, "បានបោះបង់ការទទួល Ticket ជោគជ័យ។ (Ticket claim released)"

    async def close_ticket(
        self,
        channel: Union[discord.TextChannel, discord.Thread],
        actor: Union[discord.User, discord.Member],
        reason: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """Close a ticket, lock send permissions, generate transcript, and rename channel."""
        ticket = await self.get_ticket_by_channel(channel.id)
        if not ticket:
            return False, "❌ នេះមិនមែនជា Channel Ticket ទេ។ (Not an active ticket channel)"

        if ticket.status == "closed":
            return False, "⚠️ Ticket នេះត្រូវបានបិទរួចហើយ។ (Already closed)"

        now = utc_now().isoformat()
        await self.db.execute(
            "UPDATE tickets SET status = 'closed', closed_at = ?, closed_by = ? WHERE id = ?;",
            (now, actor.id, ticket.id),
        )
        ticket.status = "closed"
        ticket.closed_at = now
        ticket.closed_by = actor.id

        # Lock user permissions in channel / thread
        ticket_creator = await self._resolve_member_or_user(channel.guild, ticket.user_id)
        if isinstance(channel, discord.Thread):
            try:
                await channel.edit(locked=True, archived=True)
            except Exception as e:
                logger.warning(f"Could not lock/archive thread {channel.name}: {e}")
        else:
            if ticket_creator:
                try:
                    await channel.set_permissions(
                        ticket_creator,
                        view_channel=True,
                        send_messages=False,
                        send_messages_in_threads=False,
                        read_message_history=True,
                    )
                except Exception as e:
                    logger.warning(f"Could not lock chat permissions on close for {ticket.user_id}: {e}")

            # Rename channel
            try:
                await channel.edit(name=f"closed-{ticket.id:06d}", reason=f"Ticket closed by {actor.name}")
            except Exception as e:
                logger.warning(f"Could not rename channel {channel.name}: {e}")

        # Send closed embed inside channel
        closed_emb = ticket_closed_embed(actor, reason)
        try:
            await channel.send(embed=closed_emb)
        except Exception:
            pass

        # Generate Transcripts
        claimed_staff = await self._resolve_member_or_user(channel.guild, ticket.claimed_by) if ticket.claimed_by else None
        html_path = await transcript_service.generate_html(
            ticket=ticket,
            channel_name=channel.name,
            creator=ticket_creator,
            claimed_staff=claimed_staff,
            closed_by_user=actor,
        )
        txt_path = await transcript_service.generate_txt(
            ticket=ticket,
            channel_name=channel.name,
        )

        # Send transcripts to Transcript / Log Channel
        settings = await self.get_guild_settings(channel.guild.id)
        panel_id = settings.get("panel_channel_id")
        transcript_chan_id = settings.get("transcript_channel_id") or settings.get("log_channel_id") or 1553102113268047874
        if transcript_chan_id and (transcript_chan_id == panel_id or transcript_chan_id == 1552438033176072352):
            transcript_chan_id = 1553102113268047874
        if transcript_chan_id:
            t_chan = channel.guild.get_channel(transcript_chan_id)
            if not t_chan:
                try:
                    t_chan = await channel.guild.fetch_channel(transcript_chan_id)
                except Exception:
                    t_chan = None
            if t_chan and (isinstance(t_chan, (discord.TextChannel, discord.Thread)) or hasattr(t_chan, "send")):
                t_embed = discord.Embed(
                    title=f"📄 Transcript: Ticket #{ticket.id:06d}",
                    description=f"Closed by {actor.mention}. See attached HTML and TXT transcripts.",
                    color=0x2B2D31,
                )
                t_embed.add_field(name="Category", value=ticket.category, inline=True)
                t_embed.add_field(name="User", value=f"<@{ticket.user_id}>", inline=True)
                if reason:
                    t_embed.add_field(name="Close Reason", value=reason, inline=False)
                
                try:
                    await t_chan.send(
                        embed=t_embed,
                        files=[
                            discord.File(str(html_path), filename=html_path.name),
                            discord.File(str(txt_path), filename=txt_path.name),
                        ],
                    )
                except Exception as te:
                    logger.warning(f"Could not post transcript to channel {transcript_chan_id}: {te}")

        # Attempt to DM transcript to ticket owner
        if ticket_creator:
            try:
                dm_embed = discord.Embed(
                    title=f"🎫 Support Ticket #{ticket.id:06d} ត្រូវបានបិទ / Closed",
                    description=(
                        f"Ticket របស់អ្នកនៅក្នុង **{channel.guild.name}** ត្រូវបានបិទរួចរាល់ហើយ។\n"
                        f"ភ្ជាប់មកជាមួយនេះគឺឯកសារកំណត់ត្រាការសន្ទនា (Transcript) របស់អ្នក។\n\n"
                        f"*(Your ticket has been closed. Attached is your conversation transcript.)*"
                    ),
                    color=0x5865F2,
                )
                if reason:
                    dm_embed.add_field(name="មូលហេតុ / Reason", value=reason, inline=False)
                await ticket_creator.send(
                    embed=dm_embed,
                    file=discord.File(str(html_path), filename=html_path.name),
                )
            except Exception as e:
                logger.info(f"Could not DM transcript to user {ticket.user_id}: {e}")

        # Audit log
        await log_service.log_event(
            guild=channel.guild,
            action="Ticket Closed",
            actor=actor,
            ticket_id=ticket.id,
            details=f"Ticket #{ticket.id:06d} closed by {actor.mention}. Reason: {reason or 'None'}",
            channel=channel,
        )

        return True, "បានបិទ Ticket ជោគជ័យ។ (Ticket closed successfully)"

    async def reopen_ticket(
        self,
        channel: Union[discord.TextChannel, discord.Thread],
        staff: discord.Member,
    ) -> Tuple[bool, str]:
        """Reopen a closed ticket, restoring user send permissions and channel name."""
        ticket = await self.get_ticket_by_channel(channel.id)
        if not ticket:
            return False, "❌ នេះមិនមែនជា Channel Ticket ទេ។ (Not an active ticket channel)"

        if ticket.status == "open":
            return False, "ℹ️ Ticket នេះកំពុងបើកដំណើរការស្រាប់ហើយ។ (Already open)"

        await self.db.execute(
            "UPDATE tickets SET status = 'open', closed_at = NULL, closed_by = NULL WHERE id = ?;",
            (ticket.id,),
        )

        ticket_creator = await self._resolve_member_or_user(channel.guild, ticket.user_id)
        if isinstance(channel, discord.Thread):
            try:
                await channel.edit(locked=False, archived=False)
            except Exception as e:
                logger.warning(f"Could not unlock thread {channel.name}: {e}")
            if ticket_creator:
                try:
                    await channel.add_user(ticket_creator)
                except Exception:
                    pass
        else:
            # Restore permissions for creator
            if ticket_creator:
                try:
                    await channel.set_permissions(
                        ticket_creator,
                        view_channel=True,
                        send_messages=True,
                        send_messages_in_threads=True,
                        read_message_history=True,
                        embed_links=True,
                        attach_files=True,
                        add_reactions=True,
                        use_external_emojis=True,
                    )
                except Exception as e:
                    logger.warning(f"Could not restore chat permissions on reopen for {ticket.user_id}: {e}")

            # Rename channel back
            settings = await self.get_guild_settings(channel.guild.id)
            name_format = settings.get("ticket_name_format", TICKET_NAME_FORMAT)
            creator_name = ticket_creator.name if ticket_creator else "user"
            original_name = format_channel_name(name_format, ticket.id, creator_name)

            try:
                await channel.edit(name=original_name, reason=f"Ticket reopened by {staff.name}")
            except Exception as e:
                logger.warning(f"Could not rename channel {channel.name}: {e}")

        embed = ticket_reopened_embed(staff)
        try:
            await channel.send(embed=embed)
        except Exception:
            pass

        await log_service.log_event(
            guild=channel.guild,
            action="Ticket Reopened",
            actor=staff,
            ticket_id=ticket.id,
            details=f"Ticket #{ticket.id:06d} reopened by {staff.mention}.",
            channel=channel,
        )

        return True, "បានបើក Ticket ឡើងវិញជោគជ័យ។ (Ticket reopened successfully)"

    async def delete_ticket(
        self,
        channel: Union[discord.TextChannel, discord.Thread],
        staff: discord.Member,
        reason: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Permanently delete the Discord channel after generating final transcript.
        Never deletes database history.
        """
        ticket = await self.get_ticket_by_channel(channel.id)
        if not ticket:
            return False, "❌ នេះមិនមែនជា Channel Ticket ទេ។ (Not an active ticket channel)"

        # Generate final transcript before channel goes away
        ticket_creator = await self._resolve_member_or_user(channel.guild, ticket.user_id)
        claimed_staff = await self._resolve_member_or_user(channel.guild, ticket.claimed_by) if ticket.claimed_by else None

        html_path = await transcript_service.generate_html(
            ticket=ticket,
            channel_name=channel.name,
            creator=ticket_creator,
            claimed_staff=claimed_staff,
            closed_by_user=staff,
        )

        # Post to transcript/log channel
        settings = await self.get_guild_settings(channel.guild.id)
        panel_id = settings.get("panel_channel_id")
        log_id = settings.get("transcript_channel_id") or settings.get("log_channel_id") or 1553102113268047874
        if log_id and (log_id == panel_id or log_id == 1552438033176072352):
            log_id = 1553102113268047874
        if log_id:
            log_chan = channel.guild.get_channel(log_id)
            if not log_chan:
                try:
                    log_chan = await channel.guild.fetch_channel(log_id)
                except Exception:
                    log_chan = None
            if log_chan and (isinstance(log_chan, (discord.TextChannel, discord.Thread)) or hasattr(log_chan, "send")):
                del_emb = discord.Embed(
                    title=f"🗑️ Ticket #{ticket.id:06d} Channel Deleted",
                    description=f"Ticket channel deleted by {staff.mention}. Reason: {reason or 'None'}",
                    color=0xED4245,
                )
                try:
                    await log_chan.send(
                        embed=del_emb,
                        file=discord.File(str(html_path), filename=html_path.name),
                    )
                except Exception as le:
                    logger.warning(f"Could not send delete log: {le}")

        await log_service.log_event(
            guild=channel.guild,
            action="Ticket Deleted",
            actor=staff,
            ticket_id=ticket.id,
            details=f"Channel deleted for Ticket #{ticket.id:06d}. Reason: {reason or 'No reason provided.'}",
            channel=None,
        )

        # Delete the Discord channel or thread
        try:
            await channel.delete(reason=f"Ticket deleted by {staff.name}")
            return True, "Channel deleted."
        except Exception as e:
            return False, f"Failed to delete channel: {str(e)}"

    async def add_user(
        self,
        channel: Union[discord.TextChannel, discord.Thread],
        target_user: Union[discord.User, discord.Member],
        staff: discord.Member,
    ) -> Tuple[bool, str]:
        """Add user to private ticket channel or thread."""
        ticket = await self.get_ticket_by_channel(channel.id)
        if not ticket:
            return False, "❌ នេះមិនមែនជា Channel Ticket ទេ។ (Not an active ticket channel)"

        if isinstance(channel, discord.Thread):
            try:
                await channel.add_user(target_user)
            except Exception as e:
                logger.warning(f"Could not add user {target_user.id} to thread: {e}")
        else:
            try:
                await channel.set_permissions(
                    target_user,
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    embed_links=True,
                    attach_files=True,
                )
            except Exception as e:
                logger.warning(f"Could not set permissions for {target_user.id}: {e}")

        emb = success_embed(
            "បានបន្ថែមសមាជិក / User Added",
            f"✅ {target_user.mention} ត្រូវបានបន្ថែមទៅកាន់ Ticket នេះដោយ {staff.mention}។",
        )
        try:
            await channel.send(embed=emb)
        except Exception:
            pass

        await log_service.log_event(
            guild=channel.guild,
            action="User Added",
            actor=staff,
            ticket_id=ticket.id,
            details=f"{target_user.mention} was added to Ticket #{ticket.id:06d} by {staff.mention}.",
            channel=channel,
        )
        return True, f"បានបន្ថែម {target_user.mention} ទៅកាន់ Ticket ជោគជ័យ។"

    async def remove_user(
        self,
        channel: Union[discord.TextChannel, discord.Thread],
        target_user: Union[discord.User, discord.Member],
        staff: discord.Member,
    ) -> Tuple[bool, str]:
        """Remove user from ticket channel or thread."""
        ticket = await self.get_ticket_by_channel(channel.id)
        if not ticket:
            return False, "❌ នេះមិនមែនជា Channel Ticket ទេ។ (Not an active ticket channel)"

        if target_user.id == ticket.user_id:
            return False, "⚠️ មិនអាចដកម្ចាស់ Ticket ចេញពី Ticket របស់ខ្លួនឯងបានឡើយ។"

        if isinstance(channel, discord.Thread):
            try:
                await channel.remove_user(target_user)
            except Exception as e:
                logger.warning(f"Could not remove user from thread: {e}")
        else:
            try:
                await channel.set_permissions(target_user, overwrite=None)
            except Exception as e:
                logger.warning(f"Could not reset permissions for {target_user.id}: {e}")

        emb = info_embed(
            "បានដកសមាជិក / User Removed",
            f"ℹ️ {target_user.mention} ត្រូវបានដកចេញពី Ticket នេះដោយ {staff.mention}។",
        )
        try:
            await channel.send(embed=emb)
        except Exception:
            pass

        await log_service.log_event(
            guild=channel.guild,
            action="User Removed",
            actor=staff,
            ticket_id=ticket.id,
            details=f"{target_user.mention} was removed from Ticket #{ticket.id:06d} by {staff.mention}.",
            channel=channel,
        )
        return True, f"បានដក {target_user.mention} ចេញពី Ticket ជោគជ័យ។"


ticket_service = TicketService()

