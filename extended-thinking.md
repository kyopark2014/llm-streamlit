# Claude 3.7 Sonnet의 Extended Thinkig

Extended Thinking과 같은 reasoning을 통해 foundation model의 성능을 향상 시킬 수 있습니다.

```python
boto3_bedrock = boto3.client(
    service_name='bedrock-runtime',
    region_name=bedrock_region,
    config=Config(
        retries = {
            'max_attempts': 30
        }
    )
)

maxReasoningOutputTokens=64000
thinking_budget = 16000
STOP_SEQUENCE = "\n\nHuman:" 
parameters = {
    "max_tokens":maxReasoningOutputTokens,
    "temperature":1,            
    "thinking": {
        "type": "enabled",
        "budget_tokens": thinking_budget
    },
    "stop_sequences": [STOP_SEQUENCE]
}

llm = ChatBedrock(   
    model_id=modelId,
    client=boto3_bedrock, 
    model_kwargs=parameters,
    region_name=bedrock_region
)
```

이를 사용할 때에는 아래와 같이 수행합니다.

```python
def general_conversation(query):
    llm = get_chat(reasoning_mode)

    system = (
        "당신의 이름은 서연이고, 질문에 대해 친절하게 답변하는 사려깊은 인공지능 도우미입니다."
        "상황에 맞는 구체적인 세부 정보를 충분히 제공합니다." 
        "모르는 질문을 받으면 솔직히 모른다고 말합니다."
    )
    
    human = "Question: {input}"
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system), 
        MessagesPlaceholder(variable_name="history"), 
        ("human", human)
    ])
                
    history = memory_chain.load_memory_variables({})["chat_history"]

    try: 
        if reasoning_mode == "Disable":
            chain = prompt | llm | StrOutputParser()
            output = chain.stream(
                {
                    "history": history,
                    "input": query,
                }
            )  
            response = output
        else:
            # output = llm.invoke(query)
            # logger.info(f"output: {output}")
            # response = output.content
            chain = prompt | llm
            output = chain.invoke(
                {
                    "history": history,
                    "input": query,
                }
            )
            logger.info(f"output: {output}")
            response = output
            
    except Exception:
        err_msg = traceback.format_exc()
        logger.info(f"error message: {err_msg}")  
        raise Exception ("Not able to request to LLM: "+err_msg)
        
    return response
```

