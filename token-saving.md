# Token Saving Options

[Claude's Token Efficient Tool Use on Amazon Bedrock](https://community.aws/content/2trguomubYb8f3JNzCeBgNvassc/claude-token-efficient-tool-use-on-amazon-bedrock)에 따르면 option 지정으로 평균 14-15% 토큰 절감이 가능하다고 합니다.

상세한 내용은 [Token Efficient Tool Use with Claude on Amazon Bedrock](https://github.com/aws-samples/anthropic-on-aws/blob/main/notebooks/token_efficient_tool_use/token_efficient_tool_use.ipynb)을 참조합니다.



관련된 파라미터는 anthropic_beta 입니다.

```python
efficient_sdk_response = anthropic_client.beta.messages.create(
    max_tokens=1024,
    model=claude_model_id,
    messages=[{"role": "user", "content": "What's the weather like in San Francisco?"}],
    tools=[weather_tool],
    betas=["token-efficient-tools-2025-02-19"]  # Add this beta flag
)
```

```python
efficient_request_body = {
    "anthropic_version": "bedrock-2023-05-31",
    "max_tokens": 1024,
    "messages": [
        {"role": "user", "content": "What's the weather like in San Francisco?"}
    ],
    "tools": [weather_tool],
    "anthropic_beta": ["token-efficient-tools-2025-02-19"]  # Add this beta flag
}
```


```python
retry_config = botocore.config.Config(
    retries={
        'max_attempts': 10,
        'mode': 'adaptive'
    }
)
```
