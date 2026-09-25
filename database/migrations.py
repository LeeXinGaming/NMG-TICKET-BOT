"""
Database Migrations and Automatic Schema Initializer.
Sets up tables and default seeds for tickets, settings, categories, and auto-replies.
"""

from __future__ import annotations

import logging
from datetime import datetime
from database.database import Database, db
from utils.helpers import utc_now

logger = logging.getLogger("ticketbot.migrations")


async def init_schema(database: Database = db) -> None:
    """Initialize database tables and seed baseline data."""
    logger.info("Initializing database schema...")
    await database.connect()

    is_pg = database.is_postgres
    auto_id = "SERIAL PRIMARY KEY" if is_pg else "INTEGER PRIMARY KEY AUTOINCREMENT"
    bigint = "BIGINT"
    bool_type = "BOOLEAN" if is_pg else "INTEGER"

    # Schema creation scripts
    queries = [
        f"""
        CREATE TABLE IF NOT EXISTS users (
            id {auto_id},
            discord_user_id {bigint} UNIQUE NOT NULL,
            username TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """,
        f"""
        CREATE TABLE IF NOT EXISTS tickets (
            id {auto_id},
            discord_channel_id {bigint} NOT NULL,
            guild_id {bigint} NOT NULL,
            user_id {bigint} NOT NULL,
            category TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            claimed_by {bigint},
            created_at TEXT NOT NULL,
            closed_at TEXT,
            closed_by {bigint}
        );
        """,
        f"""
        CREATE TABLE IF NOT EXISTS ticket_messages (
            id {auto_id},
            ticket_id INTEGER NOT NULL,
            message_id {bigint} NOT NULL,
            author_id {bigint} NOT NULL,
            author_name TEXT NOT NULL,
            content TEXT,
            attachments TEXT,
            created_at TEXT NOT NULL
        );
        """,
        f"""
        CREATE TABLE IF NOT EXISTS ticket_claims (
            id {auto_id},
            ticket_id INTEGER NOT NULL,
            staff_id {bigint} NOT NULL,
            staff_name TEXT NOT NULL,
            claimed_at TEXT NOT NULL,
            released_at TEXT
        );
        """,
        f"""
        CREATE TABLE IF NOT EXISTS ticket_categories (
            id {auto_id},
            name TEXT UNIQUE NOT NULL,
            emoji TEXT NOT NULL,
            description TEXT NOT NULL,
            role_id {bigint},
            auto_reply TEXT,
            enabled {bool_type} DEFAULT 1,
            created_at TEXT NOT NULL
        );
        """,
        f"""
        CREATE TABLE IF NOT EXISTS auto_replies (
            id {auto_id},
            category_name TEXT UNIQUE NOT NULL,
            message TEXT NOT NULL,
            enabled {bool_type} DEFAULT 1,
            updated_at TEXT NOT NULL
        );
        """,
        f"""
        CREATE TABLE IF NOT EXISTS keywords (
            id {auto_id},
            keyword TEXT UNIQUE NOT NULL,
            response TEXT NOT NULL,
            enabled {bool_type} DEFAULT 1,
            created_by {bigint},
            created_at TEXT NOT NULL
        );
        """,
        f"""
        CREATE TABLE IF NOT EXISTS settings (
            guild_id {bigint} PRIMARY KEY,
            support_role_id {bigint},
            ticket_category_id {bigint},
            log_channel_id {bigint},
            transcript_channel_id {bigint},
            panel_channel_id {bigint},
            panel_message_id {bigint},
            max_tickets INTEGER DEFAULT 1,
            ticket_name_format TEXT DEFAULT 'ticket-{{id:06d}}',
            autoreply_enabled {bool_type} DEFAULT 1,
            require_registration {bool_type} DEFAULT 1,
            registered_role_id {bigint},
            registration_channel_id {bigint}
        );
        """,
        f"""
        CREATE TABLE IF NOT EXISTS registered_users (
            id {auto_id},
            guild_id {bigint} NOT NULL,
            discord_user_id {bigint} NOT NULL,
            username TEXT NOT NULL,
            full_name TEXT NOT NULL,
            phone_or_id TEXT NOT NULL,
            notes TEXT,
            status TEXT NOT NULL DEFAULT 'registered',
            registered_at TEXT NOT NULL,
            registered_by {bigint},
            UNIQUE(guild_id, discord_user_id)
        );
        """,
        f"""
        CREATE TABLE IF NOT EXISTS ticket_logs (
            id {auto_id},
            guild_id {bigint} NOT NULL,
            ticket_id INTEGER,
            action TEXT NOT NULL,
            actor_id {bigint},
            details TEXT,
            created_at TEXT NOT NULL
        );
        """
    ]

    for q in queries:
        await database.execute(q)

    # Safe column migrations for existing installations
    alter_cols = [
        f"ALTER TABLE settings ADD COLUMN require_registration {bool_type} DEFAULT 1;",
        f"ALTER TABLE settings ADD COLUMN registered_role_id {bigint};",
        f"ALTER TABLE settings ADD COLUMN registration_channel_id {bigint};",
    ]
    for alter_query in alter_cols:
        try:
            await database.execute(alter_query)
        except Exception:
            # Column already exists
            pass


    # Seed Default Categories if none exist
    cat_count = await database.fetch_one("SELECT COUNT(*) as count FROM ticket_categories;")
    current_cat_count = cat_count["count"] if cat_count else 0

    if current_cat_count == 0:
        logger.info("Seeding default ticket categories...")
        now = utc_now().isoformat()
        categories = [
            ("General Support", "🎫", "General inquiries and customer help", None, 1, now),
            ("Payment Support", "💳", "Billing, payments, transactions and receipts", None, 1, now),
            ("Purchase Support", "🛒", "Product inquiries, orders and subscriptions", None, 1, now),
            ("Report Problem", "🐛", "Report technical bugs, glitches, or member violations", None, 1, now),
            ("Contact Staff", "📞", "Direct inquiry for senior administrators", None, 1, now),
            ("Other", "📌", "Inquiries not covered by standard categories", None, 1, now),
        ]
        cat_insert = (
            "INSERT INTO ticket_categories (name, emoji, description, role_id, enabled, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?);"
        )
        for cat in categories:
            await database.execute(cat_insert, cat)

    # Seed Default Auto Replies if none exist
    reply_count = await database.fetch_one("SELECT COUNT(*) as count FROM auto_replies;")
    current_reply_count = reply_count["count"] if reply_count else 0

    if current_reply_count == 0:
        logger.info("Seeding default auto-replies...")
        now = utc_now().isoformat()
        default_replies = [
            ("General Support", "Hello! 👋\n\nYour ticket has been received.\n\nPlease describe your question or issue in detail. A support representative will be with you shortly.", 1, now),
            ("Payment Support", "Hello! 👋\n\nFor payment support, please provide:\n• Your Transaction / Order ID\n• Payment method used\n• Screenshot of proof (if applicable)\n\nOur billing team will review it soon.", 1, now),
            ("Purchase Support", "Hello! 👋\n\nThank you for your interest! Please tell us which product or service you want to purchase or have questions about.", 1, now),
            ("Report Problem", "Hello! 👋\n\nThank you for reporting this issue. Please describe the problem, steps to reproduce, and attach screenshots or logs if possible.", 1, now),
            ("Contact Staff", "Hello! 👋\n\nA senior staff member has been notified and will reply as soon as they are available.", 1, now),
            ("Other", "Hello! 👋\n\nYour ticket has been opened. Please describe how we can assist you today.", 1, now),
        ]
        reply_insert = "INSERT INTO auto_replies (category_name, message, enabled, updated_at) VALUES (?, ?, ?, ?);"
        for rep in default_replies:
            await database.execute(reply_insert, rep)

    # Seed Default Keywords if none exist
    kw_count = await database.fetch_one("SELECT COUNT(*) as count FROM keywords;")
    current_kw_count = kw_count["count"] if kw_count else 0

    if current_kw_count == 0:
        logger.info("Seeding default keyword responses...")
        now = utc_now().isoformat()
        default_keywords = [
            ("payment", "You can use the payment methods shown in our announcements or billing channels. If you have a payment dispute, please send your transaction ID here.", 1, None, now),
            ("order", "Please provide your Order ID so our support team can verify the order status immediately.", 1, None, now),
            ("how to pay", "We accept major payment gateways and bank transfers. Please let us know which payment method you prefer.", 1, None, now),
        ]
        kw_insert = "INSERT INTO keywords (keyword, response, enabled, created_by, created_at) VALUES (?, ?, ?, ?, ?);"
        for kw in default_keywords:
            await database.execute(kw_insert, kw)

    logger.info("Database schema initialized and verified successfully.")
