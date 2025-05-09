"""
System prompt for different models
"""

import os

ENV = os.getenv("ENV", "prod")
PROMPT_BASE_PATH = "/prompts" if ENV == "prod" else "app/prompts"


def load_prompt(file_name: str) -> str:
    file_path = os.path.join(PROMPT_BASE_PATH, file_name)
    # print(f"Loading prompt from {file_path}")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        raise RuntimeError(f"Prompt file not found: {file_path}")
    except Exception as e:
        raise RuntimeError(f"Error loading prompt file '{file_path}': {e}")


AUTHOR = load_prompt("author.txt")
GENERAL_PROMPT = load_prompt("general_prompt.txt")
TEXT_SYSTEM_PROMPT = (
    f"{load_prompt('text_system_prompt.txt')}\n"
    f"{GENERAL_PROMPT}\n"
    f"About the author: {AUTHOR}"
)
VISION_SYSTEM_PROMPT = (
    f"{load_prompt('vision_system_prompt.txt')}\n" f"{GENERAL_PROMPT}"
)
