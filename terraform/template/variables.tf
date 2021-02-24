variable "application_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "region" {
  type = string
}

variable "docker_image_tag" {
  type = string
  default = "latest"
}

variable "function_handler" {
  type = string
}

variable "tags" {
  type = map(string)
}