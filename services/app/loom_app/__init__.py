"""loom_app — the single FastAPI process: edge · orchestrator · runtime · rag."""

# Importing config mirrors .env into os.environ (see config._bootstrap_dotenv) so
# the leaf provider layer (loom_llm, which reads os.getenv) sees configured values
# no matter which loom_app entrypoint runs first.
from loom_app import config as _config  # noqa: F401

__version__ = "0.1.0"
