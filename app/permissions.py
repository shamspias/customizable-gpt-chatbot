from fastapi import Request, HTTPException
from .config import settings


async def verify_api_key(request: Request):
    api_key = request.headers.get("x-api-key")
    expected_api_key = settings.MY_API_KEY

    if not api_key:
        raise HTTPException(status_code=401, detail="No API Key provided")
    if api_key != expected_api_key:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return api_key
