"""
Define tools for the agent
"""

__all__ = ["tools"]

from langchain.tools import StructuredTool
from pydantic import BaseModel, Field


class GetCurrentTimeSchema(BaseModel):
    timezone: str = Field(
        default="Asia/Taipei", description="Timezone name, e.g., Asia/Taipei"
    )


def get_current_time(timezone: str = "Asia/Taipei") -> str:
    """Get the current time in a specific timezone."""
    from datetime import datetime
    import pytz

    tz = pytz.timezone(timezone)
    return datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")


class ReminderSchema(BaseModel):
    message: str = Field(description="The message to remind the user")
    time: str = Field(description="The time to remind the user, e.g., 10:00")


def set_reminder(message: str, time: str) -> str:
    """Set a reminder for the user"""
    # TODO: Implement the reminder functionality
    return f"Reminder set for {time}: {message}"


tools = [
    StructuredTool.from_function(
        func=get_current_time,
        name="get_current_time",
        description="Get the current time in a specific timezone",
        args_schema=GetCurrentTimeSchema,
    ),
    StructuredTool.from_function(
        func=set_reminder,
        name="set_reminder",
        description="Set a reminder for the user",
        args_schema=ReminderSchema,
    ),
]
