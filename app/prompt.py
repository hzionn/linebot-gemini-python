"""
System prompt utilities for different models.

This module provides functions and constants for loading and composing
system prompts used by various model types and LLM profiles (todo).
"""

import os

from app.config import PROMPT_BASE_PATH


def _load_prompt(file_name: str) -> str:
    """
    Load a prompt template from a file.

    Args:
        file_name (str): The name of the prompt file to load.

    Returns:
        str: The contents of the prompt file.

    Raises:
        RuntimeError: If the file is not found or cannot be read.
    """
    file_path = os.path.join(PROMPT_BASE_PATH, file_name)
    # print(f"Loading prompt from {file_path}")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        raise RuntimeError(f"Prompt file not found: {file_path}")
    except Exception as e:
        raise RuntimeError(f"Error loading prompt file '{file_path}': {e}")


_AUTHOR = _load_prompt("author.txt")
_GENERAL_PROMPT = _load_prompt("general_prompt.txt")

TEXT_SYSTEM_PROMPT = (
    f"{_load_prompt('text_system_prompt.txt')}\n"
    f"{_GENERAL_PROMPT}\n"
    f"About the author: {_AUTHOR}"
)
VISION_SYSTEM_PROMPT = (
    f"{_load_prompt('vision_system_prompt.txt')}\n" f"{_GENERAL_PROMPT}"
)
