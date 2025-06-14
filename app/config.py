import os
from pathlib import Path
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
# credentials_path = Path(
#     os.path.join(BASE_DIR, "secrets/service-account-key.json")
# ).resolve()

# if credentials_path.is_file():
#     os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(credentials_path)
# else:
#     raise FileNotFoundError(
#         f"Google Application Credentials file not found at {credentials_path}"
#     )

# LINE Bot configuration
CHANNEL_SECRET = os.getenv("ChannelSecret")
CHANNEL_ACCESS_TOKEN = os.getenv("ChannelAccessToken")

# Google Cloud configuration
GOOGLE_PROJECT_ID = os.getenv("GOOGLE_PROJECT_ID")
GOOGLE_LOCATION = os.getenv("GOOGLE_LOCATION")

GEMINI_TEXT_MODEL = os.getenv("GEMINI_TEXT_MODEL", "gemini-2.0-flash")
GEMINI_VISION_MODEL = os.getenv("GEMINI_VISION_MODEL", "gemini-2.0-flash")
MAX_OUTPUT_TOKENS = int(os.getenv("MAX_OUTPUT_TOKENS", 512))

MAX_CHAT_HISTORY = int(os.getenv("MAX_CHAT_HISTORY", 10))

ENV = os.getenv("ENV", "prod")
INACTIVITY_THRESHOLD = timedelta(minutes=10)
# TODO: better manage the mount volume path
# NOTE: the production GCP bucket contains nested "history" and "prompts"
# directories.  Until that layout is updated, the base paths intentionally
# repeat the folder names.
HISTORY_BASE_PATH = "/history/history/" if ENV == "prod" else "history"
PROMPT_BASE_PATH = "/prompts/prompts/" if ENV == "prod" else "prompts"

if not CHANNEL_SECRET:
    raise ValueError("ChannelSecret environment variable is required")
if not CHANNEL_ACCESS_TOKEN:
    raise ValueError("ChannelAccessToken environment variable is required")
if not GOOGLE_PROJECT_ID:
    raise ValueError("GOOGLE_PROJECT_ID environment variable is required")
if not GOOGLE_LOCATION:
    raise ValueError("GOOGLE_LOCATION environment variable is required")
