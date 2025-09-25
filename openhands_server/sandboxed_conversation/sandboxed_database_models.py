import uuid

from sqlalchemy import JSON, UUID, Column, DateTime, Float, Integer, String

from openhands_server.database import Base
from openhands_server.utils.date_utils import utc_now


class StoredConversationMetricsSnapshot(Base):
    """
    StoredConversationMetrics - see openhands.sdk.llm.utils.metrics.MetricsSnapshot
    """

    __tablename__ = "sandboxed_conversation_metrics_snapshot"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(UUID, index=True)
    model_name = Column(String)
    accumulated_cost = Column(Float, default=0)
    max_budget_per_task = Column(Float, default=0)

    # Accumulated token usage
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    cache_read_tokens = Column(Integer, default=0)
    cache_write_tokens = Column(Integer, default=0)
    reasoning_tokens = Column(Integer, default=0)
    context_window = Column(Integer, default=0)
    per_turn_token = Column(Integer, default=0)


class StoredSandboxedConversationInfo(Base):
    __tablename__ = "sandboxed_conversation_info"
    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(UUID, unique=True, default=uuid.uuid4)
    sandbox_id = Column(UUID, index=True)
    # We currently don't store status as it is a dynamic attribute of the environment
    agent = Column(JSON, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        index=True,
    )
