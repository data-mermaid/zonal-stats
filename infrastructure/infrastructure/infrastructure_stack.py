import hashlib
import pathlib

from aws_cdk import (
    CfnOutput,
    Duration,
    Stack,
)
from aws_cdk import (
    aws_apigateway as apigw,
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

        # CloudWatch role is automatically created by cloud_watch_role=True below

        # Create Lambda function from Docker image
        lambda_function = _lambda.DockerImageFunction(
            self,
            "ZonalStatsFunction",
            code=_lambda.DockerImageCode.from_image_asset(
                "../", file="Dockerfile.lambda"
            ),
            timeout=Duration.seconds(300),
            memory_size=10240,
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

        # Force API Gateway redeployment when this stack file changes
        stack_hash = hashlib.sha256(
            pathlib.Path(__file__).read_bytes()
        ).hexdigest()[:16]
        api.latest_deployment.add_to_logical_id(stack_hash)

        # Create API Gateway integration with Lambda
        integration = apigw.LambdaIntegration(
            lambda_function,
            proxy=True,  # Enable proxy integration
        )

        # Add root method to handle the root path "/"
        api.root.add_method("ANY", integration)

        # Add proxy resource to handle all other paths
        proxy = api.root.add_proxy(
            default_integration=integration,
            any_method=True,
        )

        # Enable CORS for the root resource
        api.root.add_cors_preflight(
            allow_origins=apigw.Cors.ALL_ORIGINS,
            allow_methods=apigw.Cors.ALL_METHODS,
            allow_headers=apigw.Cors.DEFAULT_HEADERS,
            max_age=Duration.days(1),
        )

        # Enable CORS for the proxy resource
        proxy.add_cors_preflight(
            allow_origins=apigw.Cors.ALL_ORIGINS,
            allow_methods=apigw.Cors.ALL_METHODS,
            allow_headers=apigw.Cors.DEFAULT_HEADERS,
            max_age=Duration.days(1),
        )

        # Output the API endpoint
        CfnOutput(
            self,
            "ApiEndpoint",
            value=api.url,
            description="API Gateway endpoint URL",
        )
