import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

from openhands.sdk import (
    Agent,
    Conversation,
    EventBase,
    LocalFileStore,
)
from openhands.sdk.conversation.state import AgentExecutionStatus
from openhands.sdk.utils.async_utils import (
    AsyncCallbackWrapper,
    AsyncConversationCallback,
)
from openhands_server.sdk_server.models import (
    ConfirmationResponseRequest,
    EventPage,
    SendMessageRequest,
    StoredConversation,
)
from openhands_server.sdk_server.pub_sub import PubSub
from openhands_server.sdk_server.utils import utc_now


@dataclass
class EventService:
    """
    Event service for a conversation running locally, analagous to a conversation
    in the SDK. Async mostly for forward compatibility
    """

    stored: StoredConversation
    file_store_path: Path
    working_dir: Path
    _conversation: Conversation | None = field(default=None, init=False)
    _pub_sub: PubSub = field(default_factory=PubSub, init=False)

    async def load_meta(self):
        meta_file = self.file_store_path / "meta.json"
        self.stored = StoredConversation.model_validate_json(meta_file.read_text())

    async def save_meta(self):
        self.stored.updated_at = utc_now()
        meta_file = self.file_store_path / "meta.json"
        meta_file.write_text(self.stored.model_dump_json())

    async def get_event(self, event_id: str) -> EventBase | None:
        if not self._conversation:
            raise ValueError("inactive_service")
        with self._conversation.state as state:
            # TODO: It would be nice if the agent sdk had a method for
            #       getting events by id
            event = next(
                (event for event in state.events if event.id == event_id), None
            )
            return event

    async def search_events(
        self, page_id: str | None = None, limit: int = 100
    ) -> EventPage:
        if not self._conversation:
            raise ValueError("inactive_service")

        items = []
        with self._conversation.state as state:
            for event in state.events:
                # If we have reached the start of the page
                if event.id == page_id:
                    page_id = None

                # Skip pass entries before the first item...
                if page_id:
                    continue

                # If we have reached the end of the page, return it
                if limit <= 0:
                    return EventPage(items=items, next_page_id=event.id)
                limit -= 1

                items.append(event)

        return EventPage(items=items)

    async def batch_get_events(self, event_ids: list[str]) -> list[EventBase | None]:
        """Given a list of ids, get events (Or none for any which were not found)"""
        results = []
        for event_id in event_ids:
            result = await self.get_event(event_id)
            results.append(result)
        return results

    async def send_message(self, request: SendMessageRequest):
        if not self._conversation:
            raise ValueError("inactive_service")
        message = request.create_message()
        loop = asyncio.get_running_loop()
        future = loop.run_in_executor(None, self._conversation.send_message, message)
        if request.run:
            await future
            loop.run_in_executor(None, self._conversation.run)

    async def subscribe_to_events(self, callback: AsyncConversationCallback) -> UUID:
        return self._pub_sub.subscribe(callback)

    async def unsubscribe_from_events(self, callback_id: UUID) -> bool:
        return self._pub_sub.unsubscribe(callback_id)

    async def start(self, conversation_id: UUID):
        # self.stored is a subclass of AgentSpec so we can create an agent from it
        agent = Agent.from_spec(self.stored)
        conversation = Conversation(
            agent=agent,
            persist_filestore=LocalFileStore(
                str(self.file_store_path)
                # inside Conversation, events will be saved to
                # "file_store_path/{convo_id}/events"
            ),
            conversation_id=str(conversation_id),
            callbacks=[
                AsyncCallbackWrapper(self._pub_sub, loop=asyncio.get_running_loop())
            ],
            max_iteration_per_run=self.stored.max_iterations,
        )

        # Set confirmation mode if enabled
        conversation.set_confirmation_mode(self.stored.confirmation_mode)
        self._conversation = conversation

    async def run(self):
        """Run the conversation asynchronously."""
        if not self._conversation:
            raise ValueError("inactive_service")
        loop = asyncio.get_running_loop()
        loop.run_in_executor(None, self._conversation.run)

    async def respond_to_confirmation(self, request: ConfirmationResponseRequest):
        if request.accept:
            await self.run()
        else:
            await self.pause()

    async def pause(self):
        if self._conversation:
            loop = asyncio.get_running_loop()
            loop.run_in_executor(None, self._conversation.pause)

    async def close(self):
        if self._conversation:
            loop = asyncio.get_running_loop()
            loop.run_in_executor(None, self._conversation.close)

    async def get_status(self) -> AgentExecutionStatus:
        if not self._conversation:
            return AgentExecutionStatus.ERROR
        return self._conversation.state.agent_status

    async def __aenter__(self, conversation_id: UUID):
        await self.start(conversation_id=conversation_id)
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.save_meta()
        await self.close()
