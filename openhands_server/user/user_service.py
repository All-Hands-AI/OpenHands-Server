import asyncio
from abc import ABC, abstractmethod
from typing import Callable

from openhands.sdk.utils.models import DiscriminatedUnionMixin
from openhands_server.user.user_models import (
    CreateUserRequest,
    UpdateUserRequest,
    UserInfo,
    UserInfoPage,
    UserScope,
    UserSortOrder,
)


class UserService(ABC):
    # Read methods

    @abstractmethod
    async def get_current_user(self) -> UserInfo | None:
        """Get the current user"""

    @abstractmethod
    async def search_users(
        self,
        name__contains: str | None = None,
        email__contains: str | None = None,
        user_scopes__contains: UserScope | None = None,
        sort_order: UserSortOrder = UserSortOrder.EMAIL,
        page_id: str | None = None,
        limit: int = 100,
    ) -> UserInfoPage:
        """Search for users"""

    @abstractmethod
    async def count_users(
        self,
        name__contains: str | None = None,
        email__contains: str | None = None,
        user_scopes__contains: UserScope | None = None,
    ) -> int:
        """Count users"""

    @abstractmethod
    async def get_user(self, id: str) -> UserInfo | None:
        """Get a single sandbox. Return None if the sandbox was not found."""

    async def batch_get_users(self, user_ids: list[str]) -> list[UserInfo | None]:
        """Get a batch of users, returning None for any which were not found."""
        results = await asyncio.gather(
            *[self.get_user(user_id) for user_id in user_ids]
        )
        return results

    # Mutators

    @abstractmethod
    async def create_user(self, request: CreateUserRequest) -> UserInfo:
        """Create a user if possilbe. Raise a PermissionsError if it is not - the
        current user may not have permission to create users or grant the requested
        scopes."""

    @abstractmethod
    async def update_user(self, request: UpdateUserRequest) -> UserInfo:
        """Update a user if possilbe. Raise a PermissionsError if it is not - the
        current user may not have permission to create users or grant the requested
        scopes."""

    @abstractmethod
    async def delete_user(self, user_id: str) -> bool:
        """Delete a user if possible. Raise a PermissionError if it is not - the
        current user may not have permission to delete users. Returns True if the
        user was deleted, False if the user was not found."""


class UserServiceResolver(DiscriminatedUnionMixin, ABC):
    @abstractmethod
    def get_unsecured_resolver(self) -> Callable:
        """
        Get a resolver which may be used to resolve an instance of user service.
        """

    @abstractmethod
    def get_resolver_for_user(self) -> Callable:
        """
        Get a resolver which may be used to resolve an instance of user service
        limited to the current user.
        """
