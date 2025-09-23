"""User model for OpenHands Server."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class User(BaseModel):
    """User model representing a user in the system."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "user_123456",
                "created_at": "2023-01-01T12:00:00Z",
                "super_admin": False,
            }
        }
    )

    id: str = Field(..., description="Unique identifier for the user")
    created_at: datetime = Field(..., description="Timestamp when the user was created")
    updated_at: datetime = Field(..., description="Timestamp when the user was updated")
    super_admin: bool = Field(
        default=False,
        description="Flag indicating if the user has super admin privileges",
    )
