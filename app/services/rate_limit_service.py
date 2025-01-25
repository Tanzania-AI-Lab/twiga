import logging
from fastapi import Request, HTTPException
from app.database import db
from app.utils.string_manager import strings, StringCategory
from app.services.whatsapp_service import whatsapp_client
from fastapi.responses import JSONResponse
from app.utils.whatsapp_utils import get_request_type, RequestType
from app.redis.engine import get_redis_client
from app.config import settings

logger = logging.getLogger(__name__)

DAILY_MESSAGES_LIMIT = settings.daily_messages_limit
APP_DAILY_MESSAGES_LIMIT = settings.app_daily_messages_limit
DAILY_TOKEN_LIMIT = settings.daily_token_limit
APP_DAILY_TOKEN_LIMIT = settings.app_daily_token_limit


async def respond_with_rate_limit_message(
    phone_number: str, message_key: str
) -> JSONResponse:
    logger.debug(f"Responding with rate-limit message. message_key={message_key}")
    user = await db.get_or_create_user(wa_id=phone_number)
    assert user.id is not None

    response_text = strings.get_string(StringCategory.RATE_LIMIT, message_key)
    await whatsapp_client.send_message(user.wa_id, response_text)
    return JSONResponse(content={"status": "ok"}, status_code=200)


def extract_phone_number(body: dict) -> str | None:
    logger.debug("Attempting to extract phone_number from the request body.")
    try:
        return body["entry"][0]["changes"][0]["value"]["contacts"][0]["wa_id"]
    except KeyError:
        logger.debug("Failed to find wa_id in contacts. Trying 'messages' field.")
        try:
            return body["entry"][0]["changes"][0]["value"]["messages"][0]["from"]
        except KeyError:
            logger.warning("Could not extract phone_number from request body.")
            return None


async def get_int_from_redis(redis_client, key: str) -> int:
    value = await redis_client.get(key)
    return int(value) if value else 0


async def rate_limit(request: Request):
    logger.debug("Entering rate_limit function.")
    body = await request.json()
    request_type = get_request_type(body)

    if request_type != RequestType.VALID_MESSAGE:
        logger.debug("Request type is not VALID_MESSAGE. Skipping rate limiting.")
        return

    logger.debug(f"Determined request type in rate Limit: {request_type}")
    phone_number = extract_phone_number(body)
    logger.debug(f"Extracted phone_number: {phone_number}")
    if not phone_number:
        logger.warning("Phone number not found in request body.")
        raise HTTPException(status_code=400, detail="Phone number is required")

    redis_client = get_redis_client()

    user_key = f"rate_limit:user:{phone_number}"
    app_key = "rate_limit:app"

    user_messages = await get_int_from_redis(redis_client, f"{user_key}:messages")
    user_messages = await redis_client.incr(f"{user_key}:messages")
    app_messages = await redis_client.incr(f"{app_key}:messages")

    if user_messages > DAILY_MESSAGES_LIMIT:
        return await respond_with_rate_limit_message(phone_number, "user_message_limit")

    if app_messages > APP_DAILY_MESSAGES_LIMIT:
        return await respond_with_rate_limit_message(
            phone_number, "global_message_limit"
        )

    user_tokens = await get_int_from_redis(redis_client, f"{user_key}:tokens")
    app_tokens = await get_int_from_redis(redis_client, f"{app_key}:tokens")

    if user_tokens > DAILY_TOKEN_LIMIT:
        return await respond_with_rate_limit_message(phone_number, "user_token_limit")

    if app_tokens > APP_DAILY_TOKEN_LIMIT:
        return await respond_with_rate_limit_message(phone_number, "global_token_limit")
    logger.debug(
        f"Usage for user : {phone_number}. "
        f"Messages: {user_messages}, "
        f"Messages limit: {DAILY_MESSAGES_LIMIT}, "
        f"Tokens: {user_tokens}, "
        f"Tokens limit: {DAILY_TOKEN_LIMIT}"
    )
    logger.debug(
        f"Usage for app: "
        f"App messages: {app_messages}, "
        f"App messages limit: {APP_DAILY_MESSAGES_LIMIT}, "
        f"App tokens: {app_tokens}, "
        f"App tokens limit: {APP_DAILY_TOKEN_LIMIT}"
    )


# Note we don't need to add keep ttl for the keys as we are resetting the keys daily with the scheduler in app/scheduler.py
# This can help avoid race conditions and ensure that the keys are reset at the same time every day.
