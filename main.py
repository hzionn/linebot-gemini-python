from linebot.models import (
    MessageEvent, TextSendMessage
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.aiohttp_async_http_client import AiohttpAsyncHttpClient
from linebot import (
    AsyncLineBotApi, WebhookParser
)
from fastapi import Request, FastAPI, HTTPException
import os
import sys
from io import BytesIO
import aiohttp
import PIL.Image
import base64

# Import LangChain components with Vertex AI
from langchain_google_vertexai import ChatVertexAI
from langchain.schema.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate


# get channel_secret and channel_access_token from your environment variable
channel_secret = os.getenv('ChannelSecret', None)
channel_access_token = os.getenv('ChannelAccessToken', None)
imgage_prompt = '''
Describe this image with scientific detail, reply in zh-TW:
'''

# Vertex AI needs a project ID and possibly authentication
google_project_id = os.getenv('GOOGLE_PROJECT_ID')
# Location for Vertex AI resources, e.g., "us-central1"
google_location = os.getenv('GOOGLE_LOCATION', 'us-central1')

if channel_secret is None:
    print('Specify ChannelSecret as environment variable.')
    sys.exit(1)
if channel_access_token is None:
    print('Specify ChannelAccessToken as environment variable.')
    sys.exit(1)
if google_project_id is None:
    print('Specify GOOGLE_PROJECT_ID as environment variable.')
    sys.exit(1)

# Initialize the FastAPI app for LINEBot
app = FastAPI()
session = aiohttp.ClientSession()
async_http_client = AiohttpAsyncHttpClient(session)
line_bot_api = AsyncLineBotApi(channel_access_token, async_http_client)
parser = WebhookParser(channel_secret)

# Create LangChain Vertex AI model instances
# For Vertex AI, we use "gemini-2.0-flash" instead of "gemini-2.0-flash-lite"
text_model = ChatVertexAI(
    model_name="gemini-2.0-flash-001",
    project=google_project_id,
    location=google_location,
    max_output_tokens=1024,
)

vision_model = ChatVertexAI(
    model_name="gemini-2.0-flash-001",
    project=google_project_id,
    location=google_location,
    max_output_tokens=1024,
)


@app.post("/")
async def handle_callback(request: Request):
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = await request.body()
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
                message_content = await line_bot_api.get_message_content(
                    event.message.id
                )
                image = PIL.Image.open(BytesIO(await message_content.read()))
                response = await process_image_with_gemini(image)
                reply_msg = TextSendMessage(text=response)
                await line_bot_api.reply_message(event.reply_token, reply_msg)
            else:
                continue
        except Exception as e:
            print(f"Error processing event: {e}")
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
                content="You are a helpful assistant. For language, please use either en-US or zh-TW."
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
    # Convert PIL Image to base64
    buffered = BytesIO()
    image.save(buffered, format="JPEG")
    img_str = base64.b64encode(buffered.getvalue()).decode()

    # Create chat prompt template with system instructions and image
    prompt_template = ChatPromptTemplate.from_messages(
        [
            SystemMessage(
                content="You are a helpful assistant. Analyze the image and provide details."
            ),
            HumanMessage(
                content=[
                    {"type": "text", "text": image_prompt},
                    {
                        "type": "image_url",
                        "image_url": f"data:image/jpeg;base64,{img_str}",
                    },
                ]
            ),
        ]
    )

    # Format the prompt and call the vision model
    formatted_prompt = prompt_template.format_messages()
    response = vision_model.invoke(formatted_prompt)

    return response.content
