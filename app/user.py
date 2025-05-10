"""
Define user-related functions.
Mostly for managing conversation history.
"""

import asyncio
import os
import pickle
from collections import deque
from datetime import UTC, datetime
from typing import Any, List, Optional

from linebot.models import MessageEvent

from app import config
from app.utils import deprecated, build_langchain_history


def deque_factory():
    return deque(maxlen=config.MAX_CHAT_HISTORY)


def get_user_id(event: MessageEvent) -> Optional[str]:
    """Get user ID from LINE event."""
    return getattr(event.source, "user_id", None)


def to_load_user_history(
    user_id: str, last_activity: dict, conversation_history: dict
) -> bool:
    """
    Load user conversation history from disk.

    Returns:
        bool: True if the user history was newly loaded or created, False if it already existed in memory.
    """
    # If the user already exists in memory, just return False
    if user_id in conversation_history:
        return False

    file_path = os.path.join(config.HISTORY_BASE_PATH, f"{user_id}.pkl")
    try:
        if os.path.exists(file_path):
            print(f"Found history for user {user_id}")
            with open(file_path, "rb") as f:
                conversation_history[user_id] = pickle.load(f)
            print(f"Loaded history for user {user_id}")
        else:
            print(f"No history found for user {user_id}, initializing empty history.")
            conversation_history[user_id] = deque(maxlen=config.MAX_CHAT_HISTORY)
            print(f"Initialized empty history for user {user_id}")
    except Exception as e:
        print(f"Error loading history for user {user_id}: {e}")
        conversation_history[user_id] = deque(maxlen=config.MAX_CHAT_HISTORY)
        print(f"Created new history for user {user_id} after load error")

    last_activity[user_id] = datetime.now(UTC)
    return True


def _save_user_history(user_id: str, conversation_history: dict):
    """Save user conversation history to disk with error handling."""
    history = conversation_history.get(user_id)
    if not history:
        return

    file_path = os.path.join(config.HISTORY_BASE_PATH, f"{user_id}.pkl")
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "wb") as f:
            pickle.dump(history, f)
        print(f"Saved history for user {user_id}")
    except Exception as e:
        print(f"Error saving history for user {user_id}: {e}")


def add_to_history(
    user_id: str, role: str, msg: Any, last_activity: dict, conversation_history: dict
) -> None:
    """Add message to conversation history and update last activity timestamp."""
    try:
        conversation_history[user_id].append((role, msg))
        # Update last_activity timestamp
        last_activity[user_id] = datetime.now(UTC)
    except Exception as e:
        print(f"Error adding to history for user {user_id}: {str(e)}")


@deprecated("Use `sync_inactive_users` with asyncio instead.")
def cleanup_inactive_users(last_activity: dict, conversation_history: dict):
    """Clean up inactive users and save their history."""
    now = datetime.now(UTC)
    for user_id in list(last_activity.keys()):
        if now - last_activity[user_id] > config.INACTIVITY_THRESHOLD:
            # Save history before removing
            _save_user_history(user_id, conversation_history)
            del conversation_history[user_id]
            del last_activity[user_id]
            print(f"Cleaned up inactive user {user_id}")


async def sync_inactive_users(last_activity: dict, conversation_history: dict):
    """Background task to periodically save inactive user histories and clean up memory."""
    while True:
        now = datetime.now(UTC)
        for user_id, last_time in list(last_activity.items()):
            if now - last_time > config.INACTIVITY_THRESHOLD:
                print(f"User {user_id} inactive for {config.INACTIVITY_THRESHOLD} mins")
                _save_user_history(user_id, conversation_history)
                print(f"Saved history for user {user_id}")
                del conversation_history[user_id]
                del last_activity[user_id]
                print(f"Deleted in-memory history for user {user_id}")
        await asyncio.sleep(60)  # Check every minute


def ensure_history_path_exists():
    """Ensure the history directory exists."""
    try:
        os.makedirs(config.HISTORY_BASE_PATH, exist_ok=True)
        print(f"Ensured history directory exists: {config.HISTORY_BASE_PATH}")
    except Exception as e:
        print(f"Error creating history directory: {e}")


def get_user_history(user_id: str, conversation_history: dict) -> List[Any]:
    """Get the user's conversation history in LangChain format."""
    return build_langchain_history(user_id, conversation_history)


def user_exists(user_id: str, conversation_history: dict) -> bool:
    """
    Check if a user exists in the conversation history.
    
    Note: Currently unused, but kept for potential future implementation
    of user verification before processing.
    """
    return user_id in conversation_history


def update_user_activity(user_id: str, last_activity: dict) -> None:
    """Update a user's last activity timestamp."""
    last_activity[user_id] = datetime.now(UTC)


def save_all_histories(conversation_history: dict):
    """Save all user conversation histories before shutdown."""
    print("Saving all conversation histories...")
    for user_id in list(conversation_history.keys()):
        _save_user_history(user_id, conversation_history)
