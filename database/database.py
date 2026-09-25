"""
Database Manager - Supports SQLite (aiosqlite) and PostgreSQL (asyncpg).
Provides unified async execution and parameter mapping.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

import aiosqlite

try:
    import asyncpg
    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False

from config import DATABASE_URL

logger = logging.getLogger("ticketbot.database")


class Database:
    def __init__(self, db_url: str = DATABASE_URL):
        self.db_url = db_url
        self.is_postgres = db_url.startswith(("postgres://", "postgresql://"))
        self._sqlite_conn: Optional[aiosqlite.Connection] = None
        self._pg_pool: Optional[Any] = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        """Establish connection pool or file handle."""
        async with self._lock:
            if self.is_postgres:
                if not HAS_ASYNCPG:
                    raise RuntimeError("asyncpg is required for PostgreSQL. Run `pip install asyncpg`.")
                # Replace postgres:// with postgresql:// if needed for asyncpg
                pg_url = re.sub(r"^postgres://", "postgresql://", self.db_url)
                self._pg_pool = await asyncpg.create_pool(pg_url, min_size=1, max_size=10)
                logger.info("Connected to PostgreSQL database pool.")
            else:
                # SQLite
                db_path = self.db_url.replace("sqlite:///", "").replace("sqlite://", "")
                if not db_path:
                    db_path = "tickets.db"
                
                # Ensure directory exists if path contains directories
                p = Path(db_path)
                if p.parent and p.parent != Path("."):
                    p.parent.mkdir(parents=True, exist_ok=True)

                self._sqlite_conn = await aiosqlite.connect(db_path)
                self._sqlite_conn.row_factory = aiosqlite.Row
                # Enable foreign keys and WAL mode for better concurrency
                await self._sqlite_conn.execute("PRAGMA foreign_keys = ON;")
                await self._sqlite_conn.execute("PRAGMA journal_mode = WAL;")
                await self._sqlite_conn.commit()
                logger.info(f"Connected to SQLite database at: {db_path}")

    async def close(self) -> None:
        """Gracefully close database handles."""
        async with self._lock:
            if self.is_postgres and self._pg_pool:
                await self._pg_pool.close()
                self._pg_pool = None
                logger.info("Closed PostgreSQL pool.")
            elif self._sqlite_conn:
                await self._sqlite_conn.close()
                self._sqlite_conn = None
                logger.info("Closed SQLite connection.")

    def _prepare_query_for_pg(self, query: str) -> str:
        """Convert '?' placeholders into PostgreSQL '$1, $2, ...' style."""
        parts = []
        counter = 1
        for part in query.split("?"):
            parts.append(part)
            parts.append(f"${counter}")
            counter += 1
        parts.pop()  # remove extra trailing $counter
        return "".join(parts)

    async def execute(self, query: str, params: Union[Sequence[Any], Dict[str, Any]] = ()) -> None:
        """Execute a query without expecting return data (INSERT, UPDATE, DELETE)."""
        if self.is_postgres:
            pg_query = self._prepare_query_for_pg(query)
            async with self._pg_pool.acquire() as conn:
                await conn.execute(pg_query, *params)
        else:
            if self._sqlite_conn is None:
                await self.connect()
            async with self._lock:
                await self._sqlite_conn.execute(query, params)
                await self._sqlite_conn.commit()

    async def execute_returning_id(self, query: str, params: Sequence[Any] = ()) -> int:
        """Execute an INSERT and return the generated primary key."""
        if self.is_postgres:
            # If query does not contain RETURNING id, append it
            clean_query = query.strip().rstrip(";")
            if "RETURNING" not in clean_query.upper():
                clean_query += " RETURNING id"
            pg_query = self._prepare_query_for_pg(clean_query)
            async with self._pg_pool.acquire() as conn:
                result = await conn.fetchval(pg_query, *params)
                return int(result)
        else:
            if self._sqlite_conn is None:
                await self.connect()
            async with self._lock:
                cursor = await self._sqlite_conn.execute(query, params)
                await self._sqlite_conn.commit()
                return int(cursor.lastrowid)

    async def fetch_one(self, query: str, params: Sequence[Any] = ()) -> Optional[Dict[str, Any]]:
        """Fetch a single record as a dictionary."""
        if self.is_postgres:
            pg_query = self._prepare_query_for_pg(query)
            async with self._pg_pool.acquire() as conn:
                row = await conn.fetchrow(pg_query, *params)
                return dict(row) if row else None
        else:
            if self._sqlite_conn is None:
                await self.connect()
            async with self._lock:
                async with self._sqlite_conn.execute(query, params) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        return dict(row)
                    return None

    async def fetch_all(self, query: str, params: Sequence[Any] = ()) -> List[Dict[str, Any]]:
        """Fetch multiple records as a list of dictionaries."""
        if self.is_postgres:
            pg_query = self._prepare_query_for_pg(query)
            async with self._pg_pool.acquire() as conn:
                rows = await conn.fetch(pg_query, *params)
                return [dict(r) for r in rows]
        else:
            if self._sqlite_conn is None:
                await self.connect()
            async with self._lock:
                async with self._sqlite_conn.execute(query, params) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(r) for r in rows]

    async def executemany(self, query: str, seq_of_params: Sequence[Sequence[Any]]) -> None:
        """Execute multiple parameter sets for a query."""
        if self.is_postgres:
            pg_query = self._prepare_query_for_pg(query)
            async with self._pg_pool.acquire() as conn:
                await conn.executemany(pg_query, seq_of_params)
        else:
            if self._sqlite_conn is None:
                await self.connect()
            async with self._lock:
                await self._sqlite_conn.executemany(query, seq_of_params)
                await self._sqlite_conn.commit()


# Global Singleton Database Instance
db = Database()
