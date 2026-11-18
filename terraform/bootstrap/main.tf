terraform {
  required_version = ">= 1.11, < 2.0"
  required_providers { aws = { source = "hashicorp/aws", version = "~> 5.100" } }
}
variable "aws_region" { type = string }
variable "state_bucket" { type = string }
provider "aws" { region = var.aws_region }
resource "aws_s3_bucket" "state" {
  bucket        = var.state_bucket
  force_destroy = false
  tags          = { Project = "practica4-todo", Purpose = "Terraform remote state" }
  lifecycle { prevent_destroy = true }
}
resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id
  versioning_configuration { status = "Enabled" }
}
resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id
  rule { apply_server_side_encryption_by_default { sse_algorithm = "AES256" } }
}
resource "aws_s3_bucket_public_access_block" "state" {
  bucket                  = aws_s3_bucket.state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
