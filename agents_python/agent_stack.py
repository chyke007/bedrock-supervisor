from typing_extensions import runtime
import os
from aws_cdk import (
    Duration,
    CustomResource,
    Stack,
    aws_s3 as s3,
    aws_s3_deployment as s3_deploy,
    aws_dynamodb as dynamodb,
    RemovalPolicy,
    aws_lambda as lambda_,
    aws_s3_notifications as s3n,
    aws_opensearchserverless as os_serverless,
    aws_iam as iam,
    CfnOutput,
    aws_bedrock as bedrock,
    aws_ec2 as ec2,
    aws_rds as rds,
    aws_secretsmanager as secretsmanager
)
import json
from constructs import Construct
from lambdas.code import Lambdas


class AgentStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # The code that defines your stack goes here
        account_id = os.environ["CDK_DEFAULT_ACCOUNT"]
        region = os.environ["CDK_DEFAULT_REGION"]

        # Load configuration
        with open('./agents_python/config.json', 'r') as config_file:
            config = json.load(config_file)

        # Define parameters
        reservation_agent_name = config['reservationAgentName']
        reservation_agent_alias_name = config['reservationAgentAliasName']

        hr_agent_name = config['hrAgentName']
        hr_agent_alias_name = config['hrAgentAliasName']

        shortlet_agent_name = config['shortletAgentName']
        shortlet_agent_alias_name = config['shortletAgentAliasName']

        ticket_agent_name = config['ticketAgentName']
        ticket_agent_alias_name = config['ticketAgentAliasName']

        supervisor_agent_name = config['supervisorAgentName']
        supervisor_agent_alias_name = config['supervisorAgentAliasName']

        knowledge_base_name = config['knowledgeBaseName']
        knowledge_base_description = config['knowledgeBaseDescription']
        s3_bucket_name = config['s3BucketName']+region+"-"+account_id
        agent_model_id = config['agentModelId']
        agent_model_arn = bedrock.FoundationModel.from_foundation_model_id(
            scope=self,
            _id='AgentModel',
            foundation_model_id=bedrock.FoundationModelIdentifier(agent_model_id)).model_arn

        # Bedrock embedding model Amazon Titan Text v2
        embedding_model_id = config['embeddingModelId']
        embedding_model_arn = bedrock.FoundationModel.from_foundation_model_id(
            scope=self,
            _id='EmbeddingsModel',
            foundation_model_id=bedrock.FoundationModelIdentifier(embedding_model_id)).model_arn

        # Reservation Agent
        reservation_agent_description = config['reservationAgentDescription']
        reservation_agent_instruction = config['reservationAgentInstruction']
        reservation_agent_action_group_description = config['reservationAgentActionGroupDescription']
        reservation_agent_action_group_name = config['reservationAgentActionGroupName']

        # HR Agent
        hr_agent_description = config['hrAgentDescription']
        hr_agent_instruction = config['hrAgentInstruction']
        hr_agent_action_group_description = config['hrAgentActionGroupDescription']
        hr_agent_action_group_name = config['hrAgentActionGroupName']

        # Shortlet Agent
        shortlet_agent_description = config['shortletAgentDescription']
        shortlet_agent_instruction = config['shortletAgentInstruction']
        shortlet_agent_action_group_description = config['shortletAgentActionGroupDescription']
        shortlet_agent_action_group_name = config['shortletAgentActionGroupName']

        # Ticket Agent
        ticket_agent_description = config['ticketAgentDescription']
        ticket_agent_instruction = config['ticketAgentInstruction']
        ticket_agent_action_group_description = config['ticketAgentActionGroupDescription']
        ticket_agent_action_group_name = config['ticketAgentActionGroupName']

        # Supervisor Agent
        supervisor_agent_description = config['supervisorAgentDescription']
        supervisor_agent_instruction = config['supervisorAgentInstruction']

        table_name = config['dynamodbTableName']
        default_database_name = config['auroraDatabaseName']
        schema_table_name = config['auroraSchemaTableName']
        bedrock_user = config['bedrockUser']

        # Role that will be used by the KB
        kb_role = iam.Role(
            scope=self,
            id='AgentKBRole',
            role_name='AmazonBedrockExecutionRoleForKB',
            assumed_by=iam.ServicePrincipal('bedrock.amazonaws.com'))

        # Role that will be used by the Bedrock Agents
        agent_role = iam.Role(
            scope=self,
            id='AgentRole',
            role_name='AmazonBedrockExecutionRoleForAgents-Steakhouse',
            assumed_by=iam.ServicePrincipal('bedrock.amazonaws.com'))

        # Role that will be used by the Supervisor Agent
        supervisor_agent_role = iam.Role(
            scope=self,
            id='SupervisorAgentRole',
            role_name='AmazonBedrockExecutionRoleForSupervisorAgent-Steakhouse',
            assumed_by=iam.ServicePrincipal('bedrock.amazonaws.com'))

        base_lambda_policy = iam.ManagedPolicy.from_aws_managed_policy_name(
            managed_policy_name='service-role/AWSLambdaBasicExecutionRole')

        # Role that will be used by lambda function that Syncs Bedrock KB
        kb_lambda_role = iam.Role(
            scope=self,
            id='KBSyncLambdaRole',
            assumed_by=iam.ServicePrincipal(
                'lambda.amazonaws.com'),
            managed_policies=[base_lambda_policy])

        # Upload the dataset to Amazon S3
        s3Bucket = s3.Bucket(
            self, 'kbs3bucket',
            bucket_name=s3_bucket_name,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            event_bridge_enabled=True)
        bucket_deployment = s3_deploy.BucketDeployment(
            self, "Deploycontent",
            sources=[
                s3_deploy.Source.asset("./dataset")],
            destination_bucket=s3Bucket)

        # Grant permission to S3 to KB Role
        s3Bucket.grant_read(kb_role)

        # Allow KB permission to to invoke FM
        kb_role.add_to_policy(iam.PolicyStatement(
            sid='BedrockInvokeModelStatement',
            effect=iam.Effect.ALLOW,
            resources=[
                embedding_model_arn],
            actions=['bedrock:InvokeModel']))

        # Create a VPC for the Aurora cluster
        vpc = ec2.Vpc(self, "BedrockVPC", max_azs=2, nat_gateways=0)
        security_group = ec2.SecurityGroup(
            self, "SecurityGroup",
            vpc=vpc,
            allow_all_outbound=True
        )

        # Create a secret in Secrets Manager for the database credentials
        database_secret = secretsmanager.Secret(
            self,
            "AuroraDatabaseSecret",
            secret_name="AuroraDbCredentials",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template=json.dumps({"username": bedrock_user}),
                generate_string_key="password",
                exclude_punctuation=True,
            ),
        )

        # Create an Aurora PostgreSQL V2 Serverless cluster
        aurora_cluster = rds.DatabaseCluster(
            self,
            "BedrockAuroraCluster",
            engine=rds.DatabaseClusterEngine.aurora_postgres(
                version=rds.AuroraPostgresEngineVersion.VER_14_10),
            vpc=vpc,
            default_database_name=default_database_name,
            credentials=rds.Credentials.from_secret(database_secret),
            serverless_v2_min_capacity=0.5,
            serverless_v2_max_capacity=1,
            writer=rds.ClusterInstance.serverless_v2(id="AuroraWriter",
                                                     instance_identifier="BedrockAuroraCluster-writer",
                                                     auto_minor_version_upgrade=False,
                                                     allow_major_version_upgrade=False,
                                                     publicly_accessible=False,
                                                     ),
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
            ),
            enable_data_api=True,
            deletion_protection=False,
            removal_policy=RemovalPolicy.DESTROY
        )

        # Associate security to cluster
        aurora_cluster.connections.allow_default_port_from(security_group)

        # Grant necessary permissions to the Bedrock KB role
        aurora_cluster.grant_data_api_access(kb_role)

        Fn = Lambdas(self, "L")

        # Custom Lambda function to setup Postgres as a vector db: schema, table, etc
        pg_setup = CustomResource(self,
                                  "pg_setup",
                                  resource_type="Custom::PGSetup",
                                  service_token=Fn.table_creator.function_arn,
                                  properties=dict(
                                      cluster_arn=aurora_cluster.cluster_arn,
                                      secrets_arn=aurora_cluster.secret.secret_arn,
                                      table_name=schema_table_name,
                                      database_name=default_database_name,
                                      credentials_arn=database_secret.secret_arn,
                                  )
                                  )

        # Explicitly add dependency for the Settig up of Database
        # so pg_setup only gets run after the cluster and database secret setups are completed
        pg_setup.node.add_dependency(aurora_cluster)
        pg_setup.node.add_dependency(database_secret)

        Fn.table_creator.add_to_role_policy(iam.PolicyStatement(actions=["rds-data:ExecuteStatement"],
                                                                resources=[aurora_cluster.cluster_arn]))
        Fn.table_creator.add_to_role_policy(iam.PolicyStatement(actions=["secretsmanager:GetSecretValue"],
                                                                resources=[aurora_cluster.secret.secret_arn]))
        Fn.table_creator.add_to_role_policy(iam.PolicyStatement(actions=["secretsmanager:GetSecretValue"],
                                                                resources=[database_secret.secret_arn]))

        # Add Secrets Manager access to kb_role
        kb_role.add_to_policy(
            iam.PolicyStatement(
                sid="SecretsManagerAccess",
                effect=iam.Effect.ALLOW,
                actions=["secretsmanager:GetSecretValue"],
                resources=[database_secret.secret_arn,
                           database_secret.secret_full_arn],
            )
        )

        # Add RDS DescribeDBClusters permission to kb_role
        kb_role.add_to_policy(
            iam.PolicyStatement(
                sid="RDSExecuteAccessStatement",
                effect=iam.Effect.ALLOW,
                actions=[
                    "rds:DescribeDBClusters"
                ],
                resources=[aurora_cluster.cluster_arn]
            )
        )

        # Create Knowledge Base
        knowledge_base = bedrock.CfnKnowledgeBase(
            scope=self,
            id='KBforAgent',
            name=knowledge_base_name,
            description=knowledge_base_description,
            role_arn=kb_role.role_arn,
            knowledge_base_configuration={'type': 'VECTOR',
                                          'vectorKnowledgeBaseConfiguration': {
                                              'embeddingModelArn': embedding_model_arn}
                                          },
            storage_configuration={
                'type': 'RDS',
                'rdsConfiguration': {
                    "credentialsSecretArn": database_secret.secret_full_arn,
                    'databaseName': default_database_name,
                    'resourceArn': aurora_cluster.cluster_arn,
                    'tableName': f'bedrock_integration.{schema_table_name}',
                    'fieldMapping': {
                        'metadataField': 'metadata',
                        'primaryKeyField': 'id',
                        'textField': 'chunks',
                        'vectorField': 'embedding'
                    }
                }
            }
        )

        # Explicitly add dependency for the creation of Knowledge Base
        # so it only gets created after the cluster and pg_setup setups are completed
        knowledge_base.node.add_dependency(aurora_cluster)
        knowledge_base.node.add_dependency(pg_setup)

        # Create Knowlegebase datasource for provisioned S3 bucket
        datasource = bedrock.CfnDataSource(
            scope=self,
            id=config['knowledgeBaseDataSourceId'],
            name=config['knowledgeBaseDataSourceName'],
            knowledge_base_id=knowledge_base.attr_knowledge_base_id,
            data_source_configuration={'s3Configuration':
                                       {'bucketArn': s3Bucket.bucket_arn},
                                       'type': 'S3'},
            data_deletion_policy='RETAIN')

        # Create Lambda role to access KB
        kb_lambda_role.add_to_policy(iam.PolicyStatement(
            sid='SyncKBPolicy',
            effect=iam.Effect.ALLOW,
            resources=[
                knowledge_base.attr_knowledge_base_arn],
            actions=['bedrock:StartIngestionJob']))

        # Create Lambda function that sync Knowledge base and Datasource(S3)
        kb_sync_lambda = lambda_.Function(
            scope=self,
            id='SyncKB',
            runtime=lambda_.Runtime.PYTHON_3_12,
            code=lambda_.Code.from_asset(
                'lambdas/kb_sync'),
            handler='lambda_function.handler',
            timeout=Duration.seconds(300),
            role=kb_lambda_role,
            environment={'KNOWLEDGE_BASE_ID': knowledge_base.attr_knowledge_base_id,
                         'DATA_SOURCE_ID': datasource.attr_data_source_id}
        )

        # Adds an event trigger to resync KB and Datasource when Datasource contents is updated
        s3Bucket.add_event_notification(s3.EventType.OBJECT_CREATED,
                                        s3n.LambdaDestination(kb_sync_lambda))
        s3Bucket.add_event_notification(s3.EventType.OBJECT_REMOVED,
                                        s3n.LambdaDestination(kb_sync_lambda))

        # Add an explicit dependency on the lambda, so that the bucket
        # deployment is started after the lambda is in place

        bucket_deployment.node.add_dependency(kb_sync_lambda)

        # Create the DynamoDB table
        dynamodbable = dynamodb.Table(self, config['dynamodbTableId'],
                                      partition_key=dynamodb.Attribute(
            name=config['dynamodbPartitionKeyId'],
            type=dynamodb.AttributeType.STRING
        ),
            table_name=table_name,
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY
        )

        agent_role.add_to_policy(iam.PolicyStatement(
            sid='InvokeBedrockLambda',
            effect=iam.Effect.ALLOW,
            resources=[
                agent_model_arn],
            actions=['bedrock:InvokeModel', 'lambda:InvokeFunction']))
        agent_role.add_to_policy(iam.PolicyStatement(
            sid='RetrieveKBStatement',
            effect=iam.Effect.ALLOW,
            resources=[
                knowledge_base.attr_knowledge_base_arn],
            actions=['bedrock:Retrieve']))

        supervisor_agent_role.add_to_policy(iam.PolicyStatement(
            sid='SupervisorInvokeBedrockLambda',
            effect=iam.Effect.ALLOW,
            resources=[
                agent_model_arn],
            actions=['bedrock:InvokeModel', 'lambda:InvokeFunction']))
        supervisor_agent_role.add_to_policy(iam.PolicyStatement(
            sid='SupervisorAgentInvoke',
            effect=iam.Effect.ALLOW,
            resources=["*"],
            actions=['bedrock:*']))

        reservation_action_group_function = lambda_.Function(
            self, "BedrockReservationAgentActionGroupExecutor",
            runtime=lambda_.Runtime.PYTHON_3_12,
            code=lambda_.Code.from_asset(
                'lambdas/actiongroup'),
            handler='reservation_lambda_function.lambda_handler',
            timeout=Duration.seconds(300)
        )

        hr_action_group_function = lambda_.Function(
            self, "BedrockHrAgentActionGroupExecutor",
            runtime=lambda_.Runtime.PYTHON_3_12,
            code=lambda_.Code.from_asset(
                'lambdas/actiongroup'),
            handler='hr_lambda_function.lambda_handler',
            timeout=Duration.seconds(300)
        )

        shortlet_action_group_function = lambda_.Function(
            self, "BedrockShortletAgentActionGroupExecutor",
            runtime=lambda_.Runtime.PYTHON_3_12,
            code=lambda_.Code.from_asset(
                'lambdas/actiongroup'),
            handler='shortlet_lambda_function.lambda_handler',
            timeout=Duration.seconds(300)
        )

        ticket_action_group_function = lambda_.Function(
            self, "BedrockTicketAgentActionGroupExecutor",
            runtime=lambda_.Runtime.PYTHON_3_12,
            code=lambda_.Code.from_asset(
                'lambdas/actiongroup'),
            handler='ticket_lambda_function.lambda_handler',
            timeout=Duration.seconds(300)
        )

        reservation_action_group_function.add_to_role_policy(iam.PolicyStatement(
            sid="UpdateDynamoDB",
            effect=iam.Effect.ALLOW,
            resources=[
                dynamodbable.table_arn],
            actions=['dynamodb:GetItem', 'dynamodb:PutItem', 'dynamodb:DeleteItem']))

        hr_action_group_function.add_to_role_policy(iam.PolicyStatement(
            sid="UpdateDynamoDB",
            effect=iam.Effect.ALLOW,
            resources=[
                dynamodbable.table_arn],
            actions=['dynamodb:GetItem', 'dynamodb:PutItem', 'dynamodb:DeleteItem']))

        shortlet_action_group_function.add_to_role_policy(iam.PolicyStatement(
            sid="UpdateDynamoDB",
            effect=iam.Effect.ALLOW,
            resources=[
                dynamodbable.table_arn],
            actions=['dynamodb:GetItem', 'dynamodb:PutItem', 'dynamodb:DeleteItem']))

        ticket_action_group_function.add_to_role_policy(iam.PolicyStatement(
            sid="UpdateDynamoDB",
            effect=iam.Effect.ALLOW,
            resources=[
                dynamodbable.table_arn],
            actions=['dynamodb:GetItem', 'dynamodb:PutItem', 'dynamodb:DeleteItem']))

        # Create the Reservation Agent
        cfn_reservation_agent = bedrock.CfnAgent(
            self, "ReservationAgent",
            agent_name=reservation_agent_name,
            agent_resource_role_arn=agent_role.role_arn,
            auto_prepare=True,
            description=reservation_agent_description,
            foundation_model=agent_model_id,
            instruction=reservation_agent_instruction,
            idle_session_ttl_in_seconds=1800,
            knowledge_bases=[{'description': knowledge_base_description,
                              'knowledgeBaseId': knowledge_base.attr_knowledge_base_id}],

            action_groups=[bedrock.CfnAgent.AgentActionGroupProperty(
                action_group_name=reservation_agent_action_group_name,
                description=reservation_agent_action_group_description,

                # the properties below are optional
                action_group_executor=bedrock.CfnAgent.ActionGroupExecutorProperty(
                    lambda_=reservation_action_group_function.function_arn
                ),

                function_schema=bedrock.CfnAgent.FunctionSchemaProperty(
                    functions=[bedrock.CfnAgent.FunctionProperty(
                        name=config['reservation_func_getbooking_name'],
                        # the properties below are optional
                        description=config['reservation_func_getbooking_description'],
                        parameters={
                            config['reservation_func_getbooking_id']: bedrock.CfnAgent.ParameterDetailProperty(
                                type="string",

                                # the properties below are optional
                                description="The ID of the booking to retrieve",
                                required=True
                            )
                        }
                    ),
                        # create_booking
                        bedrock.CfnAgent.FunctionProperty(
                        name=config['reservation_func_createbooking_name'],
                        description=config['reservation_func_createbooking_description'],
                        parameters={
                            config['reservation_func_createbooking_date']: bedrock.CfnAgent.ParameterDetailProperty(
                                type="string",
                                description="The date of the booking",
                                required=True
                            ),
                            config['reservation_func_createbooking_person_name']: bedrock.CfnAgent.ParameterDetailProperty(
                                type="string",
                                description="The name of the customer placing a booking",
                                required=True
                            ),
                            config['reservation_func_createbooking_time']: bedrock.CfnAgent.ParameterDetailProperty(
                                type="string",
                                description="The time of the booking",
                                required=True
                            ),
                            config['reservation_func_createbooking_num_guests']: bedrock.CfnAgent.ParameterDetailProperty(
                                type="integer",
                                description="The number of guests in the booking",
                                required=True
                            ),
                            config['reservation_func_createbooking_food']: bedrock.CfnAgent.ParameterDetailProperty(
                                type="string",
                                description="The desired food",
                                required=False
                            )}
                    ),
                        # delete_booking
                        bedrock.CfnAgent.FunctionProperty(
                        name=config['reservation_func_deletebooking_name'],
                        description=config['reservation_func_deletebooking_description'],
                        parameters={
                            config['reservation_func_deletebooking_id']: bedrock.CfnAgent.ParameterDetailProperty(
                                type="string",
                                description="The ID of the booking to delete",
                                required=True
                            )
                        })
                    ]
                ),
            )])

        cfn_reservation_agent_alias = bedrock.CfnAgentAlias(
            self, "ReservationAgentAlias",
            agent_alias_name=reservation_agent_alias_name,
            agent_id=cfn_reservation_agent.attr_agent_id)

        # Create the HR Agent
        cfn_hr_agent = bedrock.CfnAgent(
            self, "HrAgent",
            agent_name=hr_agent_name,
            agent_resource_role_arn=agent_role.role_arn,
            auto_prepare=True,
            description=hr_agent_description,
            foundation_model=agent_model_id,
            instruction=hr_agent_instruction,
            idle_session_ttl_in_seconds=1800,
            knowledge_bases=[{'description': knowledge_base_description,
                              'knowledgeBaseId': knowledge_base.attr_knowledge_base_id}],

            action_groups=[bedrock.CfnAgent.AgentActionGroupProperty(
                action_group_name=hr_agent_action_group_name,
                description=hr_agent_action_group_description,

                # the properties below are optional
                action_group_executor=bedrock.CfnAgent.ActionGroupExecutorProperty(
                    lambda_=hr_action_group_function.function_arn
                ),

                function_schema=bedrock.CfnAgent.FunctionSchemaProperty(
                    functions=[bedrock.CfnAgent.FunctionProperty(
                        name=config['hr_func_getbooking_name'],
                        description=config['hr_func_getbooking_description'],
                        parameters={
                            config['hr_func_getbooking_id']: bedrock.CfnAgent.ParameterDetailProperty(
                                type="string",
                                description="The ID of the booking to retrieve",
                                required=True
                            )
                        }
                    ),
                        # create_booking
                        bedrock.CfnAgent.FunctionProperty(
                        name=config['hr_func_createbooking_name'],
                        description=config['hr_func_createbooking_description'],
                        parameters={
                            config['hr_func_createbooking_staff_name']: bedrock.CfnAgent.ParameterDetailProperty(
                                type="string",
                                description="The name of staff",
                                required=True
                            ),
                            config['hr_func_createbooking_start_date']: bedrock.CfnAgent.ParameterDetailProperty(
                                type="string",
                                description="The start date of the time off",
                                required=True
                            ),
                            config['hr_func_createbooking_end_date']: bedrock.CfnAgent.ParameterDetailProperty(
                                type="string",
                                description="The end date of the time off",
                                required=True
                            ),
                            config['hr_func_createbooking_reason']: bedrock.CfnAgent.ParameterDetailProperty(
                                type="string",
                                description="The reason of the time off",
                                required=True
                            ),
                            config['hr_func_createbooking_detailed_comment']: bedrock.CfnAgent.ParameterDetailProperty(
                                type="string",
                                description="Detailed comment for taking time off",
                                required=False
                            )}
                    ),
                        # delete_booking
                        bedrock.CfnAgent.FunctionProperty(
                        name=config['hr_func_deletebooking_name'],
                        description=config['hr_func_deletebooking_description'],
                        parameters={
                            config['hr_func_deletebooking_id']: bedrock.CfnAgent.ParameterDetailProperty(
                                type="string",
                                description="The ID of the booking to delete",
                                required=True
                            )
                        })
                    ]
                ),
            )])

        cfn_hr_agent_alias = bedrock.CfnAgentAlias(
            self, "HrAgentAlias",
            agent_alias_name=hr_agent_alias_name,
            agent_id=cfn_hr_agent.attr_agent_id)

        # Create the Shortlet Agent
        cfn_shortlet_agent = bedrock.CfnAgent(
            self, "ShortletAgent",
            agent_name=shortlet_agent_name,
            agent_resource_role_arn=agent_role.role_arn,
            auto_prepare=True,
            description=shortlet_agent_description,
            foundation_model=agent_model_id,
            instruction=shortlet_agent_instruction,
            idle_session_ttl_in_seconds=1800,
            knowledge_bases=[{'description': knowledge_base_description,
                              'knowledgeBaseId': knowledge_base.attr_knowledge_base_id}],

            action_groups=[bedrock.CfnAgent.AgentActionGroupProperty(
                action_group_name=shortlet_agent_action_group_name,
                description=shortlet_agent_action_group_description,

                # the properties below are optional
                action_group_executor=bedrock.CfnAgent.ActionGroupExecutorProperty(
                    lambda_=shortlet_action_group_function.function_arn
                ),

                function_schema=bedrock.CfnAgent.FunctionSchemaProperty(
                    functions=[bedrock.CfnAgent.FunctionProperty(
                        name=config['shortlet_func_getbooking_name'],
                        # the properties below are optional
                        description=config['shortlet_func_getbooking_description'],
                        parameters={
                            config['shortlet_func_getbooking_id']: bedrock.CfnAgent.ParameterDetailProperty(
                                type="string",
                                description="The ID of the booking to retrieve",
                                required=True
                            )
                        }
                    ),
                        # create_booking
                        bedrock.CfnAgent.FunctionProperty(
                        name=config['shortlet_func_createbooking_name'],
                        description=config['shortlet_func_createbooking_description'],
                        parameters={
                            config['shortlet_func_createbooking_date']: bedrock.CfnAgent.ParameterDetailProperty(
                                type="string",
                                description="The date of the booking",
                                required=True
                            ),
                            config['shortlet_func_createbooking_person_name']: bedrock.CfnAgent.ParameterDetailProperty(
                                type="string",
                                description="The name of the customer placing a booking",
                                required=True
                            ),
                            config['shortlet_func_createbooking_shortlet_type']: bedrock.CfnAgent.ParameterDetailProperty(
                                type="string",
                                description="Shortlet type",
                                required=True
                            ),
                            config['shortlet_func_createbooking_number_days']: bedrock.CfnAgent.ParameterDetailProperty(
                                type="integer",
                                description="Number of intended days to stay",
                                required=False
                            ),
                            config['shortlet_func_createbooking_num_guests']: bedrock.CfnAgent.ParameterDetailProperty(
                                type="integer",
                                description="The number of guests in the booking",
                                required=True
                            )}
                    ),
                        # delete_booking
                        bedrock.CfnAgent.FunctionProperty(
                        name=config['shortlet_func_deletebooking_name'],
                        description=config['shortlet_func_deletebooking_description'],
                        parameters={
                            config['shortlet_func_deletebooking_id']: bedrock.CfnAgent.ParameterDetailProperty(
                                type="string",
                                description="The ID of the booking to delete",
                                required=True
                            )
                        })
                    ]
                ),
            )])

        cfn_shortlet_agent_alias = bedrock.CfnAgentAlias(
            self, "ShortletAgentAlias",
            agent_alias_name=shortlet_agent_alias_name,
            agent_id=cfn_shortlet_agent.attr_agent_id)

        # Create the Ticket Agent
        cfn_ticket_agent = bedrock.CfnAgent(
            self, "TicketAgent",
            agent_name=ticket_agent_name,
            agent_resource_role_arn=agent_role.role_arn,
            auto_prepare=True,
            description=ticket_agent_description,
            foundation_model=agent_model_id,
            instruction=ticket_agent_instruction,
            idle_session_ttl_in_seconds=1800,
            knowledge_bases=[{'description': knowledge_base_description,
                              'knowledgeBaseId': knowledge_base.attr_knowledge_base_id}],

            action_groups=[bedrock.CfnAgent.AgentActionGroupProperty(
                action_group_name=ticket_agent_action_group_name,
                description=ticket_agent_action_group_description,

                # the properties below are optional
                action_group_executor=bedrock.CfnAgent.ActionGroupExecutorProperty(
                    lambda_=ticket_action_group_function.function_arn
                ),

                function_schema=bedrock.CfnAgent.FunctionSchemaProperty(
                    functions=[bedrock.CfnAgent.FunctionProperty(
                        name=config['ticket_func_getbooking_name'],
                        description=config['ticket_func_getbooking_description'],
                        parameters={
                            config['ticket_func_getbooking_id']: bedrock.CfnAgent.ParameterDetailProperty(
                                type="string",
                                description="The ID of the booking to retrieve",
                                required=True
                            )
                        }
                    ),
                        # create_booking
                        bedrock.CfnAgent.FunctionProperty(
                        name=config['ticket_func_createbooking_name'],
                        description=config['ticket_func_createbooking_description'],
                        parameters={
                            config['ticket_func_createbooking_person_name']: bedrock.CfnAgent.ParameterDetailProperty(
                                type="string",
                                description="The name of customer creating a ticket",
                                required=True
                            ),
                            config['ticket_func_createbooking_incident_date']: bedrock.CfnAgent.ParameterDetailProperty(
                                type="string",
                                description="Date of incident",
                                required=True
                            ),
                            config['ticket_func_createbooking_reason']: bedrock.CfnAgent.ParameterDetailProperty(
                                type="string",
                                description="Reason for creating ticket",
                                required=True
                            )}
                    ),
                        # delete_booking
                        bedrock.CfnAgent.FunctionProperty(
                        name=config['ticket_func_deletebooking_name'],
                        description=config['ticket_func_deletebooking_description'],
                        parameters={
                            config['ticket_func_deletebooking_id']: bedrock.CfnAgent.ParameterDetailProperty(
                                type="string",
                                description="The ID of the booking to delete",
                                required=True
                            )
                        })
                    ]
                ),
            )])

        cfn_ticket_agent_alias = bedrock.CfnAgentAlias(
            self, "TicketAgentAlias",
            agent_alias_name=ticket_agent_alias_name,
            agent_id=cfn_ticket_agent.attr_agent_id)

        # Create supervisor agent
        cfn_supervisor_agent = bedrock.CfnAgent(self, "SupervisorAgent",
                                                agent_name=supervisor_agent_name,
                                                agent_resource_role_arn=supervisor_agent_role.role_arn,
                                                auto_prepare=True,
                                                description=supervisor_agent_description,
                                                foundation_model=agent_model_id,
                                                instruction=supervisor_agent_instruction,
                                                idle_session_ttl_in_seconds=1800,
                                                )
        cfn_supervisor_agent_alias = bedrock.CfnAgentAlias(
            self, "SupervisorAgentAlias",
            agent_alias_name=supervisor_agent_alias_name,
            agent_id=cfn_supervisor_agent.attr_agent_id)

        self.bedrock_supervisor_agent_id = cfn_supervisor_agent.attr_agent_id
        self.bedrock_supervisor_agent_alias_id = cfn_supervisor_agent_alias.attr_agent_alias_id

        lambda_.CfnPermission(
            self,
            "BedrockInvocationPermissionReservation",
            action="lambda:InvokeFunction",
            function_name=reservation_action_group_function.function_name,
            principal="bedrock.amazonaws.com",
            source_arn=cfn_reservation_agent.attr_agent_arn
        )
        lambda_.CfnPermission(
            self,
            "BedrockInvocationPermissionHr",
            action="lambda:InvokeFunction",
            function_name=hr_action_group_function.function_name,
            principal="bedrock.amazonaws.com",
            source_arn=cfn_hr_agent.attr_agent_arn
        )
        lambda_.CfnPermission(
            self,
            "BedrockInvocationPermissionShortlet",
            action="lambda:InvokeFunction",
            function_name=shortlet_action_group_function.function_name,
            principal="bedrock.amazonaws.com",
            source_arn=cfn_shortlet_agent.attr_agent_arn
        )
        lambda_.CfnPermission(
            self,
            "BedrockInvocationPermissionTicket",
            action="lambda:InvokeFunction",
            function_name=ticket_action_group_function.function_name,
            principal="bedrock.amazonaws.com",
            source_arn=cfn_ticket_agent.attr_agent_arn
        )

        # Declare the stack outputs
        CfnOutput(scope=self, id='S3_bucket', value=s3Bucket.bucket_name)
        CfnOutput(scope=self, id='Datasource_id',
                  value=datasource.attr_data_source_id)
        CfnOutput(scope=self, id='Knowedgebase_name',
                  value=knowledge_base.name)
        CfnOutput(scope=self, id='Knowedgebase_id',
                  value=knowledge_base.attr_knowledge_base_id)

        CfnOutput(scope=self, id='Reservation_agent_name',
                  value=cfn_reservation_agent.agent_name)
        CfnOutput(scope=self, id='Reservation_agent_id',
                  value=cfn_reservation_agent.attr_agent_id)
        CfnOutput(scope=self, id='Reservation_agent_alias_id',
                  value=cfn_reservation_agent_alias.attr_agent_alias_id)

        CfnOutput(scope=self, id='Hr_agent_name',
                  value=cfn_hr_agent.agent_name)
        CfnOutput(scope=self, id='Hr_agent_id',
                  value=cfn_hr_agent.attr_agent_id)
        CfnOutput(scope=self, id='Hr_agent_alias_id',
                  value=cfn_hr_agent_alias.attr_agent_alias_id)

        CfnOutput(scope=self, id='Shortlet_agent_name',
                  value=cfn_shortlet_agent.agent_name)
        CfnOutput(scope=self, id='Shortlet_agent_id',
                  value=cfn_shortlet_agent.attr_agent_id)
        CfnOutput(scope=self, id='Shortlet_agent_alias_id',
                  value=cfn_shortlet_agent_alias.attr_agent_alias_id)

        CfnOutput(scope=self, id='Ticket_agent_name',
                  value=cfn_ticket_agent.agent_name)
        CfnOutput(scope=self, id='Ticket_agent_id',
                  value=cfn_ticket_agent.attr_agent_id)
        CfnOutput(scope=self, id='Ticket_agent_alias_id',
                  value=cfn_ticket_agent_alias.attr_agent_alias_id)

        CfnOutput(scope=self, id='Supervisor_agent_name',
                  value=cfn_supervisor_agent.agent_name)
        CfnOutput(scope=self, id='Supervisor_agent_id',
                  value=cfn_supervisor_agent.attr_agent_id)
        CfnOutput(scope=self, id='Supervisor_agent_alias_id',
                  value=cfn_supervisor_agent_alias.attr_agent_alias_id)
