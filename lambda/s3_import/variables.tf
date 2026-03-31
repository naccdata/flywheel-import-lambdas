# Variables for S3 Flywheel Import Lambda Infrastructure

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-west-2"
}

variable "lambda_function_name" {
  description = "Name of the Lambda function"
  type        = string
  default     = "s3-flywheel-import"
}

variable "lambda_handler" {
  description = "Lambda handler in Python module notation"
  type        = string
  default     = "s3_import_lambda.lambda_function.lambda_handler"
}

variable "runtime" {
  description = "Lambda runtime"
  type        = string
  default     = "python3.12"
}

variable "timeout" {
  description = "Lambda timeout in seconds"
  type        = number
  default     = 900

  validation {
    condition     = var.timeout >= 60 && var.timeout <= 900
    error_message = "Lambda timeout must be between 60 and 900 seconds."
  }
}

variable "memory_size" {
  description = "Lambda memory size in MB"
  type        = number
  default     = 512

  validation {
    condition     = var.memory_size >= 128 && var.memory_size <= 10240
    error_message = "Lambda memory size must be between 128 and 10240 MB."
  }
}

variable "lambda_file_path" {
  description = "Path to Lambda zip file (relative to this terraform directory)"
  type        = string
  default     = "../../dist/lambda.s3_import.src.python.s3_import_lambda/lambda.zip"
}

variable "layer_file_path" {
  description = "Path to layer zip file (relative to this terraform directory)"
  type        = string
  default     = "../../dist/lambda.s3_import.src.python.s3_import_lambda/layer.zip"
}

variable "layer_name" {
  description = "Name of the Lambda layer"
  type        = string
  default     = "s3-flywheel-import-deps"
}

variable "log_level" {
  description = "Logging level for Lambda function"
  type        = string
  default     = "INFO"

  validation {
    condition     = contains(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], var.log_level)
    error_message = "Log level must be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL."
  }
}

# --- IAM / Resource Access ---
# Update these variables when deploying with different S3 buckets or SSM parameters.

variable "s3_bucket_arns" {
  description = "List of S3 bucket ARNs the Lambda needs read access to. Update when using different source buckets."
  type        = list(string)
  default = [
    "arn:aws:s3:::naccquickaccess",
    "arn:aws:s3:::loni-table-data"
  ]

  validation {
    condition = alltrue([
      for arn in var.s3_bucket_arns : can(regex("^arn:aws:s3:::", arn))
    ])
    error_message = "All S3 bucket ARNs must be valid (arn:aws:s3:::bucket-name)."
  }
}

variable "ssm_parameter_arns" {
  description = "List of SSM parameter ARNs the Lambda needs read access to (e.g., Flywheel API keys). Update when using different parameters."
  type        = list(string)
  default = [
    "arn:aws:ssm:us-west-2:090173369068:parameter/prod/flywheel/gearbot/apikey"
  ]

  validation {
    condition = alltrue([
      for arn in var.ssm_parameter_arns : can(regex("^arn:aws:ssm:", arn))
    ])
    error_message = "All SSM parameter ARNs must be valid SSM ARNs."
  }
}

variable "environment_variables" {
  description = "Additional environment variables for Lambda"
  type        = map(string)
  default     = {}
}

variable "security_group_ids" {
  description = "Security group IDs for VPC configuration"
  type        = list(string)
  default     = []
}

variable "subnet_ids" {
  description = "Subnet IDs for VPC configuration"
  type        = list(string)
  default     = []
}

variable "provisioned_concurrency" {
  description = "Provisioned concurrency for the current alias"
  type        = number
  default     = 0
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30

  validation {
    condition = contains([
      1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 3653
    ], var.log_retention_days)
    error_message = "Log retention days must be a valid CloudWatch retention period."
  }
}

variable "alarm_sns_topic_arn" {
  description = "SNS topic ARN for CloudWatch alarms (optional, empty to disable)"
  type        = string
  default     = ""

  validation {
    condition     = var.alarm_sns_topic_arn == "" || can(regex("^arn:aws:sns:[a-z0-9-]+:[0-9]+:[a-zA-Z0-9-_]+$", var.alarm_sns_topic_arn))
    error_message = "SNS topic ARN must be a valid ARN or empty string."
  }
}

variable "tags" {
  description = "Resource tags"
  type        = map(string)
  default     = {}
}
