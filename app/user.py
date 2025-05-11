"""
User-related functions for managing conversation history.

This module provides utilities for:
- Loading, saving, and updating user conversation histories.
- Tracking user activity and cleaning up inactive users.
- Interfacing with persistent storage for chat history.
"""

import asyncio
import os
import pickle
from collections import deque, defaultdict
from datetime import UTC, datetime
from typing import Any, List, Optional

from linebot.models import MessageEvent

from app import config
from app.utils import deprecated, build_langchain_history


def deque_factory():
    """Create a new deque for chat history with a maximum length from config."""
    return deque(maxlen=config.MAX_CHAT_HISTORY)


def get_user_id(event: MessageEvent) -> Optional[str]:
    """
    Extract the user ID from a LINE MessageEvent.

    Args:
        event (MessageEvent): The LINE event object.

    Returns:
        Optional[str]: The user ID if present, otherwise None.
    """
    return getattr(event.source, "user_id", None)


def to_load_user_history(
    user_id: str, last_activity: dict, conversation_history: defaultdict
) -> bool:
    """
    Load a user's conversation history from disk if not already in memory.

    Args:
        user_id (str): The user's unique identifier.
        last_activity (dict): Dictionary tracking last activity timestamps.
        conversation_history (defaultdict): In-memory conversation histories.

    Returns:
        bool: True if history was loaded or initialized, False if already present in memory.
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
            conversation_history[user_id] = deque_factory()
            print(f"Initialized empty history for user {user_id}")
    except Exception as e:
        print(f"Error loading history for user {user_id}: {e}")
        conversation_history[user_id] = deque_factory()
        print(f"Created new history for user {user_id} after load error")

    last_activity[user_id] = datetime.now(UTC)
    return True


def _save_user_history(user_id: str, conversation_history: defaultdict):
    """
    Persist a user's conversation history to disk.

    Args:
        user_id (str): The user's unique identifier.
        conversation_history (defaultdict): In-memory conversation histories.

    Notes:
        Does nothing if the user has no history in memory.
    """
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
    user_id: str,
    role: str,
    msg: Any,
    last_activity: dict,
    conversation_history: defaultdict,
) -> None:
    """
    Append a message to a user's conversation history and update their last activity.

    Args:
        user_id (str): The user's unique identifier.
        role (str): The role of the message sender (e.g., 'user', 'assistant').
        msg (Any): The message content.
        last_activity (dict): Dictionary tracking last activity timestamps.
        conversation_history (defaultdict): In-memory conversation histories.
    """
    try:
        conversation_history[user_id].append((role, msg))
        last_activity[user_id] = datetime.now(UTC)
    except Exception as e:
        print(f"Error adding to history for user {user_id}: {str(e)}")


@deprecated("Use `sync_inactive_users` with asyncio instead.")
def cleanup_inactive_users(last_activity: dict, conversation_history: defaultdict):
    """
    Remove inactive users from memory and persist their histories.

    Args:
        last_activity (dict): Dictionary tracking last activity timestamps.
        conversation_history (defaultdict): In-memory conversation histories.

    Notes:
        Users are considered inactive if their last activity exceeds the configured threshold.
    """
    now = datetime.now(UTC)
    for user_id in list(last_activity.keys()):
        if now - last_activity[user_id] > config.INACTIVITY_THRESHOLD:
            _save_user_history(user_id, conversation_history)
            del conversation_history[user_id]
            del last_activity[user_id]
            print(f"Cleaned up inactive user {user_id}")


async def sync_inactive_users(last_activity: dict, conversation_history: defaultdict):
    """
    Periodically persist and remove inactive user histories from memory.

    Args:
        last_activity (dict): Dictionary tracking last activity timestamps.
        conversation_history (defaultdict): In-memory conversation histories.

    Behavior:
        Runs as a background task, checking for inactive users every minute.
    """
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
    """
    Ensure the directory for storing conversation histories exists.

    Creates the directory if it does not already exist.
    """
    try:
        os.makedirs(config.HISTORY_BASE_PATH, exist_ok=True)
        print(f"Ensured history directory exists: {config.HISTORY_BASE_PATH}")
    except Exception as e:
        print(f"Error creating history directory: {e}")


def get_user_history(user_id: str, conversation_history: defaultdict) -> List[Any]:
    """
    Retrieve a user's conversation history in LangChain format.

    Args:
        user_id (str): The user's unique identifier.
        conversation_history (defaultdict): In-memory conversation histories.

    Returns:
        List[Any]: The user's conversation history formatted for LangChain.
    """
    return build_langchain_history(user_id, conversation_history)


def user_exists(user_id: str, conversation_history: defaultdict) -> bool:
    """
    Check if a user exists in the in-memory conversation history.

    Args:
        user_id (str): The user's unique identifier.
        conversation_history (defaultdict): In-memory conversation histories.

    Returns:
        bool: True if the user exists, False otherwise.
    """
    return user_id in conversation_history


def update_user_activity(user_id: str, last_activity: dict) -> None:
    """
    Update the last activity timestamp for a user.

    Args:
        user_id (str): The user's unique identifier.
        last_activity (dict): Dictionary tracking last activity timestamps.
    """
    last_activity[user_id] = datetime.now(UTC)


def save_all_histories(conversation_history: defaultdict):
    """
    Persist all user conversation histories to disk.

    Args:
        conversation_history (defaultdict): In-memory conversation histories.

    Notes:
        Intended to be called before application shutdown.
    """
    print("Saving all conversation histories...")
    for user_id in list(conversation_history.keys()):
        _save_user_history(user_id, conversation_history)
