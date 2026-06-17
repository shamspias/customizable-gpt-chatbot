"""veldra_app.edge — HTTP/SSE surface."""

from veldra_app.edge.app import router
from veldra_app.edge.auth_routes import router as auth_router
from veldra_app.edge.plugin_routes import router as plugin_router

__all__ = ["router", "auth_router", "plugin_router"]
