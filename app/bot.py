import base64
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from io import BytesIO

import aiohttp
import PIL.Image
from fastapi import FastAPI, HTTPException, Request

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_vertexai import ChatVertexAI
from linebot import AsyncLineBotApi, WebhookParser
from linebot.aiohttp_async_http_client import AiohttpAsyncHttpClient
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextSendMessage

from app.config import (
    CHANNEL_ACCESS_TOKEN,
    CHANNEL_SECRET,
    GEMINI_TEXT_MODEL,
    GEMINI_VISION_MODEL,
    GOOGLE_LOCATION,
    GOOGLE_PROJECT_ID,
    MAX_CHAT_HISTORY,
)
from app.utils import add_to_history, get_user_id, resize_image, build_langchain_history

# Global variables for LINE Bot
line_bot_api = None
parser = None
text_model = None
vision_model = None

# Store conversation history and last activity timestamps
conversation_history = defaultdict(lambda: deque(maxlen=MAX_CHAT_HISTORY))
last_activity = defaultdict(lambda: datetime.now())

# Configure history cleanup settings
INACTIVE_TIMEOUT = timedelta(
    hours=24
)  # Time after which inactive user history is cleared
CLEANUP_INTERVAL = timedelta(hours=1)  # How often to run the cleanup
last_cleanup = datetime.now()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup and cleanup on shutdown."""
    global line_bot_api, parser, text_model, vision_model

    # Initialize LINE Bot
    session = aiohttp.ClientSession()
    async_http_client = AiohttpAsyncHttpClient(session)
    line_bot_api = AsyncLineBotApi(CHANNEL_ACCESS_TOKEN, async_http_client)
    parser = WebhookParser(CHANNEL_SECRET)

    # Initialize LangChain Vertex AI models
    text_model = ChatVertexAI(
        model_name=GEMINI_TEXT_MODEL,
        project=GOOGLE_PROJECT_ID,
        location=GOOGLE_LOCATION,
        max_output_tokens=1024,
    )

    vision_model = ChatVertexAI(
        model_name=GEMINI_VISION_MODEL,
        project=GOOGLE_PROJECT_ID,
        location=GOOGLE_LOCATION,
        max_output_tokens=1024,
    )
    yield
    # Cleanup on shutdown
    if session:
        await session.close()


# Initialize FastAPI app
app = FastAPI(lifespan=lifespan)


def cleanup_inactive_histories():
    """Remove conversation histories for users inactive for more than INACTIVE_TIMEOUT."""
    global last_cleanup
    now = datetime.now()

    # Run cleanup only at specified intervals
    if now - last_cleanup < CLEANUP_INTERVAL:
        return

    inactive_users = []
    for user_id, last_time in last_activity.items():
        if now - last_time > INACTIVE_TIMEOUT:
            inactive_users.append(user_id)

    for user_id in inactive_users:
        if user_id in conversation_history:
            del conversation_history[user_id]
        del last_activity[user_id]

    last_cleanup = now
    if inactive_users:
        print(
            f"Cleaned up conversation history for {len(inactive_users)} inactive users"
        )


async def process_text_to_LLM(text: str, user_id: str) -> str:
    """Process text using Gemini Text model and return the response."""
    if text_model is None:
        return "Text model not initialized."
    history = build_langchain_history(user_id, conversation_history)
    history.append(HumanMessage(content=text))
    history = [SystemMessage(content="You are a helpful assistant.")] + history
    response = text_model.invoke(history)
    return str(response.content)


async def process_image_to_LLM(image: PIL.Image.Image, user_id: str) -> str:
    """Process image using Gemini Vision model and return the description."""
    if vision_model is None:
        return "Vision model not initialized."
    try:
        buffered = BytesIO()
        image.save(buffered, format="JPEG")
        img_str = base64.b64encode(buffered.getvalue()).decode()

        history = build_langchain_history(user_id, conversation_history)
        history.append(
            HumanMessage(
                content=[
                    {
                        "type": "text",
                        "text": "Please analyze this image and provide a structured summary.",
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{img_str}"},
                    },
                ]
            )
        )
        history = [
            SystemMessage(
                content=(
                    "You are a scientific advisor specialized in detailed image analysis. "
                    "The following image is a general image. "
                    "Please describe the following details in English (en-US):\n"
                    "- Notable objects or elements\n"
                    "- Context or setting\n"
                    "- Any other relevant details\n"
                    "If any information is missing or unclear, state so. "
                    "Keep your response concise and under 200 words."
                )
            )
        ] + history

        response = vision_model.invoke(history)

        if not response.content:
            raise ValueError("Empty response from model")

        return str(response.content)

    except Exception as e:
        print(f"Image processing error in process_image_with_gemini: {str(e)}")
        raise


@app.post("/")
async def handle_callback(request: Request):
    """Handle LINE webhook callbacks."""
    signature = request.headers["X-Line-Signature"]
    body = await request.body()
    body = body.decode()

    try:
        assert (
            parser is not None
        ), "LINE SDK Parser not initialized. Check application startup."
        events = parser.parse(body, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    if not events:
        return "OK"

    if not isinstance(events, list):
        events = [events]

    # Run periodic cleanup of inactive user histories
    cleanup_inactive_histories()

    for event in events:
        if not isinstance(event, MessageEvent):
            continue

        user_id = get_user_id(event)
        if not user_id:
            continue

        # Update last activity timestamp for this user
        last_activity[user_id] = datetime.now()

        try:
            if line_bot_api is None:
                raise HTTPException(
                    status_code=500, detail="LINE Bot API not initialized."
                )
            if event.message.type == "text":
                msg = event.message.text
                add_to_history(user_id, "user", msg, conversation_history)
                response = await process_text_to_LLM(msg, user_id)
                add_to_history(user_id, "assistant", response, conversation_history)
                reply_msg = TextSendMessage(text=response)
                await line_bot_api.reply_message(event.reply_token, reply_msg)
            elif event.message.type == "image":
                try:
                    message_content = await line_bot_api.get_message_content(
                        event.message.id
                    )
                    image_data = await message_content.content
                    image = PIL.Image.open(BytesIO(image_data))
                    resized_image = resize_image(image)
                    add_to_history(
                        user_id, "user", "[User sent an image]", conversation_history
                    )
                    response = await process_image_to_LLM(resized_image, user_id)
                    add_to_history(user_id, "assistant", response, conversation_history)
                    reply_msg = TextSendMessage(text=response)
                    await line_bot_api.reply_message(event.reply_token, reply_msg)
                except Exception as img_error:
                    print(f"Image processing error: {str(img_error)}")
                    error_msg = TextSendMessage(
                        text="Sorry, I encountered an error while processing your image. Please try again."
                    )
                    await line_bot_api.reply_message(event.reply_token, error_msg)
            else:
                continue

        except Exception as e:
            print(f"Error processing event: {str(e)}")

    return "OK"


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
