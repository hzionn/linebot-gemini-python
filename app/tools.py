"""
Define tools for the agent
"""

__all__ = ["tools"]

from langchain.tools import StructuredTool
from pydantic import BaseModel, Field


class GetCurrentTimeSchema(BaseModel):
    """Get the current time in a specific timezone."""

    timezone: str = Field(
        default="Asia/Taipei", description="Timezone name, e.g., Asia/Taipei"
    )


def get_current_time(timezone: str = "Asia/Taipei") -> str:
    from datetime import datetime

    import pytz

    tz = pytz.timezone(timezone)
    return datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")


tools = [
    StructuredTool.from_function(
        func=get_current_time,
        name="get_current_time",
        description="Get the current time in a specific timezone",
        args_schema=GetCurrentTimeSchema,
    )
]
