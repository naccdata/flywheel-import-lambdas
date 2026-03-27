variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "lambda_function_name" {
  description = "Name of the Lambda function"
  type        = string
  default     = "s3-flywheel-import"
}

variable "lambda_handler" {
  description = "Lambda handler"
  type        = string
  default     = "lambda_function.py:lambda_handler"
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
}

variable "memory_size" {
  description = "Lambda memory size in MB"
  type        = number
  default     = 512
}

variable "lambda_file_path" {
  description = "Path to Lambda zip file"
  type        = string
  default     = "dist/lambda/s3_import/src/python/s3_import_lambda/lambda.zip"
}

variable "layer_file_path" {
  description = "Path to layer zip file"
  type        = string
  default     = "dist/lambda/s3_import/src/python/s3_import_lambda/layer.zip"
}

variable "layer_name" {
  description = "Name of the Lambda layer"
  type        = string
  default     = "s3-flywheel-import-deps"
}

variable "environment_variables" {
  description = "Environment variables for Lambda"
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

variable "ssm_parameter_arn" {
  description = "ARN of the SSM parameter storing the Flywheel API key"
  type        = string
}

variable "s3_bucket_arn" {
  description = "ARN of the source S3 bucket"
  type        = string
}

variable "prod_function_version" {
  description = "Function version for production alias"
  type        = string
  default     = "1"
}

variable "provisioned_concurrency" {
  description = "Provisioned concurrency for production"
  type        = number
  default     = 0
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 14
}

variable "tags" {
  description = "Resource tags"
  type        = map(string)
  default     = {}
}
