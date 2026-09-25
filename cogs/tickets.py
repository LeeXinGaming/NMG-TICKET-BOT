"""
Tickets Cog - Slash commands for managing ticket channels.
Commands:
/ticket-close
/ticket-reopen
/ticket-delete
/ticket-add
/ticket-remove
/ticket-claim
/ticket-unclaim
/ticket-transcript
"""

from __future__ import annotations

import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from services.ticket_service import ticket_service
from services.transcript_service import transcript_service
from utils.permissions import can_manage_ticket, is_support_staff

logger = logging.getLogger("ticketbot.cogs.tickets")


class TicketsCog(commands.Cog, name="Tickets"):
    """Commands for ticket operations within channels."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="create-ticket", description="Create a new private support ticket channel.")
    @app_commands.describe(
        category="Choose the support category for your inquiry",
        reason="Brief description of what you need assistance with (optional)",
    )
    @app_commands.choices(category=[
        app_commands.Choice(name="🎫 ជំនួយទូទៅ / General Support", value="General Support"),
        app_commands.Choice(name="💳 បង់ប្រាក់ / Payment Support", value="Payment Support"),
        app_commands.Choice(name="🛒 ការទិញទំនិញ / Purchase Support", value="Purchase Support"),
        app_commands.Choice(name="🐛 រាយការណ៍បញ្ហា / Report Problem", value="Report Problem"),
        app_commands.Choice(name="📞 ទាក់ទងបុគ្គលិក / Contact Staff", value="Contact Staff"),
    ])
    async def create_ticket(
        self,
        interaction: discord.Interaction,
        category: app_commands.Choice[str],
        reason: Optional[str] = None,
    ):
        """User command to create a ticket."""
        if not interaction.guild:
            await interaction.response.send_message("❌ Command នេះអាចប្រើបានតែនៅក្នុង Server ប៉ុណ្ណោះ។", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        success, message, channel = await ticket_service.create_ticket(
            guild=interaction.guild,
            user=interaction.user,
            category_name=category.value,
            initial_reason=reason,
        )

        if success and channel:
            await interaction.followup.send(
                f"✅ **បង្កើត Ticket ជោគជ័យ! / Ticket Created!**\n"
                f"សូមចូលទៅកាន់ Channel របស់អ្នក: {channel.mention}\n"
                f"*(Please proceed to your private support channel)*",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                f"❌ {message}",
                ephemeral=True,
            )

    @app_commands.command(name="ticket-close", description="Close the current ticket channel.")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(reason="Optional reason for closing this ticket")
    async def ticket_close(self, interaction: discord.Interaction, reason: Optional[str] = None):
        """Close current ticket."""
        if not interaction.guild or not isinstance(interaction.channel, (discord.TextChannel, discord.Thread)):
            await interaction.response.send_message("❌ ត្រូវប្រើនៅក្នុង Server Channel ប៉ុណ្ណោះ។", ephemeral=True)
            return

        ticket = await ticket_service.get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message("❌ Channel នេះមិនមែនជា Support Ticket ដែលកំពុងដំណើរការទេ។", ephemeral=True)
            return

        settings = await ticket_service.get_guild_settings(interaction.guild.id)
        if not can_manage_ticket(interaction.user, ticket, settings.get("support_role_id")):
            await interaction.response.send_message("❌ អ្នកគ្មានសិទ្ធិបិទ Ticket នេះឡើយ។", ephemeral=True)
            return

        await interaction.response.defer()
        success, msg = await ticket_service.close_ticket(
            channel=interaction.channel,
            actor=interaction.user,
            reason=reason or "បិទតាមរយៈ /ticket-close",
        )
        if not success:
            await interaction.followup.send(f"⚠️ {msg}", ephemeral=True)

    @app_commands.command(name="ticket-reopen", description="Reopen a closed ticket channel.")
    @app_commands.default_permissions(administrator=True)
    async def ticket_reopen(self, interaction: discord.Interaction):

        """Reopen closed ticket."""
        if not interaction.guild or not isinstance(interaction.channel, (discord.TextChannel, discord.Thread)):
            await interaction.response.send_message("❌ Must be used in a server channel.", ephemeral=True)
            return

        ticket = await ticket_service.get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message("❌ This channel is not a ticket.", ephemeral=True)
            return

        settings = await ticket_service.get_guild_settings(interaction.guild.id)
        if not is_support_staff(interaction.user, settings.get("support_role_id")):
            await interaction.response.send_message("❌ Only support staff or admins can reopen tickets.", ephemeral=True)
            return

        await interaction.response.defer()
        success, msg = await ticket_service.reopen_ticket(channel=interaction.channel, staff=interaction.user)
        if not success:
            await interaction.followup.send(f"⚠️ {msg}", ephemeral=True)

    @app_commands.command(name="ticket-delete", description="Permanently delete this ticket channel.")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(reason="Optional deletion reason")
    async def ticket_delete(self, interaction: discord.Interaction, reason: Optional[str] = None):
        """Delete ticket channel."""
        if not interaction.guild or not isinstance(interaction.channel, (discord.TextChannel, discord.Thread)):
            await interaction.response.send_message("❌ Must be used in a server channel.", ephemeral=True)
            return

        ticket = await ticket_service.get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message("❌ This channel is not a ticket.", ephemeral=True)
            return

        settings = await ticket_service.get_guild_settings(interaction.guild.id)
        if not is_support_staff(interaction.user, settings.get("support_role_id")):
            await interaction.response.send_message("❌ Only support staff or admins can delete tickets.", ephemeral=True)
            return

        await interaction.response.send_message("🗑️ Deleting ticket channel...", ephemeral=True)
        await ticket_service.delete_ticket(
            channel=interaction.channel,
            staff=interaction.user,
            reason=reason or "Deleted via /ticket-delete",
        )

    @app_commands.command(name="ticket-add", description="Add a member to the current ticket.")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(user="The member to add to this ticket")
    async def ticket_add(self, interaction: discord.Interaction, user: discord.Member):
        """Add member to ticket."""
        if not interaction.guild or not isinstance(interaction.channel, (discord.TextChannel, discord.Thread)):
            await interaction.response.send_message("❌ Must be used in a server channel.", ephemeral=True)
            return

        ticket = await ticket_service.get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message("❌ This channel is not an active ticket.", ephemeral=True)
            return

        settings = await ticket_service.get_guild_settings(interaction.guild.id)
        if not is_support_staff(interaction.user, settings.get("support_role_id")):
            await interaction.response.send_message("❌ Only support staff or admins can add members.", ephemeral=True)
            return

        success, msg = await ticket_service.add_user(
            channel=interaction.channel,
            target_user=user,
            staff=interaction.user,
        )
        await interaction.response.send_message(f"{'✅' if success else '❌'} {msg}", ephemeral=True)

    @app_commands.command(name="ticket-remove", description="Remove a member from the current ticket.")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(user="The member to remove from this ticket")
    async def ticket_remove(self, interaction: discord.Interaction, user: discord.Member):
        """Remove member from ticket."""
        if not interaction.guild or not isinstance(interaction.channel, (discord.TextChannel, discord.Thread)):
            await interaction.response.send_message("❌ Must be used in a server channel.", ephemeral=True)
            return

        ticket = await ticket_service.get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message("❌ This channel is not an active ticket.", ephemeral=True)
            return

        settings = await ticket_service.get_guild_settings(interaction.guild.id)
        if not is_support_staff(interaction.user, settings.get("support_role_id")):
            await interaction.response.send_message("❌ Only support staff or admins can remove members.", ephemeral=True)
            return

        success, msg = await ticket_service.remove_user(
            channel=interaction.channel,
            target_user=user,
            staff=interaction.user,
        )
        await interaction.response.send_message(f"{'✅' if success else '❌'} {msg}", ephemeral=True)

    @app_commands.command(name="ticket-claim", description="Claim this ticket as the active handler.")
    @app_commands.default_permissions(administrator=True)
    async def ticket_claim(self, interaction: discord.Interaction):
        """Claim ticket."""
        if not interaction.guild or not isinstance(interaction.channel, (discord.TextChannel, discord.Thread)):
            await interaction.response.send_message("❌ Must be used in a server channel.", ephemeral=True)
            return

        settings = await ticket_service.get_guild_settings(interaction.guild.id)
        if not is_support_staff(interaction.user, settings.get("support_role_id")):
            await interaction.response.send_message("❌ Only support staff can claim tickets.", ephemeral=True)
            return

        success, msg = await ticket_service.claim_ticket(channel=interaction.channel, staff=interaction.user)
        await interaction.response.send_message(f"{'✅' if success else '⚠️'} {msg}", ephemeral=True)

    @app_commands.command(name="ticket-unclaim", description="Release your claim on this ticket.")
    @app_commands.default_permissions(administrator=True)
    async def ticket_unclaim(self, interaction: discord.Interaction):
        """Release claim on ticket."""
        if not interaction.guild or not isinstance(interaction.channel, (discord.TextChannel, discord.Thread)):
            await interaction.response.send_message("❌ Must be used in a server channel.", ephemeral=True)
            return

        settings = await ticket_service.get_guild_settings(interaction.guild.id)
        if not is_support_staff(interaction.user, settings.get("support_role_id")):
            await interaction.response.send_message("❌ Only support staff can release tickets.", ephemeral=True)
            return

        success, msg = await ticket_service.unclaim_ticket(channel=interaction.channel, staff=interaction.user)
        await interaction.response.send_message(f"{'✅' if success else '⚠️'} {msg}", ephemeral=True)

    @app_commands.command(name="ticket-transcript", description="Generate and export the conversation transcript.")
    @app_commands.default_permissions(administrator=True)
    async def ticket_transcript(self, interaction: discord.Interaction):

        """Generate transcript."""
        if not interaction.guild or not isinstance(interaction.channel, (discord.TextChannel, discord.Thread)):
            await interaction.response.send_message("❌ Must be used in a server channel.", ephemeral=True)
            return

        ticket = await ticket_service.get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message("❌ This channel is not a ticket.", ephemeral=True)
            return

        settings = await ticket_service.get_guild_settings(interaction.guild.id)
        if not can_manage_ticket(interaction.user, ticket, settings.get("support_role_id")):
            await interaction.response.send_message("❌ You are not authorized to export transcripts.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        creator = await ticket_service._resolve_member_or_user(interaction.guild, ticket.user_id)
        staff = await ticket_service._resolve_member_or_user(interaction.guild, ticket.claimed_by) if ticket.claimed_by else None
        closer = await ticket_service._resolve_member_or_user(interaction.guild, ticket.closed_by) if ticket.closed_by else None

        html_path = await transcript_service.generate_html(
            ticket=ticket,
            channel_name=interaction.channel.name,
            creator=creator,
            claimed_staff=staff,
            closed_by_user=closer,
        )

        await interaction.followup.send(
            content=f"📄 **Transcript for Ticket #{ticket.id:06d}:**",
            file=discord.File(str(html_path), filename=html_path.name),
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(TicketsCog(bot))
