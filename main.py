import base64
import os
import sys
from collections import defaultdict, deque
from io import BytesIO
from pathlib import Path

import aiohttp
import PIL.Image
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from langchain.schema.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_vertexai import ChatVertexAI
from linebot import AsyncLineBotApi, WebhookParser
from linebot.aiohttp_async_http_client import AiohttpAsyncHttpClient
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextSendMessage

# Load environment variables first
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
credentials_path = Path(
    os.path.join(BASE_DIR, "secrets/service-account-key.json")
).resolve()

if credentials_path.is_file():
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(credentials_path)
else:
    raise FileNotFoundError(
        f"Google Application Credentials file not found at {credentials_path}"
    )

# get channel_secret and channel_access_token from your environment variable
channel_secret = os.getenv("ChannelSecret", None)
channel_access_token = os.getenv("ChannelAccessToken", None)
# image_prompt = "Describe this image with scientific detail."

google_project_id = os.getenv("GOOGLE_PROJECT_ID")
google_location = os.getenv("GOOGLE_LOCATION", "us-central1")

if channel_secret is None:
    print("Specify ChannelSecret as environment variable.")
    sys.exit(1)
if channel_access_token is None:
    print("Specify ChannelAccessToken as environment variable.")
    sys.exit(1)
if google_project_id is None:
    print("Specify GOOGLE_PROJECT_ID as environment variable.")
    sys.exit(1)

# Initialize the FastAPI app for LINEBot
app = FastAPI()
session = aiohttp.ClientSession()
async_http_client = AiohttpAsyncHttpClient(session)
line_bot_api = AsyncLineBotApi(channel_access_token, async_http_client)
parser = WebhookParser(channel_secret)

# Create LangChain Vertex AI model instances
text_model = ChatVertexAI(
    model_name=os.getenv("GEMINI_TEXT_MODEL"),
    project=google_project_id,
    location=google_location,
    max_output_tokens=1024,
)
vision_model = ChatVertexAI(
    model_name=os.getenv("GEMINI_VISION_MODEL"),
    project=google_project_id,
    location=google_location,
    max_output_tokens=1024,
)

# Store up to 10 conversations per user (user_id: deque of (role, message))
max_chat_history = int(os.getenv("MAX_CHAT_HISTORY", "10"))
conversation_history = defaultdict(lambda: deque(maxlen=max_chat_history))


def get_user_id(event):
    # For LINE, userId is in event.source.user_id
    return getattr(event.source, "user_id", None)


def build_langchain_history(user_id):
    """
    Build LangChain message history from stored conversation.
    """
    history = []
    for role, msg in conversation_history[user_id]:
        if role == "user":
            history.append(HumanMessage(content=msg))
        else:
            history.append(SystemMessage(content=msg))
    return history


def add_to_history(user_id, role, msg):
    conversation_history[user_id].append((role, msg))


@app.post("/")
async def handle_callback(request: Request):
    signature = request.headers["X-Line-Signature"]
    body = await request.body()
    body = body.decode()

    try:
        events = parser.parse(body, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

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
                    response = await process_image_with_gemini(image)
                    if not response:
                        raise ValueError("Empty response from Gemini")
                    print("✓ Gemini Vision processing complete")
                    add_to_history(user_id, "user", "[Image]")
                    add_to_history(user_id, "assistant", response)
                    reply_msg = TextSendMessage(text=response)
                    await line_bot_api.reply_message(event.reply_token, reply_msg)
                    print("✓ Response sent to LINE")
                except Exception as img_error:
                    print(f"❌ Image processing error: {str(img_error)}")
            else:
                continue
        except Exception as e:
            print(f"Error processing event: {str(e)}")
            error_msg = TextSendMessage(
                text="An error occurred while processing your request."
            )
            await line_bot_api.reply_message(event.reply_token, error_msg)

    return "OK"


def generate_text_with_langchain(prompt):
    """
    Generate a text completion using LangChain with Vertex AI model.
    """
    # Create a chat prompt template with system instructions
    prompt_template = ChatPromptTemplate.from_messages(
        [
            SystemMessage(content="You are a helpful assistant."),
            HumanMessage(content=prompt),
        ]
    )

    # Format the prompt and call the model
    formatted_prompt = prompt_template.format_messages()
    response = text_model.invoke(formatted_prompt)

    return response.content


async def process_image_with_gemini(image):
    """
    Process image using Gemini Vision model and return the description.
    """
    try:
        # Convert PIL Image to base64
        buffered = BytesIO()
        image.save(buffered, format="JPEG")
        img_str = base64.b64encode(buffered.getvalue()).decode()

        prompt_template = ChatPromptTemplate.from_messages(
            [
                SystemMessage(
                    content=(
                        "You are a scientific advisor specialized in detailed image analysis."
                        "Please provide analysis in English (en-US)."
                    )
                ),
                HumanMessage(
                    content=(
                        "Please describe this image:\n" f"[Image Base64: {img_str}]"
                    )
                ),
            ]
        )

        # Format the prompt and call the vision model
        formatted_prompt = prompt_template.format_messages()
        response = vision_model.invoke(formatted_prompt)

        if not response.content:
            raise ValueError("Empty response from model")

        return response.content

    except Exception as e:
        print(f"Image processing error in process_image_with_gemini: {str(e)}")
        raise
