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

### CloudWatch Configuration

ClouadWatch Agent를 설치합니다.

```text
sudo yum install -y amazon-cloudwatch-agent
```

아래 명령어로 config를 생성합니다.

```text
cat << EOF > /tmp/config.json
{
    "agent":{
        "metrics_collection_interval":60,
        "debug":false
    },
    "metrics": {
        "namespace": "CloudWatch/StreamlitServerMetrics",
        "metrics_collected":{
          "cpu":{
             "resources":[
                "*"
             ],
             "measurement":[
                {
                   "name":"cpu_usage_idle",
                   "rename":"CPU_USAGE_IDLE",
                   "unit":"Percent"
                },
                {
                   "name":"cpu_usage_nice",
                   "unit":"Percent"
                },
                "cpu_usage_guest"
             ],
             "totalcpu":false,
             "metrics_collection_interval":10
          },
          "mem":{
             "measurement":[
                "mem_used",
                "mem_cached",
                "mem_total"
             ],
             "metrics_collection_interval":1
          },          
          "processes":{
             "measurement":[
                "running",
                "sleeping",
                "dead"
             ]
          }
       },
        "append_dimensions":{
            "InstanceId":"\${aws:InstanceId}",
            "ImageId":"\${aws:ImageId}",
            "InstanceType":"\${aws:InstanceType}",
            "AutoScalingGroupName":"\${aws:AutoScalingGroupName}"
        }
    },
    "logs":{
       "logs_collected":{
          "files":{
             "collect_list":[
                {
                   "file_path":"/var/log/application/logs.log",
                   "log_group_name":"llm-streamlit.log",
                   "log_stream_name":"llm-streamlit.log",
                   "timezone":"UTC"
                }
             ]
          }
       }
    }
}
EOF
```

환경 설정을 업데이트 합니다.

```text
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a fetch-config -m ec2 -s -c file:/tmp/config.json
```

상태 확인하는 명령어는 아래와 같습니다.

```text
amazon-cloudwatch-agent-ctl -m ec2 -a status
systemctl status amazon-cloudwatch-agent
ps -ef|grep amazon-cloudwatch-agent
```

문제 발생시 로그 확인하는 방법입니다.

```text
cat /opt/aws/amazon-cloudwatch-agent/logs/configuration-validation.log
cat /opt/aws/amazon-cloudwatch-agent/logs/amazon-cloudwatch-agent.log
```

수동 실행하는 명령어 입니다.

```text
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -m ec2 -a start
```

## Reference 

[서버에 CloudWatch 에이전트 설치 및 실행](https://docs.aws.amazon.com/ko_kr/AmazonCloudWatch/latest/monitoring/install-CloudWatch-Agent-commandline-fleet.html)

[Amazon CloudWatch Agent와 collectd 시작하기](https://aws.amazon.com/ko/blogs/tech/getting-started-with-cloudwatch-agent-and-collectd/)

[How to install Cloudwatch agent and make configuration file](https://medium.com/@farzanajuthi08/how-to-install-cloudwatch-agent-and-make-configuration-file-f314dc1332db)

[[AWS] 리눅스 서버 CloudWatchAgent 설치하기](https://every-up.tistory.com/61)
