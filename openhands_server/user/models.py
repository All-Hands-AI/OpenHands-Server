"""Simple models for user router."""

from pydantic import BaseModel


class Success(BaseModel):
    """Simple success response model."""
    success: bool = True