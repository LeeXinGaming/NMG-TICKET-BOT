"""
Persistent In-Ticket Control View.
Provides control buttons inside every ticket channel:
Close, Reopen, Claim, Add User, Remove User, Transcript, Delete.
All buttons use persistent custom_ids so they survive bot restarts.
"""

from __future__ import annotations

import logging
from typing import Optional
import discord
from discord import ui

from services.ticket_service import ticket_service
from services.transcript_service import transcript_service
from utils.permissions import is_support_staff, can_manage_ticket
from views.confirmation import ConfirmationView, ReasonModal, AddUserModal, RemoveUserModal

logger = logging.getLogger("ticketbot.ticket_view")


class TicketControlView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def _get_ticket_and_settings(self, interaction: discord.Interaction):
        if not interaction.guild or not isinstance(interaction.channel, (discord.TextChannel, discord.Thread)):
            return None, None
        ticket = await ticket_service.get_ticket_by_channel(interaction.channel.id)
        settings = await ticket_service.get_guild_settings(interaction.guild.id)
        return ticket, settings

    @ui.button(
        label="បិទ Ticket / Close",
        style=discord.ButtonStyle.secondary,
        emoji="🔒",
        custom_id="ticket_ctrl_close",
        row=0,
    )
    async def btn_close(self, interaction: discord.Interaction, button: ui.Button):
        ticket, settings = await self._get_ticket_and_settings(interaction)
        if not ticket or not isinstance(interaction.channel, (discord.TextChannel, discord.Thread)):
            await interaction.response.send_message("❌ នេះមិនមែនជា Channel Ticket ដែលកំពុងដំណើរការទេ។", ephemeral=True)
            return

        support_role_id = settings.get("support_role_id")
        if not can_manage_ticket(interaction.user, ticket, support_role_id):
            await interaction.response.send_message("❌ អ្នកគ្មានសិទ្ធិបិទ Ticket នេះឡើយ។ (Not authorized)", ephemeral=True)
            return

        if ticket.status == "closed":
            await interaction.response.send_message("⚠️ Ticket នេះត្រូវបានបិទរួចហើយ។ (Already closed)", ephemeral=True)
            return

        # Confirmation flow
        async def on_confirm(confirm_inter: discord.Interaction):
            await confirm_inter.response.defer()
            await ticket_service.close_ticket(
                channel=interaction.channel,
                actor=confirm_inter.user,
                reason="បិទតាមរយៈប៊ូតុងបញ្ជា (Closed via button)",
            )

        confirm_view = ConfirmationView(author_id=interaction.user.id, confirm_callback=on_confirm)
        await interaction.response.send_message(
            "⚠️ **តើអ្នកប្រាកដជាចង់បិទ Ticket នេះមែនទេ?**\n"
            "*(Are you sure you want to close this ticket?)*",
            view=confirm_view,
            ephemeral=True,
        )

    @ui.button(
        label="បើកវិញ / Reopen",
        style=discord.ButtonStyle.success,
        emoji="🔓",
        custom_id="ticket_ctrl_reopen",
        row=0,
    )
    async def btn_reopen(self, interaction: discord.Interaction, button: ui.Button):
        ticket, settings = await self._get_ticket_and_settings(interaction)
        if not ticket or not isinstance(interaction.channel, (discord.TextChannel, discord.Thread)):
            await interaction.response.send_message("❌ នេះមិនមែនជា Channel Ticket ទេ។", ephemeral=True)
            return

        support_role_id = settings.get("support_role_id")
        if not is_support_staff(interaction.user, support_role_id):
            await interaction.response.send_message("❌ មានតែ Admin ឬ Support Staff ប៉ុណ្ណោះដែលអាចបើក Ticket ឡើងវិញបាន។", ephemeral=True)
            return

        if ticket.status == "open":
            await interaction.response.send_message("ℹ️ Ticket នេះកំពុងបើកដំណើរការស្រាប់ហើយ។ (Already open)", ephemeral=True)
            return

        await interaction.response.defer()
        await ticket_service.reopen_ticket(channel=interaction.channel, staff=interaction.user)

    @ui.button(
        label="ទទួលយក / Claim",
        style=discord.ButtonStyle.primary,
        emoji="📋",
        custom_id="ticket_ctrl_claim",
        row=0,
    )
    async def btn_claim(self, interaction: discord.Interaction, button: ui.Button):
        ticket, settings = await self._get_ticket_and_settings(interaction)
        if not ticket or not isinstance(interaction.channel, (discord.TextChannel, discord.Thread)):
            await interaction.response.send_message("❌ នេះមិនមែនជា Channel Ticket ដែលកំពុងដំណើរការទេ។", ephemeral=True)
            return

        support_role_id = settings.get("support_role_id")
        if not is_support_staff(interaction.user, support_role_id):
            await interaction.response.send_message("❌ មានតែ Admin ឬ Support Staff ប៉ុណ្ណោះដែលអាច Claim Ticket បាន។", ephemeral=True)
            return

        success, msg = await ticket_service.claim_ticket(channel=interaction.channel, staff=interaction.user)
        if success:
            await interaction.response.send_message(f"✅ {msg}", ephemeral=True)
        else:
            await interaction.response.send_message(f"⚠️ {msg}", ephemeral=True)

    @ui.button(
        label="បន្ថែម / Add User",
        style=discord.ButtonStyle.secondary,
        emoji="👤",
        custom_id="ticket_ctrl_add_user",
        row=1,
    )
    async def btn_add_user(self, interaction: discord.Interaction, button: ui.Button):
        ticket, settings = await self._get_ticket_and_settings(interaction)
        if not ticket or not isinstance(interaction.channel, (discord.TextChannel, discord.Thread)):
            await interaction.response.send_message("❌ នេះមិនមែនជា Channel Ticket ដែលកំពុងដំណើរការទេ។", ephemeral=True)
            return

        support_role_id = settings.get("support_role_id")
        if not is_support_staff(interaction.user, support_role_id):
            await interaction.response.send_message("❌ មានតែ Support Staff ប៉ុណ្ណោះដែលអាចបន្ថែមសមាជិកបាន។", ephemeral=True)
            return

        async def on_user_submit(modal_inter: discord.Interaction, target_id: int):
            target_member = interaction.guild.get_member(target_id)
            if not target_member:
                try:
                    target_member = await interaction.guild.fetch_member(target_id)
                except Exception:
                    await modal_inter.response.send_message("❌ មិនអាចស្វែងរកសមាជិកនេះឃើញនៅក្នុង Server ឡើយ។", ephemeral=True)
                    return

            success, msg = await ticket_service.add_user(
                channel=interaction.channel,
                target_user=target_member,
                staff=modal_inter.user,
            )
            await modal_inter.response.send_message(f"{'✅' if success else '❌'} {msg}", ephemeral=True)

        modal = AddUserModal(on_submit_callback=on_user_submit)
        await interaction.response.send_modal(modal)

    @ui.button(
        label="ដកចេញ / Remove User",
        style=discord.ButtonStyle.secondary,
        emoji="👤",
        custom_id="ticket_ctrl_remove_user",
        row=1,
    )
    async def btn_remove_user(self, interaction: discord.Interaction, button: ui.Button):
        ticket, settings = await self._get_ticket_and_settings(interaction)
        if not ticket or not isinstance(interaction.channel, (discord.TextChannel, discord.Thread)):
            await interaction.response.send_message("❌ នេះមិនមែនជា Channel Ticket ដែលកំពុងដំណើរការទេ។", ephemeral=True)
            return

        support_role_id = settings.get("support_role_id")
        if not is_support_staff(interaction.user, support_role_id):
            await interaction.response.send_message("❌ មានតែ Support Staff ប៉ុណ្ណោះដែលអាចដកសមាជិកបាន។", ephemeral=True)
            return

        async def on_remove_submit(modal_inter: discord.Interaction, target_id: int):
            target_member = interaction.guild.get_member(target_id)
            if not target_member:
                try:
                    target_member = await interaction.guild.fetch_member(target_id)
                except Exception:
                    await modal_inter.response.send_message("❌ មិនអាចស្វែងរកសមាជិកនេះឃើញនៅក្នុង Server ឡើយ។", ephemeral=True)
                    return

            success, msg = await ticket_service.remove_user(
                channel=interaction.channel,
                target_user=target_member,
                staff=modal_inter.user,
            )
            await modal_inter.response.send_message(f"{'✅' if success else '❌'} {msg}", ephemeral=True)

        modal = RemoveUserModal(on_submit_callback=on_remove_submit)
        await interaction.response.send_modal(modal)

    @ui.button(
        label="កំណត់ត្រា / Transcript",
        style=discord.ButtonStyle.secondary,
        emoji="📄",
        custom_id="ticket_ctrl_transcript",
        row=1,
    )
    async def btn_transcript(self, interaction: discord.Interaction, button: ui.Button):
        ticket, settings = await self._get_ticket_and_settings(interaction)
        if not ticket or not isinstance(interaction.channel, (discord.TextChannel, discord.Thread)):
            await interaction.response.send_message("❌ នេះមិនមែនជា Channel Ticket ដែលកំពុងដំណើរការទេ។", ephemeral=True)
            return

        support_role_id = settings.get("support_role_id")
        if not can_manage_ticket(interaction.user, ticket, support_role_id):
            await interaction.response.send_message("❌ អ្នកគ្មានសិទ្ធិទាញយកកំណត់ត្រាការសន្ទនា (Transcript) ឡើយ។", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        creator = await ticket_service._resolve_member_or_user(interaction.guild, ticket.user_id)
        claimed_staff = await ticket_service._resolve_member_or_user(interaction.guild, ticket.claimed_by) if ticket.claimed_by else None
        closer = await ticket_service._resolve_member_or_user(interaction.guild, ticket.closed_by) if ticket.closed_by else None

        html_path = await transcript_service.generate_html(
            ticket=ticket,
            channel_name=interaction.channel.name,
            creator=creator,
            claimed_staff=claimed_staff,
            closed_by_user=closer,
        )

        await interaction.followup.send(
            content=f"📄 **កំណត់ត្រាការសន្ទនា (Transcript) Ticket #{ticket.id:06d}:**",
            file=discord.File(str(html_path), filename=html_path.name),
            ephemeral=True,
        )

    @ui.button(
        label="លុប Ticket / Delete",
        style=discord.ButtonStyle.danger,
        emoji="🗑️",
        custom_id="ticket_ctrl_delete",
        row=1,
    )
    async def btn_delete(self, interaction: discord.Interaction, button: ui.Button):
        ticket, settings = await self._get_ticket_and_settings(interaction)
        if not ticket or not isinstance(interaction.channel, (discord.TextChannel, discord.Thread)):
            await interaction.response.send_message("❌ នេះមិនមែនជា Channel Ticket ដែលកំពុងដំណើរការទេ។", ephemeral=True)
            return

        support_role_id = settings.get("support_role_id")
        if not is_support_staff(interaction.user, support_role_id):
            await interaction.response.send_message("❌ មានតែ Admin ឬ Support Staff ប៉ុណ្ណោះដែលអាចលុប Ticket បាន។", ephemeral=True)
            return

        async def on_confirm_delete(confirm_inter: discord.Interaction):
            await confirm_inter.response.send_message("🗑️ កំពុងលុប Channel Ticket ក្នុងរយៈពេល ៣ វិនាទី...", ephemeral=True)
            await ticket_service.delete_ticket(
                channel=interaction.channel,
                staff=confirm_inter.user,
                reason="លុបតាមរយៈប៊ូតុងបញ្ជា (Deleted via Ticket Control Button)",
            )

        confirm_view = ConfirmationView(author_id=interaction.user.id, confirm_callback=on_confirm_delete)
        await interaction.response.send_message(
            "⚠️ **តើអ្នកប្រាកដជាចង់លុប Channel Ticket នេះជាអចិន្ត្រៃយ៍មែនទេ?**\n"
            "*(Are you sure you want to permanently delete this ticket channel?)*\n\n"
            "ឯកសារកំណត់ត្រា Transcript ចុងក្រោយនឹងត្រូវបានបង្កើត និងរក្សាទុកដោយស្វ័យប្រវត្តិ។",
            view=confirm_view,
            ephemeral=True,
        )
