# Streamlit을 이용한 Application 배포

<p align="left">
    <a href="https://hits.seeyoufarm.com"><img src="https://hits.seeyoufarm.com/api/count/incr/badge.svg?url=https%3A%2F%2Fgithub.com%2Fkyopark2014%2Fllm-streamlit&count_bg=%2379C83D&title_bg=%23555555&icon=&icon_color=%23E7E7E7&title=hits&edge_flat=false)](https://hits.seeyoufarm.com"/></a>
    <img alt="License" src="https://img.shields.io/badge/LICENSE-MIT-green">
</p>



여기서는 Streamlit을 https를 이용하기 위하여 CloudFront - ALB - EC2로 구성하는 방법을 설명합니다. 

## System Architecture 

이때의 Architecture는 아래와 같습니다. 여기서에서는 Streamlit이 설치된 EC2는 private subnet에 둬서 안전하게 관리합니다. S3는 Gateway Endpoint를 이용하여 연결합니다. Bedrock도 Private link를 이용해 연결하여야 하지만 여기서는 multi-region을 사용하므로 편의상 NAT를 이용하여 연결하였습니다.

<img width="800" alt="image" src="https://github.com/user-attachments/assets/6b428aac-5e6d-47c6-91ba-5aa37e4e37f0" />


### CDK 구현 코드

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
  //'yum install nginx -y',
  //'service nginx start',
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

EC2에는 [Console-EC2](https://us-west-2.console.aws.amazon.com/ec2/home?region=us-west-2#Instances:)에 접속하여 "app-for-llm-streamlit"를 선택한 후에 Connect - Sesseion Manager를 선택하여 접속합니다. github에서 app을 업데이트 한 경우에 아래 명령어로 업데이트 합니다. 

```text
sudo runuser -l ec2-user -c 'cd /home/ec2-user/llm-streamlit && git pull'
```

Streamlit의 동작 상태는 아래 명령어를 이용해 확인합니다.

```text
sudo systemctl status streamlit -l
```



## Streamlit

### Streamlit 실행 

아래와 같이 streamlit을 실행합니다.

```text
streamlit run application/app.py
```

github 코드를 EC2에 업데이트 할 때에는 아래 명령어를 활용합니다.

```text
sudo runuser -l ec2-user -c 'cd /home/ec2-user/llm-streamlit && git pull'
```

Streamlit 재실행을 위한 명령어는 아래와 같습니다.

```text
sudo systemctl stop streamlit
sudo systemctl start streamlit
sudo systemctl status streamlit -l
```



## 직접 실습 해보기

### 사전 준비 사항

이 솔루션을 사용하기 위해서는 사전에 아래와 같은 준비가 되어야 합니다.

- [AWS Account 생성](https://repost.aws/ko/knowledge-center/create-and-activate-aws-account)에 따라 계정을 준비합니다.

### CDK를 이용한 인프라 설치

본 실습에서는 us-west-2 리전을 사용합니다. [인프라 설치](./deployment.md)에 따라 CDK로 인프라 설치를 진행합니다. 

## 실행결과






### htts로 streamlit 연결의 어려움

ALB에 인증서를 추가해서 https 지원이 가능하나, 여기에서는 CloudFront와 API Gateway(http api)를 이용하여 https 방식의 streamlit 구현을 시도하였습니다. 그러나, CloudFront와 API Gateway (http api)는 websocket을 지원하지 않으므로 구현이 안되는것을 확인하였습니다. 

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
