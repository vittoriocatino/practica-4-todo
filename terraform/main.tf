data "aws_vpc" "default" { default = true }
data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
  filter {
    name   = "default-for-az"
    values = ["true"]
  }
}
data "aws_ssm_parameter" "ami" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

resource "aws_security_group" "api" {
  name_prefix = "${var.app_name}-api-"
  description = "To-do HTTP API; no inbound SSH"
  vpc_id      = data.aws_vpc.default.id
  ingress {
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = [var.http_cidr]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
resource "aws_security_group" "db" {
  name_prefix = "${var.app_name}-db-"
  description = "MySQL only from the API security group"
  vpc_id      = data.aws_vpc.default.id
  ingress {
    from_port       = 3306
    to_port         = 3306
    protocol        = "tcp"
    security_groups = [aws_security_group.api.id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
resource "aws_db_subnet_group" "db" {
  name       = "${var.app_name}-db"
  subnet_ids = data.aws_subnets.default.ids
}
resource "random_password" "db" {
  length  = 28
  special = false
}
resource "aws_db_instance" "db" {
  identifier              = var.app_name
  engine                  = "mysql"
  instance_class          = "db.t3.micro"
  allocated_storage       = 20
  storage_type            = "gp2"
  storage_encrypted       = true
  db_name                 = "todo"
  username                = "todoadmin"
  password                = random_password.db.result
  db_subnet_group_name    = aws_db_subnet_group.db.name
  vpc_security_group_ids  = [aws_security_group.db.id]
  publicly_accessible     = false
  skip_final_snapshot     = true
  backup_retention_period = 0
  deletion_protection     = false
  apply_immediately       = true
}
resource "aws_secretsmanager_secret" "db" {
  name_prefix             = "${var.app_name}/rds-"
  recovery_window_in_days = 7
}
resource "aws_secretsmanager_secret_version" "db" {
  secret_id = aws_secretsmanager_secret.db.id
  secret_string = jsonencode({
    host     = aws_db_instance.db.address
    port     = aws_db_instance.db.port
    dbname   = aws_db_instance.db.db_name
    username = aws_db_instance.db.username
    password = random_password.db.result
    engine   = "mysql"
  })
}
resource "aws_key_pair" "api" {
  key_name   = "${var.app_name}-key"
  public_key = var.public_key
}
resource "aws_instance" "api" {
  ami                         = data.aws_ssm_parameter.ami.value
  instance_type               = "t3.micro"
  subnet_id                   = sort(data.aws_subnets.default.ids)[0]
  vpc_security_group_ids      = [aws_security_group.api.id]
  associate_public_ip_address = true
  key_name                    = aws_key_pair.api.key_name
  iam_instance_profile        = var.instance_profile
  monitoring                  = true
  user_data_replace_on_change = true
  user_data = templatefile("${path.module}/user_data.sh.tftpl", {
    repository_url = var.repository_url
    git_ref        = var.git_ref
    secret_arn     = aws_secretsmanager_secret.db.arn
    app_name       = var.app_name
    aws_region     = var.aws_region
  })
  metadata_options {
    http_tokens   = "required"
    http_endpoint = "enabled"
  }
  root_block_device {
    volume_size           = 12
    volume_type           = "gp3"
    encrypted             = true
    delete_on_termination = true
  }
  tags       = { Name = var.app_name }
  depends_on = [aws_secretsmanager_secret_version.db]
}

resource "aws_sns_topic" "alerts" { name = "${var.app_name}-alerts" }
resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}
resource "aws_cloudwatch_metric_alarm" "cpu" {
  alarm_name          = "${var.app_name}-cpu-high"
  alarm_description   = "CPU >= 80% for two consecutive minutes; check load and scale."
  namespace           = "AWS/EC2"
  metric_name         = "CPUUtilization"
  statistic           = "Average"
  period              = 60
  evaluation_periods  = 2
  datapoints_to_alarm = 2
  threshold           = 80
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "missing"
  dimensions          = { InstanceId = aws_instance.api.id }
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
}
resource "aws_cloudwatch_metric_alarm" "db_errors" {
  alarm_name          = "${var.app_name}-database-errors"
  alarm_description   = "At least one real failed RDS operation in 60 seconds."
  namespace           = "TodoList"
  metric_name         = "DatabaseErrors"
  statistic           = "Sum"
  period              = 60
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  dimensions          = { Application = var.app_name }
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
}
resource "aws_cloudwatch_metric_alarm" "latency" {
  alarm_name          = "${var.app_name}-database-latency"
  alarm_description   = "Mean DB operation time >= 500 ms in two consecutive minutes."
  namespace           = "TodoList"
  metric_name         = "DatabaseLatency"
  statistic           = "Average"
  period              = 60
  evaluation_periods  = 2
  datapoints_to_alarm = 2
  threshold           = 500
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  dimensions          = { Application = var.app_name }
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
}
resource "aws_cloudwatch_dashboard" "todo" {
  dashboard_name = var.app_name
  dashboard_body = templatefile("${path.module}/../alerting/cloudwatch-dashboard.json.tftpl", {
    region = var.aws_region, instance_id = aws_instance.api.id, app_name = var.app_name
  })
}
