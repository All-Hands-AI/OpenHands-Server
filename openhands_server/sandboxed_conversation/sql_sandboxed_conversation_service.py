# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportOptionalMemberAccess=false
"""SQL implementation of SandboxedConversationService.

This implementation provides CRUD operations for sandboxed conversations focused purely
on SQL operations:
- Direct database access without permission checks
- Batch operations for efficient data retrieval
- Integration with SandboxService for sandbox information
- HTTP client integration for agent status retrieval
- Full async/await support using SQL async sessions

Security and permission checks are handled by wrapper services.

Key components:
- SQLSandboxedConversationService: Main service class implementing all operations
- SQLSandboxedConversationServiceResolver: Dependency injection resolver for FastAPI
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from time import time
from typing import Callable
from uuid import UUID

import httpx
from fastapi import Depends
from pydantic import Field, TypeAdapter
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from openhands.agent_server.models import (
    ConversationInfo,
    SendMessageRequest,
    StartConversationRequest,
)
from openhands.sdk import LLM
from openhands.sdk.conversation.state import AgentExecutionStatus
from openhands.tools.preset.default import get_default_agent
from openhands_server.database import async_session_dependency
from openhands_server.dependency import get_httpx_client
from openhands_server.errors import SandboxError
from openhands_server.sandbox.sandbox_models import (
    AGENT_SERVER,
    SandboxInfo,
    SandboxStatus,
)
from openhands_server.sandbox.sandbox_service import SandboxService
from openhands_server.sandboxed_conversation.sandboxed_conversation_models import (
    SandboxedConversationResponse,
    SandboxedConversationResponsePage,
    StartSandboxedConversationRequest,
    StoredConversationInfo,
)
from openhands_server.sandboxed_conversation.sandboxed_conversation_service import (
    SandboxedConversationService,
    SandboxedConversationServiceResolver,
)
from openhands_server.user.user_service import UserService


logger = logging.getLogger(__name__)
_conversation_info_type_adapter = TypeAdapter(list[ConversationInfo | None])


@dataclass
class SQLSandboxedConversationService(SandboxedConversationService):
    """SQL implementation of SandboxedConversationService focused on db operations."""

    session: AsyncSession
    sandbox_service: SandboxService
    user_service: UserService
    httpx_client: httpx.AsyncClient
    sandbox_startup_timeout: int
    sandbox_startup_poll_frequency: int

    async def search_sandboxed_conversations(
        self,
        title__contains: str | None = None,
        created_at__gte: datetime | None = None,
        created_at__lt: datetime | None = None,
        updated_at__gte: datetime | None = None,
        updated_at__lt: datetime | None = None,
        page_id: str | None = None,
        limit: int = 100,
    ) -> SandboxedConversationResponsePage:
        """Search for sandboxed conversations without permission checks."""
        query = select(StoredConversationInfo)

        # Apply filters
        conditions = []
        if title__contains is not None:
            conditions.append(StoredConversationInfo.title.like(f"%{title__contains}%"))

        if created_at__gte is not None:
            conditions.append(StoredConversationInfo.created_at >= created_at__gte)

        if created_at__lt is not None:
            conditions.append(StoredConversationInfo.created_at < created_at__lt)

        if updated_at__gte is not None:
            conditions.append(StoredConversationInfo.updated_at >= updated_at__gte)

        if updated_at__lt is not None:
            conditions.append(StoredConversationInfo.updated_at < updated_at__lt)

        if conditions:
            query = query.where(*conditions)

        # Apply pagination
        if page_id is not None:
            try:
                offset = int(page_id)
                query = query.offset(offset)
            except ValueError:
                # If page_id is not a valid integer, start from beginning
                offset = 0
        else:
            offset = 0

        # Apply sorting (default to created_at desc)
        query = query.order_by(StoredConversationInfo.created_at.desc())

        # Apply limit and get one extra to check if there are more results
        query = query.limit(limit + 1)

        result = await self.session.execute(query)
        stored_conversations = list(result.scalars().all())

        # Check if there are more results
        has_more = len(stored_conversations) > limit
        if has_more:
            stored_conversations = stored_conversations[:limit]

        # Calculate next page ID
        next_page_id = None
        if has_more:
            next_page_id = str(offset + limit)

        # Build responses with sandbox and agent status
        responses = await self._build_conversation_responses(stored_conversations)

        return SandboxedConversationResponsePage(
            items=responses, next_page_id=next_page_id
        )

    async def count_sandboxed_conversations(
        self,
        title__contains: str | None = None,
        created_at__gte: datetime | None = None,
        created_at__lt: datetime | None = None,
        updated_at__gte: datetime | None = None,
        updated_at__lt: datetime | None = None,
    ) -> int:
        """Count sandboxed conversations matching the given filters."""
        query = select(func.count(StoredConversationInfo.id))

        # Apply the same filters as search_sandboxed_conversations
        conditions = []
        if title__contains is not None:
            conditions.append(StoredConversationInfo.title.like(f"%{title__contains}%"))

        if created_at__gte is not None:
            conditions.append(StoredConversationInfo.created_at >= created_at__gte)

        if created_at__lt is not None:
            conditions.append(StoredConversationInfo.created_at < created_at__lt)

        if updated_at__gte is not None:
            conditions.append(StoredConversationInfo.updated_at >= updated_at__gte)

        if updated_at__lt is not None:
            conditions.append(StoredConversationInfo.updated_at < updated_at__lt)

        if conditions:
            query = query.where(*conditions)

        result = await self.session.execute(query)
        count = result.scalar()
        return count or 0

    async def get_sandboxed_conversation(
        self, conversation_id: UUID
    ) -> SandboxedConversationResponse | None:
        query = select(StoredConversationInfo).where(
            StoredConversationInfo.id == conversation_id
        )
        result = await self.session.execute(query)
        stored_conversation = result.scalar_one_or_none()

        if stored_conversation is None:
            return None

        # Build response with sandbox and agent status
        responses = await self._build_conversation_responses([stored_conversation])
        return responses[0] if responses else None

    async def start_sandboxed_conversation(
        self, request: StartSandboxedConversationRequest
    ) -> SandboxedConversationResponse:
        """Start a conversation, optionally specifying a sandbox in which to start."""
        sandbox = await self._wait_for_sandbox_start(request.sandbox_id)
        agent_server_url = self._get_agent_server_url(sandbox)
        start_conversation_request = (
            await self._build_start_conversation_request_for_user(
                request.initial_message
            )
        )

        # Start conversation...
        response = await self.httpx_client.post(
            f"{agent_server_url}/conversations",
            json=start_conversation_request.model_dump(),
            headers={"X-Session-API-Key": sandbox.session_api_key},
        )
        response.raise_for_status()
        info = ConversationInfo.model_validate(response.json())

        # Store info...
        stored = StoredConversationInfo(
            id=info.id, title=f"Conversation {info.id}", sandbox_id=sandbox.id
        )
        self.session.add(stored)
        await self.session.commit()
        await self.session.refresh(stored)

        return SandboxedConversationResponse(
            **stored.model_dump(),
            sandbox_status=sandbox.status,
            agent_status=AgentExecutionStatus.RUNNING,
        )

    async def _wait_for_sandbox_start(self, sandbox_id: str) -> SandboxInfo:
        """Wait for sandbox to start and return info"""
        sandbox_service = self.sandbox_service
        if not sandbox_id:
            sandbox = await sandbox_service.start_sandbox()
            sandbox_id = sandbox.id
        else:
            sandbox = await sandbox_service.get_sandbox(sandbox_id)
        assert sandbox is not None

        if sandbox.status == SandboxStatus.PAUSED:
            await sandbox_service.resume_sandbox(sandbox_id)
        if sandbox.status in (SandboxStatus.DELETED, SandboxStatus.ERROR):
            raise SandboxError(f"Sandbox status: {sandbox.status}")
        if sandbox.status == SandboxStatus.RUNNING:
            return sandbox

        start = time()
        while time() - start <= self.sandbox_startup_timeout:
            await asyncio.sleep(self.sandbox_startup_poll_frequency)
            sandbox = await sandbox_service.get_sandbox(sandbox_id)
            if sandbox is None:
                raise SandboxError(f"Sandbox not found: {sandbox_id}")
            if sandbox.status == SandboxStatus.RUNNING:
                return sandbox
        raise SandboxError(f"Sandbox failed to start: {sandbox_id}")

    def _get_agent_server_url(self, sandbox: SandboxInfo) -> str:
        """Get agent server url for running sandbox"""
        exposed_urls = sandbox.exposed_urls
        assert exposed_urls is not None
        agent_server_url = next(
            exposed_url.url
            for exposed_url in exposed_urls
            if exposed_url.name == AGENT_SERVER
        )
        return agent_server_url

    async def _build_start_conversation_request_for_user(
        self, initial_message: SendMessageRequest | None
    ) -> StartConversationRequest:
        user = await self.user_service.get_current_user()

        llm = LLM(
            model=user.llm_model,
            base_url=user.llm_base_url,
            api_key=user.llm_api_key,
            service_id="agent",
        )
        agent = get_default_agent(llm=llm, working_dir="/workspace")
        start_conversation_request = StartConversationRequest(
            agent=agent,
            # confirmation_policy=NeverConfirm(), # TODO: Add this to user
            initial_message=initial_message,
        )
        return start_conversation_request

    async def _build_conversation_responses(
        self, stored_conversations: list[StoredConversationInfo]
    ) -> list[SandboxedConversationResponse]:
        """Build conversation responses with sandbox and agent status information."""
        if not stored_conversations:
            return []

        # Extract unique sandbox IDs
        sandbox_ids = list(set(conv.sandbox_id for conv in stored_conversations))

        # Batch get sandbox information
        sandbox_infos = await self.sandbox_service.batch_get_sandboxes(sandbox_ids)
        sandbox_info_map = {info.id: info for info in sandbox_infos if info is not None}

        # Group conversations by sandbox for efficient agent status retrieval
        conversations_by_sandbox = {}
        for conv in stored_conversations:
            if conv.sandbox_id not in conversations_by_sandbox:
                conversations_by_sandbox[conv.sandbox_id] = []
            conversations_by_sandbox[conv.sandbox_id].append(conv)

        # Batch get agent status for running sandboxes
        conversation_info_tasks = []

        for sandbox_id, conversations in conversations_by_sandbox.items():
            sandbox_info = sandbox_info_map.get(sandbox_id)
            if sandbox_info and sandbox_info.status == SandboxStatus.RUNNING:
                # Find the AGENT_SERVER URL
                agent_server_url = None
                if sandbox_info.exposed_urls:
                    for exposed_url in sandbox_info.exposed_urls:
                        if exposed_url.name == AGENT_SERVER:
                            agent_server_url = exposed_url.url
                            break

                if agent_server_url:
                    conversation_ids = [str(conv.id) for conv in conversations]
                    task = self._get_info_for_conversations(
                        agent_server_url, conversation_ids, sandbox_info.session_api_key
                    )
                    conversation_info_tasks.append(task)

        # Execute all agent status requests in parallel
        conversation_info_results = await asyncio.gather(
            *conversation_info_tasks, return_exceptions=True
        )

        conversation_info_by_id = {}
        for conversation_list in conversation_info_results:
            if isinstance(conversation_list, BaseException):
                raise conversation_list
            for conversation_info in conversation_list:
                conversation_info_by_id[conversation_info.id] = conversation_info

        # Build the final responses
        responses = []
        for conversation in stored_conversations:
            sandbox_info = sandbox_info_map.get(conversation.sandbox_id)
            conversation_info = conversation_info_by_id.get(conversation.id)

            response = SandboxedConversationResponse(
                id=conversation.id,
                title=conversation.title,
                sandbox_id=conversation.sandbox_id,
                created_at=conversation.created_at,
                updated_at=conversation.updated_at,
                sandbox_status=sandbox_info.status
                if sandbox_info
                else SandboxStatus.ERROR,
                agent_status=conversation_info.agent_status
                if conversation_info
                else AgentExecutionStatus.ERROR,
            )
            responses.append(response)

        return responses

    async def _get_info_for_conversations(
        self,
        agent_server_url: str,
        conversation_ids: list[str],
        session_api_key: str | None,
    ) -> list[ConversationInfo]:
        """Get agent status for multiple conversations from the Agent Server."""
        try:
            # Build the URL with query parameters
            url = f"{agent_server_url.rstrip('/')}/conversations"
            params = {"ids": conversation_ids}

            # Set up headers
            headers = {}
            if session_api_key:
                headers["X-Session-API-Key"] = session_api_key

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params, headers=headers)
                response.raise_for_status()

                data = response.json()
                conversation_info = _conversation_info_type_adapter.validate_python(
                    data
                )
                conversation_info = [c for c in conversation_info if c]
                return conversation_info

        except Exception as e:
            logger.warning(f"Failed to get agent status from {agent_server_url}: {e}")
            raise


class SQLSandboxedConversationServiceResolver(SandboxedConversationServiceResolver):
    sandbox_startup_timeout: int = Field(
        default=120, description="The max timeout time for sandbox startup"
    )
    sandbox_startup_poll_frequency: int = Field(
        default=2, description="The frequency to poll for sandbox readiness"
    )

    def get_unsecured_resolver(self) -> Callable:
        from openhands_server.dependency import get_dependency_resolver

        sandbox_service_resolver = (
            get_dependency_resolver().sandbox.get_unsecured_resolver()
        )
        user_service_resolver = get_dependency_resolver().user.get_unsecured_resolver()

        # Define inline to prevent circular lookup
        def resolve_sandboxed_conversation_service(
            session: AsyncSession = Depends(async_session_dependency),
            sandbox_service: SandboxService = Depends(sandbox_service_resolver),
            user_service: UserService = Depends(user_service_resolver),
            httpx_client: httpx.AsyncClient = Depends(get_httpx_client),
        ) -> SandboxedConversationService:
            return SQLSandboxedConversationService(
                session=session,
                sandbox_service=sandbox_service,
                user_service=user_service,
                httpx_client=httpx_client,
                sandbox_startup_timeout=self.sandbox_startup_timeout,
                sandbox_startup_poll_frequency=self.sandbox_startup_poll_frequency,
            )

        return resolve_sandboxed_conversation_service

    def get_resolver_for_user(self) -> Callable:
        from openhands_server.dependency import get_dependency_resolver

        sandbox_service_resolver = (
            get_dependency_resolver().sandbox.get_resolver_for_user()
        )
        user_service_resolver = get_dependency_resolver().user.get_resolver_for_user()

        # Define inline to prevent circular lookup
        def resolve_sandboxed_conversation_service(
            session: AsyncSession = Depends(async_session_dependency),
            sandbox_service: SandboxService = Depends(sandbox_service_resolver),
            user_service: UserService = Depends(user_service_resolver),
            httpx_client: httpx.AsyncClient = Depends(get_httpx_client),
        ) -> SandboxedConversationService:
            service = SQLSandboxedConversationService(
                session=session,
                sandbox_service=sandbox_service,
                user_service=user_service,
                httpx_client=httpx_client,
                sandbox_startup_timeout=self.sandbox_startup_timeout,
                sandbox_startup_poll_frequency=self.sandbox_startup_poll_frequency,
            )
            # TODO: Add auth and fix
            logger.warning("⚠️ Using Unsecured SandboxedConversationService!!!")
            # service = ConstrainedSandboxedConversationService(
            #   service, self.current_user_id
            # )
            return service

        return resolve_sandboxed_conversation_service
