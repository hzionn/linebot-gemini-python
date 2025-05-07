from datetime import datetime
from typing import Any, List, Optional

import PIL.Image
from langchain_core.messages import (AIMessage, HumanMessage, SystemMessage,
                                     ToolMessage)
from linebot.models import MessageEvent


def resize_image(image: PIL.Image.Image, max_size: int = 1024) -> PIL.Image.Image:
    image.thumbnail((max_size, max_size))
    return image


def get_user_id(event: MessageEvent) -> Optional[str]:
    """Get user ID from LINE event."""
    return getattr(event.source, "user_id", None)


def build_langchain_history(user_id: str, conversation_history: dict) -> List[Any]:
    """Build LangChain message history from stored conversation."""
    history = []
    try:
        for role, msg in conversation_history[user_id]:
            if role == "user":
                history.append(HumanMessage(content=msg))
            elif role == "assistant":
                history.append(AIMessage(content=msg))
            elif role == "tool":
                # Expect msg to be a dict with 'content' and 'tool_call_id'
                if isinstance(msg, dict) and "content" in msg and "tool_call_id" in msg:
                    history.append(
                        ToolMessage(
                            content=msg["content"], tool_call_id=msg["tool_call_id"]
                        )
                    )
                else:
                    history.append(SystemMessage(content=str(msg)))
            else:
                history.append(SystemMessage(content=msg))
    except Exception as e:
        print(f"Error building langchain history for user {user_id}: {str(e)}")
    return history


def add_to_history(
    user_id: str, role: str, msg: Any, conversation_history: dict
) -> None:
    """Add message to conversation history."""
    try:
        conversation_history[user_id].append((role, msg))
    except Exception as e:
        print(f"Error adding to history for user {user_id}: {str(e)}")


def cleanup_inactive_histories(
    last_cleanup,
    last_activity,
    CLEANUP_INTERVAL,
    INACTIVE_TIMEOUT,
    conversation_history,
):
    """Remove conversation histories for users inactive for more than INACTIVE_TIMEOUT."""
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
        print(f"Cleaned up chat for {len(inactive_users)} inactive users")
