from aws_cdk import (
    CfnOutput,
    Duration,
    Stack,
)
from aws_cdk import (
    aws_apigateway as apigw,
)
from aws_cdk import (
    aws_iam as iam,
)
from aws_cdk import (
    aws_lambda as _lambda,
)
from aws_cdk import (
    aws_logs as logs,
)
from constructs import Construct


class InfrastructureStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create CloudWatch Logs role for API Gateway
        cloudwatch_role = iam.Role(
            self,
            "ApiGatewayCloudWatchRole",
            assumed_by=iam.ServicePrincipal("apigateway.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AmazonAPIGatewayPushToCloudWatchLogs"
                )
            ],
        )

        # Create Lambda layer only if deploy_layer context is True
        lambda_layer = None
        if self.node.try_get_context("deploy_layer"):
            lambda_layer = _lambda.LayerVersion(
                self,
                "ZonalStatsLayer",
                code=_lambda.Code.from_asset("lambda_layer/lambda_layer.zip"),
                compatible_runtimes=[_lambda.Runtime.PYTHON_3_11],
                description="Layer containing all dependencies for zonal statistics API",
            )

        # Create Lambda function
        lambda_function = _lambda.Function(
            self,
            "ZonalStatsFunction",
            runtime=_lambda.Runtime.PYTHON_3_11,
            code=_lambda.Code.from_asset("../src"),
            handler="app.main.handler",
            environment={
                "PYTHONPATH": "/var/task:/opt/python",
            },
            timeout=Duration.seconds(300),
            memory_size=10240,
            layers=[lambda_layer] if lambda_layer else [],
        )

        # Create API Gateway
        api = apigw.RestApi(
            self,
            "ZonalStatsApi",
            rest_api_name="Zonal Statistics API",
            description="API for calculating zonal statistics from raster data",
            deploy_options=apigw.StageOptions(
                stage_name="v1",
                logging_level=apigw.MethodLoggingLevel.INFO,
                access_log_destination=apigw.LogGroupLogDestination(
                    logs.LogGroup(
                        self,
                        "ApiGatewayAccessLogs",
                        log_group_name=f"/aws/apigateway/{construct_id}/access-logs",
                        retention=logs.RetentionDays.ONE_MONTH,
                    )
                ),
                access_log_format=apigw.AccessLogFormat.json_with_standard_fields(
                    caller=True,
                    http_method=True,
                    ip=True,
                    protocol=True,
                    request_time=True,
                    resource_path=True,
                    response_length=True,
                    status=True,
                    user=True,
                ),
            ),
            cloud_watch_role=True,
        )

        # Create usage plan with rate limiting
        usage_plan = api.add_usage_plan(
            "ZonalStatsUsagePlan",
            name="ZonalStatsUsagePlan",
            throttle=apigw.ThrottleSettings(burst_limit=10, rate_limit=1),
        )

        # Associate the usage plan with the API stage
        usage_plan.add_api_stage(stage=api.deployment_stage)

        # Create API Gateway integration with Lambda
        integration = apigw.LambdaIntegration(
            lambda_function,
            request_templates={"application/json": '{ "statusCode": "200" }'},
        )

        # Add proxy resource to handle all paths
        api.root.add_proxy(
            default_integration=integration,
            any_method=True,
        )

        # Output the API endpoint
        CfnOutput(
            self,
            "ApiEndpoint",
            value=api.url,
            description="API Gateway endpoint URL",
        )
