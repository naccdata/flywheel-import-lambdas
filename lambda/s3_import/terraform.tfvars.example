# Example Terraform variables for S3 Flywheel Import Lambda
# Copy to terraform.tfvars and customize as needed.

aws_region = "us-west-2"
log_level  = "INFO"

# Lambda configuration
lambda_function_name = "s3-flywheel-import"
timeout              = 900 # 15 minutes
memory_size          = 512
log_retention_days   = 30

# --- S3 Bucket Access ---
# List all S3 bucket ARNs the Lambda needs to read from.
# Update this list when adding or changing source buckets.
s3_bucket_arns = [
  "arn:aws:s3:::naccquickaccess",
  "arn:aws:s3:::loni-table-data"
]

# --- SSM Parameter Access ---
# List all SSM parameter ARNs for Flywheel API keys.
# Update this list when using different API key paths or accounts.
ssm_parameter_arns = [
  "arn:aws:ssm:us-west-2:090173369068:parameter/prod/flywheel/gearbot/apikey"
]

# Additional environment variables passed to the Lambda
environment_variables = {
  # Add any extra env vars here, e.g.:
  # FLYWHEEL_SSM_KEY = "/prod/flywheel/gearbot/apikey"
}

# Monitoring (optional)
# alarm_sns_topic_arn = "arn:aws:sns:us-west-2:090173369068:alerts"

# VPC configuration (optional, leave empty if not needed)
# subnet_ids         = ["subnet-abc123"]
# security_group_ids = ["sg-abc123"]

# Provisioned concurrency (optional, 0 to disable)
provisioned_concurrency = 0

# Tags
tags = {
  Project   = "flywheel-import"
  Owner     = "data-engineering"
  ManagedBy = "terraform"
}
