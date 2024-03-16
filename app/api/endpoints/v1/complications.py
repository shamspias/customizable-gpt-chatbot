from fastapi import HTTPException, APIRouter, Depends, Header, status
from fastapi.responses import StreamingResponse
from app.schemas import ConversationSchema
from app.permissions import verify_api_key
from app.utils.message_handler import LangChainService

router = APIRouter()


@router.post("/conversation")
async def legal_data_conversation(conversation_request: ConversationSchema,
                                  api_key: str = Depends(verify_api_key),
                                  x_api_key: str = Header(None, alias='x-api-key'),
                                  x_conversation_id: str = Header(default=None, alias='X-Conversation-Id'),
                                  x_contact_id: str = Header(default="1", alias='X-Contact-Id')
                                  ):
    try:
        message = conversation_request.message
        country = conversation_request.country
        webhook_use = conversation_request.webhook_use
        if x_conversation_id is None:
            conversation_id = conversation_request.conversation_id
        else:
            conversation_id = x_conversation_id

        thread_id = str(conversation_id) + str(conversation_request.user_id)
        contact_id = x_contact_id
        image = conversation_request.image
        image_url = conversation_request.image_url
        model_name = conversation_request.main_model_name

        langchain_service = LangChainService(session_id=thread_id, main_model_name=model_name)

        return StreamingResponse(
            langchain_service.get_response(message, country),
            media_type="text/event-stream")

    except Exception as e:
        # Handling exceptions and returning a 500 error
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
