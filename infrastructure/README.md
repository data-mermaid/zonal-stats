# Zonal Statistics Infrastructure

This directory contains the AWS CDK infrastructure code for deploying the Zonal Statistics API. The infrastructure includes:

- AWS Lambda function for processing zonal statistics
- API Gateway for HTTP endpoints
- Lambda Layer for dependencies

## Prerequisites

1. Install AWS CDK:

```bash
npm install -g aws-cdk
```

2. Install Python dependencies:

```bash
pip install -r requirements.txt
```

3. Configure AWS credentials:

```bash
aws configure
```

## Creating the Lambda Layer

The Lambda layer contains all the Python dependencies required by the Lambda function. To create the layer:

1. Navigate to the infrastructure directory:

```bash
cd infrastructure
```

2. Make the build script executable:

```bash
chmod +x build_layer.sh
```

3. Run the build script:

```bash
./build_layer.sh
```

This script will:

- Create a temporary directory for building the layer
- Install all required dependencies into this directory
- Create a zip file containing the dependencies
- Clean up temporary files

The resulting `lambda_layer.zip` will be created in the `lambda_layer` directory and will be used by CDK during deployment.

## Project Structure

```
infrastructure/
├── app.py                 # CDK app entry point
├── infrastructure/        # CDK stack definition
│   └── infrastructure_stack.py
├── lambda_layer/         # Lambda layer dependencies
    └── lambda_layer.zip
```

## Deployment Steps

1. Create and activate a Python virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Bootstrap your AWS environment (first time only):

```bash
cdk bootstrap
```

4. Deploy the stack:

```bash
cdk deploy
```

## Testing the Lambda Function

When testing the Lambda function directly (not through API Gateway), use the following payload format:

```json
{
  "version": "2.0",
  "routeKey": "POST /api/v1/calculate",
  "rawPath": "/api/v1/calculate",
  "rawQueryString": "",
  "headers": {
    "Content-Type": "application/json"
  },
  "requestContext": {
    "http": {
      "method": "POST",
      "path": "/api/v1/calculate",
      "sourceIp": "127.0.0.1",
      "protocol": "HTTP/1.1"
    },
    "timeEpoch": 1715168181315
  },
  "body": "{\"aoi\":{\"type\":\"Polygon\",\"coordinates\":[[[-4.147933860088441,52.654908861230659],[-4.033329348900527,52.653715064239123],[-4.018207920341011,52.5681596131787],[-4.082672957884212,52.554629913941234],[-4.143556604452791,52.552640252288668],[-4.147933860088441,52.654908861230659]]]},\"stats\":[\"count\",\"mean\",\"min\",\"max\"],\"image\":{\"url\":\"https://geodowd-test-data.s3.eu-west-1.amazonaws.com/cogs/random_global_raster_cog_001.tif\"}}"
}
```

## Infrastructure Components

### Lambda Function

- Runtime: Python 3.11
- Memory: 2048 MB
- Timeout: 300 seconds
- Handler: app.main.handler

### API Gateway

- REST API
- Stage: v1
- Logging: INFO level
- CORS enabled

### Lambda Layer

Contains all Python dependencies required by the Lambda function.

## Cleanup

To destroy the infrastructure:

```bash
cdk destroy
```

## Troubleshooting

1. If you encounter deployment issues, check the CloudFormation console for detailed error messages.

2. For Lambda function issues:
   - Check CloudWatch Logs for the Lambda function
   - Verify the Lambda layer contains all required dependencies
   - Ensure the Lambda function has appropriate IAM permissions

3. For API Gateway issues:
   - Verify the API Gateway integration with Lambda
   - Check API Gateway logs in CloudWatch
   - Test the API endpoint using the provided test payload format
