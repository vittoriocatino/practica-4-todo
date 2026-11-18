variable "aws_region" {
  type    = string
  default = "us-east-1"
}
variable "app_name" {
  type    = string
  default = "practica4-todo"
}
variable "repository_url" {
  type        = string
  description = "Public HTTPS repository URL; no credentials in user_data."
  default     = "https://github.com/vittoriocatino/practica-4-todo.git"
}
variable "git_ref" {
  type    = string
  default = "main"
}
variable "alert_email" {
  type    = string
  default = "vittorio.catino@iteso.mx"
}
variable "public_key" {
  type        = string
  description = "An SSH public key. The application does not use SSH or scp."
}
variable "instance_profile" {
  type    = string
  default = "LabInstanceProfile"
}
variable "http_cidr" {
  type        = string
  default     = "0.0.0.0/0"
  description = "Public lab API. Use only synthetic tasks; restrict for production."
}
