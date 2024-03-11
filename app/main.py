from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.celery_worker import celery_app
from app.routers.api_v1 import api_router

from app.config import settings

app = FastAPI(title=settings.API_TITLE, version=settings.API_VERSION)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

app.include_router(api_router)
