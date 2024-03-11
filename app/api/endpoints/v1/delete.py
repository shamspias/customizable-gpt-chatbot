from fastapi import HTTPException, APIRouter, Depends, Header, status

from app.permissions import verify_api_key
from app.config import settings

router = APIRouter()


@router.delete("/delete/{user_id}/{conversation_id}")
async def legal_data_conversation(conversation_id: str,
                                  user_id: str,
                                  api_key: str = Depends(verify_api_key),
                                  x_api_key: str = Header(None, alias='x-api-key')
                                  ):
    try:
        thread_id = str(conversation_id) + str(user_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
