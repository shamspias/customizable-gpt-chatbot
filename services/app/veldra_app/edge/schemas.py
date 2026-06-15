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
    description: str | None = None
    retrieval_mode: str | None = Field(
        default=None, description="semantic | keyword | hybrid (default hybrid)."
    )
    embedding_model: str | None = Field(default=None, description="'provider:model' or null.")
    rerank_model: str | None = Field(default=None, description="'provider:model' or null=none.")
    vector_store: str | None = Field(default=None, description="pgvector | qdrant.")
    page_index_enabled: bool | None = None


class KbUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    retrieval_mode: str | None = None
    embedding_model: str | None = None
    rerank_model: str | None = None
    vector_store: str | None = None
    page_index_enabled: bool | None = None


class FeedbackRequest(BaseModel):
    reward: float = Field(description="-1 (bad) .. 1 (good).")
    note: str | None = None


class IdsRequest(BaseModel):
    ids: list[str] = Field(default_factory=list, description="Ids to act on (bulk).")


class TagsRequest(BaseModel):
    tags: list[str] = Field(default_factory=list, description="Tags for the agent.")


class ReflectRequest(BaseModel):
    run_id: str = Field(description="The run to reflect on and learn from.")


class LessonRequest(BaseModel):
    content: str = Field(min_length=1, description="A lesson to teach the agent (episodic memory).")


class ManualAgentRequest(BaseModel):
    spec: dict = Field(description="A full AgentSpec to persist directly (manual create).")


class SkillRequest(BaseModel):
    name: str = Field(min_length=1, description="Skill name (referenced by agents).")
    description: str = ""
    content: str = Field(default="", description="The skill's Markdown playbook.")


class SkillUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    content: str | None = None


class DocEditRequest(BaseModel):
    text: str = Field(description="Edited document text to re-embed.")


class UrlIngestRequest(BaseModel):
    url: str = Field(min_length=4, description="Web page URL to fetch and index.")


class AgentSummary(BaseModel):
    id: str
    name: str
    current_version: int
    tags: list[str] = Field(default_factory=list)
    # spec-derived stats for the roster (informative picker, no extra fetches)
    model: str = ""
    description: str = ""
    n_tools: int = 0
    n_skills: int = 0
    n_kbs: int = 0
    n_sub_agents: int = 0
    auto_improve: bool = False


class AgentDetail(BaseModel):
    id: str
    name: str
    current_version: int
    spec: dict[str, Any]
