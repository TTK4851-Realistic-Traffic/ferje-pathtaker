terraform {
  required_version = ">= 0.14"

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
  # Only allow the correct account
  allowed_account_ids = ["314397620259"]
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

module "ferjepathtaker" {
  source = "../template"
  application_name = local.application_name
  environment = local.environment
  docker_image_tag = local.last_commit_sha
  tags = local.tags

  ecr_repository_url = "314397620259.dkr.ecr.us-east-1.amazonaws.com"
  lambda_trigger_queue_name = "ferje-ais-importer-prod-pathtaker-source"

  region = data.aws_region.current.name
}
