from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from langchain_core.messages import BaseMessage


class AgentResponse(BaseModel):
    """
    Standard output contract for all agents.
    Agents may emit messages, propose state updates,
    and optionally request routing decisions.
    """

    messages: List[BaseMessage] = Field(
        default_factory=list,
        description="New messages to append to the conversation state"
    )

    updates: Dict[str, Any] = Field(
        default_factory=dict,
        description="Top-level AgentState fields to update"
    )

    next_node: Optional[str] = Field(
        None,
        description="Explicit next node request (router-eligible agents only)"
    )
