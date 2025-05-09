import os
import base64
import pickle
import asyncio
from contextlib import asynccontextmanager
from io import BytesIO
from collections import defaultdict, deque
from datetime import timedelta, datetime, UTC
import aiohttp
import PIL.Image
from fastapi import FastAPI, HTTPException, Request
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
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
from app.prompt import TEXT_SYSTEM_PROMPT, VISION_SYSTEM_PROMPT
from app.tools import tools
from app.utils import build_langchain_history, get_user_id, add_to_history

# Global variables for LINE Bot
line_bot_api = None
parser = None
text_model = None
vision_model = None
agent_executor = None

ENV = os.getenv("ENV", "prod")
HISTORY_BASE_PATH = "/history/history/" if ENV == "prod" else "history"
INACTIVITY_THRESHOLD = timedelta(minutes=10)
last_activity = {}  # Dictionary to track last activity timestamps


def deque_factory():
    return deque(maxlen=MAX_CHAT_HISTORY)


conversation_history = defaultdict(deque_factory)


async def sync_inactive_users():
    while True:
        now = datetime.now(UTC)
        for user_id, last_time in list(last_activity.items()):
            if now - last_time > INACTIVITY_THRESHOLD:
                history = conversation_history.get(user_id)
                if history:
                    file_path = os.path.join(HISTORY_BASE_PATH, f"{user_id}.pkl")
                    try:
                        with open(file_path, "wb") as f:
                            pickle.dump(history, f)
                        print(f"Saved history for user {user_id}")
                    except Exception as e:
                        print(f"Error saving history for user {user_id}: {e}")
                    print(f"Deleted in-memory history for user {user_id}")
                    del conversation_history[user_id]
                    del last_activity[user_id]
        await asyncio.sleep(60)  # Check every minute


def load_user_history(user_id: str):
    file_path = os.path.join(HISTORY_BASE_PATH, f"{user_id}.pkl")
    if os.path.exists(file_path):
        try:
            with open(file_path, "rb") as f:
                conversation_history[user_id] = pickle.load(f)
            print(f"Loaded history for user {user_id}")
        except Exception as e:
            print(f"Error loading history for user {user_id}: {e}")
            conversation_history[user_id] = deque_factory()
            print(f"Created new history for user {user_id} after load error")
    else:
        conversation_history[user_id] = deque_factory()
        print(f"Created new history for user {user_id}")
    last_activity[user_id] = datetime.now(UTC)


def save_user_history(user_id: str):
    """Save user conversation history to disk with error handling."""
    history = conversation_history.get(user_id)
    if not history:
        return

    file_path = os.path.join(HISTORY_BASE_PATH, f"{user_id}.pkl")
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "wb") as f:
            pickle.dump(history, f)
    except Exception as e:
        print(f"Error saving history for user {user_id}: {e}")


def cleanup_inactive_users():
    now = datetime.now(UTC)
    for user_id in list(last_activity.keys()):
        if now - last_activity[user_id] > INACTIVITY_THRESHOLD:
            # Save history before removing
            save_user_history(user_id)
            del conversation_history[user_id]
            del last_activity[user_id]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup and cleanup on shutdown."""
    global line_bot_api, parser, text_model, vision_model, agent_executor

    # Ensure history directory exists
    try:
        os.makedirs(HISTORY_BASE_PATH, exist_ok=True)
        print(f"Ensured history directory exists: {HISTORY_BASE_PATH}")
    except Exception as e:
        print(f"Error creating history directory: {e}")

    # Initialize LINE Bot
    session = aiohttp.ClientSession()
    async_http_client = AiohttpAsyncHttpClient(session)
    line_bot_api = AsyncLineBotApi(CHANNEL_ACCESS_TOKEN, async_http_client)
    parser = WebhookParser(CHANNEL_SECRET)

    print(f"Using model: {GEMINI_TEXT_MODEL}")
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

    # Create the agent prompt
    agent_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", TEXT_SYSTEM_PROMPT),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}"),
        ]
    )

    # Create the agent
    agent = create_tool_calling_agent(
        llm=text_model,
        tools=tools,
        prompt=agent_prompt,
    )

    # Create the agent executor
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=False)

    # Start background task to sync inactive users
    inactive_sync_task = asyncio.create_task(sync_inactive_users())

    yield

    # Save all histories before shutdown
    print("Saving all conversation histories before shutdown...")
    for user_id in list(conversation_history.keys()):
        save_user_history(user_id)

    # Cleanup on shutdown
    if session:
        await session.close()

    # Cancel background task
    inactive_sync_task.cancel()
    try:
        await inactive_sync_task
    except asyncio.CancelledError:
        pass


# Initialize FastAPI app
app = FastAPI(lifespan=lifespan)


async def process_text_to_LLM(text: str, user_id: str) -> dict:
    """Process text using Gemini Text model and return the response via agent workflow."""
    # print(f"Text system prompt: {TEXT_SYSTEM_PROMPT}")
    if agent_executor is None:
        return {"type": "error", "content": "Agent not initialized."}
    history = build_langchain_history(user_id, conversation_history)
    history.append(HumanMessage(content=text))
    history = [SystemMessage(content=TEXT_SYSTEM_PROMPT)] + history
    result = agent_executor.invoke({"input": history})
    return {"type": "text", "content": str(result["output"])}


async def process_image_to_LLM(image: PIL.Image.Image, user_id: str) -> str:
    """Process image using Gemini Vision model and return the description."""
    if vision_model is None:
        return "Vision model not initialized."
    try:
        buffered = BytesIO()
        image.save(buffered, format="JPEG")
        img_str = base64.b64encode(buffered.getvalue()).decode()

        history = build_langchain_history(user_id, conversation_history)
        message_content = [
            {
                "type": "text",
                "text": "Please analyze this image and provide a structured summary.",
            },
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{img_str}"},
            },
        ]

        history.append(HumanMessage(content=message_content))
        history = [SystemMessage(content=VISION_SYSTEM_PROMPT)] + history
        response = vision_model.invoke(history)

        if not response or not response.content:
            raise ValueError("Empty response from model")

        return str(response.content)

    except Exception as e:
        print(f"Image processing error in process_image_with_gemini: {str(e)}")
        print(f"Error type: {type(e)}")
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

    for event in events:
        if not isinstance(event, MessageEvent):
            continue

        user_id = get_user_id(event)
        if not user_id:
            continue

        # Load user history if not already loaded
        if user_id not in conversation_history:
            load_user_history(user_id)
        else:
            # Update last activity timestamp
            last_activity[user_id] = datetime.now(UTC)

        try:
            if line_bot_api is None:
                raise HTTPException(
                    status_code=500, detail="LINE Bot API not initialized."
                )
            if event.message.type == "text":
                msg = event.message.text
                add_to_history(
                    user_id, "user", msg, conversation_history, last_activity
                )
                # Update last activity timestamp after adding to history
                last_activity[user_id] = datetime.now(UTC)
                llm_result = await process_text_to_LLM(msg, user_id)
                response = llm_result["content"]
                if not response or not response.strip():
                    response = "Sorry, the response was too long or could not be generated. Please try a shorter or simpler request."
                add_to_history(
                    user_id, "assistant", response, conversation_history, last_activity
                )
                # Update last activity timestamp after adding to history
                last_activity[user_id] = datetime.now(UTC)
                response = response.replace("\\n", "\n")
                reply_msg = TextSendMessage(text=response)
                await line_bot_api.reply_message(event.reply_token, reply_msg)

            elif event.message.type == "image":
                try:
                    message_content = await line_bot_api.get_message_content(
                        event.message.id
                    )
                    image_data = await message_content.content
                    image = PIL.Image.open(BytesIO(image_data))
                    add_to_history(
                        user_id,
                        "user",
                        "[User sent an image]",
                        conversation_history,
                        last_activity,
                    )
                    # Update last activity timestamp after adding to history
                    last_activity[user_id] = datetime.now(UTC)
                    response = await process_image_to_LLM(image, user_id)
                    add_to_history(
                        user_id,
                        "assistant",
                        response,
                        conversation_history,
                        last_activity,
                    )
                    # Update last activity timestamp after adding to history
                    last_activity[user_id] = datetime.now(UTC)
                    response = response.replace("\\n", "\n")
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
