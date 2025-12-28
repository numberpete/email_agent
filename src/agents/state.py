from typing import TypedDict, Annotated, List, Dict, Any, Optional
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class AgentState(TypedDict, total=False):
    # Conversation history (LangGraph-managed)
    messages: Annotated[List[BaseMessage], add_messages]

    # ===== Input & Parsing =====
    raw_input: str
    requires_clarification: bool
    parsed_input: Dict[str, Any]        # normalized prompt + extracted fields
    constraints: Dict[str, Any]         # length, format, audience, etc.

    # ===== Intent & Tone =====
    intent: str                         # outreach, follow-up, apology, info
    intent_confidence: float
    tone_params: Dict[str, Any]         # tokenized tone spec (formality, warmth…)
    user_intent_override: str           # if UI forces an intent
    intent_source: str                  # "ui" | "model" | "default"

    # ===== Drafting =====
    draft: str                          # generic draft
    personalized_draft: str             # after personalization

    # ===== User Context & Memory =====
    user_context: Dict[str, Any]        # profile data, preferences
    memory_updates: Dict[str, Any]      # safe-to-persist deltas only

    # ===== Validation =====
    is_valid: bool
    validation_report: Dict[str, Any]   # errors, warnings, auto-fixes

    # ===== Routing =====
    next: str                           # next node name
    retry_count: int
