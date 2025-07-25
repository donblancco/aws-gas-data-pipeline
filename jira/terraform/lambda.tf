# Create deployment package for Lambda function
data "archive_file" "lambda_zip" {
  type        = "zip"
  output_path = "${path.module}/lambda_function.zip"
  
  source {
    content  = file("${path.module}/../lambda_jira_exporter.py")
    filename = "lambda_jira_exporter.py"
  }
  
  source {
    content  = file("${path.module}/../requirements.txt")
    filename = "requirements.txt"
  }
}

# Lambda function
resource "aws_lambda_function" "jira_exporter" {
  filename         = data.archive_file.lambda_zip.output_path
  function_name    = var.lambda_function_name
  role            = aws_iam_role.lambda_execution_role.arn
  handler         = "lambda_jira_exporter.lambda_handler"
  runtime         = "python3.9"
  timeout         = 300
  memory_size     = 512
  
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  environment {
    variables = {
      JIRA_URL       = var.jira_url
      JIRA_USERNAME  = var.jira_username
      JIRA_API_TOKEN = var.jira_api_token
      S3_BUCKET      = aws_s3_bucket.jira_exports.bucket
      S3_PREFIX      = var.s3_prefix
    }
  }

  tags = var.tags
}

# CloudWatch Log Group for Lambda
resource "aws_cloudwatch_log_group" "lambda_log_group" {
  name              = "/aws/lambda/${var.lambda_function_name}"
  retention_in_days = 14
  tags              = var.tags
}