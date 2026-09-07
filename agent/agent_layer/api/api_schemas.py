"""Pydantic request and response models for the backend API."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    """Incoming chat request from the frontend or API clients."""

    query: str = Field(..., description="User's natural language question")
    session_id: str | None = Field(default=None, description="Conversation session id")
    max_tool_calls: int = Field(default=5, ge=1, le=10, description="Guard against runaway tool loops")

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("query cannot be empty")
        return cleaned


class ChatResponse(BaseModel):
    """Final answer returned by the agent."""

    answer: str
    sources: list[str]
    tool_calls_made: list[str]
    latency_ms: int


class HealthResponse(BaseModel):
    """Backend and dependency health status."""

    status: str
    qdrant: bool
    postgres: bool
    agent: bool
    version: str


class SecuritySuiteRequest(BaseModel):
    """Bounded configuration for the controlled hackathon attack suite."""

    max_tool_calls: int = Field(default=3, ge=1, le=5)
