from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_iam as iam,
    CfnOutput,
)

from constructs import Construct

class StreamlitStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, bedrock_agent_id, bedrock_agent_alias_id, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Creating the VPC for the ECS service
        vpc = ec2.Vpc(self, "ECSVPC",
            ip_addresses=ec2.IpAddresses.cidr("10.0.0.0/16"),
            max_azs=2,
            nat_gateway_subnets=None,
            subnet_configuration=[ec2.SubnetConfiguration(name="public",subnet_type=ec2.SubnetType.PUBLIC,cidr_mask=24)]
        )
       

        # Build Dockerfile from local folder and push to ECR
        image = ecs.ContainerImage.from_asset("streamlit")

        # Use the ApplicationLoadBalancedFargateService L3 construct to place the application behind an ALB
        load_balanced_service = ecs_patterns.ApplicationLoadBalancedFargateService(self, "StreamlitService",
            vpc=vpc,
            cpu=1024,
            memory_limit_mib=4096,
            desired_count=1,
            public_load_balancer=True,
            assign_public_ip=True,
            enable_execute_command=True,
            load_balancer_name=("streamlit-lb"),
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
               image=image, 
               container_port=8501,
               environment={
                  "STREAMLIT_SERVER_RUN_ON_SAVE": "true",
                  "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false",
                  "STREAMLIT_THEME_BASE": "light",
                  "BEDROCK_AGENT_ID": bedrock_agent_id,
                  "BEDROCK_AGENT_ALIAS_ID": bedrock_agent_alias_id,
                  "AWS_REGION": self.region,
                  "AWS_ACCOUNT_ID": self.account,
              }
            )
        )   

        load_balanced_service.task_definition.add_to_task_role_policy(
            statement=iam.PolicyStatement(
                actions=[
                    "bedrock:*"
                ],
                resources=["*"]
            )
        )

        load_balanced_service.task_definition.add_to_task_role_policy(
            statement=iam.PolicyStatement(
                actions=[
                "cloudwatch:DescribeAlarmsForMetric",
                "cloudwatch:GetMetricData",
                "ec2:*",
                "s3:*"
                ],
                resources=["*"]
            )
        )            

        # Declare the stack outputs
        domain_name = "http://" + load_balanced_service.load_balancer.load_balancer_dns_name
        CfnOutput(scope=self, id='load_balancer_dns_name', value=domain_name)
        