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
from constructs import Construct


class InfrastructureStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # The code that defines your stack goes here

        # example resource
        # queue = sqs.Queue(
        #     self, "InfrastructureQueue",
        #     visibility_timeout=Duration.seconds(300),
        # )

        # Create Lambda function
        lambda_function = _lambda.Function(
            self,
            "ZonalStatsFunction",
            runtime=_lambda.Runtime.PYTHON_3_11,
            code=_lambda.Code.from_asset("../src"),
            handler="app.main.handler",
            environment={
                "PYTHONPATH": "/var/task",
            },
            timeout=Duration.seconds(300),
            memory_size=1024,
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
            ),
        )

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
