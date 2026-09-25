"""
Registration Cog - Slash commands for member registration and verification.
Commands:
- /register: Open registration form modal
- /register-panel [channel]: Deploy persistent registration panel
- /register-status [member]: Check registration details
- /register-user <member> <name> <phone_or_id> [notes]: Admin manually registers a user
- /unregister-user <member>: Admin revokes registration
- /register-settings [require_registration] [registered_role] [log_channel]: Configure registration
- /register-list [page]: View registered members directory
"""

from __future__ import annotations

import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from config import BASE_DIR
from database.database import db
from services.logging_service import log_service
from services.registration_service import registration_service
from utils.embeds import (
    create_base_embed,
    registration_panel_embed,
    registration_success_embed,
    success_embed,
    error_embed,
    info_embed,
)
from utils.helpers import format_iso_to_discord
from utils.permissions import is_admin
from views.registration_view import RegisterModal, RegisterPanelView

logger = logging.getLogger("ticketbot.cogs.registration")


class RegistrationCog(commands.Cog, name="Registration"):
    """Commands for member registration and verification."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="register", description="Register your character/citizen profile to access tickets.")
    async def cmd_register(self, interaction: discord.Interaction):
        """Open the registration modal."""
        if not interaction.guild:
            await interaction.response.send_message("❌ This command must be used in a server.", ephemeral=True)
            return

        modal = RegisterModal(default_name=interaction.user.display_name)
        await interaction.response.send_modal(modal)

    @app_commands.command(name="register-panel", description="Deploy the persistent Member Registration Panel.")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(channel="Channel where the registration panel will be posted (default: current channel)")
    async def cmd_register_panel(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None,
    ):
        """Deploy registration panel."""
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Administrator permissions required.", ephemeral=True)
            return

        target_channel = channel or interaction.channel
        if not isinstance(target_channel, discord.TextChannel):
            await interaction.response.send_message("❌ Target must be a standard text channel.", ephemeral=True)
            return

        embed = registration_panel_embed()
        view = RegisterPanelView()

        image_path = BASE_DIR / "assets" / "nightmare.png"
        if image_path.exists():
            embed.set_image(url="attachment://nightmare.png")
            file = discord.File(str(image_path), filename="nightmare.png")
            msg = await target_channel.send(embed=embed, file=file, view=view)
        else:
            msg = await target_channel.send(embed=embed, view=view)

        # Save registration channel in settings
        await db.execute(
            """
            INSERT INTO settings (guild_id, registration_channel_id) VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET registration_channel_id = excluded.registration_channel_id;
            """,
            (interaction.guild.id, target_channel.id),
        )

        await interaction.response.send_message(
            f"✅ **Registration Panel deployed** in {target_channel.mention}!",
            ephemeral=True,
        )

        await log_service.log_event(
            guild=interaction.guild,
            action="Registration Panel Deployed",
            actor=interaction.user,
            ticket_id=None,
            details=f"Registration panel deployed in {target_channel.mention} (Message ID: `{msg.id}`).",
            channel=target_channel,
        )

    @app_commands.command(name="register-status", description="Check registration profile and verification status.")
    @app_commands.describe(member="Member to inspect (defaults to yourself)")
    async def cmd_register_status(
        self,
        interaction: discord.Interaction,
        member: Optional[discord.Member] = None,
    ):
        """View registration info."""
        if not interaction.guild:
            await interaction.response.send_message("❌ Must be used inside a server.", ephemeral=True)
            return

        target = member or interaction.user
        reg = await registration_service.get_registered_user(interaction.guild.id, target.id)

        if not reg or reg.get("status") != "registered":
            embed = info_embed(
                "Registration Status",
                f"👤 {target.mention} is **Not Registered**.\n\n"
                "Use `/register` or click the button on the Registration Panel to register.",
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        time_str = format_iso_to_discord(reg.get("registered_at"))
        embed = create_base_embed(
            title="📋 Registration Profile",
            description=f"Verified profile for {target.mention}.",
            color=0x57F287,
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="👤 Discord User", value=f"{target.mention} (`{target.id}`)", inline=True)
        embed.add_field(name="📝 Registered Name / IC", value=f"`{reg.get('full_name')}`", inline=True)
        embed.add_field(name="🆔 Character ID / Phone", value=f"`{reg.get('phone_or_id')}`", inline=True)
        if reg.get("notes"):
            embed.add_field(name="📌 Notes", value=f"{reg.get('notes')}", inline=False)
        embed.add_field(name="🕒 Registered At", value=time_str, inline=False)
        embed.add_field(name="🛡️ System Status", value="`✅ VERIFIED (Can create tickets)`", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="register-user", description="Manually register or verify a member (Admin).")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        member="The member to register",
        character_name="Full Name or In-Game Name",
        phone_or_id="Character ID or Phone Number",
        notes="Optional notes or details",
    )
    async def cmd_register_user(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        character_name: str,
        phone_or_id: str,
        notes: Optional[str] = None,
    ):
        """Admin manually registers a member."""
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Administrator permissions required.", ephemeral=True)
            return

        success, msg, _ = await registration_service.register_user(
            guild=interaction.guild,
            user=member,
            full_name=character_name,
            phone_or_id=phone_or_id,
            notes=notes,
            registered_by=interaction.user.id,
        )

        if success:
            embed = success_embed(
                "Member Registered",
                f"✅ {member.mention} was manually registered!\n\n"
                f"• **Name / IC:** `{character_name}`\n"
                f"• **ID / Phone:** `{phone_or_id}`\n"
                f"• **Notes:** `{notes or 'None'}`\n\n"
                "This member can now open support tickets.",
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=error_embed("Registration Failed", msg), ephemeral=True)

    @app_commands.command(name="unregister-user", description="Revoke registration from a member (Admin).")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(member="The member to unregister")
    async def cmd_unregister_user(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
    ):
        """Admin revokes registration from a member."""
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Administrator permissions required.", ephemeral=True)
            return

        success, msg = await registration_service.unregister_user(
            guild=interaction.guild,
            user_id=member.id,
            actor=interaction.user,
        )

        if success:
            await interaction.response.send_message(f"✅ {msg}", ephemeral=True)
        else:
            await interaction.response.send_message(f"⚠️ {msg}", ephemeral=True)

    @app_commands.command(name="register-settings", description="Configure registration requirements and roles (Admin).")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        require_registration="Whether registration is mandatory to open tickets",
        registered_role="Role automatically assigned upon registration",
        registration_channel="Channel designated for registration panel or audit logs",
    )
    async def cmd_register_settings(
        self,
        interaction: discord.Interaction,
        require_registration: Optional[bool] = None,
        registered_role: Optional[discord.Role] = None,
        registration_channel: Optional[discord.TextChannel] = None,
    ):
        """Configure registration settings."""
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Administrator permissions required.", ephemeral=True)
            return

        settings = await registration_service.get_guild_settings(interaction.guild.id)
        current_req = settings.get("require_registration", 1)
        current_role = settings.get("registered_role_id")
        current_chan = settings.get("registration_channel_id")

        new_req = int(require_registration) if require_registration is not None else current_req
        new_role = registered_role.id if registered_role is not None else current_role
        new_chan = registration_channel.id if registration_channel is not None else current_chan

        await db.execute(
            """
            INSERT INTO settings (guild_id, require_registration, registered_role_id, registration_channel_id)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET
                require_registration = excluded.require_registration,
                registered_role_id = excluded.registered_role_id,
                registration_channel_id = excluded.registration_channel_id;
            """,
            (interaction.guild.id, new_req, new_role, new_chan),
        )

        embed = success_embed(
            "Registration Settings Saved",
            f"• **Require Registration:** `{'Yes (Active)' if new_req else 'No (Disabled)'}`\n"
            f"• **Registered Role:** {f'<@&{new_role}>' if new_role else '*(Not configured)*'}\n"
            f"• **Registration Channel:** {f'<#{new_chan}>' if new_chan else '*(Not configured)*'}",
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="register-list", description="List registered members in the server (Admin).")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(page="Page number (default: 1)")
    async def cmd_register_list(
        self,
        interaction: discord.Interaction,
        page: Optional[int] = 1,
    ):
        """List registered members."""
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Administrator permissions required.", ephemeral=True)
            return

        p = max(1, page or 1)
        limit = 15
        offset = (p - 1) * limit

        rows = await registration_service.list_registered_users(interaction.guild.id, limit=limit, offset=offset)
        total = await registration_service.count_registered_users(interaction.guild.id)

        if not rows:
            await interaction.response.send_message(f"ℹ️ No registered users found (Page {p}).", ephemeral=True)
            return

        lines = []
        for idx, r in enumerate(rows, start=offset + 1):
            time_short = r["registered_at"][:10]
            lines.append(f"`{idx}.` <@{r['discord_user_id']}> | **{r['full_name']}** (`{r['phone_or_id']}`) - *{time_short}*")

        embed = create_base_embed(
            title=f"📋 Registered Members Directory (Page {p})",
            description=f"Total Registered Users: **{total}**\n\n" + "\n".join(lines),
            color=0x5865F2,
        )
        embed.set_footer(text=f"Page {p} • Showing up to {limit} per page")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(RegistrationCog(bot))
