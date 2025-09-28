# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportOptionalMemberAccess=false
"""SQL implementation of SandboxedConversationService.

This implementation provides CRUD operations for sandboxed conversations focused purely on SQL operations:
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
from typing import Callable
from uuid import UUID

import httpx
from fastapi import Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from openhands.core.schema import AgentState
from openhands_server.database import async_session_dependency
from openhands_server.sandbox.sandbox_models import AGENT_SERVER, SandboxStatus
from openhands_server.sandbox.sandbox_service import SandboxService, SandboxServiceResolver
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
from openhands_server.utils.date_utils import utc_now


logger = logging.getLogger(__name__)


@dataclass
class SQLSandboxedConversationService(SandboxedConversationService):
    """SQL implementation of SandboxedConversationService focused on database operations."""

    session: AsyncSession
    sandbox_service: SandboxService

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

        return SandboxedConversationResponsePage(items=responses, next_page_id=next_page_id)

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
        """Get a single sandboxed conversation info. Return None if the conversation was not found."""
        query = select(StoredConversationInfo).where(StoredConversationInfo.id == conversation_id)
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
        # For now, this is a placeholder implementation
        # In a real implementation, this would:
        # 1. Create or get a sandbox
        # 2. Start a conversation in that sandbox
        # 3. Set up event callbacks
        # 4. Return the conversation response
        raise NotImplementedError("start_sandboxed_conversation not yet implemented")

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
        sandbox_info_map = {
            info.id: info for info in sandbox_infos if info is not None
        }

        # Group conversations by sandbox for efficient agent status retrieval
        conversations_by_sandbox = {}
        for conv in stored_conversations:
            if conv.sandbox_id not in conversations_by_sandbox:
                conversations_by_sandbox[conv.sandbox_id] = []
            conversations_by_sandbox[conv.sandbox_id].append(conv)

        # Batch get agent status for running sandboxes
        agent_status_tasks = []
        sandbox_to_task_map = {}
        
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
                    task = self._get_agent_status_for_conversations(
                        agent_server_url, conversation_ids, sandbox_info.session_api_key
                    )
                    agent_status_tasks.append(task)
                    sandbox_to_task_map[sandbox_id] = len(agent_status_tasks) - 1

        # Execute all agent status requests in parallel
        agent_status_results = []
        if agent_status_tasks:
            agent_status_results = await asyncio.gather(*agent_status_tasks, return_exceptions=True)

        # Build the final responses
        responses = []
        for conv in stored_conversations:
            sandbox_info = sandbox_info_map.get(conv.sandbox_id)
            sandbox_status = sandbox_info.status if sandbox_info else SandboxStatus.ERROR
            
            # Determine agent status
            agent_status = None
            if (sandbox_info and 
                sandbox_info.status == SandboxStatus.RUNNING and 
                conv.sandbox_id in sandbox_to_task_map):
                
                task_index = sandbox_to_task_map[conv.sandbox_id]
                if task_index < len(agent_status_results):
                    result = agent_status_results[task_index]
                    if not isinstance(result, Exception):
                        agent_status = result.get(str(conv.id))

            response = SandboxedConversationResponse(
                id=conv.id,
                title=conv.title,
                sandbox_id=conv.sandbox_id,
                created_at=conv.created_at,
                updated_at=conv.updated_at,
                sandbox_status=sandbox_status,
                agent_status=agent_status,
            )
            responses.append(response)

        return responses

    async def _get_agent_status_for_conversations(
        self, agent_server_url: str, conversation_ids: list[str], session_api_key: str | None
    ) -> dict[str, AgentState]:
        """Get agent status for multiple conversations from the OpenHands Agent Server."""
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
                
                # Extract agent status for each conversation
                agent_statuses = {}
                if isinstance(data, list):
                    for conversation_data in data:
                        if isinstance(conversation_data, dict):
                            conv_id = conversation_data.get("id")
                            status_str = conversation_data.get("agent_status")
                            if conv_id and status_str:
                                try:
                                    agent_status = AgentState(status_str)
                                    agent_statuses[conv_id] = agent_status
                                except ValueError:
                                    logger.warning(f"Invalid agent status: {status_str}")
                
                return agent_statuses
                
        except Exception as e:
            logger.warning(f"Failed to get agent status from {agent_server_url}: {e}")
            return {}


class SQLSandboxedConversationServiceResolver(SandboxedConversationServiceResolver):
    def get_unsecured_resolver(self) -> Callable:
        from openhands_server.dependency import get_dependency_resolver
        
        sandbox_service_resolver = (
            get_dependency_resolver().sandbox.get_unsecured_resolver()
        )

        # Define inline to prevent circular lookup
        def resolve_sandboxed_conversation_service(
            session: AsyncSession = Depends(async_session_dependency),
            sandbox_service: SandboxService = Depends(sandbox_service_resolver),
        ) -> SandboxedConversationService:
            return SQLSandboxedConversationService(session, sandbox_service)

        return resolve_sandboxed_conversation_service

    def get_resolver_for_user(self) -> Callable:
        from openhands_server.dependency import get_dependency_resolver
        
        sandbox_service_resolver = (
            get_dependency_resolver().sandbox.get_resolver_for_user()
        )

        # Define inline to prevent circular lookup
        def resolve_sandboxed_conversation_service(
            session: AsyncSession = Depends(async_session_dependency),
            sandbox_service: SandboxService = Depends(sandbox_service_resolver),
        ) -> SandboxedConversationService:
            service = SQLSandboxedConversationService(session, sandbox_service)
            # TODO: Add auth and fix
            logger.warning("⚠️ Using Unsecured SandboxedConversationService!!!")
            # service = ConstrainedSandboxedConversationService(service, self.current_user_id)
            return service

        return resolve_sandboxed_conversation_service