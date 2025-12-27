import json
from typing import Optional, List, Dict, Any, Tuple

from langchain_core.messages import BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from langgraph.prebuilt import create_react_agent

from src.agents.response import AgentResponse
from src.agents.state import AgentState


class BaseAgent:
    def __init__(
        self,
        name: str,
        llm,
        system_prompt: str,
        logger,
        tools=None,
        state_key: Optional[str] = None,  # key this agent updates (simple agents)
        next_default: Optional[str] = None,
    ):
        self.name = name
        self.logger = logger
        self.logger.info(f"{self.name} Agent Initializing")

        self.llm = llm
        self.system_prompt = system_prompt
        self.state_key = state_key
        self.next_default = next_default

        if tools is not None and len(tools) > 0:
            # Tool/ReAct agents: state_modifier is fine; inputs must include "messages"
            self.agent = create_react_agent(llm, tools, state_modifier=system_prompt)
        else:
            # Non-tool agents: explicitly accept state_json so passing state is always safe
            prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", system_prompt),
                    ("system", "STATE (for reference): {state_json}"),
                    ("placeholder", "{messages}"),
                ]
            )
            self.agent = prompt | llm

    async def run(self, state: AgentState) -> AgentResponse:
        self.logger.info(f"[{self.name}] Agent Running")
        messages, updates = await self._execute(state)
        return self.create_response(messages, updates)

    def _safe_state_json(self, state: AgentState) -> str:
        """
        Serialize only non-message, JSON-friendly parts of state.
        This prevents failures due to BaseMessage objects in state.
        """
        safe: Dict[str, Any] = dict(state)

        # Messages are already provided separately; remove to avoid serialization issues
        safe.pop("messages", None)

        # Anything non-serializable should be stringified as a last resort
        try:
            return json.dumps(safe, ensure_ascii=False)
        except TypeError:
            def default(o):
                return str(o)
            return json.dumps(safe, ensure_ascii=False, default=default)

    async def _execute(self, state: AgentState) -> Tuple[List[BaseMessage], Dict[str, Any]]:
        """
        Override this in agents that need structured outputs (dict/bool/etc).
        BaseAgent supports updating one simple state field (string) via state_key.
        """

        messages = state.get("messages", [])
        state_json = self._safe_state_json(state)

        # ----------------------------
        # DEBUG: inputs
        # ----------------------------
        self.logger.debug(
            f"[{self.name}] _execute() called | "
            f"messages={len(messages)} | "
            f"state_keys={list(state.keys())}"
        )

        if messages:
            last_msg = messages[-1]
            last_content = getattr(last_msg, "content", "")
            self.logger.debug(
                f"[{self.name}] last_message_type={type(last_msg).__name__} | "
                f"last_message_preview={last_content[:200]!r}"
            )

        # Truncate state_json to avoid log spam
        if state_json:
            self.logger.debug(
                f"[{self.name}] state_json_preview={state_json[:500]!r}"
            )

        # ----------------------------
        # LLM invocation
        # ----------------------------
        response = await self.agent.ainvoke(
            {
                "messages": messages,
                "state_json": state_json,
            }
        )

        # ----------------------------
        # DEBUG: outputs
        # ----------------------------
        content = getattr(response, "content", "")
        self.logger.debug(
            f"[{self.name}] LLM response received | "
            f"content_length={len(content)}"
        )

        if content:
            self.logger.debug(
                f"[{self.name}] response_preview={content[:300]!r}"
            )

        # ----------------------------
        # State updates
        # ----------------------------
        updates: Dict[str, Any] = {}
        if self.state_key:
            updates[self.state_key] = content
            self.logger.debug(
                f"[{self.name}] state update | "
                f"{self.state_key} length={len(content)}"
            )
        else:
            self.logger.debug(f"[{self.name}] no state_key; no direct state update")

        return [response], updates

    def create_response(
        self,
        messages: Optional[List[BaseMessage]] = None,
        updates: Optional[Dict[str, Any]] = None,
        next_node: Optional[str] = None,
    ) -> AgentResponse:
        return AgentResponse(
            messages=messages or [],
            updates=updates or {},
            next_node=next_node or self.next_default,
        )
