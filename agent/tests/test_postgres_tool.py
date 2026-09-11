"""Regression tests for Postgres tool infrastructure."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from agent_layer.services import postgres_tool


class PostgresPoolTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        postgres_tool._pool = None

    async def asyncTearDown(self) -> None:
        postgres_tool._pool = None

    async def test_get_pool_logs_initialization_failure(self) -> None:
        failure = ConnectionError("database unavailable")

        with (
            patch.object(postgres_tool.asyncpg, "create_pool", new=AsyncMock(side_effect=failure)),
            patch.object(postgres_tool.logger, "error") as log_error,
        ):
            with self.assertRaises(ConnectionError):
                await postgres_tool.get_pool()

        log_error.assert_called_once()
        message, = log_error.call_args.args
        self.assertEqual(message, "Postgres pool initialization failed")
        self.assertEqual(log_error.call_args.kwargs["extra"]["error_type"], "ConnectionError")
        self.assertEqual(log_error.call_args.kwargs["extra"]["error_message"], "database unavailable")
        self.assertIsNone(postgres_tool._pool)


if __name__ == "__main__":
    unittest.main()
