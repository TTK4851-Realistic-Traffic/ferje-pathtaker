terraform {
  required_version = "0.14.3"

  required_providers {
    aws = {
      source = "hashicorp/aws"
      version = "3.27.0"
    }
  }

  backend "s3" {
    bucket = "lokalvert-terraform-state"
    key    = "ferje-pathtaker/prod.terraform.tfstate"
    region = "us-east-1"
  }
}

provider "aws" {
  # Configuration options
  region = "us-east-1"
}

data "aws_region" "current" {}

locals {
  application_name = "ferje-pathtaker"
  environment = "prod"

  last_commit_sha = trimspace(file("../../.git/${trimspace(trimprefix(file("../../.git/HEAD"), "ref:"))}"))

  qualified_name = "${local.application_name}-${local.environment}"
  tags = {
    "managedBy" = "terraform"
    "application" = local.application_name
    "environment" = local.environment
    "ntnuCourse" = "ttk4851"
  }
}

module "ferjeimporter" {
  source = "../template"
  application_name = local.application_name
  environment = local.environment
  function_handler = "main.handler"
  docker_image_tag = local.last_commit_sha
  tags = local.tags

  region = data.aws_region.current.name
}
