from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional

load_dotenv()


class Settings(BaseSettings):
    # Application config
    API_TITLE: str = Field(default="Legal Data")
    API_VERSION: str = Field(default="0.0.1")

    # Vector Database
    PINECONE_API_KEY: Optional[str] = Field(default=None)
    PINECONE_INDEX_NAME: Optional[str] = Field(default=None)
    PINECONE_NAMESPACE: Optional[str] = Field(default=None)

    # LLM Config Models
    OPENAI_MODEL_1: Optional[str] = Field(default="gpt-4-0125-preview")
    OPENAI_MODEL_2: Optional[str] = Field(default="gpt-3.5-turbo-0125")
    AZURE_MODEL_1: Optional[str] = Field(default="gpt-3.5-turbo-0125")
    FIREWORK_MODEL: Optional[str] = Field(default="accounts/fireworks/models/mixtral-8x7b-instruct")
    GOOGLE_MODEL: Optional[str] = Field(default="gemini-pro")
    OPENAI_EMBEDDED_MODEL: Optional[str] = Field(default="text-embedding-3-small")
    OPENAI_EMBEDDED_MODEL_FALLBACK: Optional[str] = Field(default="text-embedding-3-small")
    AZURE_EMBEDDED_MODEL: Optional[str] = Field(default="text-embedding-3-small")
    GROQ_MODEL: Optional[str] = Field(default="mixtral-8x7b-32768")

    # LLM Config APi Keys
    GOOGLE_API_KEY: Optional[str] = Field(default=None)
    FIREWORKS_API_KEY: Optional[str] = Field(default=None)
    OPENAI_API_KEY: Optional[str] = Field(default=None)
    GIGACHAT_API_KEY: Optional[str] = Field(default=None)
    GROQ_API_KEY: Optional[str] = Field(default=None)

    # Azure
    AZURE_OPENAI_API_KEY: Optional[str] = Field(default=None)
    AZURE_OPENAI_ENDPOINT: Optional[str] = Field(default=None)
    AZURE_OPENAI_AD_TOKEN: Optional[str] = Field(default=None)
    OPENAI_API_VERSION: Optional[str] = Field(default=None)

    # LLM Common Config
    LLM_TEMPERATURE: Optional[str] = Field(default="0.7")
    LLM_INSTRUCTION_PROMPT: str = Field(default="You are an AI")

    # Redis
    REDIS_MEMORY_URL: Optional[str] = Field(default="redis://localhost:6379/1")
    REDIS_CONVERSATION_MEMORY_URL: Optional[str] = Field(default="redis://localhost:6379/2")

    # Other Config
    MY_API_KEY: str = Field(default="1234567890")
    WEBHOOK_ENDPOINT: Optional[str]
    WEBHOOK_API_KEY: Optional[str]
    PROXY_URLS: Optional[str] = Field(default=None)

    # Task config
    CELERY_BROKER_URL: str = Field(default="redis://localhost:6379/0")
    CELERY_RESULT_BACKEND: str = Field(default="redis://localhost:6379/0")

    # Observatory by Langsmith
    LANGCHAIN_TRACING_V2: Optional[str] = Field(default=True)
    LANGCHAIN_ENDPOINT: Optional[str] = Field(default="https://api.smith.langchain.com")
    LANGCHAIN_API_KEY: Optional[str] = Field(default=None)
    LANGCHAIN_PROJECT: Optional[str] = Field(default=None)

    class Config:
        env_file = ".env"


settings = Settings()
