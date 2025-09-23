from sqlalchemy import UUID as SQLAlchemyUUID, Column, Float, Integer, String

from openhands_server.database import Base


class StoredConversationMetricsSnapshot(Base):
    """StoredConversationMetrics - see openhands.sdk.llm.utils.metrics.MetricsSnapshot"""

    __tablename__ = "local_conversation_metrics_snapshot"

    conversation_id = Column(SQLAlchemyUUID, primary_key=True)
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
