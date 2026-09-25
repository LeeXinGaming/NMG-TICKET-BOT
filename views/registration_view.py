"""
Registration Views and Modals.
Contains:
- RegisterModal: Modal form collecting character / citizen details.
- RegisterPanelView: Persistent view deployed with /register-panel.
- RegisterPromptView: Ephemeral view prompted when an unregistered user attempts to open a ticket.
"""

from __future__ import annotations

import logging
from typing import Optional
import discord
from discord import ui

from services.registration_service import registration_service
from utils.embeds import registration_success_embed, error_embed

logger = logging.getLogger("ticketbot.views.registration")


class RegisterModal(ui.Modal, title="ចុះឈ្មោះសមាជិក / Member Registration"):
    """Interactive modal to register character/user details."""

    def __init__(self, default_name: Optional[str] = None):
        super().__init__()
        self.name_input = ui.TextInput(
            label="ឈ្មោះតួអង្គ / IC Name (Full Name)",
            placeholder="e.g. John Wick or ឈ្មោះក្នុងហ្គេម",
            default=default_name or "",
            required=True,
            max_length=60,
        )
        self.phone_input = ui.TextInput(
            label="លេខសម្គាល់ ឬ ទូរស័ព្ទ / ID or Phone",
            placeholder="e.g. 1042 or 012345678",
            required=True,
            max_length=30,
        )
        self.notes_input = ui.TextInput(
            label="ព័ត៌មានបន្ថែម / Note (Optional)",
            style=discord.TextStyle.paragraph,
            placeholder="ព័ត៌មានផ្សេងៗ ឬ អាយុ / Details...",
            required=False,
            max_length=200,
        )
        self.add_item(self.name_input)
        self.add_item(self.phone_input)
        self.add_item(self.notes_input)

    async def on_submit(self, interaction: discord.Interaction):
        full_name = self.name_input.value.strip()
        phone_or_id = self.phone_input.value.strip()
        notes = self.notes_input.value.strip() or None

        success, msg, _ = await registration_service.register_user(
            guild=interaction.guild,
            user=interaction.user,
            full_name=full_name,
            phone_or_id=phone_or_id,
            notes=notes,
        )

        if success:
            embed = registration_success_embed(
                full_name=full_name,
                phone_or_id=phone_or_id,
                notes=notes,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(
                embed=error_embed("Registration Failed", msg),
                ephemeral=True,
            )


class RegisterPanelView(ui.View):
    """
    Persistent Registration Panel View.
    Maintains a persistent button across restarts.
    """

    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(
        label="Register / ចុះឈ្មោះ",
        style=discord.ButtonStyle.primary,
        emoji="📝",
        custom_id="register_panel_btn_register",
        row=0,
    )
    async def btn_register(self, interaction: discord.Interaction, button: ui.Button):
        # Open the registration modal directly
        modal = RegisterModal(default_name=interaction.user.display_name)
        await interaction.response.send_modal(modal)


class RegisterPromptView(ui.View):
    """
    Direct prompt view displayed when an unregistered user attempts to create a ticket.
    Provides a 1-click button to open the registration modal immediately.
    """

    def __init__(self):
        super().__init__(timeout=180)

    @ui.button(
        label="Register Now / ចុះឈ្មោះឥឡូវនេះ",
        style=discord.ButtonStyle.success,
        emoji="📝",
        row=0,
    )
    async def btn_register_now(self, interaction: discord.Interaction, button: ui.Button):
        modal = RegisterModal(default_name=interaction.user.display_name)
        await interaction.response.send_modal(modal)
