"""
Persistent Ticket Panel View.
Contains the category selection buttons for users to open support tickets.
Persists across bot reboots (timeout=None and explicit custom_ids).
"""

from __future__ import annotations

import logging
import discord
from discord import ui

from services.ticket_service import ticket_service

logger = logging.getLogger("ticketbot.panel_view")


class TicketPanelView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def _handle_create(
        self,
        interaction: discord.Interaction,
        category_name: str,
    ) -> None:
        """Helper to process ticket generation with safe response deferral."""
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ Ticket អាចបង្កើតបានតែនៅក្នុង Discord Server ប៉ុណ្ណោះ។\n(Tickets can only be created inside a Discord server.)",
                ephemeral=True,
            )
            return

        if interaction.response.is_done():
            return

        # Defer response ephemerally so Discord does not time out during channel creation
        await interaction.response.defer(ephemeral=True, thinking=True)

        success, message, channel = await ticket_service.create_ticket(
            guild=interaction.guild,
            user=interaction.user,
            category_name=category_name,
        )

        if success and channel:
            await interaction.followup.send(
                f"✅ **បង្កើត Ticket ជោគជ័យ! / Ticket Created!**\n"
                f"សូមចូលទៅកាន់ Channel របស់អ្នក: {channel.mention} (`#{channel.name}`)\n"
                f"*(Please proceed to your private support channel)*",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                f"❌ {message}",
                ephemeral=True,
            )


    @ui.button(
        label="បង្កើត Ticket / Create Ticket",
        style=discord.ButtonStyle.primary,
        emoji="🎫",
        custom_id="ticket_panel_btn_general",
        row=0,
    )
    async def btn_general(self, interaction: discord.Interaction, button: ui.Button):
        await self._handle_create(interaction, "Support Ticket")

