# Streamlit을 이용한 GenAI Application 배포 및 활용

<p align="left">
    <a href="https://hits.seeyoufarm.com"><img src="https://hits.seeyoufarm.com/api/count/incr/badge.svg?url=https%3A%2F%2Fgithub.com%2Fkyopark2014%2Fllm-streamlit&count_bg=%2379C83D&title_bg=%23555555&icon=&icon_color=%23E7E7E7&title=hits&edge_flat=false)](https://hits.seeyoufarm.com"/></a>
    <img alt="License" src="https://img.shields.io/badge/LICENSE-MIT-green">
</p>



여기서는 [Streamlit](https://streamlit.io/)을 이용해 개발한 GenAI application을 쉽게 배포하고 안전하게 활용할 수 있는 방법에 대해 설명합니다. 한번에 배포하고 바로 활용할 수 있도록 [CDK](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-construct-library.html)를 이용하였고, ALB - EC2의 구조를 이용해서 필요시 scale out도 구현할 수 있습니다. 또한, [CloudFront](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/Introduction.html) - ALB 구조를 이용해 배포후 HTTPS로 안전하게 접속할 수 있습니다. Streamlit이 설치되는 EC2의 OS는 EKS/ECS와 같은 컨테이너 서비스에 주로 사용되는 [Amazon Linux](https://docs.aws.amazon.com/linux/al2023/ug/what-is-amazon-linux.html)을 사용하여 트래픽이 증가하여 ECS/EKS로 전환할 때에 수고를 줄일 수 있도록 하였습니다.

## System Architecture 

전체적인 architecture는 아래와 같습니다. 여기서에서는 streamlit이 설치된 EC2는 private subnet에 둬서 안전하게 관리합니다. [Amazon S3는 Gateway Endpoint](https://docs.aws.amazon.com/vpc/latest/privatelink/vpc-endpoints-s3.html)를 이용하여 연결하고 Bedrock은 [Private link](https://docs.aws.amazon.com/ko_kr/bedrock/latest/userguide/usingVPC.html)를 이용하여 연결하였으므로 EC2의 트래픽은 외부로 나가지 않고 AWS 내부에서 처리가 됩니다. 인터넷 및 날씨의 검색 API는 외부 서비스 공급자의 API를 이용하므로 [NAT gateway](https://docs.aws.amazon.com/vpc/latest/userguide/vpc-nat-gateway.html)를 이용하여 연결하였습니다.

<img width="800" alt="image" src="https://github.com/user-attachments/assets/2fd4a38c-170c-401a-8103-e5641ed25378" />

### CDK로 배포 환경 구현

EC2를 아래와 같이 정의합니다. 상세한 내용은 [cdk-llm-streamlit-stack.ts](./cdk-llm-streamlit/lib/cdk-llm-streamlit-stack.ts)을 참조합니다.

```java
const appInstance = new ec2.Instance(this, `app-for-${projectName}`, {
    instanceName: `app-for-${projectName}`,
    instanceType: new ec2.InstanceType('t2.small'), // m5.large
    machineImage: new ec2.AmazonLinuxImage({
        generation: ec2.AmazonLinuxGeneration.AMAZON_LINUX_2023
    }),
    vpc: vpc,
    vpcSubnets: {
        subnets: vpc.privateSubnets 
    },
    securityGroup: ec2Sg,
    role: ec2Role,
    userData: userData,
    blockDevices: [{
        deviceName: '/dev/xvda',
        volume: ec2.BlockDeviceVolume.ebs(8, {
            deleteOnTermination: true,
            encrypted: true,
        }),
    }],
    detailedMonitoring: true,
    instanceInitiatedShutdownBehavior: ec2.InstanceInitiatedShutdownBehavior.TERMINATE,
});
appInstance.applyRemovalPolicy(cdk.RemovalPolicy.DESTROY);
```

EC2의 userdata는 아래와 같이 설정합니다. 필요한 패키지를 설치하고 streamlit을 서비스로 배포합니다. Streamlit의 기본 포트는 8501이나 여기서는 config.toml을 이용하여 포트를 8080으로 변경하였습니다. App이 ec2-user 계정에 있어야 하므로 아래와 같이 필요한 패키지를 설치합니다.

```java
const userData = ec2.UserData.forLinux();

const commands = [
  'yum install git python-pip -y',
  'pip install pip --upgrade',            
  `sh -c "cat <<EOF > /etc/systemd/system/streamlit.service
[Unit]
Description=Streamlit
After=network-online.target

[Service]
User=ec2-user
Group=ec2-user
Restart=always
ExecStart=/home/ec2-user/.local/bin/streamlit run /home/ec2-user/${projectName}/application/app.py

[Install]
WantedBy=multi-user.target
EOF"`,
    `runuser -l ec2-user -c "mkdir -p /home/ec2-user/.streamlit"`,
    `runuser -l ec2-user -c "cat <<EOF > /home/ec2-user/.streamlit/config.toml
[server]
port=${targetPort}
EOF"`,
  `runuser -l ec2-user -c 'cd && git clone https://github.com/kyopark2014/${projectName}'`,
  `runuser -l ec2-user -c 'pip install streamlit streamlit_chat'`,        
  `runuser -l ec2-user -c 'pip install boto3 langchain_aws langchain langchain_community langgraph'`,
  `runuser -l ec2-user -c 'pip install beautifulsoup4 pytz tavily-python'`,
  'systemctl enable streamlit.service',
  'systemctl start streamlit'
];
userData.addCommands(...commands);
```

ALB를 준비합니다.

```java
const alb = new elbv2.ApplicationLoadBalancer(this, `alb-for-${projectName}`, {
  internetFacing: true,
  vpc: vpc,
  vpcSubnets: {
    subnets: vpc.publicSubnets
  },
  securityGroup: albSg,
  loadBalancerName: `alb-for-${projectName}`
})
alb.applyRemovalPolicy(cdk.RemovalPolicy.DESTROY);
```

HTTPS로 streamlit을 이용하기 위해서는 ALB에 인증서를 추가하거나 CloudFront를 이용할 수 있습니다. Streamlit은 주로 PoC나 테스트 앱 용도로 활용하므로 별도 인증서를 받지 않고 CloudFront로 손쉽게 HTTPS 커텍션을 제공합니다. 이를 위해, CloudFront가 ALB의 HTTP 80포트와 연결가능하도록 사용하도록 준비합니다. 

```java
const CUSTOM_HEADER_NAME = "X-Custom-Header"
const CUSTOM_HEADER_VALUE = `xxxx`
const origin = new origins.LoadBalancerV2Origin(alb, {      
  httpPort: 80,
  customHeaders: {[CUSTOM_HEADER_NAME] : CUSTOM_HEADER_VALUE},
  originShieldEnabled: false,
  protocolPolicy: cloudFront.OriginProtocolPolicy.HTTP_ONLY      
});
const distribution = new cloudFront.Distribution(this, `cloudfront-for-${projectName}`, {
  comment: "CloudFront distribution for Streamlit frontend application",
  defaultBehavior: {
    origin: origin,
    viewerProtocolPolicy: cloudFront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
    allowedMethods: cloudFront.AllowedMethods.ALLOW_ALL,
    cachePolicy: cloudFront.CachePolicy.CACHING_DISABLED,
    originRequestPolicy: cloudFront.OriginRequestPolicy.ALL_VIEWER        
  },
  priceClass: cloudFront.PriceClass.PRICE_CLASS_200
}); 
```

ALB의 Listener가 stremlit이 설치되는 EC2로 라우팅 되도록 설정합니다. 
    
```java
const listener = alb.addListener(`HttpListener-for-${projectName}`, {   
  port: 80,
  open: true
});     
const targetGroup = listener.addTargets(`WebEc2Target-for-${projectName}`, {
  targetGroupName: `TG-for-${projectName}`,
  targets: targets,
  protocol: elbv2.ApplicationProtocol.HTTP,
  port: targetPort,
  conditions: [elbv2.ListenerCondition.httpHeader(CUSTOM_HEADER_NAME, [CUSTOM_HEADER_VALUE])],
  priority: 10      
});
listener.addTargetGroups(`addTG-for-${projectName}`, {
  targetGroups: [targetGroup]
})
const defaultAction = elbv2.ListenerAction.fixedResponse(403, {
    contentType: "text/plain",
    messageBody: 'Access denied',
})
listener.addAction(`RedirectHttpListener-for-${projectName}`, {
  action: defaultAction
});  
```

## 상세 구현

Agentic workflow (tool use)는 아래와 같이 구현할 수 있습니다. 상세한 내용은 [chat.py](./application/chat.py)을 참조합니다.

```python
def buildAgentExecutor():
    workflow = StateGraph(State)

    workflow.add_node("agent", execution_agent_node)
    workflow.add_node("action", tool_node)
    workflow.add_node("final_answer", final_answer)
    
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "continue": "action",
            "end": "final_answer",
        },
    )
    workflow.add_edge("action", "agent")
    workflow.add_edge("final_answer", END)

    return workflow.compile()
```

번역하기는 아래와 같이 한/영이 변환 가능하도록 구성하였습니다. XML tag를 이용해 답변만 추출하는 방식을 사용하였습니다. XML tag는 anthropic의 claude 모델에서 추천하는 방식인데, Nova pro에서도 유용하게 사용할 수 있습니다. 

```python
def translate_text(text):
    chat = get_chat()

    system = (
        "You are a helpful assistant that translates {input_language} to {output_language} in <article> tags. Put it in <result> tags."
    )
    human = "<article>{text}</article>"
    
    prompt = ChatPromptTemplate.from_messages([("system", system), ("human", human)])
    # print('prompt: ', prompt)
    
    if isKorean(text)==False :
        input_language = "English"
        output_language = "Korean"
    else:
        input_language = "Korean"
        output_language = "English"
                        
    chain = prompt | chat    
    try: 
        result = chain.invoke(
            {
                "input_language": input_language,
                "output_language": output_language,
                "text": text,
            }
        )
        msg = result.content
        print('translated text: ', msg)
    except Exception:
        err_msg = traceback.format_exc()
        print('error message: ', err_msg)                    
        raise Exception ("Not able to request to LLM")

    return msg[msg.find('<result>')+8:msg.find('</result>')] 
```

이미지 분석하는 방법은 아래와 같습니다. 이미지 분석을 요청할때 "사진속 사람들의 행동을 분석해주세요"와 같이 base64로 encoding된 이미지의 내용에 대해 힌트를 제공하면 훨씬 더 좋은 결과를 얻을 수 있습니다. 여기에서는 아래와 같이 사용자가 입력한 메시지를 힌트로 사용하여 이미지를 분석하고 있습니다.

```python
def use_multimodal(img_base64, query):    
    multimodal = get_chat()
    
    messages = [
        SystemMessage(content="답변은 500자 이내의 한국어로 설명해주세요."),
        HumanMessage(
            content=[
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{img_base64}", 
                    },
                },
                {
                    "type": "text", "text": query
                },
            ]
        )
    ]
    
    try: 
        result = multimodal.invoke(messages)
        
        summary = result.content
        print('result of code summarization: ', summary)
    except Exception:
        err_msg = traceback.format_exc()
        print('error message: ', err_msg)                    
        raise Exception ("Not able to request to LLM")
    
    return summary
```

### Basic Chat

일반적인 대화는 아래와 같이 stream으로 결과를 얻을 수 있습니다. 여기에서는 LangChain의 ChatBedrock과 Nova Pro의 모델명인 "us.amazon.nova-pro-v1:0"을 활용하고 있습니다.

```python
modelId = "us.amazon.nova-pro-v1:0"
bedrock_region = "us-west-2"
boto3_bedrock = boto3.client(
    service_name='bedrock-runtime',
    region_name=bedrock_region,
    config=Config(
        retries = {
            'max_attempts': 30
        }
    )
)
parameters = {
    "max_tokens":maxOutputTokens,     
    "temperature":0.1,
    "top_k":250,
    "top_p":0.9,
    "stop_sequences": ["\n\n<thinking>", "\n<thinking>", " <thinking>"]
}

chat = ChatBedrock(  
    model_id=modelId,
    client=boto3_bedrock, 
    model_kwargs=parameters,
    region_name=bedrock_region
)

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

chain = prompt | chat | StrOutputParser()
stream = chain.stream(
    {
        "history": history,
        "input": query,
    }
)  
print('stream: ', stream)
```

### Agentic Workflow: Tool Use

아래와 같이 activity diagram을 이용하여 node/edge/conditional edge로 구성되는 tool use 방식의 agent를 구현할 수 있습니다.

<img width="261" alt="image" src="https://github.com/user-attachments/assets/31202a6a-950f-44d6-b50e-644d28012d8f" />

Tool use 방식 agent의 workflow는 아래와 같습니다. Fuction을 선택하는 call model 노드과 실행하는 tool 노드로 구성됩니다. 선택된 tool의 결과에 따라 cycle형태로 추가 실행을 하거나 종료하면서 결과를 전달할 수 있습니다.

```python
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

app = workflow.compile()

inputs = [HumanMessage(content=query)]
config = {
    "recursion_limit": 50
}
message = app.invoke({"messages": inputs}, config)

print(event["messages"][-1].content)
```


### 활용 방법

EC2는 Private Subnet에 있으므로 SSL로 접속할 수 없습니다. 따라서, [Console-EC2](https://us-west-2.console.aws.amazon.com/ec2/home?region=us-west-2#Instances:)에 접속하여 "app-for-llm-streamlit"를 선택한 후에 Connect에서 sesseion manager를 선택하여 접속합니다. 

Github에서 app에 대한 코드를 업데이트 하였다면, EC2에 session manager를 이용해 접속한 후에 아래 명령어로 업데이트 합니다. 

```text
sudo runuser -l ec2-user -c 'cd /home/ec2-user/llm-streamlit && git pull'
```

Streamlit의 재시작이 필요하다면 아래 명령어로 service를 stop/start 시키고 동작을 확인할 수 있습니다.

```text
sudo systemctl stop streamlit
sudo systemctl start streamlit
sudo systemctl status streamlit -l
```

Local에서 디버깅을 빠르게 진행하고 싶다면 [Local에서 실행하기](https://github.com/kyopark2014/llm-streamlit/blob/main/deployment.md#local%EC%97%90%EC%84%9C-%EC%8B%A4%ED%96%89%ED%95%98%EA%B8%B0)에 따라서 Local에 필요한 패키지와 환경변수를 업데이트 합니다. 이후 아래 명령어서 실행합니다.

```text
streamlit run application/app.py
```

EC2에서 debug을 하면서 개발할때 사용하는 명령어입니다.

먼저, 시스템에 등록된 streamlit을 종료합니다.

```text
sudo systemctl stop streamlit
```

이후 EC2를 session manager를 이용해 접속한 이후에 아래 명령어를 이용해 실행하면 로그를 보면서 수정을 할 수 있습니다. 

```text
sudo runuser -l ec2-user -c "/home/ec2-user/.local/bin/streamlit run /home/ec2-user/llm-streamlit/application/app.py"
```



## 직접 실습 해보기

### 사전 준비 사항

이 솔루션을 사용하기 위해서는 사전에 아래와 같은 준비가 되어야 합니다.

- [AWS Account 생성](https://repost.aws/ko/knowledge-center/create-and-activate-aws-account)에 따라 계정을 준비합니다.

### CDK를 이용한 인프라 설치

본 실습에서는 us-west-2 리전을 사용합니다. [인프라 설치](./deployment.md)에 따라 CDK로 인프라 설치를 진행합니다. 

## 실행결과

왼쪽의 메뉴에서 아래와 같이 일상적인 대화, Agentic Workflow (Tool Use), 번역하기, 문법 검토하기, 이미지 분석을 제공합니다. 각 메뉴를 선택하여 아래와 같이 활용할 수 있습니다. 

![image](https://github.com/user-attachments/assets/7ab0d2e7-3bd0-44b9-b2be-f4d68a6ff60b)



### 일상적인 대화

메뉴에서 일상적인 대화를 선택하고 아래와 같이 인사와 함께 날씨 질문을 합니다. Prompt에 따라서 챗봇의 이름이 서연이라고 얘기하고 있으며, 일상적인 대화에서는 API를 호출할수 없으므로 날씨 정보는 제공할 수 없습니다. 

![image](https://github.com/user-attachments/assets/a0c305a0-34ca-450f-9cd5-5689aca9a0f9)

### Agentic Workflow

Agentic Workflow(Tool Use) 메뉴를 선택하여 오늘 서울의 날씨에 대해 질문을 하면, 아래와 같이 입력하고 결과를 확인합니다. LangGraph로 구현된 Tool Use 패턴의 agent는 날씨에 대한 요청이 올 경우에 openweathermap의 API를 요청해 날씨정보를 조회하여 활용할 수 있습니다. 

![image](https://github.com/user-attachments/assets/4693c1ff-b7e9-43f5-b7b7-af354b572f07)

아래와 같은 질문은 LLM이 가지고 있지 않은 정보이므로, 인터넷 검색을 수행하고 그 결과로 아래와 같은 답변을 얻었습니다.

![image](https://github.com/user-attachments/assets/8f8d2e94-8be1-4b75-8795-4db9a8fa340f)


### 번역하기

메뉴에서 "번역하기"를 선택하고 아래와 같이 한국어를 입력하면 영어로 번역을 수행합니다. 만약 입력이 영어였다면 한국어로 번역하도록 프롬프트를 구성하였습니다.

![image](https://github.com/user-attachments/assets/8649b4c9-3f9d-45ab-8bb2-5693501972cd)

### 문법 검토하기

문법 검토하기를 선택후 문장을 입력하면 아래와 같이 수정이 필요한 부분을 알려주고 수정된 문장도 함께 제시합니다. 

![image](https://github.com/user-attachments/assets/0afc2778-772c-4505-b901-67eae5beeb90)

### 이미지 분석

이미지를 분석할 수 있는 프롬프트를 테스트해 볼 수 있습니다. 왼쪽의 "Browse files"를 선택하고, "ReAct의 장점에 대해 설명해주세요."라고 입력합니다. 

이때 [사용한 이미지](./contents/example-table.png)는 아래와 같습니다. 이 이미지는 ReAct와 CoT를 비교하고 있습니다.

![image](https://github.com/user-attachments/assets/ec22508a-1569-49a1-a6fb-6442bc972d2a)

이때의 결과는 아래와 같습니다. 입력한 메시지에 맞는 의미를 그림파일에서 찾고 아래와 같이 먼저 결과를 제시합니다. 실제 LLM이 인식한 표를 아래와 같이 확인할 수 있습니다.

![image](https://github.com/user-attachments/assets/39fb2235-c6ef-42e0-8f43-f158cb088db4)

메뉴에서 [이미지 분석]과 모델로 [Claude 3.5 Sonnet]을 선택한 후에 [기다리는 사람들 사진](./contents/waiting_people.jpg)을 다운받아서 업로드합니다. 이후 "사진속에 있는 사람들은 모두 몇명인가요?"라고 입력후 결과를 확인하면 아래와 같습니다.

<img width="600" alt="image" src="https://github.com/user-attachments/assets/3e1ea017-4e46-4340-87c6-4ebf019dae4f" />


### Amazon S3와 Bedrock Endpoint의 동작 확인

[cdk-llm-streamlit-stack.ts](./cdk-llm-streamlit/lib/cdk-llm-streamlit-stack.ts)의 VPC 설정은 아래와 같습니다. 여기에서 natGateways을 0으로 설정하면 private subnet에 있는 streamlit은 외부로 요청을 보낼수 없습니다. 하지만, 여기에서는 Amazon S3에 대한 gateway endpoint와 Bedrock-runtime을 위한 interface endpoint를 설정하였으므로, NAT 없이 Amazon S3와 Bedrock에 대한 요청 및 처리가 가능합니다. 이와같이 메시지 전송 또는 이미지 업로드를 외부 연결없이 endpoint를 이용하여 처리할 수 있습니다.

```java
const vpc = new ec2.Vpc(this, `vpc-for-${projectName}`, {
  vpcName: `vpc-for-${projectName}`,
  maxAzs: 2,
  ipAddresses: ec2.IpAddresses.cidr("10.20.0.0/16"),
  natGateways: 1,
  createInternetGateway: true,
  subnetConfiguration: [
    {
      cidrMask: 24,
      name: `public-subnet-for-${projectName}`,
      subnetType: ec2.SubnetType.PUBLIC
    }, 
    {
      cidrMask: 24,
      name: `private-subnet-for-${projectName}`,
      subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS
    }
  ]
}); 
```

### Reference 

[deploy-streamlit-app](https://github.com/aws-samples/deploy-streamlit-app/tree/main)

[Serverless Streamlit app on AWS with HTTPS](https://kawsaur.medium.com/serverless-streamlit-app-on-aws-with-https-b5e5ff889590)

[frontend_stack.py](https://github.com/kawsark/streamlit-serverless/blob/main/streamlit_serverless_app/frontend_stack.py)

[Running streamlit as a System Service](https://medium.com/@stevenjlm/running-streamlit-on-amazon-ec2-with-https-f20e38fffbe7)

[Amazon Bedrock Knowledge base로 30분 만에 멀티모달 RAG 챗봇 구축하기 실전 가이드](https://aws.amazon.com/ko/blogs/tech/practical-guide-for-bedrock-kb-multimodal-chatbot/)

[CDK-Ubuntu Steamlit](https://github.com/aws-samples/kr-tech-blog-sample-code/tree/main/cdk_bedrock_rag_chatbot/lib)

[Github - Welcome to Streamlit](https://github.com/streamlit/streamlit)

[Streamlit cheat sheet](https://daniellewisdl-streamlit-cheat-sheet-app-ytm9sg.streamlit.app/)

[CDK-Instance](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_ec2.Instance.html)

[CDK-LoadBalancer](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_elasticloadbalancing.LoadBalancer.html)

[CDK-VPC](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_ec2.Vpc.html)

[CDK-VpcEndpoint](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_ec2.VpcEndpoint.html)

[EC2에 간단한 Streamlit 웹 서비스 올리기](https://everenew.tistory.com/317)

[Deploying Streamlit Application on AWS EC2 Instance with NGINX Server](https://medium.com/@borghareshubham510/deploying-streamlit-application-on-aws-ec2-instances-with-nginx-server-d20c83bf150a)

[How to Deploy a Streamlit Application on Amazon Linux EC2](https://towardsaws.com/how-to-deploy-a-streamlit-application-on-amazon-linux-ec2-9a71593b434)

[Running Streamlit on Amazon EC2 with HTTPS](https://medium.com/@stevenjlm/running-streamlit-on-amazon-ec2-with-https-f20e38fffbe7)

[Setting up a VPC Endpoint for yum with AWS CDK](https://dev.to/jhashimoto/setting-up-a-vpc-endpoint-for-yum-with-aws-cdk-3a8o)

[CloudFront - ALB 구성 시 보안 강화 방안](https://everenew.tistory.com/317)

[자습서: Amazon ECS 서비스에 대한 프라이빗 통합을 통해 HTTP API 생성](https://docs.aws.amazon.com/ko_kr/apigateway/latest/developerguide/http-api-private-integration.html)

[API Gateway to ECS Fargate cluster](https://serverlessland.com/patterns/apigw-vpclink-pvt-alb?ref=search)

