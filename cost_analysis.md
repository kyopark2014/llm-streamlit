# Cost Analysis

## Reference

## 결과값 예제

### Service Cost

서비스 비용은 아래와 같이 알 수 있습니다.

```python
ce = boto3.client('ce')
service_response = ce.get_cost_and_usage(
   TimePeriod={
       'Start': start_date.strftime('%Y-%m-%d'),
       'End': end_date.strftime('%Y-%m-%d')
   },
   Granularity='MONTHLY',
   Metrics=['UnblendedCost'],
   GroupBy=[{'Type': 'DIMENSION', 'Key': 'SERVICE'}]
)
```

이때의 결과는 아래와 같습니다. 

```java
{
   "GroupDefinitions":[
      {
         "Type":"DIMENSION",
         "Key":"SERVICE"
      }
   ],
   "ResultsByTime":[
      {
         "TimePeriod":{
            "Start":"2025-01-24",
            "End":"2025-02-01"
         },
         "Total":{
            
         },
         "Groups":[
            {
               "Keys":[
                  "AWS Amplify"
               ],
               "Metrics":{
                  "UnblendedCost":{
                     "Amount":"0.000000404",
                     "Unit":"USD"
                  }
               }
            },
            {
               "Keys":[
                  "AWS CloudFormation"
               ],
               "Metrics":{
                  "UnblendedCost":{
                     "Amount":"0",
                     "Unit":"USD"
                  }
               }
            },
            {
               "Keys":[
                  "AWS Key Management Service"
               ],
               "Metrics":{
                  "UnblendedCost":{
                     "Amount":"0",
                     "Unit":"USD"
                  }
               }
            },
            {
               "Keys":[
                  "AWS Lambda"
               ],
               "Metrics":{
                  "UnblendedCost":{
                     "Amount":"0.0004068809",
                     "Unit":"USD"
                  }
               }
            },
            {
               "Keys":[
                  "AWS Secrets Manager"
               ],
               "Metrics":{
                  "UnblendedCost":{
                     "Amount":"1.0289848416",
                     "Unit":"USD"
                  }
               }
            },
            {
               "Keys":[
                  "AWS Step Functions"
               ],
               "Metrics":{
                  "UnblendedCost":{
                     "Amount":"0",
                     "Unit":"USD"
                  }
               }
            },
            {
               "Keys":[
                  "Amazon Bedrock"
               ],
               "Metrics":{
                  "UnblendedCost":{
                     "Amount":"12.743910805",
                     "Unit":"USD"
                  }
               }
            },
            {
               "Keys":[
                  "Amazon CloudFront"
               ],
               "Metrics":{
                  "UnblendedCost":{
                     "Amount":"0.0062566867",
                     "Unit":"USD"
                  }
               }
            },
            {
               "Keys":[
                  "Amazon EC2 Container Registry (ECR)"
               ],
               "Metrics":{
                  "UnblendedCost":{
                     "Amount":"0.8438748417",
                     "Unit":"USD"
                  }
               }
            },
            {
               "Keys":[
                  "EC2 - Other"
               ],
               "Metrics":{
                  "UnblendedCost":{
                     "Amount":"31.8662854621",
                     "Unit":"USD"
                  }
               }
            },
            {
               "Keys":[
                  "Amazon Elastic Compute Cloud - Compute"
               ],
               "Metrics":{
                  "UnblendedCost":{
                     "Amount":"84.7393299404",
                     "Unit":"USD"
                  }
               }
            },
            {
               "Keys":[
                  "Amazon Elastic Load Balancing"
               ],
               "Metrics":{
                  "UnblendedCost":{
                     "Amount":"14.2265036121",
                     "Unit":"USD"
                  }
               }
            },
            {
               "Keys":[
                  "Amazon OpenSearch Service"
               ],
               "Metrics":{
                  "UnblendedCost":{
                     "Amount":"250.6457589762",
                     "Unit":"USD"
                  }
               }
            },
            {
               "Keys":[
                  "Amazon Simple Queue Service"
               ],
               "Metrics":{
                  "UnblendedCost":{
                     "Amount":"0.110466",
                     "Unit":"USD"
                  }
               }
            },
            {
               "Keys":[
                  "Amazon Simple Storage Service"
               ],
               "Metrics":{
                  "UnblendedCost":{
                     "Amount":"0.0131739687",
                     "Unit":"USD"
                  }
               }
            },
            {
               "Keys":[
                  "Amazon Virtual Private Cloud"
               ],
               "Metrics":{
                  "UnblendedCost":{
                     "Amount":"14.7142018378",
                     "Unit":"USD"
                  }
               }
            },
            {
               "Keys":[
                  "AmazonCloudWatch"
               ],
               "Metrics":{
                  "UnblendedCost":{
                     "Amount":"2.8177419537",
                     "Unit":"USD"
                  }
               }
            }
         ],
         "Estimated":false
      },
      {
         "TimePeriod":{
            "Start":"2025-02-01",
            "End":"2025-02-23"
         },
         "Total":{
            
         },
         "Groups":[
            {
               "Keys":[
                  "AWS Amplify"
               ],
               "Metrics":{
                  "UnblendedCost":{
                     "Amount":"0.0757989027",
                     "Unit":"USD"
                  }
               }
            },
            {
               "Keys":[
                  "AWS CloudFormation"
               ],
               "Metrics":{
                  "UnblendedCost":{
                     "Amount":"0",
                     "Unit":"USD"
                  }
               }
            },
            {
               "Keys":[
                  "AWS Key Management Service"
               ],
               "Metrics":{
                  "UnblendedCost":{
                     "Amount":"0",
                     "Unit":"USD"
                  }
               }
            },
            {
               "Keys":[
                  "AWS Lambda"
               ],
               "Metrics":{
                  "UnblendedCost":{
                     "Amount":"0.0018137456",
                     "Unit":"USD"
                  }
               }
            },
            {
               "Keys":[
                  "AWS Secrets Manager"
               ],
               "Metrics":{
                  "UnblendedCost":{
                     "Amount":"3.9456726351",
                     "Unit":"USD"
                  }
               }
            },
            {
               "Keys":[
                  "Amazon Bedrock"
               ],
               "Metrics":{
                  "UnblendedCost":{
                     "Amount":"83.928766",
                     "Unit":"USD"
                  }
               }
            },
            {
               "Keys":[
                  "Amazon CloudFront"
               ],
               "Metrics":{
                  "UnblendedCost":{
                     "Amount":"0.0081417347",
                     "Unit":"USD"
                  }
               }
            },
            {
               "Keys":[
                  "Amazon EC2 Container Registry (ECR)"
               ],
               "Metrics":{
                  "UnblendedCost":{
                     "Amount":"2.6635078515",
                     "Unit":"USD"
                  }
               }
            },
            {
               "Keys":[
                  "EC2 - Other"
               ],
               "Metrics":{
                  "UnblendedCost":{
                     "Amount":"105.4861137783",
                     "Unit":"USD"
                  }
               }
            },
            {
               "Keys":[
                  "Amazon Elastic Compute Cloud - Compute"
               ],
               "Metrics":{
                  "UnblendedCost":{
                     "Amount":"231.247917215",
                     "Unit":"USD"
                  }
               }
            },
            {
               "Keys":[
                  "Amazon Elastic Load Balancing"
               ],
               "Metrics":{
                  "UnblendedCost":{
                     "Amount":"46.5538047393",
                     "Unit":"USD"
                  }
               }
            },
            {
               "Keys":[
                  "Amazon OpenSearch Service"
               ],
               "Metrics":{
                  "UnblendedCost":{
                     "Amount":"687.3228778414",
                     "Unit":"USD"
                  }
               }
            },
            {
               "Keys":[
                  "Amazon Simple Queue Service"
               ],
               "Metrics":{
                  "UnblendedCost":{
                     "Amount":"0.1145403",
                     "Unit":"USD"
                  }
               }
            },
            {
               "Keys":[
                  "Amazon Simple Storage Service"
               ],
               "Metrics":{
                  "UnblendedCost":{
                     "Amount":"0.0194256162",
                     "Unit":"USD"
                  }
               }
            },
            {
               "Keys":[
                  "Amazon Virtual Private Cloud"
               ],
               "Metrics":{
                  "UnblendedCost":{
                     "Amount":"52.1573418335",
                     "Unit":"USD"
                  }
               }
            },
            {
               "Keys":[
                  "AmazonCloudWatch"
               ],
               "Metrics":{
                  "UnblendedCost":{
                     "Amount":"11.6147322516",
                     "Unit":"USD"
                  }
               }
            }
         ],
         "Estimated":true
      }
   ],
   "DimensionValueAttributes":[
      
   ],
   "ResponseMetadata":{
      "RequestId":"6ffd11ce-8728-465c-bd41-74ff9205c24c",
      "HTTPStatusCode":200,
      "HTTPHeaders":{
         "date":"Sun, 23 Feb 2025 06:31:38 GMT",
         "content-type":"application/x-amz-json-1.1",
         "content-length":"3645",
         "connection":"keep-alive",
         "x-amzn-requestid":"6ffd11ce-8728-465c-bd41-74ff9205c24c",
         "cache-control":"no-cache"
      },
      "RetryAttempts":0
   }
}
```

서비스 비용은 아래와 같이 panda를 통해 정리합니다.

```python
service_costs = pd.DataFrame([
   {
       'SERVICE': group['Keys'][0],
       'cost': float(group['Metrics']['UnblendedCost']['Amount'])
   }
   for group in service_response['ResultsByTime'][0]['Groups']
])
logger.info(f"Service Costs: {service_costs}")
```

이때의 결과는 아래와 같습니다.

```text
Service Costs:                                    SERVICE          cost
0                              AWS Amplify  4.040000e-07
1                       AWS CloudFormation  0.000000e+00
2               AWS Key Management Service  0.000000e+00
3                               AWS Lambda  4.068809e-04
4                      AWS Secrets Manager  1.028985e+00
5                       AWS Step Functions  0.000000e+00
6                           Amazon Bedrock  1.274391e+01
7                        Amazon CloudFront  6.256687e-03
8      Amazon EC2 Container Registry (ECR)  8.438748e-01
9                              EC2 - Other  3.186629e+01
10  Amazon Elastic Compute Cloud - Compute  8.473933e+01
11           Amazon Elastic Load Balancing  1.422650e+01
12               Amazon OpenSearch Service  2.506458e+02
13             Amazon Simple Queue Service  1.104660e-01
14           Amazon Simple Storage Service  1.317397e-02
15            Amazon Virtual Private Cloud  1.471420e+01
16                        AmazonCloudWatch  2.817742e+00
```


