"""veldra_llm — provider layer.

Provider-pluggable chat/structured-output (Anthropic or local Ollama) + pluggable
embeddings. The runtime and orchestrator depend only on the normalized provider
interface, so swapping providers is an env change (VELDRA_LLM_PROVIDER).
"""

from veldra_llm.chat import CHEAP_MODEL, ORCHESTRATOR_MODEL, WORKER_MODEL, get_client
from veldra_llm.embeddings import EmbeddingConfig, embed_query, embed_texts
from veldra_llm.providers import (
    AnthropicProvider,
    BaseProvider,
    OllamaProvider,
    OpenAICompatProvider,
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
    "OpenAICompatProvider",
    "ToolCall",
    "Turn",
    "prepare_json_schema",
    # embeddings
    "EmbeddingConfig",
    "embed_texts",
    "embed_query",
]
