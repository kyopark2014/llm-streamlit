# LangGraph의 메모리




| 구분 | Short-term Memory | Long-term Memory |
|------|------------------|------------------|
| 범위 | 단일 대화 스레드 내에서만 유효 | 여러 대화 스레드에서 공유 가능 |
| 저장 위치 | 에이전트의 상태(state)로 관리 | 커스텀 네임스페이스에 저장 |
| 지속성 | 체크포인터를 통해 데이터베이스에 저장 | 스토어(Store)를 통해 JSON 문서로 저장 |
| 주요 용도 | 현재 진행 중인 대화 컨텍스트 유지 | 사용자 정보, 경험, 규칙 등 장기 보존 필요 정보 저장 |
| 메모리 관리 | 메시지 목록 편집, 요약 등으로 관리 | 시맨틱, 에피소딕, 프로시저 메모리로 구분하여 관리 |

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


## memory

![image](https://github.com/user-attachments/assets/9e9fe6ba-8d14-4bab-9dbe-5efbf33c171c)

https://www.linkedin.com/posts/rakeshgohel01_these-explanations-will-clarify-your-ai-agent-activity-7313175951243190273-hZl_/?utm_source=share&utm_medium=member_android&rcm=ACoAAA5jTp0BX-JuOkof3Ak56U3VlXjQVT43NzQ

## Reference

[How to add long-term memory using PostgreSQL to LangGraph ReAct agent🤖: Python — LangGraph #3](https://www.youtube.com/watch?v=hE8C2M8GRLo)

