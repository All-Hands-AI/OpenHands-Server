import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

import openhands.tools    
from openhands.sdk import Conversation, EventBase, LocalFileStore, Message, Agent, create_mcp_tools
from openhands.sdk.conversation.state import AgentExecutionStatus
from openhands.sdk.utils.async_utils import (
    AsyncCallbackWrapper,
    AsyncConversationCallback,
)
from openhands_server.event.event_context import EventContext
from openhands_server.event.event_models import EventPage
from openhands_server.local_conversation.local_conversation_models import (
    StoredLocalConversation,
)
from openhands_server.utils.date_utils import utc_now
from openhands_server.utils.pub_sub import PubSub


@dataclass
class LocalConversationEventContext(EventContext):
    """
    Event service for a conversation running locally. Use an event manager to start the service before use
    """

    stored: StoredLocalConversation
    file_store_path: Path
    working_dir: Path
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)
    _conversation: Conversation | None = field(default=None, init=False)
    _pub_sub: PubSub = field(default_factory=PubSub, init=False)

    async def load_meta(self):
        meta_file = self.file_store_path / "meta.json"
        self.stored = StoredLocalConversation.model_validate_json(meta_file.read_text())

    async def save_meta(self):
        self.stored.updated_at = utc_now()
        meta_file = self.file_store_path / "meta.json"
        meta_file.write_text(self.stored.model_dump_json())

    async def get_event(self, event_id: str) -> EventBase | None:
        if self._conversation is None:
            raise RuntimeError("Conversation not started")
        async with self._lock:
            with self._conversation.state as state:
                event_id_idx = state.events.get_index(event_id)
                return state.events[event_id_idx]

    async def search_events(self, page_id: str | None = None, limit: int = 100) -> EventPage:
        if self._conversation is None:
            raise RuntimeError("Conversation not started")
        
        items = []
        async with self._lock:
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

    async def search(self, page_id: str | None = None, limit: int = 100) -> EventPage:
        """Alias for search_events to match the expected interface."""
        return await self.search_events(page_id, limit)

    async def send_message(self, message: Message):
        async with self._lock:
            loop = asyncio.get_running_loop()
            loop.run_in_executor(None, self._conversation.send_message, message)
            with self._conversation.state as state:
                if state.agent_status != AgentExecutionStatus.RUNNING:
                    loop.run_in_executor(None, self._conversation.run, message)


    async def subscribe_to_events(self, callback: AsyncConversationCallback) -> UUID:
        return self._pub_sub.subscribe(callback)

    async def unsubscribe_from_events(self, callback_id: UUID) -> bool:
        return self._pub_sub.unsubscribe(callback_id)

    async def start(self):
        async with self._lock:
            llm = self.stored.llm
            tools = []
            
            # Create tools from tool specs
            for tool_spec in self.stored.tools:
                if tool_spec.name not in openhands.tools.__dict__:
                    continue
                tool_class = openhands.tools.__dict__[tool_spec.name]
                tools.append(tool_class.create(**tool_spec.params))
            
            # Add MCP tools if configured
            if self.stored.mcp_config:
                mcp_tools = create_mcp_tools(self.stored.mcp_config, timeout=30)
                tools.extend(mcp_tools)
            
            agent = Agent(llm=llm, tools=tools, agent_context=self.stored.agent_context)
            conversation = Conversation(
                agent=agent,
                callbacks=[AsyncCallbackWrapper(self._pub_sub, loop=asyncio.get_running_loop())],
                persist_filestore=LocalFileStore(str(self.file_store_path / "events")),
            )
            
            # Set confirmation mode if enabled
            conversation.set_confirmation_mode(self.stored.confirmation_mode)
            self._conversation = conversation
            await self.run()


    async def run(self):
        """Run the conversation asynchronously."""
        if not self._conversation:
            raise RuntimeError("Conversation not started")
        async with self._lock:
            loop = asyncio.get_running_loop()
            loop.run_in_executor(None, self._conversation.run)

    async def pause(self):
        async with self._lock:
            if self._conversation:
                loop = asyncio.get_running_loop()
                loop.run_in_executor(None, self._conversation.pause)

    async def close(self):
        async with self._lock:
            if self._conversation:
                loop = asyncio.get_running_loop()
                loop.run_in_executor(None, self._conversation.close)

    async def get_status(self) -> AgentExecutionStatus:
        async with self._lock:
            if not self._conversation:
                return AgentExecutionStatus.ERROR
            with self._conversation.state as state:
                return state.agent_status

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        self.save_meta()
        await self.close()
