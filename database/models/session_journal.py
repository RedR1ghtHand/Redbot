from datetime import datetime

from pydantic import Field

from .base import Base
from .member import Member

class SessionJournal(Base):
    session_id: int = Field(..., description="active session channel ID")
    user_joined: Member = Field(..., description="user who joined the session")
    user_joined_at: datetime = Field(..., description="timestamp when the user joined the session")
    user_left_at: datetime | None = Field(None, description="timestamp when the user left the session")