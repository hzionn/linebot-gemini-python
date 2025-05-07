from datetime import datetime
from typing import Any, List, Optional

import PIL.Image
from langchain_core.messages import (AIMessage, HumanMessage, SystemMessage,
                                     ToolMessage)
from linebot.models import MessageEvent


class ConversationManager:
    def __init__(self, max_history: int = 20, cleanup_interval: int = 3600, inactive_timeout: int = 86400):
        self.conversation_history = {}
        self.last_activity = {}
        self.last_cleanup = datetime.now()
        self.max_history = max_history
        self.cleanup_interval = cleanup_interval
        self.inactive_timeout = inactive_timeout

    def add_to_history(self, user_id: str, role: str, msg: Any) -> None:
        """Add message to conversation history."""
        try:
            if user_id not in self.conversation_history:
                self.conversation_history[user_id] = []
            self.conversation_history[user_id].append((role, msg))
            if len(self.conversation_history[user_id]) > self.max_history:
                self.conversation_history[user_id] = self.conversation_history[user_id][-self.max_history:]
        except Exception as e:
            print(f"Error adding to history for user {user_id}: {str(e)}")

    def build_langchain_history(self, user_id: str) -> List[Any]:
        """Build LangChain message history from stored conversation."""
        history = []
        try:
            if user_id not in self.conversation_history:
                return history
            for role, msg in self.conversation_history[user_id]:
                if role == "user":
                    history.append(HumanMessage(content=msg))
                elif role == "assistant":
                    history.append(AIMessage(content=msg))
                elif role == "tool":
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

    def update_activity(self, user_id: str) -> None:
        """Update the last activity timestamp for a user."""
        self.last_activity[user_id] = datetime.now()

    def cleanup_inactive_histories(self) -> None:
        """Remove conversation histories for users inactive for more than inactive_timeout."""
        now = datetime.now()

        # Run cleanup only at specified intervals
        if (now - self.last_cleanup).total_seconds() < self.cleanup_interval:
            return

        inactive_users = []
        for user_id, last_time in self.last_activity.items():
            if (now - last_time).total_seconds() > self.inactive_timeout:
                inactive_users.append(user_id)

        for user_id in inactive_users:
            if user_id in self.conversation_history:
                del self.conversation_history[user_id]
            del self.last_activity[user_id]

        self.last_cleanup = now
        if inactive_users:
            print(f"Cleaned up chat for {len(inactive_users)} inactive users")


def resize_image(image: PIL.Image.Image, max_size: int = 1024) -> PIL.Image.Image:
    image.thumbnail((max_size, max_size))
    return image


def get_user_id(event: MessageEvent) -> Optional[str]:
    """Get user ID from LINE event."""
    return getattr(event.source, "user_id", None)
