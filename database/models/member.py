from pydantic import Field

from .base import Base


class Member(Base):
    member_id: int = Field(..., description="Discord user ID")
    username: str = Field(..., description="username")
    public_name: str = Field(..., description="public name")
    avatar_url: str = Field(..., description="avatar URL")
    is_admin: bool = Field(default=False, description="whether the user is an admin")
