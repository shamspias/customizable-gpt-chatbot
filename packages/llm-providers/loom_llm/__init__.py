"""loom_llm — provider layer.

Provider-pluggable chat/structured-output (Anthropic or local Ollama) + pluggable
embeddings. The runtime and orchestrator depend only on the normalized provider
interface, so swapping providers is an env change (LOOM_LLM_PROVIDER).
"""

from loom_llm.chat import CHEAP_MODEL, ORCHESTRATOR_MODEL, WORKER_MODEL, get_client
from loom_llm.embeddings import EmbeddingConfig, embed_query, embed_texts
from loom_llm.providers import (
    AnthropicProvider,
    BaseProvider,
    OllamaProvider,
    ToolCall,
    Turn,
    get_provider,
    prepare_json_schema,
)

__all__ = [
    # chat / models
    "get_client",
    "ORCHESTRATOR_MODEL",
    "WORKER_MODEL",
    "CHEAP_MODEL",
    # providers
    "get_provider",
    "BaseProvider",
    "AnthropicProvider",
    "OllamaProvider",
    "ToolCall",
    "Turn",
    "prepare_json_schema",
    # embeddings
    "EmbeddingConfig",
    "embed_texts",
    "embed_query",
]
