"""
Reusable Confirmation Views and Input Modals for Ticket Bot.
"""

from __future__ import annotations

from typing import Callable, Coroutine, Optional, Union
import discord
from discord import ui


class ConfirmationView(ui.View):
    """Generic confirmation view with Confirm and Cancel buttons."""

    def __init__(
        self,
        author_id: int,
        confirm_callback: Optional[Callable[[discord.Interaction], Coroutine]] = None,
        cancel_callback: Optional[Callable[[discord.Interaction], Coroutine]] = None,
        timeout: float = 60.0,
    ):
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.confirm_callback = confirm_callback
        self.cancel_callback = cancel_callback
        self.value: Optional[bool] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "❌ អ្នកគ្មានសិទ្ធិប្រើប្រាស់ប៊ូតុងនេះឡើយ។\n(You are not authorized to interact with this prompt.)",
                ephemeral=True,
            )
            return False
        return True

    @ui.button(label="បញ្ជាក់ / Confirm", style=discord.ButtonStyle.danger, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: ui.Button):
        self.value = True
        self.stop()
        if self.confirm_callback:
            await self.confirm_callback(interaction)
        else:
            await interaction.response.defer()

    @ui.button(label="បោះបង់ / Cancel", style=discord.ButtonStyle.secondary, emoji="✖️")
    async def cancel(self, interaction: discord.Interaction, button: ui.Button):
        self.value = False
        self.stop()
        if self.cancel_callback:
            await self.cancel_callback(interaction)
        else:
            await interaction.response.send_message("ប្រតិបត្តិការត្រូវបានបោះបង់។ (Action cancelled.)", ephemeral=True)


class ReasonModal(ui.Modal):
    """Modal for collecting action reasons (e.g. ticket close or delete)."""

    def __init__(self, title: str, on_submit_callback: Callable[[discord.Interaction, str], Coroutine]):
        super().__init__(title=title[:45])
        self.on_submit_callback = on_submit_callback

        self.reason_input = ui.TextInput(
            label="មូលហេតុ / Reason",
            style=discord.TextStyle.paragraph,
            placeholder="បញ្ជាក់ពីមូលហេតុ (មិនបង្ខំ) / Describe reason (optional)...",
            required=False,
            max_length=500,
        )
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction):
        await self.on_submit_callback(interaction, self.reason_input.value.strip())


class AddUserModal(ui.Modal, title="បន្ថែមសមាជិក / Add User"):
    """Modal to input a user ID or mention to add to the ticket."""

    def __init__(self, on_submit_callback: Callable[[discord.Interaction, int], Coroutine]):
        super().__init__()
        self.on_submit_callback = on_submit_callback

        self.user_input = ui.TextInput(
            label="User ID ឬ Mention",
            placeholder="ឧ. 123456789012345678 ឬ @user",
            required=True,
            max_length=40,
        )
        self.add_item(self.user_input)

    async def on_submit(self, interaction: discord.Interaction):
        raw = self.user_input.value.strip()
        # Clean mention formatting <@12345>
        clean_id = raw.replace("<@", "").replace("!", "").replace(">", "").strip()
        if not clean_id.isdigit():
            await interaction.response.send_message(
                "❌ User ID មិនត្រឹមត្រូវ។ សូមបញ្ចូលលេខ ID ឬ Mention សមាជិក។\n(Invalid User ID or mention.)",
                ephemeral=True,
            )
            return
        await self.on_submit_callback(interaction, int(clean_id))


class RemoveUserModal(ui.Modal, title="ដកសមាជិក / Remove User"):
    """Modal to input a user ID or mention to remove from the ticket."""

    def __init__(self, on_submit_callback: Callable[[discord.Interaction, int], Coroutine]):
        super().__init__()
        self.on_submit_callback = on_submit_callback

        self.user_input = ui.TextInput(
            label="User ID ឬ Mention",
            placeholder="ឧ. 123456789012345678 ឬ @user",
            required=True,
            max_length=40,
        )
        self.add_item(self.user_input)

    async def on_submit(self, interaction: discord.Interaction):
        raw = self.user_input.value.strip()
        clean_id = raw.replace("<@", "").replace("!", "").replace(">", "").strip()
        if not clean_id.isdigit():
            await interaction.response.send_message(
                "❌ User ID មិនត្រឹមត្រូវ។ សូមបញ្ចូលលេខ ID ឬ Mention សមាជិក។\n(Invalid User ID or mention.)",
                ephemeral=True,
            )
            return
        await self.on_submit_callback(interaction, int(clean_id))
