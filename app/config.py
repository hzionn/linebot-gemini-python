import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
credentials_path = Path(
    os.path.join(BASE_DIR, "secrets/service-account-key.json")
).resolve()

if credentials_path.is_file():
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(credentials_path)
else:
    raise FileNotFoundError(
        f"Google Application Credentials file not found at {credentials_path}"
    )

# LINE Bot configuration
CHANNEL_SECRET = os.getenv("ChannelSecret")
CHANNEL_ACCESS_TOKEN = os.getenv("ChannelAccessToken")

# Google Cloud configuration
GOOGLE_PROJECT_ID = os.getenv("GOOGLE_PROJECT_ID")
GOOGLE_LOCATION = os.getenv("GOOGLE_LOCATION", "us-central1")

# Gemini model configuration
GEMINI_TEXT_MODEL = os.getenv("GEMINI_TEXT_MODEL")
GEMINI_VISION_MODEL = os.getenv("GEMINI_VISION_MODEL")

# Chat history configuration
MAX_CHAT_HISTORY = int(os.getenv("MAX_CHAT_HISTORY", "10"))

# Validate required environment variables
if not CHANNEL_SECRET:
    raise ValueError("ChannelSecret environment variable is required")
if not CHANNEL_ACCESS_TOKEN:
    raise ValueError("ChannelAccessToken environment variable is required")
if not GOOGLE_PROJECT_ID:
    raise ValueError("GOOGLE_PROJECT_ID environment variable is required")
if not GEMINI_TEXT_MODEL:
    raise ValueError("GEMINI_TEXT_MODEL environment variable is required")
if not GEMINI_VISION_MODEL:
    raise ValueError("GEMINI_VISION_MODEL environment variable is required")
