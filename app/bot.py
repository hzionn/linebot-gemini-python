import base64
from collections import defaultdict, deque
from io import BytesIO
from typing import Any, List, Optional, Union

import aiohttp
import PIL.Image
from fastapi import FastAPI, HTTPException, Request
from langchain.schema.messages import HumanMessage, SystemMessage
from langchain_core.messages import SystemMessage, HumanMessage
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

# Initialize FastAPI app
app = FastAPI()

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

# Store conversation history
conversation_history = defaultdict(lambda: deque(maxlen=MAX_CHAT_HISTORY))


def get_user_id(event: MessageEvent) -> Optional[str]:
    """Get user ID from LINE event."""
    return getattr(event.source, "user_id", None)


def build_langchain_history(user_id: str) -> List[Any]:
    """Build LangChain message history from stored conversation."""
    history = []
    for role, msg in conversation_history[user_id]:
        if role == "user":
            history.append(HumanMessage(content=msg))
        else:
            history.append(SystemMessage(content=msg))
    return history


def add_to_history(user_id: str, role: str, msg: Union[str, List[Any]]) -> None:
    """Add message to conversation history."""
    conversation_history[user_id].append((role, str(msg)))


async def process_image_with_gemini(image: PIL.Image.Image) -> str:
    """Process image using Gemini Vision model and return the description."""
    try:
        # Convert PIL Image to base64
        buffered = BytesIO()
        image.save(buffered, format="JPEG")
        img_str = base64.b64encode(buffered.getvalue()).decode()

        # Prepare your messages
        messages = [
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
            ),
            HumanMessage(
                content=[
                    {"type": "text", "text": "Please analyze this image and provide a structured summary."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_str}"}},
                ]
            ),
        ]

        # Call the model
        response = vision_model.invoke(messages)

        if not response.content:
            raise ValueError("Empty response from model")

        return str(response.content)

    except Exception as e:
        print(f"Image processing error in process_image_with_gemini: {str(e)}")
        raise


def resize_image(image: PIL.Image.Image, max_size: int = 512) -> PIL.Image.Image:
    image.thumbnail((max_size, max_size))
    return image


@app.post("/")
async def handle_callback(request: Request):
    """Handle LINE webhook callbacks."""
    signature = request.headers["X-Line-Signature"]
    body = await request.body()
    body = body.decode()

    try:
        events = parser.parse(body, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    if not events:
        return "OK"

    for event in events:
        if not isinstance(event, MessageEvent):
            continue

        user_id = get_user_id(event)
        if not user_id:
            continue

        try:
            if event.message.type == "text":
                msg = event.message.text
                add_to_history(user_id, "user", msg)
                history = build_langchain_history(user_id)
                history = [
                    SystemMessage(content="You are a helpful assistant.")
                ] + history
                response = text_model.invoke(history)
                add_to_history(user_id, "assistant", response.content)
                reply_msg = TextSendMessage(text=response.content)
                await line_bot_api.reply_message(event.reply_token, reply_msg)
            elif event.message.type == "image":
                try:
                    print("Starting image processing...")
                    message_content = await line_bot_api.get_message_content(
                        event.message.id
                    )
                    print("✓ Image received from LINE")
                    image_data = await message_content.content
                    image = PIL.Image.open(BytesIO(image_data))
                    print(
                        f"✓ Image converted to PIL format: {image.format} {image.size}"
                    )
                    print("Processing with Gemini Vision...")
                    resized_image = resize_image(image)
                    response = await process_image_with_gemini(resized_image)
                    if not response:
                        raise ValueError("Empty response from Gemini")
                    print("✓ Gemini Vision processing complete")

                    # Add a more descriptive user message
                    add_to_history(user_id, "user", "[User sent an image]")
                    # Add a more focused assistant response
                    add_to_history(user_id, "assistant", response)

                    reply_msg = TextSendMessage(text=response)
                    await line_bot_api.reply_message(event.reply_token, reply_msg)
                    print("✓ Response sent to LINE")
                except Exception as img_error:
                    print(f"❌ Image processing error: {str(img_error)}")
                    error_msg = TextSendMessage(
                        text="Sorry, I encountered an error while processing your image. Please try again."
                    )
                    await line_bot_api.reply_message(event.reply_token, error_msg)
            else:
                continue

        except Exception as e:
            print(f"Error processing event: {str(e)}")
            error_msg = TextSendMessage(
                text="An error occurred while processing your request."
            )
            await line_bot_api.reply_message(event.reply_token, error_msg)

    return "OK"
