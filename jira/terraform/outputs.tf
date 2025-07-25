output "s3_bucket_name" {
  description = "Name of the S3 bucket"
  value       = aws_s3_bucket.jira_exports.bucket
}

output "s3_bucket_arn" {
  description = "ARN of the S3 bucket"
  value       = aws_s3_bucket.jira_exports.arn
}

output "lambda_function_name" {
  description = "Name of the Lambda function"
  value       = aws_lambda_function.jira_exporter.function_name
}

output "lambda_function_arn" {
  description = "ARN of the Lambda function"
  value       = aws_lambda_function.jira_exporter.arn
}

output "lambda_log_group_name" {
  description = "Name of the CloudWatch Log Group"
  value       = aws_cloudwatch_log_group.lambda_log_group.name
}

output "eventbridge_rule_name" {
  description = "Name of the EventBridge rule"
  value       = aws_cloudwatch_event_rule.lambda_schedule.name
}

output "csv_public_url" {
  description = "Public URL for the latest CSV file"
  value       = "https://${aws_s3_bucket.jira_exports.bucket}.s3.amazonaws.com/${var.s3_prefix}latest.csv"
}

output "s3_daily_prefix" {
  description = "S3 prefix for daily exports"
  value       = "${var.s3_prefix}daily/"
}

