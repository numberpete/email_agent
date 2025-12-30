from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

MOCK_LLM = RunnableLambda(lambda _: AIMessage(content="noop"))
