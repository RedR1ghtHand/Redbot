from datetime import datetime

from pydantic import BaseModel

from .mixins import TimestampsMixin


class Base(BaseModel, TimestampsMixin):
    class Config:
        json_encoders = {
            datetime: lambda dt: dt.isoformat(),
        }

