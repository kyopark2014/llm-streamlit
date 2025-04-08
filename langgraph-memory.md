# LangGraph의 메모리

## 메모리 설명

아래와 같이 short term과 long term 메모리로 나누어 구현할 수 있습니다.

![image](https://github.com/user-attachments/assets/fef5bbb7-e750-4d26-a1e6-d7d460026447)

두 메모리의 특징을 비교하면 아래와 같습니다.

| 구분 | Short-term Memory | Long-term Memory |
|------|------------------|------------------|
| 범위 | 단일 대화 스레드 내에서만 유효 | 여러 대화 스레드에서 공유 가능 |
| 저장 위치 | agent의 state로 관리 | custom namespace에 저장 |
| 지속성 | checkpoint를 통해 데이터베이스에 저장 | store를 통해 JSON 문서로 저장 |
| 주요 용도 | 현재 진행 중인 대화 컨텍스트 유지 | 사용자 정보, 경험, 규칙 등 장기 보존 필요 정보 저장 |
| 메모리 관리 | 메시지 목록 편집, 요약 등으로 관리 | Semantic, Episodic, Procedural 메모리로 구분하여 관리 |

## Short Term Memory

단일 대화 thread에서만 사용되는 메모리로 주로 대화 이력과 업로드된 파일, 검색된 문서를 포함합니다. 긴 대화를 관리하기 위해서는 오래된 메시지를 제거하거나 요약을 수행하여야 합니다. 

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


여러 대화 세션에서 공유 가능한 메모리로 Semantic(의미), Episodic(일화), Procedual(절차) 메모리 형태가 있습니다. Semantic Memory는 사용자 정보 저장에, Episodic Memory는 작업 수행 방법 학습에, Procedural Memory는 에이전트의 행동 규칙 정의에 효과적입니다. 각 메모리 타입들의 장단점과 애플리케이션의 요구사항에 따라 적절히 조합하여 사용합니다.

| 메모리 타입 | 저장 내용 | 인간의 예시 | AI 에이전트의 예시 | 주요 특징 |
|------------|----------|------------|-----------------|-----------|
| Semantic Memory (의미 기억) | 사실과 개념 | 학교에서 배운 지식 | 사용자에 대한 사실 정보 | - Profile 또는 Collection 형태로 관리<br>- 지속적으로 업데이트 가능<br>- 개인화된 상호작용에 활용 |
| Episodic Memory (일화 기억) | 경험과 사건 | 과거에 했던 일들 | 에이전트의 과거 행동 | - Few-shot 예제로 구현<br>- 과거 시퀀스를 통한 학습<br>- 작업 수행 방법 기억 |
| Procedural Memory (절차 기억) | 작업 수행 규칙 | 본능적 기술(자전거 타기 등) | 에이전트 시스템 프롬프트 | - 모델 가중치, 코드, 프롬프트 포함<br>- 주로 프롬프트 수정을 통해 개선<br>- Reflection을 통한 자가 학습 |






### Persistant memory

[LangGraph & Redis: Build smarter AI agents with memory & persistence](https://redis.io/blog/langgraph-redis-build-smarter-ai-agents-with-memory-persistence/)


## memory

![image](https://github.com/user-attachments/assets/9e9fe6ba-8d14-4bab-9dbe-5efbf33c171c)

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


https://www.linkedin.com/posts/rakeshgohel01_these-explanations-will-clarify-your-ai-agent-activity-7313175951243190273-hZl_/?utm_source=share&utm_medium=member_android&rcm=ACoAAA5jTp0BX-JuOkof3Ak56U3VlXjQVT43NzQ

## Reference

[How to add long-term memory using PostgreSQL to LangGraph ReAct agent🤖: Python — LangGraph #3](https://www.youtube.com/watch?v=hE8C2M8GRLo)

