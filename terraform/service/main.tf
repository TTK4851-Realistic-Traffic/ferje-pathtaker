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
    key    = "ferje-pathtaker/service.terraform.tfstate"
    region = "us-east-1"
  }
}

////
// Service
//
// Setup any additional resources, necessary for development
// but not related to any specific deployment/environment.
//
// This include setting up an Elastic Container Registry
////

locals {
  application_name = "ferje-pathtaker"
  environment = "prod"
  tags = {
    "managedBy" = "terraform"
    "application" = local.application_name
    "environment" = local.environment
    "ntnuCourse" = "ttk4851"
  }
}

provider "aws" {
  # Configuration options
  region = "us-east-1"
}

resource "aws_ecr_repository" "pathtaker" {
  name                 = "ferje-pathtaker"
  image_tag_mutability = "MUTABLE"
  tags = local.tags
  image_scanning_configuration {
    scan_on_push = false
  }
}
resource "aws_ecr_repository" "pathtaker_ingest" {
  name                 = "ferje-pathtaker-ingest"
  image_tag_mutability = "MUTABLE"
  tags = local.tags
  image_scanning_configuration {
    scan_on_push = false
  }
}