output "api_url" { value = "http://${aws_instance.api.public_ip}:8000" }
output "instance_id" { value = aws_instance.api.id }
output "db_identifier" { value = aws_db_instance.db.identifier }
output "secret_arn" { value = aws_secretsmanager_secret.db.arn }
output "sns_topic_arn" { value = aws_sns_topic.alerts.arn }
output "dashboard_url" {
  value = "https://${var.aws_region}.console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards/dashboard/${var.app_name}"
}
