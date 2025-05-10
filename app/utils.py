from datetime import UTC, datetime
from typing import Any, Dict, List, Optional
import warnings
import functools

import PIL.Image
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
# from linebot.models import MessageEvent


def resize_image(image: PIL.Image.Image, max_size: int = 1024) -> PIL.Image.Image:
    image.thumbnail((max_size, max_size))
    return image


# def get_user_id(event: MessageEvent) -> Optional[str]:
#     """Get user ID from LINE event."""
#     return getattr(event.source, "user_id", None)


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
    user_id: str,
    role: str,
    msg: Any,
    conversation_history: dict,
    last_activity: Optional[Dict[str, datetime]] = None,
) -> None:
    """Add message to conversation history and update last activity timestamp."""
    try:
        conversation_history[user_id].append((role, msg))
        # Update last_activity timestamp if provided
        if last_activity is not None:
            last_activity[user_id] = datetime.now(UTC)
    except Exception as e:
        print(f"Error adding to history for user {user_id}: {str(e)}")


def deprecated(message: str):
    """Decorator to mark functions as deprecated."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            warnings.warn(
                f"{func.__name__} is deprecated. {message}",
                category=DeprecationWarning,
                stacklevel=2
            )
            return func(*args, **kwargs)
        return wrapper
    return decorator
