"""
Events Cog - Global event listeners, message recording, keyword execution, and error handling.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from config import GUILD_ID
from database.database import db
from services.autoreply_service import autoreply_service
from services.ticket_service import ticket_service
from utils.helpers import utc_now
from views.ticket_panel import TicketPanelView
from views.ticket_view import TicketControlView

logger = logging.getLogger("ticketbot.events")


class EventsCog(commands.Cog, name="Events"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._synced = False

    @commands.Cog.listener()
    async def on_ready(self):
        """Called when bot has connected to Discord Gateway."""
        logger.info(f"Logged in as {self.bot.user.name} ({self.bot.user.id})")
        logger.info(f"Connected to {len(self.bot.guilds)} guild(s). Gateway latency: {self.bot.latency * 1000:.1f}ms")

        # Set rich presence activity
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name="🎫 Support Tickets | /ticket-panel",
        )
        await self.bot.change_presence(status=discord.Status.online, activity=activity)

        # Register persistent views so buttons work across restarts
        self.bot.add_view(TicketPanelView())
        self.bot.add_view(TicketControlView())
        logger.info("Registered persistent views: TicketPanelView, TicketControlView")


        # Sync slash commands
        if not self._synced:
            synced_count = 0
            if GUILD_ID:
                try:
                    guild_obj = discord.Object(id=GUILD_ID)
                    self.bot.tree.copy_global_to(guild=guild_obj)
                    synced = await self.bot.tree.sync(guild=guild_obj)
                    logger.info(f"Synced {len(synced)} slash commands directly to Guild ID {GUILD_ID}.")
                    synced_count = len(synced)
                except Exception as ge:
                    logger.warning(f"Could not sync to Guild ID {GUILD_ID}: {ge}")

            # Also sync to known guilds or globally if not synced yet
            if not synced_count:
                for g in self.bot.guilds:
                    try:
                        self.bot.tree.copy_global_to(guild=g)
                        synced = await self.bot.tree.sync(guild=g)
                        logger.info(f"Synced {len(synced)} slash commands directly to Guild: {g.name} ({g.id})")
                        synced_count = len(synced)
                    except Exception:
                        pass

            if not synced_count:
                try:
                    synced = await self.bot.tree.sync()
                    logger.info(f"Synced {len(synced)} slash commands globally.")
                except Exception as e:
                    logger.error(f"Failed to sync slash commands globally: {e}")

            self._synced = True

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        """Automatically sync slash commands immediately when added to a server."""
        logger.info(f"Joined new guild: {guild.name} ({guild.id})")
        try:
            guild_obj = discord.Object(id=guild.id)
            self.bot.tree.copy_global_to(guild=guild_obj)
            synced = await self.bot.tree.sync(guild=guild_obj)
            logger.info(f"Instantly synced {len(synced)} slash commands to newly joined guild: {guild.name}")
        except Exception as e:
            logger.error(f"Failed to sync slash commands on join: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        """Handle legacy component clicks from old panel messages."""
        if interaction.type == discord.InteractionType.component:
            custom_id = interaction.data.get("custom_id", "")
            cat_map = {
                "ticket_panel_btn_general": "Support Ticket",
                "ticket_panel:create": "Support Ticket",
                "ticket_panel_create": "Support Ticket",
                "ticket_panel_btn_payment": "Payment Support",
                "ticket_panel_btn_purchase": "Purchase Support",
                "ticket_panel_btn_report": "Report Problem",
                "ticket_panel_btn_staff": "Contact Staff",
            }
            if custom_id in cat_map and not interaction.response.is_done():
                panel_view = TicketPanelView()
                await panel_view._handle_create(interaction, cat_map[custom_id])

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):

        """Record messages in ticket channels for transcripts and handle keyword triggers."""
        # Ignore messages from bots or DMs
        if message.author.bot or not message.guild:
            return

        # Check if message is in an active ticket channel
        ticket = await ticket_service.get_ticket_by_channel(message.channel.id)
        if not ticket:
            return

        # 1. Record message in DB for HTML/TXT transcript
        att_urls = [a.url for a in message.attachments]
        att_json = json.dumps(att_urls) if att_urls else ""
        now = utc_now().isoformat()

        try:
            await db.execute(
                """
                INSERT INTO ticket_messages (ticket_id, message_id, author_id, author_name, content, attachments, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    ticket.id,
                    message.id,
                    message.author.id,
                    message.author.display_name,
                    message.content,
                    att_json,
                    now,
                ),
            )
        except Exception as e:
            logger.error(f"Failed to log ticket message: {e}", exc_info=True)

        # 2. Check for Keyword Auto-Responses (only if ticket is open)
        if ticket.is_open and message.content:
            try:
                matched_reply = await autoreply_service.check_keywords(message.content)
                if matched_reply:
                    embed = discord.Embed(
                        description=matched_reply,
                        color=0x5865F2,
                    )
                    embed.set_author(name="Support Assistant", icon_url=self.bot.user.display_avatar.url)
                    await message.channel.send(embed=embed)
            except Exception as e:
                logger.error(f"Failed processing keyword auto-response: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Global app command error handler."""
        logger.error(f"Command '{interaction.command.name if interaction.command else 'Unknown'}' error: {error}", exc_info=True)

        if isinstance(error, app_commands.MissingPermissions):
            msg = f"❌ You lack the required permissions to run this command: `{', '.join(error.missing_permissions)}`."
        elif isinstance(error, app_commands.BotMissingPermissions):
            msg = f"❌ The bot lacks required permissions in this channel: `{', '.join(error.missing_permissions)}`."
        elif isinstance(error, app_commands.CommandOnCooldown):
            msg = f"⏳ Command is on cooldown. Try again in {error.retry_after:.1f}s."
        else:
            msg = "❌ An unexpected error occurred while executing this command. Our team has been notified."

        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(EventsCog(bot))
