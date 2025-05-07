from typing import Any, List, Optional, Union

import PIL.Image
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from linebot.models import MessageEvent


def resize_image(image: PIL.Image.Image, max_size: int = 512) -> PIL.Image.Image:
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
            else:
                history.append(SystemMessage(content=msg))
    except Exception as e:
        print(f"Error building langchain history for user {user_id}: {str(e)}")
    return history


def add_to_history(
    user_id: str, role: str, msg: Union[str, List[Any]], conversation_history: dict
) -> None:
    """Add message to conversation history."""
    try:
        conversation_history[user_id].append((role, str(msg)))
    except Exception as e:
        print(f"Error adding to history for user {user_id}: {str(e)}")
