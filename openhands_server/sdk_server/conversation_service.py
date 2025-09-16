import asyncio
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID, uuid4

from openhands.sdk import Event, Message
from openhands_server.sdk_server.config import Config
from openhands_server.sdk_server.event_service import EventService
from openhands_server.sdk_server.models import (
    ConversationInfo,
    ConversationPage,
    StartConversationRequest,
    StoredConversation,
)
from openhands_server.sdk_server.subscriber_service import SubscriberService
from openhands_server.sdk_server.utils import utc_now


logger = logging.getLogger(__name__)


@dataclass
class ConversationService:
    """
    Conversation service which stores to a local file store. When the context starts
    all event_services are loaded into memory, and stored when it stops.
    """

    event_services_path: Path = field(default=Path("workspace/event_services"))
    workspace_path: Path = field(default=Path("workspace/project"))
    _event_services: dict[UUID, EventService] | None = field(default=None, init=False)
    _subscriber_services: dict[UUID, SubscriberService] | None = field(
        default=None, init=False
    )

    async def get_conversation(self, conversation_id: UUID) -> ConversationInfo | None:
        if self._event_services is None:
            raise ValueError("inactive_service")
        event_service = self._event_services.get(conversation_id)
        if event_service is None:
            return None
        status = await event_service.get_status()
        return ConversationInfo(**event_service.stored.model_dump(), status=status)

    async def search_conversations(
        self, page_id: str | None = None, limit: int = 100
    ) -> ConversationPage:
        if self._event_services is None:
            raise ValueError("inactive_service")
        items = []
        for id, event_service in self._event_services.items():
            # If we have reached the start of the page
            if page_id is not None:
                try:
                    # Convert page_id to UUID for comparison
                    page_uuid = UUID(page_id)
                    if id == page_uuid:
                        page_id = None
                except (ValueError, TypeError):
                    # Invalid page_id, skip comparison and start from beginning
                    page_id = None

            # Skip past entries before the first item...
            if page_id:
                continue

            # If we have reached the end of the page, return it
            if limit <= 0:
                return ConversationPage(items=items, next_page_id=id.hex)
            limit -= 1

            items.append(
                ConversationInfo(
                    **event_service.stored.model_dump(),
                    status=await event_service.get_status(),
                )
            )
        return ConversationPage(items=items)

    async def batch_get_conversations(
        self, event_service_ids: list[UUID]
    ) -> list[ConversationInfo | None]:
        """Given a list of ids, get a batch of conversation info, returning
        None for any that were not found."""
        results = []
        for id in event_service_ids:
            result = await self.get_conversation(id)
            results.append(result)
        return results

    # Write Methods

    async def start_conversation(
        self, request: StartConversationRequest
    ) -> ConversationInfo:
        """Start a local event_service and return its id."""
        if self._event_services is None or self._subscriber_services is None:
            raise ValueError("inactive_service")
        event_service_id = uuid4()
        stored = StoredConversation(id=event_service_id, **request.model_dump())
        file_store_path = (
            self.event_services_path / event_service_id.hex / "event_service"
        )
        file_store_path.mkdir(parents=True)
        event_service = EventService(
            stored=stored,
            file_store_path=file_store_path,
            working_dir=self.workspace_path,
        )
        await event_service.subscribe_to_events(_EventListener(service=event_service))

        # Create subscriber service
        subscriber_service = SubscriberService(
            conversation_id=event_service_id,
            file_store_path=file_store_path,
            pub_sub=event_service._pub_sub,
        )

        self._event_services[event_service_id] = event_service
        self._subscriber_services[event_service_id] = subscriber_service

        await event_service.start()
        await subscriber_service.start()

        initial_message = request.initial_message
        if initial_message:
            message = Message(
                role=initial_message.role, content=initial_message.content
            )
            await event_service.send_message(message, run=initial_message.run)

        status = await event_service.get_status()
        return ConversationInfo(**event_service.stored.model_dump(), status=status)

    async def pause_conversation(self, conversation_id: UUID) -> bool:
        if self._event_services is None:
            raise ValueError("inactive_service")
        event_service = self._event_services.get(conversation_id)
        if event_service:
            await event_service.pause()
        return bool(event_service)

    async def resume_conversation(self, conversation_id: UUID) -> bool:
        if self._event_services is None:
            raise ValueError("inactive_service")
        event_service = self._event_services.get(conversation_id)
        if event_service:
            await event_service.start()
        return bool(event_service)

    async def delete_conversation(self, conversation_id: UUID) -> bool:
        if self._event_services is None or self._subscriber_services is None:
            raise ValueError("inactive_service")
        event_service = self._event_services.pop(conversation_id, None)
        subscriber_service = self._subscriber_services.pop(conversation_id, None)

        if event_service:
            await event_service.close()
            if subscriber_service:
                await subscriber_service.close()
            shutil.rmtree(self.event_services_path / conversation_id.hex)
            shutil.rmtree(self.workspace_path / conversation_id.hex)
            return True
        return False

    async def get_event_service(self, conversation_id: UUID) -> EventService | None:
        if self._event_services is None:
            raise ValueError("inactive_service")
        return self._event_services.get(conversation_id)

    async def get_subscriber_service(
        self, conversation_id: UUID
    ) -> SubscriberService | None:
        if self._subscriber_services is None:
            raise ValueError("inactive_service")
        return self._subscriber_services.get(conversation_id)

    async def __aenter__(self):
        self.event_services_path.mkdir(parents=True, exist_ok=True)
        event_services = {}
        subscriber_services = {}

        for event_service_dir in self.event_services_path.iterdir():
            try:
                meta_file = event_service_dir / "event_service" / "meta.json"
                json_str = meta_file.read_text()
                id = UUID(event_service_dir.name)

                event_service = EventService(
                    stored=StoredConversation.model_validate_json(json_str),
                    file_store_path=self.event_services_path / id.hex / "event_service",
                    working_dir=self.workspace_path / id.hex,
                )

                # Create subscriber service for existing conversations
                subscriber_service = SubscriberService(
                    conversation_id=id,
                    file_store_path=self.event_services_path / id.hex / "event_service",
                    pub_sub=event_service._pub_sub,
                )

                event_services[id] = event_service
                subscriber_services[id] = subscriber_service

            except Exception:
                logger.exception(
                    f"error_loading_event_service:{event_service_dir}", stack_info=True
                )
                shutil.rmtree(event_service_dir)

        self._event_services = event_services
        self._subscriber_services = subscriber_services
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        event_services = self._event_services
        subscriber_services = self._subscriber_services

        if event_services is None:
            return

        self._event_services = None
        self._subscriber_services = None

        # Close all services
        tasks = []

        # Close event services
        for event_service in event_services.values():
            tasks.append(event_service.__aexit__(exc_type, exc_value, traceback))

        # Close subscriber services
        if subscriber_services:
            for subscriber_service in subscriber_services.values():
                tasks.append(
                    subscriber_service.__aexit__(exc_type, exc_value, traceback)
                )

        await asyncio.gather(*tasks)

    @classmethod
    def get_instance(cls, config: Config) -> "ConversationService":
        return ConversationService(
            event_services_path=config.conversations_path,
            workspace_path=config.workspace_path,
        )


@dataclass
class _EventListener:
    service: EventService

    async def __call__(self, event: Event):
        self.service.stored.updated_at = utc_now()


_conversation_service: ConversationService | None = None


def get_default_conversation_service() -> ConversationService:
    global _conversation_service
    if _conversation_service:
        return _conversation_service

    from openhands_server.sdk_server.config import (
        get_default_config,
    )

    config = get_default_config()
    _conversation_service = ConversationService.get_instance(config)
    return _conversation_service
