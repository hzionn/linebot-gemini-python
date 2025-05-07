import base64
from collections import defaultdict, deque
from io import BytesIO

import aiohttp
import PIL.Image
from fastapi import FastAPI, HTTPException, Request

# from langchain.schema.messages import HumanMessage, SystemMessage
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


async def process_text_to_LLM(text: str, user_id: str) -> str:
    """Process text using Gemini Text model and return the response."""
    # Build conversation history
    history = build_langchain_history(user_id, conversation_history)
    # Append the new user message
    history.append(HumanMessage(content=text))
    # Add a system message at the start
    history = [SystemMessage(content="You are a helpful assistant.")] + history
    response = text_model.invoke(history)
    return str(response.content)


async def process_image_to_LLM(image: PIL.Image.Image, user_id: str) -> str:
    """Process image using Gemini Vision model and return the description."""
    try:
        # Convert PIL Image to base64
        buffered = BytesIO()
        image.save(buffered, format="JPEG")
        img_str = base64.b64encode(buffered.getvalue()).decode()

        # Build conversation history (with placeholders)
        history = build_langchain_history(user_id, conversation_history)
        # Append the actual image message as the latest user message
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
        # Add a system message at the start if desired
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
        events = parser.parse(body, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    if not events:
        return "OK"

    if not isinstance(events, list):
        events = [events]

    for event in events:
        if not isinstance(event, MessageEvent):
            continue

        user_id = get_user_id(event)
        if not user_id:
            continue

        try:
            if event.message.type == "text":
                msg = event.message.text
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
            error_msg = TextSendMessage(
                text="An error occurred while processing your request."
            )
            await line_bot_api.reply_message(event.reply_token, error_msg)

    return "OK"
