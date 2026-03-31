# Deployment Guide

This guide covers deploying the S3 Flywheel Import Lambda using Terraform.

## Overview

The deployment process:

1. Build Lambda packages with Pants
2. Configure variables in `terraform.tfvars`
3. Deploy infrastructure with Terraform

## Prerequisites

- AWS CLI configured with appropriate credentials
- Terraform >= 1.0 installed (available in dev container)
- Pants build system set up
- Access to the `nacc-terraform-state` S3 bucket for Terraform state

## Build Process

### Building Lambda Packages

```bash
# Ensure dev container is running
./bin/start-devcontainer.sh

# Build the s3_import lambda (function code + dependencies layer)
./bin/exec-in-devcontainer.sh pants package lambda/s3_import/src/python/s3_import_lambda::

# Verify build artifacts
ls -la dist/lambda.s3_import.src.python.s3_import_lambda/
```

### Build Artifacts

```text
dist/lambda.s3_import.src.python.s3_import_lambda/
├── lambda.zip   # Lambda function code
└── layer.zip    # Dependencies layer (boto3, pydantic, fw-client, powertools)
```

## Terraform Configuration

All Terraform files live in `lambda/s3_import/`:

| File | Purpose |
| ---- | ------- |
| `main.tf` | Resources: IAM role, Lambda function, layer, alias, alarms |
| `variables.tf` | Input variables with validation |
| `outputs.tf` | Exported values (ARNs, names) |
| `terraform.tfvars.example` | Example variable values — copy to `terraform.tfvars` and customize |

### Remote State

Terraform state is stored in S3:

- Bucket: `nacc-terraform-state`
- Key: `lambda/s3-flywheel-import/terraform.tfstate`
- Region: `us-east-1`
- Encryption: enabled

## IAM Policy Management

The Terraform configuration creates an IAM execution role with inline policies for the specific AWS resources the Lambda needs. These policies are managed via Terraform variables so they can be updated without modifying `main.tf`.

### Included Policies

The Lambda role includes four policy attachments:

| Policy | Source | Purpose |
| ------ | ------ | ------- |
| `AWSLambdaBasicExecutionRole` | AWS managed | CloudWatch Logs write access |
| `AWSXRayDaemonWriteAccess` | AWS managed | X-Ray tracing |
| S3 read policy | Inline, from `s3_bucket_arns` | `s3:GetObject`, `s3:ListBucket` on source buckets |
| SSM read policy | Inline, from `ssm_parameter_arns` | `ssm:GetParameter`, `ssm:GetParameters` for API keys |

### Default Resource ARNs

The default variable values grant access to:

**S3 buckets:**

- `arn:aws:s3:::naccquickaccess`
- `arn:aws:s3:::loni-table-data`

**SSM parameters:**

- `arn:aws:ssm:us-west-2:090173369068:parameter/prod/flywheel/gearbot/apikey`

### Updating Policies for Different Scenarios

When deploying with different S3 buckets or SSM parameters, override the variables in your `terraform.tfvars`. You do not need to edit `main.tf`.

**Adding a new source bucket:**

```hcl
s3_bucket_arns = [
  "arn:aws:s3:::naccquickaccess",
  "arn:aws:s3:::loni-table-data",
  "arn:aws:s3:::my-new-source-bucket"
]
```

**Using a different SSM parameter path (e.g., a different Flywheel instance):**

```hcl
ssm_parameter_arns = [
  "arn:aws:ssm:us-west-2:090173369068:parameter/dev/flywheel/gearbot/apikey"
]
```

**Using multiple SSM parameters:**

```hcl
ssm_parameter_arns = [
  "arn:aws:ssm:us-west-2:090173369068:parameter/prod/flywheel/gearbot/apikey",
  "arn:aws:ssm:us-west-2:090173369068:parameter/prod/flywheel/other-bot/apikey"
]
```

**Using a wildcard for SSM (all parameters under a path):**

```hcl
ssm_parameter_arns = [
  "arn:aws:ssm:us-west-2:090173369068:parameter/prod/flywheel/*"
]
```

### Validation

Both variables include validation rules:

- `s3_bucket_arns` — each entry must start with `arn:aws:s3:::`
- `ssm_parameter_arns` — each entry must start with `arn:aws:ssm:`

Terraform will reject invalid ARN formats at plan time.

### S3 Policy Details

The S3 inline policy grants both bucket-level and object-level access for each ARN in `s3_bucket_arns`:

```hcl
Resource = flatten([
  for arn in var.s3_bucket_arns : [
    arn,        # bucket-level (for ListBucket)
    "${arn}/*"  # object-level (for GetObject)
  ]
])
```

Listing objects and reading files are both covered. Write access is intentionally excluded — the Lambda only reads from S3.

## Deployment Workflow

### First-Time Setup

```bash
# Start dev container
./bin/start-devcontainer.sh

# Build packages
./bin/exec-in-devcontainer.sh pants package lambda/s3_import/src/python/s3_import_lambda::

# Initialize Terraform (from the lambda/s3_import directory)
cd lambda/s3_import
terraform init

# Copy and edit the example tfvars
cp terraform.tfvars.example terraform.tfvars
```

### Deploy

```bash
# Build
./bin/exec-in-devcontainer.sh pants package lambda/s3_import/src/python/s3_import_lambda::

# Plan (review changes)
cd lambda/s3_import
terraform plan -var-file="terraform.tfvars"

# Apply
terraform apply -var-file="terraform.tfvars"
```

### Updating Code Only

If only the Lambda function code changed (no infrastructure changes), the same workflow applies. Terraform detects the changed `source_code_hash` and updates the function and publishes a new version.

### Lambda Alias

The deployment creates a `current` alias that points to the latest published version. Use this as a stable invocation endpoint.

## Monitoring

The Terraform configuration creates two CloudWatch alarms:

| Alarm | Metric | Threshold |
| ----- | ------ | --------- |
| `{name}-errors` | Error count | > 0 over 2 consecutive 5-min periods |
| `{name}-duration` | Average duration | > 10 minutes (600,000 ms) |

Alarms route to the SNS topic specified in `alarm_sns_topic_arn`. If empty, alarms are created but have no notification target.

X-Ray tracing is enabled by default (`Active` mode).

## Rollback

```bash
# Get the previous version number
aws lambda list-versions-by-function \
    --function-name s3-flywheel-import \
    --query 'Versions[-2].Version' \
    --output text

# Update the alias to point to the previous version
aws lambda update-alias \
    --function-name s3-flywheel-import \
    --name current \
    --function-version <PREVIOUS_VERSION>
```

For a full infrastructure rollback, use `terraform apply` with the previous code artifacts in `dist/`.

## Outputs

After `terraform apply`, these outputs are available:

| Output | Description |
| ------ | ----------- |
| `lambda_function_arn` | Lambda function ARN |
| `lambda_function_name` | Lambda function name |
| `lambda_invoke_arn` | Invoke ARN (for API Gateway integration) |
| `lambda_function_version` | Latest published version |
| `lambda_alias_arn` | Current alias ARN (stable endpoint) |
| `lambda_role_arn` | IAM execution role ARN |
| `lambda_role_name` | IAM execution role name |
| `layer_arn` | Dependencies layer ARN |
| `cloudwatch_log_group_name` | CloudWatch log group name |
| `lambda_configuration` | Configuration summary object |
