# Streamlit을 이용한 GenAI Application 배포 및 활용

<p align="left">
    <a href="https://hits.seeyoufarm.com"><img src="https://hits.seeyoufarm.com/api/count/incr/badge.svg?url=https%3A%2F%2Fgithub.com%2Fkyopark2014%2Fllm-streamlit&count_bg=%2379C83D&title_bg=%23555555&icon=&icon_color=%23E7E7E7&title=hits&edge_flat=false)](https://hits.seeyoufarm.com"/></a>
    <img alt="License" src="https://img.shields.io/badge/LICENSE-MIT-green">
</p>



여기서는 Streamlit을 이용해 개발한 application을 쉽게 배포하고 안전할게 활용할 수 있는 방법에 대해 설명합니다. AWS CDK를 통해 한번에 배포가 가능하고, 수정된 소스를 쉽게 반영할 수 있습니다. 또한, ALB - EC2의 구조를 가지고 있으므로 필요하다면 scale out도 지원합니다. Streamlit이 설치되는 EC2의 OS는 EKS/ECS와 같은 컨테이너 서비스에 주로 사용되는 Amazon Linux를 base하여, 추후 상용으로 전환할때 수고를 줄일 수 있습니다. 

## System Architecture 

이때의 Architecture는 아래와 같습니다. 여기서에서는 Streamlit이 설치된 EC2는 private subnet에 둬서 안전하게 관리합니다. Amazon S3는 Gateway Endpoint를 이용하여 연결하고 Bedrock은 Private link를 이용하여 연결하였으므로 EC2의 트래픽은 외부로 나가지 않고 AWS 내부에서 처리가 됩니다. 인터넷 및 날씨의 검색 API는 외부 서비스 공급자의 API를 이용하므로 NAT를 이용하여 연결하였습니다.

<img width="800" alt="image" src="https://github.com/user-attachments/assets/6de1c8a9-c8d3-485f-b836-97a24d635b0d" />

### CDK로 배포 환경 구현

EC2를 아래와 같이 정의합니다. 

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

EC2의 userdata는 아래와 같이 설정합니다.

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
  `runuser -l ec2-user -c 'export projectName=${projectName}'`,
  `runuser -l ec2-user -c 'export accountId=${accountId}'`,      
  `runuser -l ec2-user -c 'export region=${region}'`,
  `runuser -l ec2-user -c 'export bucketName=${bucketName}'`,
  'systemctl enable streamlit.service',
  'systemctl start streamlit'
];
userData.addCommands(...commands);
```

ALB와 EC2를 연결합니다.

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

const listener = alb.addListener(`HttpListener-for-${projectName}`, {   
  port: 80,
  protocol: elbv2.ApplicationProtocol.HTTP,      
}); 

listener.addTargets(`WebEc2Target-for-${projectName}`, {
  targets,
  protocol: elbv2.ApplicationProtocol.HTTP,
  port: targetPort
}) 
```

Agentic workflow (tool use)의 workflow는 아래와 같이 구현할 수 있습니다.

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


### 활용 방법

EC2는 Private Subnet에 있으므로 SSL로 접속할 수 없습니다. 따라서, [Console-EC2](https://us-west-2.console.aws.amazon.com/ec2/home?region=us-west-2#Instances:)에 접속하여 "app-for-llm-streamlit"를 선택한 후에 Connect에서 sesseion manager를 선택하여 접속합니다. 

Github에서 app에 대한 코드를 업데이트 하였다면, session manager에 접속하여 아래 명령어로 업데이트 합니다. 

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

이때 사용한 이미지는 아래와 같습니다. 이 이미지는 ReAct와 CoT를 비교하고 있습니다.

![image](https://github.com/user-attachments/assets/ec22508a-1569-49a1-a6fb-6442bc972d2a)

이때의 결과는 아래와 같습니다. 입력한 메시지에 맞는 의미를 그림파일에서 찾고 아래와 같이 먼저 결과를 제시합니다. 실제 LLM이 인식한 표를 아래와 같이 확인할 수 있습니다.

![image](https://github.com/user-attachments/assets/39fb2235-c6ef-42e0-8f43-f158cb088db4)



### (참고) HTTPS로 streamlit 연결 방안

ALB에 인증서를 추가해서 https로 연결을 제공할 수 있습니다. 참고로, CloudFront와 API Gateway(http api)를 이용하여 https 방식의 streamlit 구현을 시도하였으나, CloudFront와 API Gateway (http api)는 websocket을 지원하지 않으므로 구현이 안되는것을 확인하였습니다. 

- [Serverless Streamlit app on AWS with HTTPS](https://kawsaur.medium.com/serverless-streamlit-app-on-aws-with-https-b5e5ff889590)

- [frontend_stack.py](https://github.com/kawsark/streamlit-serverless/blob/main/streamlit_serverless_app/frontend_stack.py)

- [Running streamlit as a System Service](https://medium.com/@stevenjlm/running-streamlit-on-amazon-ec2-with-https-f20e38fffbe7)

#### Reference 

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
