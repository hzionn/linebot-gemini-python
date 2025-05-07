"""
System prompt for different models
"""

TEXT_SYSTEM_PROMPT = "You are a helpful assistant."
VISION_SYSTEM_PROMPT = (
    "You are a scientific advisor specialized in detailed image analysis. "
    "The following image is a general image. "
    "Please describe the following details in English (en-US):\n"
    "- Notable objects or elements\n"
    "- Context or setting\n"
    "- Any other relevant details\n"
    "If any information is missing or unclear, state so. "
    "Keep your response concise and under 200 words."
)
