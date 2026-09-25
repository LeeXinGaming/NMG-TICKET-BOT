"""
Support Ticket Bot - Main Entrypoint.
Initializes the Discord bot, database migrations, persistent views, and cog extensions.
Run with: python bot.py
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
from typing import Optional

import discord
from discord.ext import commands

from config import (
    DISCORD_TOKEN,
    ENABLE_DASHBOARD,
    DASHBOARD_HOST,
    DASHBOARD_PORT,
    ENABLE_PRIVILEGED_INTENTS,
)
from database.database import db
from database.migrations import init_schema
from services.logging_service import logger

# Cog extensions to load
INITIAL_EXTENSIONS = [
    "cogs.events",
    "cogs.tickets",
    "cogs.admin",
    "cogs.autoreply",
]



class SupportBot(commands.Bot):
    """Custom bot class supporting persistent views and graceful lifecycle management."""

    def __init__(self, intents: Optional[discord.Intents] = None):
        if intents is None:
            intents = discord.Intents.default()
            intents.guilds = True
            intents.messages = True
            if ENABLE_PRIVILEGED_INTENTS:
                intents.members = True
                intents.message_content = True

        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,
        )
        self._shutdown_event = asyncio.Event()

    async def setup_hook(self) -> None:
        """Called by discord.py before the websocket connection is initiated."""
        logger.info("Starting bot setup hook...")

        # 1. Initialize Database Schema and Seeds
        await init_schema(db)

        # 2. Load Cogs
        for ext in INITIAL_EXTENSIONS:
            try:
                await self.load_extension(ext)
                logger.info(f"Loaded extension: {ext}")
            except Exception as e:
                logger.error(f"Failed to load extension {ext}: {e}", exc_info=True)

        logger.info("Bot setup hook completed successfully.")

    async def close(self) -> None:
        """Gracefully close bot and database connections."""
        logger.info("Initiating graceful shutdown...")
        try:
            await super().close()
        finally:
            await db.close()
            logger.info("Database connections closed. Bot shutdown complete.")


async def start_web_dashboard() -> None:
    """Launch the optional FastAPI admin dashboard in the background."""
    try:
        import uvicorn
        from dashboard.app import app
        config = uvicorn.Config(app=app, host=DASHBOARD_HOST, port=DASHBOARD_PORT, log_level="warning")
        server = uvicorn.Server(config)
        logger.info(f"Starting web dashboard on http://{DASHBOARD_HOST}:{DASHBOARD_PORT}/dashboard")
        await server.serve()
    except Exception as e:
        logger.error(f"Dashboard failed to start: {e}", exc_info=True)


async def main() -> None:
    """Main application loop."""
    if not DISCORD_TOKEN or DISCORD_TOKEN == "your_bot_token_here":
        logger.critical(
            "DISCORD_TOKEN is missing or not configured!\n"
            "Please create a .env file from .env.example and supply a valid bot token.\n"
            "See README.md for instructions."
        )
        sys.exit(1)

    # Optional background web dashboard
    if ENABLE_DASHBOARD:
        asyncio.create_task(start_web_dashboard())

    bot = SupportBot()

    # Graceful shutdown handler for UNIX & Windows signals
    loop = asyncio.get_running_loop()

    def signal_handler():
        logger.info("Shutdown signal received.")
        asyncio.create_task(bot.close())

    if sys.platform != "win32":
        for s in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(s, signal_handler)

    try:
        await bot.start(DISCORD_TOKEN)
    except discord.errors.PrivilegedIntentsRequired:
        logger.warning(
            "⚠️ Privileged Gateway Intents (Server Members / Message Content) are not enabled in Discord Developer Portal.\n"
            "👉 Falling back to Standard Gateway Intents so the bot starts and functions immediately!\n"
            "💡 To enable full keyword scanner & member sync, go to https://discord.com/developers/applications -> Bot -> Privileged Gateway Intents."
        )
        safe_intents = discord.Intents.default()
        safe_intents.guilds = True
        safe_intents.messages = True
        bot = SupportBot(intents=safe_intents)
        await bot.start(DISCORD_TOKEN)
    except discord.LoginFailure:
        logger.critical("Invalid Discord Bot Token provided. Please verify DISCORD_TOKEN in .env.")
    except Exception as e:
        logger.error(f"Fatal bot runtime error: {e}", exc_info=True)
    finally:
        if not bot.is_closed():
            await bot.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application terminated by user (KeyboardInterrupt).")
