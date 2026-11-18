terraform {
  required_version = ">= 1.11, < 2.0"
  required_providers { aws = { source = "hashicorp/aws", version = "~> 5.100" } }
}
variable "aws_region" { type = string }
variable "state_bucket" { type = string }
variable "create_state_bucket" {
  type    = bool
  default = false
}
provider "aws" { region = var.aws_region }
resource "aws_s3_bucket" "state" {
  count         = var.create_state_bucket ? 1 : 0
  bucket        = var.state_bucket
  force_destroy = false
  tags          = { Project = "practica4-todo", Purpose = "Terraform remote state" }
  lifecycle { prevent_destroy = true }
}
data "aws_s3_bucket" "existing" {
  count  = var.create_state_bucket ? 0 : 1
  bucket = var.state_bucket
}
resource "aws_s3_bucket_versioning" "state" {
  bucket = var.state_bucket
  versioning_configuration { status = "Enabled" }
}
resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = var.state_bucket
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}
resource "aws_s3_bucket_public_access_block" "state" {
  bucket                  = var.state_bucket
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
