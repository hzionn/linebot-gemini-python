"""
Entry point for the LINE bot application.
"""

import asyncio
import base64
from collections import defaultdict
from contextlib import asynccontextmanager
from io import BytesIO

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

from app import config
from app.prompt import TEXT_SYSTEM_PROMPT, VISION_SYSTEM_PROMPT
from app.tools import tools
from app.user import (
    add_to_history,
    deque_factory,
    ensure_history_path_exists,
    get_user_id,
    get_user_history,
    save_all_histories,
    sync_inactive_users,
    to_load_user_history,
    update_user_activity,
)

last_activity = {}
conversation_history = defaultdict(deque_factory)

# Global variables for LINE Bot
line_bot_api_g = None
parser_g = None
text_model_g = None
vision_model_g = None
agent_executor_g = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup and cleanup on shutdown."""
    global line_bot_api_g, parser_g, text_model_g, vision_model_g, agent_executor_g

    ensure_history_path_exists()

    # Initialize LINE Bot
    session = aiohttp.ClientSession()
    async_http_client = AiohttpAsyncHttpClient(session)
    line_bot_api_g = AsyncLineBotApi(config.CHANNEL_ACCESS_TOKEN, async_http_client)
    parser_g = WebhookParser(config.CHANNEL_SECRET)

    print(f"Using model: {config.GEMINI_TEXT_MODEL}")
    text_model_g = ChatVertexAI(
        model_name=config.GEMINI_TEXT_MODEL,
        project=config.GOOGLE_PROJECT_ID,
        location=config.GOOGLE_LOCATION,
        max_output_tokens=config.MAX_OUTPUT_TOKENS,
    )

    vision_model_g = ChatVertexAI(
        model_name=config.GEMINI_VISION_MODEL,
        project=config.GOOGLE_PROJECT_ID,
        location=config.GOOGLE_LOCATION,
        max_output_tokens=config.MAX_OUTPUT_TOKENS,
    )

    agent_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", TEXT_SYSTEM_PROMPT),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}"),
        ]
    )

    # Create the agent
    agent = create_tool_calling_agent(
        llm=text_model_g,
        tools=tools,
        prompt=agent_prompt,
    )

    # Create the agent executor
    agent_executor_g = AgentExecutor(agent=agent, tools=tools, verbose=False)

    # Start background task to sync inactive users
    inactive_sync_task = asyncio.create_task(
        sync_inactive_users(
            last_activity=last_activity, conversation_history=conversation_history
        )
    )

    yield

    # Save all histories before shutdown
    save_all_histories(conversation_history)

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
    if agent_executor_g is None:
        return {"type": "error", "content": "Agent not initialized."}

    history = get_user_history(user_id, conversation_history)
    history.append(HumanMessage(content=text))
    history = [SystemMessage(content=TEXT_SYSTEM_PROMPT)] + history
    result = agent_executor_g.invoke({"input": history})
    return {"type": "text", "content": str(result["output"])}


async def process_image_to_LLM(image: PIL.Image.Image, user_id: str) -> str:
    """Process image using Gemini Vision model and return the description."""
    if vision_model_g is None:
        return "Vision model not initialized."
    try:
        buffered = BytesIO()
        image.save(buffered, format="JPEG")
        img_str = base64.b64encode(buffered.getvalue()).decode()

        history = get_user_history(user_id, conversation_history)
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
        response = vision_model_g.invoke(history)

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
            parser_g is not None
        ), "LINE SDK Parser not initialized. Check application startup."
        events = parser_g.parse(body, signature)
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
        if not to_load_user_history(
            user_id,
            last_activity=last_activity,
            conversation_history=conversation_history,
        ):
            # If it was already loaded, just update the activity timestamp
            update_user_activity(user_id, last_activity=last_activity)

        try:
            if line_bot_api_g is None:
                raise HTTPException(
                    status_code=500, detail="LINE Bot API not initialized."
                )
            if event.message.type == "text":
                msg = event.message.text

                add_to_history(
                    user_id,
                    "user",
                    msg,
                    last_activity=last_activity,
                    conversation_history=conversation_history,
                )

                llm_result = await process_text_to_LLM(msg, user_id)
                response = llm_result["content"]

                if not response or not response.strip():
                    response = (
                        "Sorry, the response was too long or could not be generated. "
                        "Please try a shorter or simpler request."
                    )

                add_to_history(
                    user_id,
                    "assistant",
                    response,
                    last_activity=last_activity,
                    conversation_history=conversation_history,
                )

                # Format and send reply
                response = response.replace("\\n", "\n")
                response = response.replace("**", "")
                reply_msg = TextSendMessage(text=response)
                await line_bot_api_g.reply_message(event.reply_token, reply_msg)

            elif event.message.type == "image":
                try:
                    # Get image from LINE
                    message_content = await line_bot_api_g.get_message_content(
                        event.message.id
                    )
                    image_data = await message_content.content
                    image = PIL.Image.open(BytesIO(image_data))

                    add_to_history(
                        user_id,
                        "user",
                        "[User sent an image]",  # Placeholder for image sent
                        last_activity=last_activity,
                        conversation_history=conversation_history,
                    )

                    response = await process_image_to_LLM(image, user_id)

                    add_to_history(
                        user_id,
                        "assistant",
                        response,
                        last_activity=last_activity,
                        conversation_history=conversation_history,
                    )

                    response = response.replace("\\n", "\n")
                    reply_msg = TextSendMessage(text=response)
                    await line_bot_api_g.reply_message(event.reply_token, reply_msg)
                except Exception as img_error:
                    print(f"Image processing error: {str(img_error)}")
                    error_msg = TextSendMessage(
                        text="Sorry, I encountered an error while processing your image. Please try again."
                    )
                    await line_bot_api_g.reply_message(event.reply_token, error_msg)
            else:
                continue

        except Exception as e:
            print(f"Error processing event: {str(e)}")

    return "OK"


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
