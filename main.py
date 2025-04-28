import base64
import os
import sys
from io import BytesIO
from pathlib import Path

import aiohttp
import PIL.Image
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
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

from langchain.schema.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_vertexai import ChatVertexAI

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


@app.post("/")
async def handle_callback(request: Request):
    signature = request.headers["X-Line-Signature"]

    body = await request.body()  # get text
    body = body.decode()

    try:
        events = parser.parse(body, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    for event in events:
        if not isinstance(event, MessageEvent):
            continue

        try:
            if event.message.type == "text":
                # Process text message using LangChain with Vertex AI
                msg = event.message.text
                response = generate_text_with_langchain(f"{msg}")
                reply_msg = TextSendMessage(text=response)
                await line_bot_api.reply_message(event.reply_token, reply_msg)
            elif event.message.type == "image":
                try:
                    print("Starting image processing...")

                    # Get message content and properly await it
                    message_content = await line_bot_api.get_message_content(
                        event.message.id
                    )
                    print("✓ Image received from LINE")

                    # Await the content
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

                    reply_msg = TextSendMessage(text=response)
                    await line_bot_api.reply_message(event.reply_token, reply_msg)
                    print("✓ Response sent to LINE")

                except Exception as img_error:
                    print(f"❌ Image processing error: {str(img_error)}")
                    error_msg = TextSendMessage(
                        text=f"Image processing failed: {str(img_error)}"
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


def generate_text_with_langchain(prompt):
    """
    Generate a text completion using LangChain with Vertex AI model.
    """
    # Create a chat prompt template with system instructions
    prompt_template = ChatPromptTemplate.from_messages(
        [
            SystemMessage(
                content="You are a helpful assistant. For language, please use either en-US or zh-TW depends on the user's language."
            ),
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

        # Create chat prompt template with system instructions and image
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
                        "Please describe this image:\n"
                        f"[Image Base64: {img_str}]"
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
