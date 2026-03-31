# Outputs for S3 Flywheel Import Lambda Infrastructure

output "lambda_function_arn" {
  description = "ARN of the Lambda function"
  value       = aws_lambda_function.main.arn
}

output "lambda_function_name" {
  description = "Name of the Lambda function"
  value       = aws_lambda_function.main.function_name
}

output "lambda_invoke_arn" {
  description = "Invoke ARN of the Lambda function"
  value       = aws_lambda_function.main.invoke_arn
}

output "lambda_function_version" {
  description = "Latest published version of the Lambda function"
  value       = aws_lambda_function.main.version
}

output "lambda_alias_arn" {
  description = "ARN of the current alias (stable endpoint)"
  value       = aws_lambda_alias.current.arn
}

output "lambda_role_arn" {
  description = "ARN of the Lambda execution role"
  value       = aws_iam_role.lambda_role.arn
}

output "lambda_role_name" {
  description = "Name of the Lambda execution role"
  value       = aws_iam_role.lambda_role.name
}

output "layer_arn" {
  description = "ARN of the Lambda layer"
  value       = aws_lambda_layer_version.dependencies.arn
}

output "cloudwatch_log_group_name" {
  description = "Name of the CloudWatch log group"
  value       = aws_cloudwatch_log_group.lambda_logs.name
}

output "lambda_configuration" {
  description = "Lambda function configuration summary"
  value = {
    function_name = aws_lambda_function.main.function_name
    runtime       = aws_lambda_function.main.runtime
    handler       = aws_lambda_function.main.handler
    timeout       = aws_lambda_function.main.timeout
    memory_size   = aws_lambda_function.main.memory_size
  }
}
