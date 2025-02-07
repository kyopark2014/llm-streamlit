# Logging

Streamlit을 이용해 소규모로 PoC나 상용을 하는 경우에 logger를 이용한 관리가 필요합니다. 여기서는 CloudWatch를 이용해 로그를 관리하는 방법을 알아봅니다.


## Permission

AWS에서 제공하는 CloudWatchAgentServerPolicy을 사용합니다.

아래는 CDK에서 추가하는 방법입니다.

```java
managedPolicies: [cdk.aws_iam.ManagedPolicy.fromAwsManagedPolicyName('CloudWatchAgentServerPolicy')] 
```

CloudWatchAgentServerPolicy의 세부 내용은 아래와 같습니다.

```java
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "CWACloudWatchServerPermissions",
            "Effect": "Allow",
            "Action": [
                "cloudwatch:PutMetricData",
                "ec2:DescribeVolumes",
                "ec2:DescribeTags",
                "logs:PutLogEvents",
                "logs:PutRetentionPolicy",
                "logs:DescribeLogStreams",
                "logs:DescribeLogGroups",
                "logs:CreateLogStream",
                "logs:CreateLogGroup",
                "xray:PutTraceSegments",
                "xray:PutTelemetryRecords",
                "xray:GetSamplingRules",
                "xray:GetSamplingTargets",
                "xray:GetSamplingStatisticSummaries"
            ],
            "Resource": "*"
        },
        {
            "Sid": "CWASSMServerPermissions",
            "Effect": "Allow",
            "Action": [
                "ssm:GetParameter"
            ],
            "Resource": "arn:aws:ssm:*:*:parameter/AmazonCloudWatch-*"
        }
    ]
}
```


## Reference 

[서버에 CloudWatch 에이전트 설치 및 실행](https://docs.aws.amazon.com/ko_kr/AmazonCloudWatch/latest/monitoring/install-CloudWatch-Agent-commandline-fleet.html)

[Amazon CloudWatch Agent와 collectd 시작하기](https://aws.amazon.com/ko/blogs/tech/getting-started-with-cloudwatch-agent-and-collectd/)

[How to install Cloudwatch agent and make configuration file](https://medium.com/@farzanajuthi08/how-to-install-cloudwatch-agent-and-make-configuration-file-f314dc1332db)
