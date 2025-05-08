"""
Define tools for the agent
"""

__all__ = ["tools"]

from langchain.tools import StructuredTool
from pydantic import BaseModel, Field
from langchain_google_community.search import GoogleSearchAPIWrapper, GoogleSearchRun


class GetCurrentTimeSchema(BaseModel):
    timezone: str = Field(
        default="Asia/Taipei", description="Timezone name, e.g., Asia/Taipei"
    )


def get_current_time(timezone: str = "Asia/Taipei") -> str:
    from datetime import datetime
    import pytz

    tz = pytz.timezone(timezone)
    return datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")


class ReminderSchema(BaseModel):
    message: str = Field(description="The message to remind the user")
    time: str = Field(description="The time to remind the user, e.g., 10:00")


def set_reminder(message: str, time: str) -> str:
    return f"Reminder set for {time}: {message}"


class GoogleSearchSchema(BaseModel):
    query: str = Field(description="The query to search the public web for")


def google_search(query: str) -> str:
    """Search the public web using Google Custom Search API."""
    from dotenv import load_dotenv
    import os

    load_dotenv()

    wrapper = GoogleSearchAPIWrapper(
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        google_cse_id=os.getenv("GOOGLE_CSE_ID"),
    )
    search = GoogleSearchRun(api_wrapper=wrapper)
    return search.run(query)


tools = [
    StructuredTool.from_function(
        func=get_current_time,
        name="get_current_time",
        description="Get the current time in a specific timezone",
        args_schema=GetCurrentTimeSchema,
    ),
    StructuredTool.from_function(
        func=set_reminder,
        name="set_reminder_placeholder",
        description="Placeholder for set a reminder for the user",
        args_schema=ReminderSchema,
    ),
    StructuredTool.from_function(
        func=google_search,
        name="google_search",
        description="Search the public web using Google Custom Search API",
        args_schema=GoogleSearchSchema,
    ),
]
