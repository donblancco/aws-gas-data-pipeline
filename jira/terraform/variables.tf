variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "s3_bucket_name" {
  description = "S3 bucket name for JIRA exports"
  type        = string
  default     = "your-company-exports"
}

variable "s3_prefix" {
  description = "S3 prefix for JIRA exports"
  type        = string
  default     = "project-exports/"
}

variable "lambda_function_name" {
  description = "Lambda function name"
  type        = string
  default     = "jira-csv-exporter"
}

variable "jira_url" {
  description = "JIRA URL"
  type        = string
  sensitive   = true
}

variable "jira_username" {
  description = "JIRA username"
  type        = string
  sensitive   = true
}

variable "jira_api_token" {
  description = "JIRA API token"
  type        = string
  sensitive   = true
}

variable "schedule_expression" {
  description = "CloudWatch Events schedule expression"
  type        = string
  default     = "cron(0 19 * * ? *)"  # 毎日19時UTC（JST朝4時）
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"
}

variable "tags" {
  description = "Tags to be applied to resources"
  type        = map(string)
  default = {
    Project     = "JIRA-S3-Export"
    Environment = "dev"
    ManagedBy   = "Terraform"
  }
}