import uuid
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class GitProvider(Enum):
    GITHUB = "GITHUB"
    GITLAB = "GITLAB"
    BITBUCKET = "BITBUCKET"


class GitInfo(BaseModel):
    """Information about an interaction with git."""

    id: UUID = Field(default_factory=uuid.uuid4)
    name: str = Field(
        description="Descriptive name for this git info - mostly used to distinguish if there are multiple."
    )
    selected_repository: str | None = None
    selected_branch: str | None = None
    git_provider: GitProvider | None = None
    pr_number: int | None = None
