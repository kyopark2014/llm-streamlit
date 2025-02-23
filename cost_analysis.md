# Cost Analysis

[AWS Resource Monitor ChatBot](https://github.com/aws-samples/aws-ai-ml-workshop-kr/blob/master/genai/aws-gen-ai-kr/20_applications/15_AWS_Resource_Monitoring_Chatbot/main.ipynb)을 참조하여 비용 분석을 수행합니다.

## 비용 분석

Cost Explorer를 이용하여 지난 한달 간의 데이터를 가져옯니다.

```python
def get_cost_analysis():
  end_date = datetime.now()
  start_date = end_date - timedelta(days=30)
  
  # cost explorer
  ce = boto3.client('ce')

  # service cost
  service_response = ce.get_cost_and_usage(
      TimePeriod={
          'Start': start_date.strftime('%Y-%m-%d'),
          'End': end_date.strftime('%Y-%m-%d')
      },
      Granularity='MONTHLY',
      Metrics=['UnblendedCost'],
      GroupBy=[{'Type': 'DIMENSION', 'Key': 'SERVICE'}]
  )
        
  service_costs = pd.DataFrame([
      {
          'SERVICE': group['Keys'][0],
          'cost': float(group['Metrics']['UnblendedCost']['Amount'])
      }
      for group in service_response['ResultsByTime'][0]['Groups']
  ])
  
  # region cost
  region_response = ce.get_cost_and_usage(
      TimePeriod={
          'Start': start_date.strftime('%Y-%m-%d'),
          'End': end_date.strftime('%Y-%m-%d')
      },
      Granularity='MONTHLY',
      Metrics=['UnblendedCost'],
      GroupBy=[{'Type': 'DIMENSION', 'Key': 'REGION'}]
  )
        
  region_costs = pd.DataFrame([
      {
          'REGION': group['Keys'][0],
          'cost': float(group['Metrics']['UnblendedCost']['Amount'])
      }
      for group in region_response['ResultsByTime'][0]['Groups']
  ])
  
  # Daily Cost
  daily_response = ce.get_cost_and_usage(
      TimePeriod={
          'Start': start_date.strftime('%Y-%m-%d'),
          'End': end_date.strftime('%Y-%m-%d')
      },
      Granularity='DAILY',
      Metrics=['UnblendedCost'],
      GroupBy=[{'Type': 'DIMENSION', 'Key': 'SERVICE'}]
  )
  
  daily_costs = []
  for time_period in daily_response['ResultsByTime']:
      date = time_period['TimePeriod']['Start']
      for group in time_period['Groups']:
          daily_costs.append({
              'date': date,
              'SERVICE': group['Keys'][0],
              'cost': float(group['Metrics']['UnblendedCost']['Amount'])
          })
  
     daily_costs_df = pd.DataFrame(daily_costs)
     
  return {
      'service_costs': service_costs,
      'region_costs': region_costs,
      'daily_costs': daily_costs_df
  }
```

아래와 같이 Service 비용, 리전 비용, 일반 사용 트랜드를 그래프로 그릴 수 있습니다.

```python
def create_cost_visualizations(cost_data):
    visualizations = {}    
    # service cost (pie chart)
    fig_pie = px.pie(
        cost_data['service_costs'],
        values='cost',
        names='SERVICE',
        title='Cost Distribution by Service'
    )
    visualizations['service_pie'] = fig_pie
            
    # daily trend cost (line chart)
    fig_line = px.line(
        cost_data['daily_costs'],
        x='date',
        y='cost',
        color='SERVICE',
        title='Daily Cost Trend by Service'
    )
    visualizations['daily_trend'] = fig_line
    
    # region cost (bar chart)
    fig_bar = px.bar(
        cost_data['region_costs'],
        x='REGION',
        y='cost',
        title='Cost by Region'
    )
    visualizations['region_bar'] = fig_bar
    
    return visualizations
```

비용에 대한 insight를 아래와 같이 추출할 수 있습니다.

```python
def generate_cost_insights():
     cost_data_dict = {
         'service_costs': cost_data['service_costs'].to_dict(orient='records'),
         'region_costs': cost_data['region_costs'].to_dict(orient='records'),
         'daily_costs': cost_data['daily_costs'].to_dict(orient='records') if 'daily_costs' in cost_data else []
     }
    system = (
        "당신의 AWS solutions architect입니다."
        "다음의 Cost Data을 이용하여 user의 질문에 답변합니다."
        "모르는 질문을 받으면 솔직히 모른다고 말합니다."
        "답변의 이유를 풀어서 명확하게 설명합니다."
    )
    human = (
        "다음 AWS 비용 데이터를 분석하여 상세한 인사이트를 제공해주세요:"
        "Cost Data:"
        "{raw_cost}"
        
        "다음 항목들에 대해 분석해주세요:"
        "1. 주요 비용 발생 요인"
        "2. 비정상적인 패턴이나 급격한 비용 증가"
        "3. 비용 최적화가 가능한 영역"
        "4. 전반적인 비용 추세와 향후 예측"
        
        "분석 결과를 다음과 같은 형식으로 제공해주세요:"

        "### 주요 비용 발생 요인"
        "- [구체적인 분석 내용]"

        "### 이상 패턴 분석"
        "- [비정상적인 비용 패턴 설명]"

        "### 최적화 기회"
        "- [구체적인 최적화 방안]"

        "### 비용 추세"
        "- [추세 분석 및 예측]"
    ) 
    prompt = ChatPromptTemplate.from_messages([("system", system), ("human", human)])
    llm = chat.get_chat()
    chain = prompt | llm
    raw_cost = json.dumps(cost_data_dict)
    response = chain.invoke({
       "raw_cost": raw_cost
    })    
    return response.content
```

## 실행 결과



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

이때의 Service Cost에 대한 결과는 아래와 같습니다.

```text
                                SERVICE          cost
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

Region Cost에 대한 결과는 아래와 같습니다.

```text
          REGION        cost
0  ap-northeast-1    0.247742
1  ap-northeast-2    0.294199
2  ap-southeast-1    0.006241
3       eu-west-1    0.000000
4          global    0.774194
5       us-east-1    3.633604
6       us-east-2    0.891332
7       us-west-2  407.909584
```

Daily Cost에 대한 결과는 아래와 같습니다.

```text
           date                        SERVICE          cost
0    2025-01-24             AWS CloudFormation  0.000000e+00
1    2025-01-24     AWS Key Management Service  0.000000e+00
2    2025-01-24                     AWS Lambda  0.000000e+00
3    2025-01-24            AWS Secrets Manager  1.194390e-01
4    2025-01-24                 Amazon Bedrock  3.296282e+00
..          ...                            ...           ...
419  2025-02-22      Amazon OpenSearch Service  1.685505e+01
420  2025-02-22    Amazon Simple Queue Service  7.365600e-03
421  2025-02-22  Amazon Simple Storage Service  6.990000e-08
422  2025-02-22   Amazon Virtual Private Cloud  1.240000e+00
423  2025-02-22               AmazonCloudWatch  2.410714e-01
```
