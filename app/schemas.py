from pydantic import BaseModel, Field, AnyUrl
from typing import Optional, Text


class ConversationSchema(BaseModel):
    """
    Pydantic schema to get chat request
    """
    message: str
    message_id: Optional[str]
    user_id: Optional[str]
    webhook_use: Optional[bool] = Field(default=False)
    conversation_id: Optional[str] = Field(default=None, description="Conversation id if don't put inside header")
    image: Optional[bool] = Field(default=False, description="True or False image use or not")
    image_url: Optional[str] = Field(default=None, description="Url of image that you want to analysis")
    country: Optional[str] = Field(default="", description="country")
    main_model_name: Optional[str] = Field(default="groq", description="LLM name")


class ChatRequest(BaseModel):
    """
    Pydantic schema to send chat request to conversation server
    """
    message_id: Optional[str]
    query: str
    conversation_id: Optional[str]
    image: Optional[bool] = Field(default=False)
    image_url: Optional[AnyUrl] = Field(default="")


class ChatResponse(BaseModel):
    response: Text
