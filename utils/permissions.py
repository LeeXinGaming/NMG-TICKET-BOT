"""
Permission and Role Validation Utilities for Ticket Bot.
"""

from __future__ import annotations

from typing import Optional, Union
import discord
from database.models import Ticket


def is_admin(member: Union[discord.Member, discord.User]) -> bool:
    """Check if member has administrator rights or owns the guild."""
    guild = getattr(member, "guild", None)
    if guild and getattr(guild, "owner_id", None) == member.id:
        return True
    perms = getattr(member, "guild_permissions", None)
    return getattr(perms, "administrator", False)


# Explicit Staff / Claim Ticket Allowed IDs
STAFF_CLAIM_IDS = {1552441867499733124, 1552438033176072352}


def is_support_staff(
    member: Union[discord.Member, discord.User],
    support_role_id: Optional[int] = None,
) -> bool:
    """
    Check if member is qualified support staff.
    Qualified if:
    - User ID is in STAFF_CLAIM_IDS (1552441867499733124)
    - Has role in STAFF_CLAIM_IDS (1552441867499733124)
    - Administrator
    - Has Manage Channels permission
    - Possesses configured support role
    """
    if getattr(member, "id", None) in STAFF_CLAIM_IDS:
        return True

    roles = getattr(member, "roles", [])
    if any(getattr(r, "id", None) in STAFF_CLAIM_IDS for r in roles):
        return True

    if is_admin(member):
        return True

    perms = getattr(member, "guild_permissions", None)
    if getattr(perms, "manage_channels", False):
        return True

    if support_role_id and any(getattr(r, "id", None) == support_role_id for r in roles):
        return True

    return False


def can_manage_ticket(
    member: Union[discord.Member, discord.User],
    ticket: Ticket,
    support_role_id: Optional[int] = None,
) -> bool:
    """Check if member is authorized to manage the ticket (staff, admin, or ticket owner for close)."""
    if is_support_staff(member, support_role_id):
        return True
    return member.id == ticket.user_id
