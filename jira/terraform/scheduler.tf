# EventBridge Rule for scheduled Lambda execution
resource "aws_cloudwatch_event_rule" "lambda_schedule" {
  name                = "${var.lambda_function_name}-schedule"
  description         = "Trigger Lambda function for JIRA CSV export"
  schedule_expression = var.schedule_expression
  
  tags = var.tags
}

# EventBridge Target
resource "aws_cloudwatch_event_target" "lambda_target" {
  rule      = aws_cloudwatch_event_rule.lambda_schedule.name
  target_id = "LambdaTarget"
  arn       = aws_lambda_function.jira_exporter.arn
}

# Lambda permission for EventBridge
resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.jira_exporter.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.lambda_schedule.arn
}