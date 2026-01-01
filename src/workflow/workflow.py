import logging, json
from typing import Dict, Any

from langchain_litellm import ChatLiteLLMRouter
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END

from src.agents.state import AgentState

from src.agents.input_parser_agent import InputParsingAgent
from src.agents.intent_detection_agent import IntentDetectionAgent
from src.agents.tone_stylist_agent import ToneStylistAgent
from src.templates.sqlite_template_store import SQLiteTemplateStore
from src.templates.engine import EmailTemplateEngine
from src.agents.draft_writer_agent import DraftWriterAgent
from src.profiles.sqlite_profile_store import SQLiteProfileStore
from src.memory.sqlite_memory_store import SQLiteMemoryStore
from src.agents.personalization_agent import PersonalizationAgent
from src.agents.review_validator_agent import ReviewValidatorAgent
from src.agents.memory_agent import MemoryAgent
from src.utils.logging import ecid_var
from src.utils.recipient import normalize_recipient
from src.workflow.router import LLM_ROUTER
import uuid_utils as uuid

class EmailWorkflow:
    def __init__(self, logger: logging.Logger):
        # ------------------------------------------------------------------
        # 1. Model setup (explicit and intentional)
        # ------------------------------------------------------------------
        deterministic_llm = ChatLiteLLMRouter(router=LLM_ROUTER, model_name="deterministic")
        creative_llm = ChatLiteLLMRouter(router=LLM_ROUTER, model_name="creative")

        # ------------------------------------------------------------------
        # 2. Agent instantiation
        # ------------------------------------------------------------------
        self.input_parser = InputParsingAgent(deterministic_llm, logger)
        self.intent_detector = IntentDetectionAgent(deterministic_llm, logger)
        self.tone_stylist = ToneStylistAgent(deterministic_llm, logger)

        db_path = "data/email_assist.db"  # or env var
        template_store = SQLiteTemplateStore(db_path)
        template_engine = EmailTemplateEngine(template_store)
        profile_store = SQLiteProfileStore(db_path)
        memory_store = SQLiteMemoryStore(db_path)

        self.draft_writer = DraftWriterAgent(creative_llm, logger, template_engine)

        self.personalizer = PersonalizationAgent(deterministic_llm, logger, profile_store, memory_store)
        self.validator = ReviewValidatorAgent(deterministic_llm, logger)
        self.memory_agent = MemoryAgent(deterministic_llm, logger, memory_store=memory_store)
        self.logger = logger

        # ------------------------------------------------------------------
        # 3. Build the LangGraph
        # ------------------------------------------------------------------
        builder = StateGraph(AgentState)

        async def run_agent(agent, state: AgentState) -> Dict[str, Any]:
            result = await agent.run(state)
            return {
                "messages": result.messages,
                **result.updates,
            }

        # ---- Node definitions (MUST be async defs, not lambdas) ----

        async def input_parser_node(state: AgentState):
            return await run_agent(self.input_parser, state)

        async def intent_detection_node(state: AgentState):
            return await run_agent(self.intent_detector, state)

        async def tone_stylist_node(state: AgentState):
            return await run_agent(self.tone_stylist, state)

        async def draft_writer_node(state: AgentState):
            return await run_agent(self.draft_writer, state)

        async def personalization_node(state: AgentState):
            return await run_agent(self.personalizer, state)

        async def review_validator_node(state: AgentState):
            return await run_agent(self.validator, state)

        async def memory_node(state: AgentState):
            return await run_agent(self.memory_agent, state)

        async def bump_retry_node(state: AgentState) -> Dict[str, Any]:
            retry_count = (state.get("retry_count") or 0) + 1
            logger.debug(f"Validation failed. Retry count now: {retry_count}")
            return {"retry_count": retry_count}

        async def apply_revision_hints_node(state: AgentState) -> Dict[str, Any]:
            report = state.get("validation_report") or {}
            res = report.get("constraint_resolution") or {}

            if not isinstance(res, dict) or not res:
                return {}

            constraints = dict(state.get("constraints") or {})
            tone_params = dict(state.get("tone_params") or {})

            # Drop items from must_include
            drop = res.get("drop_must_include") or []
            if drop and isinstance(constraints.get("must_include"), list):
                constraints["must_include"] = [x for x in constraints["must_include"] if x not in drop]

            # Add items to must_avoid
            add_avoid = res.get("add_must_avoid") or []
            if add_avoid:
                existing = constraints.get("must_avoid") or []
                if not isinstance(existing, list):
                    existing = []
                constraints["must_avoid"] = list(dict.fromkeys(existing + add_avoid))

            # Override tone label (optional)
            override_tone = res.get("override_tone_label")
            if override_tone and isinstance(override_tone, str) and override_tone.strip():
                tone_params["tone_label"] = override_tone.strip()

            return {"constraints": constraints, "tone_params": tone_params}

        # ---- Register nodes ----
        builder.add_node("input_parser", input_parser_node)
        builder.add_node("intent_detection", intent_detection_node)
        builder.add_node("tone_stylist", tone_stylist_node)
        builder.add_node("draft_writer", draft_writer_node)
        builder.add_node("personalization", personalization_node)
        builder.add_node("review_validator", review_validator_node)
        builder.add_node("memory", memory_node)
        builder.add_node("bump_retry", bump_retry_node)
        builder.add_node("apply_revision_hints", apply_revision_hints_node)

        # Linear flow (first pass)
        builder.set_entry_point("input_parser")

        def input_parser_router(state: AgentState):
            """
            Routes based on whether the input parser determined
            that clarification is required.
            """
            if state.get("requires_clarification"):
                return END
            return "intent_detection"

        builder.add_conditional_edges(
            "input_parser",
            input_parser_router,
            {
                "intent_detection": "intent_detection",
                END: END,
            },
        )

        builder.add_edge("intent_detection", "tone_stylist")
        builder.add_edge("tone_stylist", "draft_writer")
        builder.add_edge("draft_writer", "personalization")
        builder.add_edge("personalization", "review_validator")

        # Conditional retry on validation
        def validation_router(state: AgentState):
            report = state.get("validation_report", {}) or {}
            status = (report.get("status") or "").upper()
            if status == "FAIL":
                return "bump_retry"
            return "memory"

        def retry_router(state: AgentState):
            if (state.get("retry_count") or 0) < 2:
                return "apply_revision_hints"
            return "memory"

        builder.add_conditional_edges(
            "review_validator",
            validation_router,
            {
                "bump_retry": "bump_retry",
                "memory": "memory",
            },
        )

        builder.add_conditional_edges(
            "bump_retry",
            retry_router,
            {
                "apply_revision_hints": "apply_revision_hints",
                "memory": "memory",
            },
        )

        builder.add_edge("apply_revision_hints", "draft_writer")
        builder.add_edge("memory", END)

        self.app = builder.compile()

    # ----------------------------------------------------------------------
    # 4. UI-facing entry point
    # ----------------------------------------------------------------------
    async def run_query(
        self,
        user_input: str,
        tone: str | None = None,
        intent: str | None = None,
        metadata: dict | None = None
    ) -> Dict[str, Any]:
    
        self.logger.debug(
            "run_query inputs: user_input_len=%d tone=%r intent=%r metadata_keys=%s",
            len(user_input or ""),
            tone,
            intent,
            sorted(metadata.keys()) if isinstance(metadata, dict) else None,
        )
        #initialize ecid for tracing
        ecid_var.set(uuid.uuid7().hex[:12])
        # Normalize optional inputs
        tone_params = {}
        if tone and tone.strip() and tone.strip().lower() not in {"(auto)", "auto", "none"}:
            tone_params = {"tone_label": tone.strip()}

        metadata_dict = metadata if isinstance(metadata, dict) else {}

        user_id = "default" #for personalization
        messages = []
        initial_constraints: Dict[str, Any] = {}
        recipient = {}

        if metadata_dict:
            initial_constraints.update(metadata_dict)
            user_id = (metadata.get("user_id") or user_id)
            if "recipient" in metadata_dict and isinstance(metadata_dict["recipient"], dict):
                recipient = normalize_recipient(recipient, metadata_dict["recipient"])
            messages.append(SystemMessage(content=f"METADATA (authoritative): {json.dumps(metadata)}"))
        if intent:
            # Optional: keep the UI override visible in state for debugging
            initial_constraints["intent_override"] = intent
        if tone:
            initial_constraints["tone_override"] = tone

        # Optional: make UI overrides explicit too
        if tone:
            messages.append(SystemMessage(content=f"TONE OVERRIDE (authoritative): {tone}"))
        if intent:
            messages.append(SystemMessage(content=f"INTENT OVERRIDE (authoritative): {intent}"))

        messages.append(HumanMessage(content=user_input))

        initial_state: AgentState = {
            "messages": messages,
            "raw_input": user_input,
            "requires_clarification": False,
            "parsed_input": {},
            "constraints": initial_constraints,   # <-- now includes optional metadata/overrides
            "intent": "",               
            "intent_confidence": 0.0,
            "intent_source": "",
            "tone_source": "",             
            "user_intent_override": "",      
            "tone_params": tone_params,           # <-- UI override if provided
            "draft": "",
            "personalized_draft": "",
            "user_id": user_id,
            "user_context": {},
            "memory_updates": {},
            "is_valid": True,
            "validation_report": {},
            "retry_count": 0,
        }

        if intent and intent.lower() not in {"auto", "(auto)"}:
            initial_state["user_intent_override"] = intent.strip()

        self.logger.debug(
            "run_query initial_state keys=%s intent_source=%r user_intent_override=%r id=%s",
            sorted(initial_state.keys()),
            initial_state.get("intent_source"),
            initial_state.get("user_intent_override"),
            id(self),
        )

        final_state = await self.app.ainvoke(
            initial_state,
            config={"recursion_limit": 50}
        )

        debug_snapshot = {
            "intent": final_state.get("intent"),
            "intent_confidence": final_state.get("intent_confidence"),
            "intent_source": final_state.get("intent_source"),
            "tone_source": final_state.get("tone_source"),
            "tone_label": (final_state.get("tone_params") or {}).get("tone_label"),
            "template_id": final_state.get("template_id"),
            "template_plan": final_state.get("template_plan"),
            "user_id": final_state.get("user_id"),
            "draft_len": len(final_state.get("draft") or ""),
            "personalized_draft_len": len(final_state.get("personalized_draft") or ""),
            "retry_count": final_state.get("retry_count"),
            "is_valid": final_state.get("is_valid"),
            "validation_status": (final_state.get("validation_report") or {}).get("status"),
        }

        self.logger.debug("Workflow end snapshot=%s", debug_snapshot)

        return {
            "draft": final_state.get("personalized_draft") or final_state.get("draft"),
            "validation_report": final_state.get("validation_report"),
            "messages": final_state.get("messages", []),
            "intent": final_state.get("intent"),
            "intent_confidence": final_state.get("intent_confidence"),
            "intent_source": final_state.get("intent_source"),
            "tone_params": final_state.get("tone_params"),
            "tone_source": final_state.get("tone_source"),
            "template_id": final_state.get("template_id"),
            "template_plan": final_state.get("template_plan"),
            "user_id": final_state.get("user_id"),
        }