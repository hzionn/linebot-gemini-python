"""
System prompt utilities for different models.

This module provides functions and constants for loading and composing
system prompts used by various model types and LLM profiles (todo).
"""

import os

from app.config import PROMPT_BASE_PATH


DEFAULT_AUTHOR = "Anonymous"
DEFAULT_GENERAL_PROMPT = (
    "Respond concisely and helpfully to the user."
)
DEFAULT_TEXT_SYSTEM_PROMPT = "You are a helpful assistant."
DEFAULT_VISION_SYSTEM_PROMPT = (
    "You are a helpful assistant capable of understanding images."
)


def _load_prompt(file_name: str, default: str) -> str:
    """
    Loads a prompt template from a file, returning a default string if unavailable.
    
    If the specified file is missing, empty, or cannot be read, a warning is printed and the provided default string is returned.
    
    Args:
        file_name: Name of the prompt file to load.
        default: Default string to return if the file is missing, empty, or unreadable.
    
    Returns:
        The contents of the prompt file, or the default string if the file is unavailable.
    """
    file_path = os.path.join(PROMPT_BASE_PATH, file_name)
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            if content.strip():
                return content
            print(f"Warning: prompt file {file_path} is empty, using default")
    except FileNotFoundError:
        print(f"Warning: prompt file not found: {file_path}. Using default.")
    except Exception as e:
        print(
            f"Warning: error reading prompt file '{file_path}': {e}. Using default."
        )
    return default


_AUTHOR = _load_prompt("author.txt", DEFAULT_AUTHOR)
_GENERAL_PROMPT = _load_prompt("general_prompt.txt", DEFAULT_GENERAL_PROMPT)

TEXT_SYSTEM_PROMPT = (
    f"{_load_prompt('text_system_prompt.txt', DEFAULT_TEXT_SYSTEM_PROMPT)}\n"
    f"{_GENERAL_PROMPT}\n"
    f"About the author: {_AUTHOR}"
)
VISION_SYSTEM_PROMPT = (
    f"{_load_prompt('vision_system_prompt.txt', DEFAULT_VISION_SYSTEM_PROMPT)}\n" f"{_GENERAL_PROMPT}"
)
