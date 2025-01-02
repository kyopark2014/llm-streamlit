import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as elbv2 from 'aws-cdk-lib/aws-elasticloadbalancingv2';
import * as elbv2_tg from 'aws-cdk-lib/aws-elasticloadbalancingv2-targets'
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import * as s3 from 'aws-cdk-lib/aws-s3';

const projectName = `llm-streamlit`; 
const region = process.env.CDK_DEFAULT_REGION;    
const accountId = process.env.CDK_DEFAULT_ACCOUNT;
const targetPort = 8080;
const bucketName = `storage-for-${projectName}-${accountId}-${region}`; 
import * as cloudFront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';

export class CdkLlmStreamlitStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // s3 
    const s3Bucket = new s3.Bucket(this, `storage-${projectName}`,{
      bucketName: bucketName,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      publicReadAccess: false,
      versioned: false,
      cors: [
        {
          allowedHeaders: ['*'],
          allowedMethods: [
            s3.HttpMethods.POST,
            s3.HttpMethods.PUT,
          ],
          allowedOrigins: ['*'],
        },
      ],
    });
    new cdk.CfnOutput(this, 'bucketName', {
      value: s3Bucket.bucketName,
      description: 'The nmae of bucket',
    });
    
    // EC2 Role
    const ec2Role = new iam.Role(this, `role-ec2-for-${projectName}`, {
      roleName: `role-ec2-for-${projectName}-${region}`,
      assumedBy: new iam.CompositePrincipal(
        new iam.ServicePrincipal("ec2.amazonaws.com"),
        new iam.ServicePrincipal("bedrock.amazonaws.com"),
      )
    });

    const secreatManagerPolicy = new iam.PolicyStatement({  
      resources: ['*'],
      actions: ['secretsmanager:GetSecretValue'],
    });       
    ec2Role.attachInlinePolicy( // for isengard
      new iam.Policy(this, `secret-manager-policy-ec2-for-${projectName}`, {
        statements: [secreatManagerPolicy],
      }),
    );  

    // Secret
    const weatherApiSecret = new secretsmanager.Secret(this, `weather-api-secret-for-${projectName}`, {
      description: 'secret for weather api key', // openweathermap
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      secretName: `openweathermap-${projectName}`,
      secretObjectValue: {
        project_name: cdk.SecretValue.unsafePlainText(projectName),
        weather_api_key: cdk.SecretValue.unsafePlainText(''),
      },
    });
    weatherApiSecret.grantRead(ec2Role) 

    const langsmithApiSecret = new secretsmanager.Secret(this, `weather-langsmith-secret-for-${projectName}`, {
      description: 'secret for lamgsmith api key', // openweathermap
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      secretName: `langsmithapikey-${projectName}`,
      secretObjectValue: {
        langchain_project: cdk.SecretValue.unsafePlainText(projectName),
        langsmith_api_key: cdk.SecretValue.unsafePlainText(''),
      }, 
    });
    langsmithApiSecret.grantRead(ec2Role) 

    const tavilyApiSecret = new secretsmanager.Secret(this, `weather-tavily-secret-for-${projectName}`, {
      description: 'secret for lamgsmith api key', // openweathermap
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      secretName: `tavilyapikey-${projectName}`,
      secretObjectValue: {
        project_name: cdk.SecretValue.unsafePlainText(projectName),
        tavily_api_key: cdk.SecretValue.unsafePlainText(''),
      },
    });
    tavilyApiSecret.grantRead(ec2Role) 

    const pvrePolicy = new iam.PolicyStatement({  
      resources: ['*'],
      actions: ['ssm:*', 'ssmmessages:*', 'ec2messages:*', 'tag:*'],
    });       
    ec2Role.attachInlinePolicy( // for isengard
      new iam.Policy(this, `pvre-policy-ec2-for-${projectName}`, {
        statements: [pvrePolicy],
      }),
    );  

    // Bedrock Policy
    const BedrockPolicy = new iam.PolicyStatement({  
      resources: ['*'],
      actions: ['bedrock:*'],
    });        
    ec2Role.attachInlinePolicy( // add bedrock policy
      new iam.Policy(this, `bedrock-policy-ec2-for-${projectName}`, {
        statements: [BedrockPolicy],
      }),
    );     

    const ec2Policy = new iam.PolicyStatement({  
      resources: ['arn:aws:ec2:*:*:instance/*'],
      actions: ['ec2:*'],
    });
    ec2Role.attachInlinePolicy( // add bedrock policy
      new iam.Policy(this, `ec2-policy-for-${projectName}`, {
        statements: [ec2Policy],
      }),
    );

    // VPC
    const vpc = new ec2.Vpc(this, `vpc-for-${projectName}`, {
      vpcName: `vpc-for-${projectName}`,
      maxAzs: 2,
      ipAddresses: ec2.IpAddresses.cidr("10.20.0.0/16"),
      natGateways: 0,
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

    // S3 endpoint
    const s3BucketAcessPoint = vpc.addGatewayEndpoint(`s3Endpoint-${projectName}`, {
      service: ec2.GatewayVpcEndpointAwsService.S3,
    });

    s3BucketAcessPoint.addToPolicy(
      new iam.PolicyStatement({
        principals: [new iam.AnyPrincipal()],
        actions: ['s3:*'],
        resources: ['*'],
      }),
    ); 

    // Bedrock endpoint
    new ec2.InterfaceVpcEndpoint(this, `VPC Endpoint-${projectName}`, {
      privateDnsEnabled: true,
      vpc: vpc,
      service: new ec2.InterfaceVpcEndpointService('com.amazonaws.us-west-2.bedrock', 443),
      subnets: {
        subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS
      }
    });

    // EC2 Security Group
    const ec2Sg = new ec2.SecurityGroup(this, `ec2-sg-for-${projectName}`,
      {
        vpc: vpc,
        allowAllOutbound: true,
        description: "Security group for ec2",
        securityGroupName: `ec2-sg-for-${projectName}`,
      }
    );
    // ec2Sg.addIngressRule(
    //   ec2.Peer.anyIpv4(),
    //   ec2.Port.tcp(22),
    //   'SSH',
    // );
    // ec2Sg.addIngressRule(
    //   ec2.Peer.anyIpv4(),
    //   ec2.Port.tcp(80),
    //   'HTTP',
    // );

    const userData = ec2.UserData.forLinux();

    const environment = {
      "projectName": projectName,
      "accountId": accountId,
      "region": region,
      "s3_arn": s3Bucket.bucketArn
    }    
    new cdk.CfnOutput(this, `environment-for-${projectName}`, {
      value: JSON.stringify(environment),
      description: `environment-${projectName}`,
      exportName: `environment-${projectName}`
    });

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

[theme]
base="dark
EOF"`,
      `json='${JSON.stringify(environment)}' && echo "$json">/home/config.json`,      
      `runuser -l ec2-user -c 'cd && git clone https://github.com/kyopark2014/${projectName}'`,
      `runuser -l ec2-user -c 'pip install streamlit streamlit_chat watchtower'`,        
      `runuser -l ec2-user -c 'pip install boto3 langchain_aws langchain langchain_community langgraph'`,
      `runuser -l ec2-user -c 'pip install beautifulsoup4 pytz tavily-python'`,
      'systemctl enable streamlit.service',
      'systemctl start streamlit'
    ];
    userData.addCommands(...commands);
    
    // EC2 instance
    const appInstance = new ec2.Instance(this, `app-for-${projectName}`, {
      instanceName: `app-for-${projectName}`,
      instanceType: new ec2.InstanceType('t2.small'), // m5.large
      // instanceType: ec2.InstanceType.of(ec2.InstanceClass.T2, ec2.InstanceSize.SMALL),
      machineImage: new ec2.AmazonLinuxImage({
        generation: ec2.AmazonLinuxGeneration.AMAZON_LINUX_2023
      }),
      // machineImage: ec2.MachineImage.latestAmazonLinux2023(),
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
    s3Bucket.grantReadWrite(appInstance);
    appInstance.applyRemovalPolicy(cdk.RemovalPolicy.DESTROY);

    // ALB Target
    const targets: elbv2_tg.InstanceTarget[] = new Array();
    targets.push(new elbv2_tg.InstanceTarget(appInstance)); 

    // ALB SG
    const albSg = new ec2.SecurityGroup(this, `alb-sg-for-${projectName}`, {
      vpc: vpc,
      allowAllOutbound: true,
      securityGroupName: `alb-sg-for-${projectName}`,
      description: 'security group for alb'
    });
    ec2Sg.connections.allowFrom(albSg, ec2.Port.tcp(targetPort), 'allow traffic from alb') // alb -> ec2
    
    // ALB
    const alb = new elbv2.ApplicationLoadBalancer(this, `alb-for-${projectName}`, {
      internetFacing: true,
      vpc: vpc,
      vpcSubnets: {
        subnets: vpc.publicSubnets
      },
      securityGroup: albSg,
      loadBalancerName: `alb-for-${projectName}`
    });
    alb.applyRemovalPolicy(cdk.RemovalPolicy.DESTROY); 

    new cdk.CfnOutput(this, `albUrl-for-${projectName}`, {
      value: `http://${alb.loadBalancerDnsName}/`,
      description: `albUrl-${projectName}`,
      exportName: `albUrl-${projectName}`
    });    

    // CloudFront
    const CUSTOM_HEADER_NAME = "X-Custom-Header"
    const CUSTOM_HEADER_VALUE = `${projectName}_12dab15e4s31` // Temporary value
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
    new cdk.CfnOutput(this, `distributionDomainName-for-${projectName}`, {
      value: 'https://'+distribution.domainName,
      description: 'The domain name of the Distribution'
    });    

    // ALB Listener
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
  }
}
