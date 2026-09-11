"""Compatibility adapter for API settings.

New code should import settings from agent_layer.config.settings.
"""

from __future__ import annotations

from agent_layer.config.settings import AgentSettings, get_settings

BackendSettings = AgentSettings


def get_backend_settings() -> BackendSettings:
    """Return cached agent/API settings."""

    return get_settings()
