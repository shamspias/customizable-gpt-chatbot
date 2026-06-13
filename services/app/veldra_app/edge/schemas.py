"""Request/response models for the edge API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class BuildRequest(BaseModel):
    request: str = Field(description="Natural-language description of the agent to build.")
    idempotency_key: str | None = None


class AskRequest(BaseModel):
    message: str
    history: list[dict[str, Any]] = Field(
        default_factory=list, description="Prior turns [{role, text}] for multi-turn chat."
    )


class SelfModProposeRequest(BaseModel):
    instruction: str = Field(description="Natural-language change to apply to the agent.")


class SelfModApplyRequest(BaseModel):
    spec: dict[str, Any] = Field(description="The approved revised AgentSpec to persist.")


class WorkflowSaveRequest(BaseModel):
    graph: dict[str, Any] = Field(description="The WorkflowGraph (nodes + edges) to save.")


class UploadResponse(BaseModel):
    document_id: str
    kb_id: str
    filename: str
    num_pages: int
    num_chunks: int


class KbCreateRequest(BaseModel):
    name: str = Field(min_length=1, description="Knowledge base name.")


class AgentSummary(BaseModel):
    id: str
    name: str
    current_version: int


class AgentDetail(BaseModel):
    id: str
    name: str
    current_version: int
    spec: dict[str, Any]
