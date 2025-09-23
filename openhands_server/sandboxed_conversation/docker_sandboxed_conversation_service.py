from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID

import docker
import httpx
from sqlalchemy import select

from openhands.sdk import EventBase
from openhands.sdk.conversation.state import AgentExecutionStatus
from openhands.sdk.llm.utils.metrics import MetricsSnapshot
from openhands_server.database import AsyncSessionLocal
from openhands_server.event.event_models import EventPage
from openhands_server.event.read_only_event_context import ReadOnlyEventContext
from openhands_server.local_conversation.agent_info import AgentInfo
from openhands_server.sandbox.sandbox_models import SandboxStatus
from openhands_server.sandbox.sandbox_service import (
    SandboxService,
    get_default_sandbox_service,
)
from openhands_server.sandboxed_conversation.sandboxed_conversation_models import (
    SandboxedConversationInfo,
    SandboxedConversationPage,
)
from openhands_server.sandboxed_conversation.sandboxed_conversation_service import (
    SandboxedConversationService,
)
from openhands_server.sandboxed_conversation.sandboxed_database_models import (
    StoredConversationMetricsSnapshot,
    StoredSandboxedConversationInfo,
)


@dataclass
class DockerSandboxedEventContext(ReadOnlyEventContext):
    """Event context that communicates with a sandboxed container via REST API"""

    conversation_id: UUID
    sandbox_url: str
    session_api_key: str

    async def get_event(self, event_id: str) -> EventBase | None:
        """Get an event from the sandboxed container via REST API"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.sandbox_url}/api/events/{event_id}",
                    headers={"Authorization": f"Bearer {self.session_api_key}"},
                    timeout=10.0,
                )
                if response.status_code == 200:
                    event_data = response.json()
                    return EventBase.model_validate(event_data)
                elif response.status_code == 404:
                    return None
                else:
                    response.raise_for_status()
        except (httpx.RequestError, httpx.HTTPStatusError):
            return None

    async def search_events(
        self, page_id: str | None = None, limit: int = 100
    ) -> EventPage:
        """Search/list events from the sandboxed container via REST API"""
        try:
            params = {"limit": limit}
            if page_id:
                params["page_id"] = page_id

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.sandbox_url}/api/events",
                    params=params,
                    headers={"Authorization": f"Bearer {self.session_api_key}"},
                    timeout=10.0,
                )
                if response.status_code == 200:
                    page_data = response.json()
                    events = [
                        EventBase.model_validate(event)
                        for event in page_data.get("items", [])
                    ]
                    return EventPage(
                        items=events, next_page_id=page_data.get("next_page_id")
                    )
                else:
                    response.raise_for_status()
        except (httpx.RequestError, httpx.HTTPStatusError):
            return EventPage(items=[], next_page_id=None)


@dataclass
class DockerSandboxedConversationService(SandboxedConversationService):
    sandbox_service: SandboxService = field(default_factory=get_default_sandbox_service)

    def _sandbox_status_to_conversation_status(
        self, sandbox_status: SandboxStatus
    ) -> AgentExecutionStatus:
        """Convert sandbox status to conversation status"""
        status_mapping = {
            SandboxStatus.RUNNING: AgentExecutionStatus.RUNNING,
            SandboxStatus.PAUSED: AgentExecutionStatus.PAUSED,
            SandboxStatus.STARTING: AgentExecutionStatus.RUNNING,
            SandboxStatus.DELETED: AgentExecutionStatus.ERROR,
            SandboxStatus.ERROR: AgentExecutionStatus.ERROR,
        }
        return status_mapping.get(sandbox_status, AgentExecutionStatus.ERROR)

    async def _stored_to_sandboxed_info(
        self,
        stored: StoredSandboxedConversationInfo,
        metrics: Optional[StoredConversationMetricsSnapshot] = None,
    ) -> SandboxedConversationInfo:
        """Convert stored database model to SandboxedConversationInfo with live status"""
        # Get live sandbox status
        sandbox_info = None
        status = AgentExecutionStatus.FINISHED

        if stored.sandbox_id:
            sandbox_info = await self.sandbox_service.get_sandboxes(stored.sandbox_id)
            if sandbox_info:
                status = self._sandbox_status_to_conversation_status(
                    sandbox_info.status
                )

        # Convert metrics if available
        metrics_snapshot = None
        if metrics:
            metrics_snapshot = MetricsSnapshot(
                model_name=metrics.model_name,
                accumulated_cost=metrics.accumulated_cost,
                max_budget_per_task=metrics.max_budget_per_task,
                prompt_tokens=metrics.prompt_tokens,
                completion_tokens=metrics.completion_tokens,
                cache_read_tokens=metrics.cache_read_tokens,
                cache_write_tokens=metrics.cache_write_tokens,
                reasoning_tokens=metrics.reasoning_tokens,
                context_window=metrics.context_window,
                per_turn_token=metrics.per_turn_token,
            )

        # Parse agent info from JSON
        agent_info = AgentInfo.model_validate(stored.agent)

        return SandboxedConversationInfo(
            id=stored.conversation_id,
            sandbox_id=stored.sandbox_id,
            title=None,  # Not stored in current schema
            agent=agent_info,
            metrics=metrics_snapshot,
            created_at=stored.created_at,
            updated_at=stored.updated_at,
            status=status,
        )

    async def search_sandboxed_conversations(
        self, user_id: UUID | None = None, page_id: str | None = None, limit: int = 100
    ) -> SandboxedConversationPage:
        """Load a page of sandboxed conversation info from the database and combine it with live status from the docker container"""
        async with AsyncSessionLocal() as session:
            # Build query
            query = select(StoredSandboxedConversationInfo).order_by(
                StoredSandboxedConversationInfo.created_at.desc()
            )

            # Apply pagination
            if page_id:
                try:
                    offset = int(page_id)
                    query = query.offset(offset)
                except ValueError:
                    pass  # Invalid page_id, start from beginning

            query = query.limit(
                limit + 1
            )  # Get one extra to check if there's a next page

            result = await session.execute(query)
            stored_conversations = result.scalars().all()

            # Determine if there's a next page
            has_next_page = len(stored_conversations) > limit
            if has_next_page:
                stored_conversations = stored_conversations[:limit]

            # Convert to SandboxedConversationInfo with live status
            conversations = []
            for stored in stored_conversations:
                # Get metrics for this conversation
                metrics_query = (
                    select(StoredConversationMetricsSnapshot)
                    .where(
                        StoredConversationMetricsSnapshot.conversation_id
                        == stored.conversation_id
                    )
                    .order_by(StoredConversationMetricsSnapshot.id.desc())
                    .limit(1)
                )

                metrics_result = await session.execute(metrics_query)
                metrics = metrics_result.scalar_one_or_none()

                conversation_info = await self._stored_to_sandboxed_info(
                    stored, metrics
                )
                conversations.append(conversation_info)

            # Calculate next page ID
            next_page_id = None
            if has_next_page:
                current_offset = int(page_id) if page_id else 0
                next_page_id = str(current_offset + limit)

            return SandboxedConversationPage(
                items=conversations, next_page_id=next_page_id
            )

    async def get_sandboxed_conversation(
        self, user_id: UUID, conversation_id: UUID
    ) -> SandboxedConversationInfo | None:
        """Get a single sandboxed conversation info from the database and combine it with live status from the docker container."""
        async with AsyncSessionLocal() as session:
            # Get stored conversation
            query = select(StoredSandboxedConversationInfo).where(
                StoredSandboxedConversationInfo.conversation_id == conversation_id
            )
            result = await session.execute(query)
            stored = result.scalar_one_or_none()

            if not stored:
                return None

            # Get metrics for this conversation
            metrics_query = (
                select(StoredConversationMetricsSnapshot)
                .where(
                    StoredConversationMetricsSnapshot.conversation_id == conversation_id
                )
                .order_by(StoredConversationMetricsSnapshot.id.desc())
                .limit(1)
            )

            metrics_result = await session.execute(metrics_query)
            metrics = metrics_result.scalar_one_or_none()

            return await self._stored_to_sandboxed_info(stored, metrics)

    async def batch_get_sandboxed_conversations(
        self, user_id: UUID, conversation_ids: list[UUID]
    ) -> list[SandboxedConversationInfo | None]:
        """Get a batch of sandboxed conversation info from the database and by id and combine it with live status from the docker container(s). Return None for any conversation which was not found."""
        if not conversation_ids:
            return []

        async with AsyncSessionLocal() as session:
            # Get all stored conversations in one query
            query = select(StoredSandboxedConversationInfo).where(
                StoredSandboxedConversationInfo.conversation_id.in_(conversation_ids)
            )
            result = await session.execute(query)
            stored_conversations = {
                conv.conversation_id: conv for conv in result.scalars().all()
            }

            # Get all metrics in one query
            metrics_query = (
                select(StoredConversationMetricsSnapshot)
                .where(
                    StoredConversationMetricsSnapshot.conversation_id.in_(
                        conversation_ids
                    )
                )
                .order_by(
                    StoredConversationMetricsSnapshot.conversation_id,
                    StoredConversationMetricsSnapshot.id.desc(),
                )
            )

            metrics_result = await session.execute(metrics_query)
            all_metrics = metrics_result.scalars().all()

            # Group metrics by conversation_id (taking the latest one for each)
            metrics_by_conversation = {}
            for metric in all_metrics:
                if metric.conversation_id not in metrics_by_conversation:
                    metrics_by_conversation[metric.conversation_id] = metric

            # Build result list in the same order as requested
            results = []
            for conversation_id in conversation_ids:
                stored = stored_conversations.get(conversation_id)
                if stored:
                    metrics = metrics_by_conversation.get(conversation_id)
                    conversation_info = await self._stored_to_sandboxed_info(
                        stored, metrics
                    )
                    results.append(conversation_info)
                else:
                    results.append(None)

            return results

    # Event methods...

    async def get_event_context(self, id: UUID) -> ReadOnlyEventContext | None:
        """Create an event context which loads directly from the sanboxed container via its rest API."""
        # Get the conversation to find its sandbox
        conversation = await self.get_sandboxed_conversation(
            None, id
        )  # user_id not needed for this lookup
        if not conversation or not conversation.sandbox_id:
            return None

        # Get sandbox info to get URL and API key
        sandbox_info = await self.sandbox_service.get_sandboxes(conversation.sandbox_id)
        if not sandbox_info or not sandbox_info.url or not sandbox_info.session_api_key:
            return None

        return DockerSandboxedEventContext(
            conversation_id=id,
            sandbox_url=sandbox_info.url,
            session_api_key=sandbox_info.session_api_key.get_secret_value(),
        )

    # Lifecycle methods

    async def __aenter__(self):
        """Start using this sandboxed conversation service"""
        self._client = docker.from_env()
        await self.sandbox_service.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Stop using this sandbox service"""
        if hasattr(self.sandbox_service, "__aexit__"):
            await self.sandbox_service.__aexit__(exc_type, exc_val, exc_tb)
        self._client = None

    @classmethod
    def get_instance(cls) -> "SandboxedConversationService":
        """Get an instance of sandboxed conversation service"""
        return cls()
