"""
AutoReply and Keyword Cog.
Handles slash commands for category auto-reply greetings and smart keyword triggers.
Commands:
/autoreply enable <category>
/autoreply disable <category>
/autoreply set <category> <message>
/autoreply reset <category>
/autoreply list
/keyword add <keyword> <response>
/keyword remove <keyword>
/keyword list
"""

from __future__ import annotations

import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from services.autoreply_service import autoreply_service
from services.logging_service import log_service
from utils.embeds import success_embed, error_embed, info_embed, create_base_embed
from utils.permissions import is_admin

logger = logging.getLogger("ticketbot.cogs.autoreply")


class AutoReplyCog(commands.Cog, name="AutoReply"):
    """Management commands for automated responses."""

    autoreply_group = app_commands.Group(
        name="autoreply",
        description="Manage category greeting messages",
        default_permissions=discord.Permissions(administrator=True),
    )
    keyword_group = app_commands.Group(
        name="keyword",
        description="Manage in-ticket keyword auto-responses",
        default_permissions=discord.Permissions(administrator=True),
    )


    # ==========================================
    # Auto-Reply Subcommands
    # ==========================================

    @autoreply_group.command(name="list", description="List all category auto-reply greetings.")
    async def reply_list(self, interaction: discord.Interaction):
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Administrator permission required.", ephemeral=True)
            return

        replies = await autoreply_service.list_replies()
        if not replies:
            await interaction.response.send_message("ℹ️ No auto-replies found in database.", ephemeral=True)
            return

        embed = create_base_embed(title="💬 Category Auto-Replies")
        for r in replies:
            status = "🟢 Enabled" if r["enabled"] else "🔴 Disabled"
            embed.add_field(
                name=f"{r['category_name']} ({status})",
                value=f"```{r['message'][:300]}```",
                inline=False,
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @autoreply_group.command(name="set", description="Set a custom auto-reply greeting for a category.")
    @app_commands.describe(
        category="Target category name",
        message="The greeting message to send when a ticket is opened",
    )
    async def reply_set(self, interaction: discord.Interaction, category: str, message: str):
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Administrator permission required.", ephemeral=True)
            return

        await autoreply_service.set_reply(category, message)
        embed = success_embed(
            "Auto-Reply Updated",
            f"Successfully updated greeting for **{category}**:\n```{message}```",
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

        await log_service.log_event(
            guild=interaction.guild,
            action="Auto-Reply Updated",
            actor=interaction.user,
            ticket_id=None,
            details=f"Auto-reply set for category '{category}' by {interaction.user.mention}.",
        )

    @autoreply_group.command(name="enable", description="Enable auto-reply for a category.")
    @app_commands.describe(category="Target category name")
    async def reply_enable(self, interaction: discord.Interaction, category: str):
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Administrator permission required.", ephemeral=True)
            return

        success = await autoreply_service.toggle_reply(category, enabled=True)
        if success:
            await interaction.response.send_message(f"✅ Auto-reply enabled for **{category}**.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Category **{category}** not found.", ephemeral=True)

    @autoreply_group.command(name="disable", description="Disable auto-reply for a category.")
    @app_commands.describe(category="Target category name")
    async def reply_disable(self, interaction: discord.Interaction, category: str):
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Administrator permission required.", ephemeral=True)
            return

        success = await autoreply_service.toggle_reply(category, enabled=False)
        if success:
            await interaction.response.send_message(f"✅ Auto-reply disabled for **{category}**.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Category **{category}** not found.", ephemeral=True)

    @autoreply_group.command(name="reset", description="Reset a category auto-reply to system default.")
    @app_commands.describe(category="Target category name")
    async def reply_reset(self, interaction: discord.Interaction, category: str):
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Administrator permission required.", ephemeral=True)
            return

        success = await autoreply_service.reset_reply(category)
        if success:
            await interaction.response.send_message(f"✅ Auto-reply reset to default for **{category}**.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Category **{category}** has no default template.", ephemeral=True)

    # ==========================================
    # Keyword Subcommands
    # ==========================================

    @keyword_group.command(name="list", description="List all configured keyword triggers.")
    async def keyword_list(self, interaction: discord.Interaction):
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Administrator permission required.", ephemeral=True)
            return

        keywords = await autoreply_service.list_keywords()
        if not keywords:
            await interaction.response.send_message("ℹ️ No keyword triggers configured.", ephemeral=True)
            return

        embed = create_base_embed(title="🔑 Keyword Triggers")
        for kw in keywords:
            status = "🟢" if kw["enabled"] else "🔴"
            embed.add_field(
                name=f"{status} '{kw['keyword']}'",
                value=f"```{kw['response'][:250]}```",
                inline=False,
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @keyword_group.command(name="add", description="Add or update a keyword trigger response.")
    @app_commands.describe(
        keyword="Word or phrase that triggers the bot",
        response="The message the bot will send",
    )
    async def keyword_add(self, interaction: discord.Interaction, keyword: str, response: str):
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Administrator permission required.", ephemeral=True)
            return

        await autoreply_service.add_keyword(keyword, response, interaction.user.id)
        embed = success_embed(
            "Keyword Added",
            f"When users mention `{keyword.lower()}` inside a ticket, the bot will respond:\n```{response}```",
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

        await log_service.log_event(
            guild=interaction.guild,
            action="Keyword Added",
            actor=interaction.user,
            ticket_id=None,
            details=f"Keyword '{keyword}' added by {interaction.user.mention}.",
        )

    @keyword_group.command(name="remove", description="Remove an existing keyword trigger.")
    @app_commands.describe(keyword="Word or phrase to delete")
    async def keyword_remove(self, interaction: discord.Interaction, keyword: str):
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ Administrator permission required.", ephemeral=True)
            return

        success = await autoreply_service.remove_keyword(keyword)
        if success:
            await interaction.response.send_message(f"✅ Keyword `{keyword.lower()}` removed.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Keyword `{keyword.lower()}` was not found.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoReplyCog(bot))
