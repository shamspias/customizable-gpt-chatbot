import asyncio
from fastapi import HTTPException, APIRouter, Depends, Header, status
from fastapi.responses import StreamingResponse
from typing import AsyncGenerator

from app.schemas import ConversationSchema
from app.permissions import verify_api_key

router = APIRouter()


# Define a generator function that yields text data
async def stream_text_data(message: str) -> AsyncGenerator[str, None]:
    for i in message:
        yield i  # This will stream the provided message text
        await asyncio.sleep(0.01)


@router.post("/debug/s")
async def legal_data_conversation(conversation_request: ConversationSchema,
                                  api_key: str = Depends(verify_api_key),
                                  x_api_key: str = Header(None, alias='x-api-key'),
                                  x_conversation_id: str = Header(default=None, alias='X-Conversation-Id'),
                                  x_contact_id: str = Header(default="1", alias='X-Contact-Id')):
    try:
        message = conversation_request.message

        # Use the generator function to create a streaming response
        # The message from the request is streamed back in the response
        return StreamingResponse(stream_text_data(message),
                                 media_type="text/event-stream")

    except Exception as e:
        # Handling exceptions and returning a 500 error
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
