variable "application_name" {
  type = string
}

variable "environment" {
  type = string
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