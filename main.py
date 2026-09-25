"""
Main entrypoint for Render and PaaS hosting platforms.
Delegates execution to bot.py
"""
import asyncio
from bot import main

if __name__ == "__main__":
    asyncio.run(main())
