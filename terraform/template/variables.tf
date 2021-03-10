variable "application_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "lambda_trigger_queue_name" {
  type = string
  description = "Name of the queue which will trigger the AWS lambda"
}

variable "region" {
  type = string
}

variable "ecr_repository_url" {
  type = string
}

variable "docker_image_tag" {
  type = string
  default = "latest"
}

variable "tags" {
  type = map(string)
}