"""
Admin Cog - Core Administration and Configuration Commands.
Commands:
/ticket-panel [channel]
/ticket-config (interactive view/modal configuration)
/ticket-settings (direct slash command configuration)
/ticket-stats (summary metrics & staff leaderboard)
/ticket-list (list open or closed tickets)
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

import discord
from discord import app_commands, ui
from discord.ext import commands

from config import BASE_DIR
from database.database import Database, db
from services.logging_service import log_service
from services.ticket_service import ticket_service
from utils.embeds import (
    ticket_panel_embed,
    success_embed,
    error_embed,
    info_embed,
    create_base_embed,
)
from utils.helpers import utc_now
from utils.permissions import is_admin
from views.ticket_panel import TicketPanelView

logger = logging.getLogger("ticketbot.cogs.admin")


class ConfigModal(ui.Modal, title="Ticket System Configuration"):
    """Modal to edit max tickets and name format."""

    def __init__(self, current_max: int, current_format: str):
        super().__init__()
        self.max_input = ui.TextInput(
            label="Max Open Tickets Per User",
            default=str(current_max),
            min_length=1,
            max_length=2,
            required=True,
        )
        self.format_input = ui.TextInput(
            label="Ticket Name Format",
            default=current_format,
            placeholder="e.g. ticket-{id:06d} or ticket-{username}",
            required=True,
            max_length=50,
        )
        self.add_item(self.max_input)
        self.add_item(self.format_input)

    async def on_submit(self, interaction: discord.Interaction):
        max_val_str = self.max_input.value.strip()
        fmt = self.format_input.value.strip()
        if not max_val_str.isdigit() or int(max_val_str) < 1:
            await interaction.response.send_message("❌ Max tickets must be a positive integer.", ephemeral=True)
            return

        max_val = int(max_val_str)
        await db.execute(
            "INSERT INTO settings (guild_id, max_tickets, ticket_name_format) VALUES (?, ?, ?) "
            "ON CONFLICT(guild_id) DO UPDATE SET max_tickets = excluded.max_tickets, ticket_name_format = excluded.ticket_name_format;",
            (interaction.guild.id, max_val, fmt),
        )

        await interaction.response.send_message(
            f"✅ Settings updated!\n• **Max Tickets:** `{max_val}`\n• **Format:** `{fmt}`",
            ephemeral=True,
        )


class ConfigChannelSelect(ui.ChannelSelect):
    """Channel selector for log channel or transcript channel."""

    def __init__(self, placeholder: str, config_type: str, row: int):
        super().__init__(
            placeholder=placeholder,
            channel_types=[discord.ChannelType.text],
            min_values=1,
            max_values=1,
            row=row,
        )
        self.config_type = config_type

    async def callback(self, interaction: discord.Interaction):
        channel = self.values[0]
        col = "log_channel_id" if self.config_type == "log" else "transcript_channel_id"
        await db.execute(
            f"INSERT INTO settings (guild_id, {col}) VALUES (?, ?) "
            f"ON CONFLICT(guild_id) DO UPDATE SET {col} = excluded.{col};",
            (interaction.guild.id, channel.id),
        )
        await interaction.response.send_message(
            f"✅ Configured **{self.config_type.title()} Channel** to {channel.mention}.",
            ephemeral=True,
        )


class ConfigRoleSelect(ui.RoleSelect):
    """Role selector for Support Role."""

    def __init__(self, row: int):
        super().__init__(
            placeholder="Select Support Role...",
            min_values=1,
            max_values=1,
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        role = self.values[0]
        await db.execute(
            "INSERT INTO settings (guild_id, support_role_id) VALUES (?, ?) "
            "ON CONFLICT(guild_id) DO UPDATE SET support_role_id = excluded.support_role_id;",
            (interaction.guild.id, role.id),
        )
        await interaction.response.send_message(
            f"✅ Configured **Support Role** to {role.mention}.",
            ephemeral=True,
        )


class InteractiveConfigView(ui.View):
    """Interactive Discord view for server ticket setup."""

    def __init__(self, current_settings: dict):
        super().__init__(timeout=300)
        self.current_settings = current_settings
        self.add_item(ConfigRoleSelect(row=0))
        self.add_item(ConfigChannelSelect("Select Audit Log Channel...", "log", row=1))
        self.add_item(ConfigChannelSelect("Select Transcript Channel...", "transcript", row=2))

    @ui.button(label="Edit Formats & Limits", style=discord.ButtonStyle.primary, emoji="⚙️", row=3)
    async def edit_formats(self, interaction: discord.Interaction, button: ui.Button):
        current_max = self.current_settings.get("max_tickets", 1)
        current_fmt = self.current_settings.get("ticket_name_format", "ticket-{id:06d}")
        modal = ConfigModal(current_max, current_fmt)
        await interaction.response.send_modal(modal)


class AdminCog(commands.Cog, name="Admin"):
    """Administrative management and setup commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ticket-panel", description="Send the interactive ticket panel to a channel.")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(channel="Channel where the panel will be posted (defaults to current)")
    async def ticket_panel(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None,
    ):
        """Post the support ticket panel."""
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Only server administrators can post the ticket panel.", ephemeral=True)
            return

        target_channel = channel or interaction.channel
        if not isinstance(target_channel, discord.TextChannel):
            await interaction.response.send_message("❌ Target must be a standard text channel.", ephemeral=True)
            return

        embed = ticket_panel_embed()
        view = TicketPanelView()

        image_path = BASE_DIR / "assets" / "nightmare.png"
        if image_path.exists():
            embed.set_image(url="attachment://nightmare.png")
            file = discord.File(str(image_path), filename="nightmare.png")
            msg = await target_channel.send(embed=embed, file=file, view=view)
        else:
            msg = await target_channel.send(embed=embed, view=view)

        # Save panel message ID and channel ID in DB
        await db.execute(
            "INSERT INTO settings (guild_id, panel_channel_id, panel_message_id) VALUES (?, ?, ?) "
            "ON CONFLICT(guild_id) DO UPDATE SET panel_channel_id = excluded.panel_channel_id, panel_message_id = excluded.panel_message_id;",
            (interaction.guild.id, target_channel.id, msg.id),
        )

        await interaction.response.send_message(
            f"✅ **Ticket Panel posted successfully** in {target_channel.mention}!",
            ephemeral=True,
        )

        await log_service.log_event(
            guild=interaction.guild,
            action="Panel Created",
            actor=interaction.user,
            ticket_id=None,
            details=f"Ticket panel deployed in {target_channel.mention}.",
            channel=target_channel,
        )

    @app_commands.command(name="ticket-config", description="Open interactive ticket system configuration UI.")
    @app_commands.default_permissions(administrator=True)
    async def ticket_config(self, interaction: discord.Interaction):
        """Open interactive setup view."""
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Only server administrators can configure the bot.", ephemeral=True)
            return

        settings = await ticket_service.get_guild_settings(interaction.guild.id)
        embed = create_base_embed(
            title="⚙️ Ticket System Configuration",
            description=(
                "Use the interactive menus below to configure roles, channels, and limits.\n\n"
                f"• **Support Role:** {f'<@&{settings.get('support_role_id')}>' if settings.get('support_role_id') else '*(Not Configured)*'}\n"
                f"• **Log Channel:** {f'<#{settings.get('log_channel_id')}>' if settings.get('log_channel_id') else '*(Not Configured)*'}\n"
                f"• **Transcript Channel:** {f'<#{settings.get('transcript_channel_id')}>' if settings.get('transcript_channel_id') else '*(Not Configured)*'}\n"
                f"• **Max Open Tickets:** `{settings.get('max_tickets', 1)}`\n"
                f"• **Name Format:** `{settings.get('ticket_name_format', 'ticket-{id:06d}')}`\n"
                f"• **Auto-Reply Enabled:** `{'Yes' if settings.get('autoreply_enabled', 1) else 'No'}`\n"
            ),
        )
        view = InteractiveConfigView(settings)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="ticket-settings", description="Configure ticket system parameters via command.")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        support_role="Role designated to handle tickets",
        category="Discord category to place ticket channels under",
        log_channel="Channel where audit events will be logged",
        transcript_channel="Channel where transcripts will be sent",
        max_tickets="Maximum open tickets allowed per user",
        name_format="Template for channel name (e.g. ticket-{id:06d})",
        require_registration="Whether users must register before opening tickets",
        registered_role="Role designated for registered members",
    )
    async def ticket_settings(
        self,
        interaction: discord.Interaction,
        support_role: Optional[discord.Role] = None,
        category: Optional[discord.CategoryChannel] = None,
        log_channel: Optional[discord.TextChannel] = None,
        transcript_channel: Optional[discord.TextChannel] = None,
        max_tickets: Optional[int] = None,
        name_format: Optional[str] = None,
        require_registration: Optional[bool] = None,
        registered_role: Optional[discord.Role] = None,
    ):
        """Direct settings command."""
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Only server administrators can update settings.", ephemeral=True)
            return

        settings = await ticket_service.get_guild_settings(interaction.guild.id)
        s_role_id = support_role.id if support_role else settings.get("support_role_id")
        cat_id = category.id if category else settings.get("ticket_category_id")
        log_id = log_channel.id if log_channel else settings.get("log_channel_id")
        trans_id = transcript_channel.id if transcript_channel else settings.get("transcript_channel_id")
        max_t = max_tickets if max_tickets is not None else settings.get("max_tickets", 1)
        fmt = name_format if name_format is not None else settings.get("ticket_name_format", "ticket-{id:06d}")
        req_reg = int(require_registration) if require_registration is not None else settings.get("require_registration", 1)
        reg_r_id = registered_role.id if registered_role else settings.get("registered_role_id")

        await db.execute(
            """
            INSERT INTO settings (guild_id, support_role_id, ticket_category_id, log_channel_id, transcript_channel_id, max_tickets, ticket_name_format, require_registration, registered_role_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET
                support_role_id = excluded.support_role_id,
                ticket_category_id = excluded.ticket_category_id,
                log_channel_id = excluded.log_channel_id,
                transcript_channel_id = excluded.transcript_channel_id,
                max_tickets = excluded.max_tickets,
                ticket_name_format = excluded.ticket_name_format,
                require_registration = excluded.require_registration,
                registered_role_id = excluded.registered_role_id;
            """,
            (interaction.guild.id, s_role_id, cat_id, log_id, trans_id, max_t, fmt, req_reg, reg_r_id),
        )

        embed = success_embed(
            "Settings Saved",
            f"• **Support Role:** {f'<@&{s_role_id}>' if s_role_id else 'None'}\n"
            f"• **Ticket Category:** {f'<#{cat_id}>' if cat_id else 'None'}\n"
            f"• **Log Channel:** {f'<#{log_id}>' if log_id else 'None'}\n"
            f"• **Transcript Channel:** {f'<#{trans_id}>' if trans_id else 'None'}\n"
            f"• **Max Open Tickets:** `{max_t}`\n"
            f"• **Name Format:** `{fmt}`\n"
            f"• **Require Registration:** `{'Yes' if req_reg else 'No'}`\n"
            f"• **Registered Role:** {f'<@&{reg_r_id}>' if reg_r_id else 'None'}",
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="ticket-stats", description="Display support system analytics and metrics.")
    @app_commands.default_permissions(administrator=True)
    async def ticket_stats(self, interaction: discord.Interaction):
        """View system statistics."""
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Administrator permissions required.", ephemeral=True)
            return

        guild_id = interaction.guild.id
        total_row = await db.fetch_one("SELECT COUNT(*) as count FROM tickets WHERE guild_id = ?;", (guild_id,))
        open_row = await db.fetch_one("SELECT COUNT(*) as count FROM tickets WHERE guild_id = ? AND status = 'open';", (guild_id,))
        closed_row = await db.fetch_one("SELECT COUNT(*) as count FROM tickets WHERE guild_id = ? AND status = 'closed';", (guild_id,))

        today_prefix = utc_now().strftime("%Y-%m-%d")
        today_row = await db.fetch_one(
            "SELECT COUNT(*) as count FROM tickets WHERE guild_id = ? AND created_at LIKE ?;",
            (guild_id, f"{today_prefix}%"),
        )

        month_prefix = utc_now().strftime("%Y-%m")
        month_row = await db.fetch_one(
            "SELECT COUNT(*) as count FROM tickets WHERE guild_id = ? AND created_at LIKE ?;",
            (guild_id, f"{month_prefix}%"),
        )

        # Top staff claims
        top_staff = await db.fetch_all(
            """
            SELECT staff_id, staff_name, COUNT(*) as claim_count
            FROM ticket_claims
            JOIN tickets ON ticket_claims.ticket_id = tickets.id
            WHERE tickets.guild_id = ?
            GROUP BY staff_id
            ORDER BY claim_count DESC
            LIMIT 5;
            """,
            (guild_id,),
        )

        staff_text = ""
        if top_staff:
            for idx, s in enumerate(top_staff, 1):
                staff_text += f"{idx}. <@{s['staff_id']}> ({s['staff_name']}) - **{s['claim_count']}** claims\n"
        else:
            staff_text = "*No staff claims recorded yet.*"

        embed = create_base_embed(
            title="📊 Support Ticket Analytics",
            description="Overview of server ticket activity and staff performance.",
            color=0x5865F2,
        )
        embed.add_field(name="📦 Total Tickets", value=f"`{total_row['count'] if total_row else 0}`", inline=True)
        embed.add_field(name="🟢 Open Tickets", value=f"`{open_row['count'] if open_row else 0}`", inline=True)
        embed.add_field(name="🔴 Closed Tickets", value=f"`{closed_row['count'] if closed_row else 0}`", inline=True)
        embed.add_field(name="📅 Created Today", value=f"`{today_row['count'] if today_row else 0}`", inline=True)
        embed.add_field(name="📆 Created This Month", value=f"`{month_row['count'] if month_row else 0}`", inline=True)
        embed.add_field(name="🏆 Top Support Staff", value=staff_text, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="ticket-list", description="List recent support tickets.")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(status="Filter by status: open or closed (default: all)")
    @app_commands.choices(status=[
        app_commands.Choice(name="All Tickets", value="all"),
        app_commands.Choice(name="Open Tickets", value="open"),
        app_commands.Choice(name="Closed Tickets", value="closed"),
    ])
    async def ticket_list(self, interaction: discord.Interaction, status: Optional[str] = "all"):
        """List tickets."""
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Administrator permissions required.", ephemeral=True)
            return

        guild_id = interaction.guild.id
        if status in ("open", "closed"):
            rows = await db.fetch_all(
                "SELECT * FROM tickets WHERE guild_id = ? AND status = ? ORDER BY id DESC LIMIT 15;",
                (guild_id, status),
            )
        else:
            rows = await db.fetch_all(
                "SELECT * FROM tickets WHERE guild_id = ? ORDER BY id DESC LIMIT 15;",
                (guild_id,),
            )

        if not rows:
            await interaction.response.send_message(f"ℹ️ No tickets found matching status '{status}'.", ephemeral=True)
            return

        lines = []
        for r in rows:
            stat_emoji = "🟢" if r["status"] == "open" else "🔴"
            chan_mention = f"<#{r['discord_channel_id']}>"
            user_mention = f"<@{r['user_id']}>"
            lines.append(f"{stat_emoji} `#{r['id']:06d}` | {r['category']} | User: {user_mention} | Chan: {chan_mention}")

        embed = create_base_embed(
            title=f"📋 Ticket Directory ({status.title()})",
            description="\n".join(lines),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))
