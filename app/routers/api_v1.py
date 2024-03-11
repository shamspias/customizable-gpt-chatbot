from fastapi import APIRouter
from app.api.endpoints.v1 import complications, delete, debugs

api_router = APIRouter()

api_router.include_router(complications.router, prefix="/api/v1", tags=["Conversation"])
api_router.include_router(delete.router, prefix="/api/v1", tags=["Remove Conversation"])
api_router.include_router(debugs.router, prefix="/api/v1", tags=["Conversation Debugs"])
