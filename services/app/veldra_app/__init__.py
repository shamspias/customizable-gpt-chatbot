"""veldra_app — the single FastAPI process: edge · orchestrator · runtime · rag."""

# Importing config mirrors .env into os.environ (see config._bootstrap_dotenv) so
# the leaf provider layer (veldra_llm, which reads os.getenv) sees configured values
# no matter which veldra_app entrypoint runs first.
from veldra_app import config as _config  # noqa: F401

__version__ = "0.1.0"
