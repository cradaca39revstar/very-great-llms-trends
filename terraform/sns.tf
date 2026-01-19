# SNS Topics for Beauty Products Data Lake Notifications

# Main alerts topic (defined in cloudwatch.tf, but additional subscriptions can be added here)

# Optional: SMS subscription
# Uncomment if SMS notifications are needed
# resource "aws_sns_topic_subscription" "sms_alert" {
#   topic_arn = aws_sns_topic.alerts.arn
#   protocol  = "sms"
#   endpoint  = var.alert_phone_number
# }

# Optional: Slack webhook integration via Lambda
# Uncomment and configure if Slack notifications are needed
# resource "aws_sns_topic_subscription" "slack_alert" {
#   topic_arn = aws_sns_topic.alerts.arn
#   protocol  = "lambda"
#   endpoint  = aws_lambda_function.slack_notifier.arn
# }

# Output SNS topic ARN
output "sns_alerts_topic_arn" {
  value       = aws_sns_topic.alerts.arn
  description = "ARN of SNS topic for data lake alerts"
}
