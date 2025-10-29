from datetime import datetime, timezone
from typing import Any

from pydantic import Field

from .base import Base


class Session(Base):
    created_by: str = Field(..., description="user ID who created the voice session")
    channel_id: int = Field(..., description="voice channel ID")
    channel_name: str = Field(..., max_length=100, description="voice channel name")
    is_ended: bool = Field(default=False, description="Whether the voice session is closed")
    duration: int | None = None
    creator_metadata: dict[str, Any] = Field(default_factory=dict, description="Additional info about the creator")

    def mark_updated(self) -> None:
        self.updated_at = datetime.now(timezone.utc)

    def mark_ended(self) -> None:
        self.is_ended = True
        self.mark_updated()

    def duration_seconds(self):
        end_time = self.updated_at if self.is_ended else datetime.now(timezone.utc)
        created_at = self.created_at

        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=timezone.utc)

        delta = end_time - created_at
        return int(delta.total_seconds())

    def duration_pretty(self) -> str:
        total_seconds = self.duration_seconds()
        days, rem = divmod(total_seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, seconds = divmod(rem, 60)
        if days > 0:
            return f"{days}d | {hours:02}h | {minutes:02}m | {seconds:02}s"
        return f"{hours:02}h | {minutes:02}m | {seconds:02}s"