"""
Transcript Service - Generates standalone Discord Dark themed HTML transcripts
and plain text transcripts from logged ticket messages.
"""

from __future__ import annotations

import html
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import discord

from config import TRANSCRIPTS_DIR
from database.database import Database, db
from database.models import Ticket
from utils.helpers import utc_now

logger = logging.getLogger("ticketbot.transcript")


class TranscriptService:
    def __init__(self, database: Database = db):
        self.db = database

    async def generate_html(
        self,
        ticket: Ticket,
        channel_name: str,
        creator: Optional[discord.User | discord.Member] = None,
        claimed_staff: Optional[discord.User | discord.Member] = None,
        closed_by_user: Optional[discord.User | discord.Member] = None,
    ) -> Path:
        """Create a Discord-styled HTML transcript file."""
        # Fetch recorded messages
        messages = await self.db.fetch_all(
            "SELECT * FROM ticket_messages WHERE ticket_id = ? ORDER BY id ASC;",
            (ticket.id,),
        )

        creator_name = (
            creator.display_name if creator else f"User ID {ticket.user_id}"
        )
        staff_name = (
            claimed_staff.display_name if claimed_staff else "None"
        )
        closer_name = (
            closed_by_user.display_name if closed_by_user else (f"ID {ticket.closed_by}" if ticket.closed_by else "None")
        )

        message_cards = []
        for msg in messages:
            author_escaped = html.escape(msg["author_name"])
            content_escaped = html.escape(msg["content"] or "").replace("\n", "<br>")
            timestamp_raw = msg["created_at"]
            
            attachments_html = ""
            if msg["attachments"]:
                try:
                    att_urls = json.loads(msg["attachments"])
                except Exception:
                    att_urls = [u.strip() for u in msg["attachments"].split(",") if u.strip()]

                for url in att_urls:
                    clean_url = html.escape(url)
                    if any(clean_url.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".gif", ".webp"]):
                        attachments_html += (
                            f'<div class="msg-attachment">'
                            f'<a href="{clean_url}" target="_blank">'
                            f'<img src="{clean_url}" alt="Attachment" class="preview-img" loading="lazy" />'
                            f'</a></div>'
                        )
                    else:
                        attachments_html += (
                            f'<div class="msg-attachment-link">'
                            f'📎 <a href="{clean_url}" target="_blank">{clean_url}</a></div>'
                        )

            card = f"""
            <div class="message-row">
                <div class="avatar-placeholder">{author_escaped[:1].upper()}</div>
                <div class="message-content-wrapper">
                    <div class="message-header">
                        <span class="author-name">{author_escaped}</span>
                        <span class="timestamp">{timestamp_raw}</span>
                    </div>
                    <div class="message-body">{content_escaped}</div>
                    {attachments_html}
                </div>
            </div>
            """
            message_cards.append(card)

        all_messages_html = "\n".join(message_cards) if message_cards else "<p class='empty-log'>No messages were recorded in this ticket.</p>"

        html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ticket #{ticket.id:06d} Transcript</title>
    <style>
        :root {{
            --bg-primary: #1e1f22;
            --bg-secondary: #2b2d31;
            --bg-tertiary: #111214;
            --accent: #5865f2;
            --text-normal: #dbdee1;
            --text-muted: #949ba4;
            --header-primary: #f2f3f5;
            --border-color: #3f4147;
            --font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            background-color: var(--bg-primary);
            color: var(--text-normal);
            font-family: var(--font-family);
            line-height: 1.5;
            padding: 24px;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
            background: var(--bg-secondary);
            border-radius: 10px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
            overflow: hidden;
            border: 1px solid var(--border-color);
        }}
        .header {{
            background: var(--bg-tertiary);
            padding: 24px;
            border-bottom: 1px solid var(--border-color);
        }}
        .header h1 {{
            color: var(--header-primary);
            font-size: 24px;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .badge {{
            background: var(--accent);
            color: #fff;
            font-size: 13px;
            padding: 3px 8px;
            border-radius: 4px;
            font-weight: 600;
        }}
        .meta-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 12px;
            margin-top: 16px;
            font-size: 14px;
        }}
        .meta-item {{
            background: rgba(255,255,255,0.03);
            padding: 8px 12px;
            border-radius: 6px;
            border-left: 3px solid var(--accent);
        }}
        .meta-label {{
            color: var(--text-muted);
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .meta-value {{
            color: var(--header-primary);
            font-weight: 500;
            margin-top: 2px;
        }}
        .messages-container {{
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 14px;
        }}
        .message-row {{
            display: flex;
            gap: 14px;
            padding: 8px;
            border-radius: 6px;
            transition: background 0.15s;
        }}
        .message-row:hover {{
            background: rgba(255, 255, 255, 0.02);
        }}
        .avatar-placeholder {{
            width: 40px;
            height: 40px;
            border-radius: 50%;
            background: var(--accent);
            color: #fff;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 16px;
            flex-shrink: 0;
        }}
        .message-content-wrapper {{
            flex-grow: 1;
            min-width: 0;
        }}
        .message-header {{
            display: flex;
            align-items: baseline;
            gap: 8px;
            margin-bottom: 4px;
        }}
        .author-name {{
            color: var(--header-primary);
            font-weight: 600;
            font-size: 15px;
        }}
        .timestamp {{
            color: var(--text-muted);
            font-size: 11px;
        }}
        .message-body {{
            color: var(--text-normal);
            font-size: 14px;
            word-wrap: break-word;
        }}
        .msg-attachment {{
            margin-top: 10px;
        }}
        .preview-img {{
            max-width: 400px;
            max-height: 300px;
            border-radius: 6px;
            border: 1px solid var(--border-color);
        }}
        .msg-attachment-link a {{
            color: #00a8fc;
            text-decoration: none;
            font-size: 13px;
        }}
        .msg-attachment-link a:hover {{
            text-decoration: underline;
        }}
        .empty-log {{
            color: var(--text-muted);
            text-align: center;
            padding: 40px;
        }}
        .footer {{
            padding: 16px;
            text-align: center;
            font-size: 12px;
            color: var(--text-muted);
            background: var(--bg-tertiary);
            border-top: 1px solid var(--border-color);
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎫 Ticket Transcript <span class="badge">#{ticket.id:06d}</span></h1>
            <div class="meta-grid">
                <div class="meta-item">
                    <div class="meta-label">Channel</div>
                    <div class="meta-value">#{html.escape(channel_name)}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">Category</div>
                    <div class="meta-value">{html.escape(ticket.category)}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">Created By</div>
                    <div class="meta-value">{html.escape(creator_name)}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">Claimed Staff</div>
                    <div class="meta-value">{html.escape(staff_name)}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">Created At</div>
                    <div class="meta-value">{ticket.created_at}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">Closed By / At</div>
                    <div class="meta-value">{html.escape(closer_name)} ({ticket.closed_at or 'Open'})</div>
                </div>
            </div>
        </div>
        <div class="messages-container">
            {all_messages_html}
        </div>
        <div class="footer">
            Generated by Support Ticket Bot • {utc_now().strftime("%Y-%m-%d %H:%M:%S UTC")}
        </div>
    </div>
</body>
</html>
"""
        file_path = TRANSCRIPTS_DIR / f"ticket-{ticket.id:06d}.html"
        file_path.write_text(html_template, encoding="utf-8")
        return file_path

    async def generate_txt(
        self,
        ticket: Ticket,
        channel_name: str,
    ) -> Path:
        """Create a plain text fallback transcript file."""
        messages = await self.db.fetch_all(
            "SELECT * FROM ticket_messages WHERE ticket_id = ? ORDER BY id ASC;",
            (ticket.id,),
        )
        lines = [
            f"=== TICKET #{ticket.id:06d} TRANSCRIPT ===",
            f"Channel: #{channel_name}",
            f"Category: {ticket.category}",
            f"User ID: {ticket.user_id}",
            f"Claimed By: {ticket.claimed_by or 'None'}",
            f"Created At: {ticket.created_at}",
            f"Closed At: {ticket.closed_at or 'Open'}",
            f"Closed By: {ticket.closed_by or 'None'}",
            "=" * 40,
            "",
        ]
        for msg in messages:
            ts = msg["created_at"]
            author = msg["author_name"]
            content = msg["content"] or ""
            att = f" [Attachments: {msg['attachments']}]" if msg["attachments"] else ""
            lines.append(f"[{ts}] {author}: {content}{att}")

        file_path = TRANSCRIPTS_DIR / f"ticket-{ticket.id:06d}.txt"
        file_path.write_text("\n".join(lines), encoding="utf-8")
        return file_path


transcript_service = TranscriptService()
