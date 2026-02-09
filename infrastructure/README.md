# Zonal Statistics Infrastructure

This directory contains the AWS CDK infrastructure code for deploying the Zonal Statistics API. The infrastructure includes:

- AWS Lambda function (Docker container image)
- API Gateway for HTTP endpoints
- ECR repository for the Lambda container image (managed by CDK)

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

4. Docker must be installed and running (CDK builds the Lambda image locally).

## Project Structure

```
infrastructure/               # <-- You should be in THIS directory for all deployment commands
├── app.py                   # CDK app entry point
├── cdk.json                 # CDK configuration
├── requirements.txt         # CDK Python dependencies (separate from main app)
└── infrastructure/          # Python package with CDK stack definition
    └── infrastructure_stack.py
```

## Deployment Steps

**Working directory:** All commands below should be run from `infrastructure/` (the top-level infrastructure directory).

**About virtual environments:**
- The project root has a venv for the FastAPI app (created with `uv venv` and `uv sync`)
- This infrastructure directory needs its own **separate** venv for AWS CDK deployment tools
- These are two different environments for two different purposes

1. Create and activate a CDK deployment virtual environment:

```bash
# If you don't already have a .venv in the infrastructure/ directory:
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

2. Install CDK dependencies in this venv:

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

CDK will automatically build the Docker image from `Dockerfile.lambda`, push it to ECR, and update the Lambda function.

## Local Development

From the **project root** directory:

```bash
# Run local API server with hot-reload
docker compose up api

# Test Lambda locally with the Runtime Interface Emulator
docker compose up lambda
curl -X POST "http://localhost:9000/2015-03-31/functions/function/invocations" \
  -d '{"httpMethod": "GET", "path": "/docs"}'
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

- Runtime: Docker container image (Python 3.11)
- Memory: 10240 MB
- Timeout: 300 seconds
- Handler: app.main.handler

### API Gateway

- REST API
- Stage: v1
- Logging: INFO level
- CORS enabled

## Cleanup

To destroy the infrastructure:

```bash
cdk destroy
```

## Troubleshooting

1. If you encounter deployment issues, check the CloudFormation console for detailed error messages.

2. For Lambda function issues:
   - Check CloudWatch Logs for the Lambda function
   - Ensure Docker is running when deploying (CDK builds the image locally)
   - Ensure the Lambda function has appropriate IAM permissions

3. For API Gateway issues:
   - Verify the API Gateway integration with Lambda
   - Check API Gateway logs in CloudWatch
   - Test the API endpoint using the provided test payload format
