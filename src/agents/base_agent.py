from langchain.agents import create_agent
from langchain_core.messages import BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from typing import Optional, List, Dict, Any
from src.agents.response import AgentResponse
from src.agents.state import AgentState
from langgraph.prebuilt import create_react_agent

class BaseAgent:
    def __init__(self, name: str, llm, system_prompt, logger, tools = None,
                 state_key: str = None, # The specific key this agent updates (e.g., 'intent')
                 next_default: Optional[str] = None):
        self.name = name
        self.logger = logger
        self.logger.info(f"{self.name} Agent Initializing")

        if tools is not None and len(tools) > 0:
            self.agent = create_react_agent(llm, tools, state_modifier=system_prompt)
        else:
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("placeholder", "{messages}")
            ])
            self.agent = prompt | llm

        self.llm = llm
        self.system_prompt = system_prompt
        self.state_key = state_key
        self.next_default = next_default

    async def run(self, state: AgentState) -> AgentResponse:
        self.logger.info(f"[{self.name}] Agent Running")
        
        # 1. The generic execute logic
        messages, updates = await self._execute(state)
        
        return self.create_response(messages, updates)

    async def _execute(self, state: AgentState) -> tuple[List[BaseMessage], Dict[str, Any]]:
        """
        This is to be ovedr-written by any subclass that returns structured (non-str) output.

        BaseAgent:
        supports one simple field

        Complex agents:
        override _execute() and return full updates, especially tool-using agents
        """
        messages = state.get("messages", [])
        response = await self.agent.ainvoke({
            "messages": messages,
            "state": state
        })
        
        updates = {}
        if self.state_key:
            updates[self.state_key] = response.content
            
        return [response], updates

    def _determine_next(self, state: Dict[str, Any], updates: Dict[str, Any]) -> Optional[str]:
        """
        Docstring for _determine_next
        Only router-eligible agents override _determine_next().

        :param self
        :param state: the AgentState
        :type state: Dict[str, Any]
        :param updates: 
        :type updates: Dict[str, Any]
        :return: next node to call
        :rtype: str
        """
        return self.next_default
    
    def create_response(self, 
                        messages: List[BaseMessage] = None, 
                        updates: Dict[str, Any] = None, 
                        next_node: str = None) -> AgentResponse:
        """Helper to ensure consistent response formatting."""
        return AgentResponse(
            messages=messages or [],
            updates=updates or {},
            # Use the passed next_node, or fall back to the agent's default
            next_node=next_node or self.next_default
        )