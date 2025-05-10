"""
System prompt for different models.
"""

import os

from app.config import PROMPT_BASE_PATH


def _load_prompt(file_name: str) -> str:
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
