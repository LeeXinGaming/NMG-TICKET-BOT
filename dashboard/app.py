"""
FastAPI Web Admin Dashboard for Support Ticket Bot.
Provides browser-based monitoring, statistics, and configuration management.
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates

from config import (
    BASE_DIR,
    DASHBOARD_ADMIN_USER,
    DASHBOARD_ADMIN_PASSWORD,
    GUILD_ID,
)
from database.database import db
from utils.helpers import utc_now

logger = logging.getLogger("ticketbot.dashboard")

app = FastAPI(title="Support Ticket Bot Dashboard")
templates = Jinja2Templates(directory=str(BASE_DIR / "dashboard" / "templates"))
security = HTTPBasic()


def authenticate_user(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    """Validate HTTP Basic Authentication."""
    is_user_correct = secrets.compare_digest(credentials.username, DASHBOARD_ADMIN_USER)
    is_password_correct = secrets.compare_digest(credentials.password, DASHBOARD_ADMIN_PASSWORD)

    if not (is_user_correct and is_password_correct):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


@app.get("/health")
async def health_check():
    """Lightweight health check endpoint for Render/hosting providers."""
    return {"status": "ok", "service": "NMG-TICKET-BOT"}


@app.get("/", response_class=RedirectResponse)
async def root():
    return RedirectResponse(url="/dashboard", status_code=303)


@app.get("/logout")
async def logout():
    return HTMLResponse("<h3>Logged out. Close your browser tab or reload to log back in.</h3>", status_code=401, headers={"WWW-Authenticate": "Basic"})


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_home(request: Request, user: str = Depends(authenticate_user), message: Optional[str] = None):
    # Fetch statistics
    total_row = await db.fetch_one("SELECT COUNT(*) as count FROM tickets;")
    open_row = await db.fetch_one("SELECT COUNT(*) as count FROM tickets WHERE status = 'open';")
    closed_row = await db.fetch_one("SELECT COUNT(*) as count FROM tickets WHERE status = 'closed';")

    today_prefix = utc_now().strftime("%Y-%m-%d")
    today_row = await db.fetch_one("SELECT COUNT(*) as count FROM tickets WHERE created_at LIKE ?;", (f"{today_prefix}%",))

    month_prefix = utc_now().strftime("%Y-%m")
    month_row = await db.fetch_one("SELECT COUNT(*) as count FROM tickets WHERE created_at LIKE ?;", (f"{month_prefix}%",))

    # Fetch Top Staff
    top_staff = await db.fetch_all(
        """
        SELECT staff_id, staff_name, COUNT(*) as claim_count
        FROM ticket_claims
        GROUP BY staff_id
        ORDER BY claim_count DESC
        LIMIT 5;
        """
    )

    # Fetch Settings (default to first guild or GUILD_ID)
    settings = None
    if GUILD_ID:
        settings = await db.fetch_one("SELECT * FROM settings WHERE guild_id = ?;", (GUILD_ID,))
    if not settings:
        settings = await db.fetch_one("SELECT * FROM settings LIMIT 1;")
    if not settings:
        settings = {}

    # Fetch Auto Replies and Keywords
    auto_replies = await db.fetch_all("SELECT * FROM auto_replies ORDER BY category_name ASC;")
    keywords = await db.fetch_all("SELECT * FROM keywords ORDER BY keyword ASC;")

    stats = {
        "total": total_row["count"] if total_row else 0,
        "open": open_row["count"] if open_row else 0,
        "closed": closed_row["count"] if closed_row else 0,
        "today": today_row["count"] if today_row else 0,
        "this_month": month_row["count"] if month_row else 0,
    }

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "stats": stats,
            "settings": settings,
            "top_staff": top_staff,
            "auto_replies": auto_replies,
            "keywords": keywords,
            "message": message,
        },
    )


@app.post("/dashboard/settings")
async def save_settings(
    support_role_id: Optional[str] = Form(None),
    ticket_category_id: Optional[str] = Form(None),
    log_channel_id: Optional[str] = Form(None),
    transcript_channel_id: Optional[str] = Form(None),
    max_tickets: int = Form(1),
    ticket_name_format: str = Form("ticket-{id:06d}"),
    autoreply_enabled: int = Form(1),
    user: str = Depends(authenticate_user),
):
    guild_id = GUILD_ID or 0

    s_role = int(support_role_id) if support_role_id and support_role_id.strip().isdigit() else None
    cat_id = int(ticket_category_id) if ticket_category_id and ticket_category_id.strip().isdigit() else None
    log_id = int(log_channel_id) if log_channel_id and log_channel_id.strip().isdigit() else None
    trans_id = int(transcript_channel_id) if transcript_channel_id and transcript_channel_id.strip().isdigit() else None

    await db.execute(
        """
        INSERT INTO settings (guild_id, support_role_id, ticket_category_id, log_channel_id, transcript_channel_id, max_tickets, ticket_name_format, autoreply_enabled)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(guild_id) DO UPDATE SET
            support_role_id = excluded.support_role_id,
            ticket_category_id = excluded.ticket_category_id,
            log_channel_id = excluded.log_channel_id,
            transcript_channel_id = excluded.transcript_channel_id,
            max_tickets = excluded.max_tickets,
            ticket_name_format = excluded.ticket_name_format,
            autoreply_enabled = excluded.autoreply_enabled;
        """,
        (guild_id, s_role, cat_id, log_id, trans_id, max_tickets, ticket_name_format, autoreply_enabled),
    )

    return RedirectResponse(url="/dashboard?message=Settings+saved+successfully", status_code=303)


def run_dashboard(host: str = "0.0.0.0", port: int = 8080):
    """Entry point to run dashboard with uvicorn."""
    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    from config import DASHBOARD_HOST, DASHBOARD_PORT
    run_dashboard(host=DASHBOARD_HOST, port=DASHBOARD_PORT)
