# LangGraph의 메모리

## Short Term Memory

여기서는 MemorySaver, InMemoryStore를 이용해 memory 기능을 구현합니다.

```python
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore

checkpointer = MemorySaver()
memorystore = InMemoryStore()

def buildChatAgentWithHistory():
    workflow = StateGraph(State)

    workflow.add_node("agent", call_model)
    workflow.add_node("action", tool_node)
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "continue": "action",
            "end": END,
        },
    )
    workflow.add_edge("action", "agent")

    return workflow.compile(
        checkpointer=checkpointer,
        store=memorystore
    )

app = buildChatAgentWithHistory()
config = {
    "recursion_limit": 50,
    "configurable": {"thread_id": userId}
}

result = app.invoke({"messages": inputs}, config)
msg = result["messages"][-1].content
```

메모리 적용후 결과를 테스트하면 아래와 같습니다.

![image](https://github.com/user-attachments/assets/a29cd27f-cbb9-4ee3-89bd-0a0e8bb9f358)


## Long Term Memory

[LangGraph & Redis: Build smarter AI agents with memory & persistence](https://redis.io/blog/langgraph-redis-build-smarter-ai-agents-with-memory-persistence/)

```python
from typing import Literal
 
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.redis import RedisSaver
 
# Define a simple tool
@tool
def get_weather(city: Literal["nyc", "sf"]):
    """Use this to get weather information."""
    if city == "nyc":
        return "It might be cloudy in nyc"
    elif city == "sf":
        return "It's always sunny in sf"
    else:
        raise AssertionError("Unknown city")
 
# Set up model and tools
tools = [get_weather]
model = ChatOpenAI(model="gpt-4o-mini", temperature=0)
 
# Create Redis persistence
REDIS_URI = "redis://localhost:6379"
with RedisSaver.from_conn_string(REDIS_URI) as checkpointer:
    # Initialize Redis indices (only needed once)
    checkpointer.setup()
     
    # Create agent with memory
    graph = create_react_agent(model, tools=tools, checkpointer=checkpointer)
     
    # Use the agent with a specific thread ID to maintain conversation state
    config = {"configurable": {"thread_id": "user123"}}
    res = graph.invoke({"messages": [("human", "what's the weather in sf")]}, config)
```
