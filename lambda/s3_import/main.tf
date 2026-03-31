# S3 Flywheel Import Lambda Infrastructure
# Imports files from S3 into Flywheel projects via copy-by-reference.
#
# IAM Policy Note:
# This configuration includes S3 and SSM policies for the default buckets
# and parameter paths. If you use different S3 buckets or SSM parameters,
# update the s3_bucket_arns and ssm_parameter_arns variables accordingly.

terraform {
  required_version = ">= 1.0, < 2.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket  = "nacc-terraform-state"
    key     = "lambda/s3-flywheel-import/terraform.tfstate"
    region  = "us-east-1"
    encrypt = true
  }
}

provider "aws" {
  region = var.aws_region
}

# --- IAM Role ---

resource "aws_iam_role" "lambda_role" {
  name = "${var.lambda_function_name}-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = merge(var.tags, {
    Name = "${var.lambda_function_name}-role"
  })
}

# S3 read permissions for source buckets
resource "aws_iam_role_policy" "lambda_s3_policy" {
  name = "${var.lambda_function_name}-s3-policy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = flatten([
          for arn in var.s3_bucket_arns : [
            arn,
            "${arn}/*"
          ]
        ])
      }
    ]
  })
}

# SSM Parameter Store read permissions for API keys
resource "aws_iam_role_policy" "lambda_ssm_policy" {
  name = "${var.lambda_function_name}-ssm-policy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters"
        ]
        Resource = var.ssm_parameter_arns
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "lambda_xray" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/AWSXRayDaemonWriteAccess"
}

# --- CloudWatch ---

resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${var.lambda_function_name}"
  retention_in_days = var.log_retention_days

  tags = merge(var.tags, {
    Name = "${var.lambda_function_name}-logs"
  })
}

# --- Lambda Layer ---

resource "aws_lambda_layer_version" "dependencies" {
  filename            = var.layer_file_path
  source_code_hash    = filebase64sha256(var.layer_file_path)
  layer_name          = var.layer_name
  compatible_runtimes = [var.runtime]
  description         = "Dependencies layer for ${var.lambda_function_name}"

  lifecycle {
    create_before_destroy = true
  }
}

# --- Lambda Function ---

resource "aws_lambda_function" "main" {
  function_name    = var.lambda_function_name
  role             = aws_iam_role.lambda_role.arn
  handler          = var.lambda_handler
  runtime          = var.runtime
  timeout          = var.timeout
  memory_size      = var.memory_size
  filename         = var.lambda_file_path
  source_code_hash = filebase64sha256(var.lambda_file_path)

  layers = [aws_lambda_layer_version.dependencies.arn]

  dynamic "vpc_config" {
    for_each = length(var.subnet_ids) > 0 ? [1] : []
    content {
      security_group_ids = var.security_group_ids
      subnet_ids         = var.subnet_ids
    }
  }

  environment {
    variables = merge(
      {
        POWERTOOLS_SERVICE_NAME = var.lambda_function_name
        LOG_LEVEL               = var.log_level
      },
      var.environment_variables
    )
  }

  tracing_config {
    mode = "Active"
  }

  publish = true

  depends_on = [
    aws_iam_role_policy_attachment.lambda_basic_execution,
    aws_iam_role_policy_attachment.lambda_xray,
    aws_cloudwatch_log_group.lambda_logs,
  ]

  tags = merge(var.tags, {
    Name = var.lambda_function_name
  })
}

# --- Alias ---

resource "aws_lambda_alias" "current" {
  name             = "current"
  description      = "Points to the latest published version"
  function_name    = aws_lambda_function.main.function_name
  function_version = aws_lambda_function.main.version

  lifecycle {
    # Remove ignore_changes to allow Terraform to update the alias
    # when new Lambda versions are published via pants package + apply.
    # If using CodeDeploy or external alias management, re-enable this.
  }
}

# --- CloudWatch Alarms ---

resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = "${var.lambda_function_name}-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Sum"
  threshold           = "0"
  alarm_description   = "Lambda error rate for ${var.lambda_function_name}"
  alarm_actions       = var.alarm_sns_topic_arn != "" ? [var.alarm_sns_topic_arn] : []

  dimensions = {
    FunctionName = aws_lambda_function.main.function_name
  }

  tags = merge(var.tags, {
    Name = "${var.lambda_function_name}-errors"
  })
}

resource "aws_cloudwatch_metric_alarm" "lambda_duration" {
  alarm_name          = "${var.lambda_function_name}-duration"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Average"
  threshold           = "600000" # 10 minutes in milliseconds
  alarm_description   = "Lambda duration for ${var.lambda_function_name}"
  alarm_actions       = var.alarm_sns_topic_arn != "" ? [var.alarm_sns_topic_arn] : []

  dimensions = {
    FunctionName = aws_lambda_function.main.function_name
  }

  tags = merge(var.tags, {
    Name = "${var.lambda_function_name}-duration"
  })
}

# --- Provisioned Concurrency (optional) ---

resource "aws_lambda_provisioned_concurrency_config" "main" {
  count = var.provisioned_concurrency > 0 ? 1 : 0

  function_name                     = aws_lambda_function.main.function_name
  provisioned_concurrent_executions = var.provisioned_concurrency
  qualifier                         = aws_lambda_alias.current.name

  depends_on = [aws_lambda_alias.current]
}
