"""Safe internal Postgres query tools for structured repository records.

No raw SQL is ever accepted from the model. The agent supplies a named intent
and parameters, and this module maps that intent to a fixed parameterized query.
"""

from __future__ import annotations

import time
from typing import Any

import asyncpg

from agent_layer.config.logging import get_logger
from agent_layer.config.settings import get_settings

logger = get_logger(__name__)

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    """Create or return the asyncpg connection pool."""
    global _pool
    if _pool is None:
        settings = get_settings()
        try:
            _pool = await asyncpg.create_pool(dsn=settings.postgres_url, min_size=1, max_size=5)
        except Exception as exc:
            logger.error(
                "Postgres pool initialization failed",
                extra={
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                },
            )
            raise
        logger.debug("Postgres pool initialized")
    return _pool


async def close_pool() -> None:
    """Close the asyncpg connection pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def _safe_limit(value: Any, default: int = 10, maximum: int = 25) -> int:
    try:
        return max(1, min(int(value), maximum))
    except (TypeError, ValueError):
        return default


def _rows_to_dicts(rows: list[asyncpg.Record]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


async def ping_postgres() -> bool:
    """Return True if Postgres responds to SELECT 1."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        value = await conn.fetchval("SELECT 1")
    return value == 1


async def query_saved_repositories(intent: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run one named, read-only, parameterized repository query.

    Supported intents:
    - top_repositories_by_stars: optional language, limit
    - repositories_by_tag: tag, optional limit
    - repository_details: name
    - repositories_by_author: username, optional limit
    - language_summary: no params
    - recent_saved_repositories: optional limit
    - count_repositories: no params
    """
    params = params or {}
    started = time.perf_counter()
    pool = await get_pool()

    async with pool.acquire() as conn:
        if intent == "top_repositories_by_stars":
            limit = _safe_limit(params.get("limit"), default=10)
            language = params.get("language")
            if language:
                rows = await conn.fetch(
                    """
                    SELECT id, name, language, stars, description, saved_at
                    FROM repos
                    WHERE lower(language) = lower($1)
                    ORDER BY stars DESC, name ASC
                    LIMIT $2
                    """,
                    str(language),
                    limit,
                )
                params_count = 2
            else:
                rows = await conn.fetch(
                    """
                    SELECT id, name, language, stars, description, saved_at
                    FROM repos
                    ORDER BY stars DESC, name ASC
                    LIMIT $1
                    """,
                    limit,
                )
                params_count = 1

        elif intent == "repositories_by_tag":
            tag = str(params.get("tag", "")).strip()
            if not tag:
                raise ValueError("tag parameter is required for repositories_by_tag.")
            limit = _safe_limit(params.get("limit"), default=10)
            rows = await conn.fetch(
                """
                SELECT r.id, r.name, r.language, r.stars, r.description, r.saved_at,
                       array_agg(t.tag ORDER BY t.tag) AS tags
                FROM repos r
                JOIN tags t ON t.repo_id = r.id
                WHERE lower(t.tag) = lower($1)
                GROUP BY r.id
                ORDER BY r.stars DESC, r.name ASC
                LIMIT $2
                """,
                tag,
                limit,
            )
            params_count = 2

        elif intent == "repository_details":
            name = str(params.get("name", "")).strip()
            if not name:
                raise ValueError("name parameter is required for repository_details.")
            rows = await conn.fetch(
                """
                SELECT r.id, r.name, r.language, r.stars, r.description, r.saved_at,
                       COALESCE(array_agg(DISTINCT t.tag) FILTER (WHERE t.tag IS NOT NULL), '{}') AS tags,
                       COALESCE(json_agg(DISTINCT jsonb_build_object('username', a.username, 'role', a.role))
                                FILTER (WHERE a.username IS NOT NULL), '[]') AS authors
                FROM repos r
                LEFT JOIN tags t ON t.repo_id = r.id
                LEFT JOIN authors a ON a.repo_id = r.id
                WHERE lower(r.name) = lower($1)
                GROUP BY r.id
                LIMIT 1
                """,
                name,
            )
            params_count = 1

        elif intent == "repositories_by_author":
            username = str(params.get("username", "")).strip()
            if not username:
                raise ValueError("username parameter is required for repositories_by_author.")
            limit = _safe_limit(params.get("limit"), default=10)
            rows = await conn.fetch(
                """
                SELECT r.id, r.name, r.language, r.stars, r.description, a.username, a.role
                FROM repos r
                JOIN authors a ON a.repo_id = r.id
                WHERE lower(a.username) = lower($1)
                ORDER BY r.stars DESC, r.name ASC
                LIMIT $2
                """,
                username,
                limit,
            )
            params_count = 2

        elif intent == "language_summary":
            rows = await conn.fetch(
                """
                SELECT language,
                       COUNT(*) AS repo_count,
                       SUM(stars) AS total_stars,
                       ROUND(AVG(stars)::numeric, 2) AS avg_stars
                FROM repos
                GROUP BY language
                ORDER BY repo_count DESC, total_stars DESC
                """
            )
            params_count = 0

        elif intent == "recent_saved_repositories":
            limit = _safe_limit(params.get("limit"), default=10)
            rows = await conn.fetch(
                """
                SELECT id, name, language, stars, description, saved_at
                FROM repos
                ORDER BY saved_at DESC, id DESC
                LIMIT $1
                """,
                limit,
            )
            params_count = 1

        elif intent == "count_repositories":
            rows = await conn.fetch("SELECT COUNT(*) AS repo_count FROM repos")
            params_count = 0

        else:
            raise ValueError(
                "Unsupported query intent. Use one of: top_repositories_by_stars, "
                "repositories_by_tag, repository_details, repositories_by_author, "
                "language_summary, recent_saved_repositories, count_repositories."
            )

    exec_ms = int((time.perf_counter() - started) * 1000)
    result_rows = _rows_to_dicts(rows)
    logger.debug(
        "DB query completed",
        extra={
            "intent": intent,
            "params_count": params_count,
            "rows_returned": len(result_rows),
            "exec_ms": exec_ms,
        },
    )
    logger.info(
        "Postgres query tool response",
        extra={
            "tool_name": "query_saved_repositories",
            "result_count": len(result_rows),
            "latency_ms": exec_ms,
        },
    )
    return {"intent": intent, "rows": result_rows, "rows_returned": len(result_rows)}



