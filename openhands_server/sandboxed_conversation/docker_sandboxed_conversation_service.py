

from dataclasses import dataclass
from uuid import UUID
from openhands_server.event.read_only_event_context import ReadOnlyEventContext
from openhands_server.sandboxed_conversation.sandboxed_conversation_models import SandboxedConversationInfo, SandboxedConversationPage
from openhands_server.sandboxed_conversation.sandboxed_conversation_service import SandboxedConversationService


@dataclass
class DockerSandboxedConversationService(SandboxedConversationService):

    async def search_sandboxed_conversations(self, user_id: UUID | None = None, page_id: str | None = None, limit: int = 100) -> SandboxedConversationPage:
        """Load a page of sandboxed conversation info from the database and combine it with live status from the docker container"""
        raise NotImplementedError()

    async def get_sandboxed_conversation(self, user_id: UUID, conversation_id: UUID) -> SandboxedConversationInfo | None:
        """Get a single sandboxed conversation info from the database and combine it with live status from the docker container."""
        raise NotImplementedError()

    async def batch_get_sandboxed_conversations(self, user_id: UUID, conversation_ids: list[UUID]) -> list[SandboxedConversationInfo | None]:
        """Get a batch of sandboxed conversation info from the database and by id and combine it with live status from the docker container(s). Return None for any conversation which was not found."""
        raise NotImplementedError()

    # Event methods...

    async def get_event_context(self, id: UUID) -> ReadOnlyEventContext | None:
        """ Create an event context which loads directly from the sanboxed container via its rest API. """
        raise NotImplementedError()

    # Lifecycle methods

    async def __aenter__(self):
        """Start using this runtime image service"""
        raise NotImplementedError()

    async def __aexit__(self, exc_type, exc_value, traceback):
        """Stop using this runtime image service"""
        raise NotImplementedError()

    @classmethod
    def get_instance(cls) -> "SandboxedConversationService":
        """ Get an instance of runtime image service """
        raise NotImplementedError()
