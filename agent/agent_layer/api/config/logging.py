"""Agent API logging helpers.

The API reuses the shared request-id aware JSON logger from the agent
package so request traces stay consistent when the FastAPI route calls the
agent runtime in-process.
"""

from agent_layer.config.logging import (  # noqa: F401
    JsonLogFormatter,
    get_logger,
    get_request_id,
    reset_request_id,
    set_request_id,
    setup_logging,
)
