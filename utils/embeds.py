"""
Reusable Discord Embed Builders for Ticket Bot.
Maintains consistent professional theme, emojis, and layouts.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Union
import discord

from config import (
    COLOR_PRIMARY,
    COLOR_SUCCESS,
    COLOR_WARNING,
    COLOR_DANGER,
    COLOR_INFO,
    COLOR_DARK,
)
from utils.helpers import discord_timestamp, format_iso_to_discord, utc_now


def create_base_embed(
    title: str,
    description: str = "",
    color: int = COLOR_PRIMARY,
    timestamp: bool = True,
) -> discord.Embed:
    """Create a standardized base embed with consistent footer styling."""
    embed = discord.Embed(title=title, description=description, color=color)
    if timestamp:
        embed.timestamp = utc_now()
    embed.set_footer(text="Support Ticket System • សេវាកម្មជំនួយ ២៤/៧")
    return embed


def success_embed(title: str, description: str = "") -> discord.Embed:
    return create_base_embed(f"✅ {title}", description, color=COLOR_SUCCESS)


def error_embed(title: str, description: str = "") -> discord.Embed:
    return create_base_embed(f"❌ {title}", description, color=COLOR_DANGER)


def warning_embed(title: str, description: str = "") -> discord.Embed:
    return create_base_embed(f"⚠️ {title}", description, color=COLOR_WARNING)


def info_embed(title: str, description: str = "") -> discord.Embed:
    return create_base_embed(f"ℹ️ {title}", description, color=COLOR_INFO)


def ticket_panel_embed(custom_description: Optional[str] = None) -> discord.Embed:
    """The main embed displayed in the support panel channel."""
    desc = custom_description or (
        "ត្រូវការជំនួយ ឬមានបញ្ហាក្នុង Server? ក្រុមការងារយើងខ្ញុំត្រៀមជួយអ្នកជានិច្ច!\n"
        "Need assistance or have an inquiry? Our support team is ready to help you.\n\n"
        "👉 សូមចុចប៊ូតុង **បង្កើត Ticket / Create Ticket** ខាងក្រោមដើម្បីបើក Channel ឯកជន។\n"
        "👉 Click the **Create Ticket** button below to open your private support channel.\n\n"
        "⚠️ *កំណត់៖ សមាជិកម្នាក់អាចបង្កើត Ticket បានចំនួន **៣ ដងក្នុង ១ ថ្ងៃ** (Limit: 3 tickets per day / 24h).*"
    )
    embed = create_base_embed(
        title="🎫 Support Center | មជ្ឈមណ្ឌលជំនួយ",
        description=desc,
        color=COLOR_PRIMARY,
    )
    return embed


def ticket_welcome_embed(
    ticket_id: int,
    user: Union[discord.User, discord.Member],
    category_name: str,
    created_at_iso: Optional[str] = None,
    registered_info: Optional[dict] = None,
    daily_info: Optional[str] = None,
) -> discord.Embed:
    """Embed sent immediately after a ticket channel is created."""
    time_display = format_iso_to_discord(created_at_iso) if created_at_iso else discord_timestamp()

    embed = create_base_embed(
        title="🎫 បង្កើត Ticket ជោគជ័យ | Ticket Created",
        description=(
            f"សួស្ដី {user.mention}! សូមស្វាគមន៍មកកាន់ប្រព័ន្ធ Support។\n"
            "សូមរៀបរាប់ពីបញ្ហា ឬសំណួររបស់អ្នកឱ្យបានក្បោះក្បាយ រួមជាមួយរូបភាព Screenshot (ប្រសិនបើមាន)។\n"
            "ក្រុមការងារ Admin & Staff ត្រូវបានជូនដំណឹង ហើយនឹងមកជួយអ្នកក្នុងពេលបន្តិចទៀតនេះ!\n\n"
            "*(Welcome! Please describe your inquiry in detail with screenshots if available. "
            "Our staff has been notified and will assist you shortly.)*"
        ),
        color=COLOR_PRIMARY,
    )
    embed.add_field(name="📂 ប្រភេទ / Category", value=f"`{category_name}`", inline=True)
    embed.add_field(name="👤 អ្នកបង្កើត / Created By", value=user.mention, inline=True)
    embed.add_field(name="🔢 លេខសម្គាល់ / Ticket ID", value=f"`#{ticket_id:06d}`", inline=True)

    if daily_info:
        embed.add_field(name="📊 សំបុត្រថ្ងៃនេះ / Daily Quota", value=f"`{daily_info}`", inline=True)

    if registered_info:
        r_name = registered_info.get("full_name") or "N/A"
        r_phone = registered_info.get("phone_or_id") or "N/A"
        embed.add_field(
            name="📋 ព័ត៌មានសមាជិក / Citizen Info",
            value=f"• **ឈ្មោះ / IC:** `{r_name}`\n• **ID / Phone:** `{r_phone}`",
            inline=False,
        )

    embed.add_field(
        name="⏳ ស្ថានភាពសន្ទនា / Chat Status",
        value=(
            "🔒 **រង់ចាំបុគ្គលិក Claim / Waiting for Staff Claim**\n"
            "ការសន្ទនានឹងត្រូវបានបើកដំណើរការភ្លាមៗនៅពេលបុគ្គលិក Claim Ticket នេះ!\n"
            "*(Chat will unlock automatically when staff claims this ticket)*"
        ),
        inline=False,
    )

    embed.add_field(name="🕒 ពេលវេលាបង្កើត / Created At", value=time_display, inline=False)
    embed.set_footer(text="Staff: សូមចុច 'ទទួលយក / Claim' ដើម្បីបើកការជជែក | Click Claim to unlock chat.")
    return embed


def ticket_claimed_embed(staff: Union[discord.User, discord.Member]) -> discord.Embed:
    """Embed sent when staff claims a ticket."""
    embed = create_base_embed(
        title="📋 បានទទួលយក Ticket | Chat Unlocked! 💬",
        description=(
            f"🎉 Ticket នេះត្រូវបានទទួលមើលថែដោយបុគ្គលិក {staff.mention}!\n\n"
            "💬 **ការសន្ទនាត្រូវបានបើកដំណើរការ!** ឥឡូវនេះអ្នកអាចសន្ទនា និងរៀបរាប់បញ្ហាជាមួយបុគ្គលិកបានហើយ។\n\n"
            f"*(This ticket is now claimed by {staff.mention}. Chat has been unlocked!)*"
        ),
        color=COLOR_SUCCESS,
    )
    embed.set_thumbnail(url=staff.display_avatar.url)
    return embed


def ticket_unclaimed_embed(staff: Union[discord.User, discord.Member]) -> discord.Embed:
    """Embed sent when staff unclaims a ticket."""
    return create_base_embed(
        title="📋 បោះបង់ការទទួល | Chat Paused 🔒",
        description=(
            f"Ticket នេះត្រូវបានលែងការទទួលដោយ {staff.mention}។\n\n"
            "⏳ ការផ្ញើសារត្រូវបានផ្អាកជាបណ្ដោះអាសន្ន រហូតដល់មានបុគ្គលិកផ្សេងទៀតមកទទួលយក Ticket។\n\n"
            "*(Ticket claim released. Chat is paused until another staff member claims this ticket.)*"
        ),
        color=COLOR_WARNING,
    )


def ticket_closed_embed(
    staff_or_user: Union[discord.User, discord.Member],
    reason: Optional[str] = None,
) -> discord.Embed:
    """Embed sent when a ticket is closed."""
    desc = (
        f"🔒 Ticket នេះត្រូវបានបិទដោយ {staff_or_user.mention}។\n"
        "ការផ្ញើសារធម្មតាត្រូវបានចាក់សោ។ Support Staff អាចបើកឡើងវិញ ឬលុប Channel នេះជាអចិន្ត្រៃយ៍។\n\n"
        "*(This ticket has been closed. Messaging is locked. Staff may reopen or permanently delete this channel.)*"
    )

    embed = create_base_embed(
        title="🔒 បានបិទ Ticket | Ticket Closed",
        description=desc,
        color=COLOR_DANGER,
    )
    if reason:
        embed.add_field(name="📝 មូលហេតុ / Reason", value=reason, inline=False)
    return embed


def ticket_reopened_embed(staff: Union[discord.User, discord.Member]) -> discord.Embed:
    """Embed sent when a ticket is reopened."""
    return create_base_embed(
        title="🔓 បើក Ticket ឡើងវិញ | Ticket Reopened",
        description=(
            f"Ticket នេះត្រូវបានបើកដំណើរការឡើងវិញដោយ {staff.mention}។\n"
            "សិទ្ធិផ្ញើសារ និងការសន្ទនាត្រូវបានស្ដារមកវិញជាធម្មតា។\n\n"
            "*(This ticket has been reopened. Regular chat permissions have been restored.)*"
        ),
        color=COLOR_SUCCESS,
    )


def audit_log_embed(
    action: str,
    actor: Optional[Union[discord.User, discord.Member]],
    ticket_id: Optional[int],
    details: str,
    channel: Optional[discord.TextChannel] = None,
) -> discord.Embed:
    """Audit log embed sent to the designated logging channel."""
    embed = create_base_embed(
        title=f"📋 Audit Log: {action}",
        description=details,
        color=COLOR_DARK,
    )
    if actor:
        embed.add_field(name="អ្នកអនុវត្ត / Actor", value=f"{actor.mention} (`{actor.id}`)", inline=True)
    if ticket_id:
        embed.add_field(name="Ticket ID", value=f"`#{ticket_id:06d}`", inline=True)
    if channel:
        chan_name = getattr(channel, "name", None) or (f"ticket-{ticket_id:06d}" if ticket_id else "ticket")
        chan_mention = getattr(channel, "mention", "")
        display_val = f"`#{chan_name}` ({chan_mention})" if chan_mention else f"`#{chan_name}`"
        embed.add_field(name="Channel", value=display_val, inline=True)
    elif ticket_id:
        embed.add_field(name="Channel", value=f"`#ticket-{ticket_id:06d}`", inline=True)
    return embed


def registration_panel_embed(custom_description: Optional[str] = None) -> discord.Embed:
    """Embed displayed in the public registration channel."""
    desc = custom_description or (
        "សូមស្វាគមន៍មកកាន់ប្រព័ន្ធចុះឈ្មោះសមាជិក / Citizen Registration System!\n\n"
        "ដើម្បីអាចបង្កើត Support Ticket ឬទទួលបានសិទ្ធិប្រើប្រាស់សេវាកម្មក្នុង Server បាន "
        "សូមចុចប៊ូតុង **ចុះឈ្មោះ / Register** ខាងក្រោមដើម្បីបំពេញព័ត៌មានរបស់អ្នក៖\n\n"
        "• 📝 **ឈ្មោះតួអង្គ / IC Name (Full Name)**\n"
        "• 🆔 **លេខសម្គាល់ ឬ លេខទូរស័ព្ទ / Character ID or Phone**\n"
        "• 📌 **ព័ត៌មានបន្ថែម / Note or Details**\n\n"
        "*(All users must complete registration before opening support tickets)*"
    )
    embed = create_base_embed(
        title="📋 ប្រព័ន្ធចុះឈ្មោះសមាជិក | Member Registration",
        description=desc,
        color=COLOR_PRIMARY,
    )
    embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/3135/3135715.png")
    embed.set_footer(text="Click the button below to register • 100% Automated System")
    return embed


def registration_required_embed() -> discord.Embed:
    """Embed displayed when an unregistered user attempts to open a ticket."""
    embed = create_base_embed(
        title="⚠️ តម្រូវឱ្យចុះឈ្មោះជាមុន / Registration Required",
        description=(
            "សូមអភ័យទោស! អ្នកមិនទាន់បានចុះឈ្មោះក្នុងប្រព័ន្ធនៅឡើយទេ។\n"
            "អ្នកត្រូវតែបំពេញការចុះឈ្មោះជាមុនសិន ទើបអាចបង្កើត Support Ticket បាន!\n\n"
            "👉 **សូមចុចប៊ូតុងខាងក្រោមដើម្បីចុះឈ្មោះឥឡូវនេះ (Click Register below):**"
        ),
        color=COLOR_WARNING,
    )
    embed.add_field(
        name="📌 ព័ត៌មានដែលត្រូវការ / Required Info",
        value="1. ឈ្មោះតួអង្គ / Character Name\n2. លេខសម្គាល់ ឬ លេខទូរស័ព្ទ / ID or Phone",
        inline=False,
    )
    embed.set_footer(text="After registering, click the ticket button again to open your ticket.")
    return embed


def registration_success_embed(
    full_name: str,
    phone_or_id: str,
    notes: Optional[str] = None,
) -> discord.Embed:
    """Embed displayed when a user successfully registers."""
    embed = create_base_embed(
        title="✅ ចុះឈ្មោះជោគជ័យ / Registration Completed!",
        description=(
            "🎉 អបអរសាទរ! អ្នកបានចុះឈ្មោះក្នុងប្រព័ន្ធរួចរាល់ហើយ។\n"
            "ឥឡូវនេះអ្នកអាចបង្កើត Support Ticket និងប្រើប្រាស់សេវាកម្មទាំងអស់បានជាធម្មតា!\n\n"
            "*(You are now registered and can create support tickets anytime.)*"
        ),
        color=COLOR_SUCCESS,
    )
    embed.add_field(name="👤 ឈ្មោះ / Name", value=f"`{full_name}`", inline=True)
    embed.add_field(name="🆔 ID / Phone", value=f"`{phone_or_id}`", inline=True)
    if notes:
        embed.add_field(name="📝 សម្គាល់ / Note", value=f"*{notes}*", inline=False)
    embed.set_footer(text="Verified Member • System Access Granted")
    return embed


def registration_audit_embed(
    actor: Union[discord.User, discord.Member],
    full_name: str,
    phone_or_id: str,
    notes: Optional[str] = None,
    action: str = "New User Registered",
) -> discord.Embed:
    """Embed dispatched to log channels when registration events occur."""
    embed = create_base_embed(
        title=f"📋 Member Registration: {action}",
        description=f"User {actor.mention} (`{actor.id}`) has completed system registration.",
        color=COLOR_INFO,
    )
    embed.add_field(name="👤 Discord Account", value=f"{actor.mention} ({actor.name})", inline=True)
    embed.add_field(name="📝 Registered Name", value=f"`{full_name}`", inline=True)
    embed.add_field(name="🆔 Character ID / Phone", value=f"`{phone_or_id}`", inline=True)
    if notes:
        embed.add_field(name="📌 Additional Notes", value=f"{notes}", inline=False)
    embed.set_thumbnail(url=actor.display_avatar.url)
    return embed

