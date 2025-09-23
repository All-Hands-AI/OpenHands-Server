import asyncio

from openhands_server.models.conversation import Conversation

from openhands_server.utils.pub_sub import PubSub


class ConversationExecutor:
    """Run a conversation in a background thread"""

    def __init__(self, conversation: Conversation, pubsub: PubSub):
        self.conversation = conversation
        self.pubsub = pubsub

    async def run_async(self):
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.conversation.run)
