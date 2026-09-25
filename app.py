"""
App entrypoint for Render Web Service (FastAPI / Uvicorn / Gunicorn).
"""
import asyncio
from dashboard.app import app

if __name__ == "__main__":
    from bot import main
    asyncio.run(main())
