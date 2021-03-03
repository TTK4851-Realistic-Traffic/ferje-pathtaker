data "aws_caller_identity" "current" {}

locals {
  qualified_name = "${var.application_name}-${var.environment}"
}

////
//
// ferje-pathtaker
//
////

resource "aws_iam_role" "pathtaker" {
  name = "${local.qualified_name}-role"

  assume_role_policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": "sts:AssumeRole",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Effect": "Allow",
      "Sid": ""
    }
  ]
}
EOF

  tags = var.tags
}

# This is to optionally manage the CloudWatch Log Group for the Lambda Function.
# If skipping this resource configuration, also add "logs:CreateLogGroup" to the IAM policy below.
resource "aws_cloudwatch_log_group" "pathtaker_logging" {
  name              = "/aws/lambda/${local.qualified_name}"
  retention_in_days = 7
  tags = var.tags
}

# See also the following AWS managed policy: AWSLambdaBasicExecutionRole
resource "aws_iam_policy" "pathtaker_logging" {
  name        = "${local.qualified_name}-lambda-logging"
  path        = "/"
  description = "IAM policy for logging from a lambda"

  policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*",
      "Effect": "Allow"
    }
  ]
}
EOF
}

resource "aws_iam_role_policy_attachment" "pathtaker_allow_logs" {
  role       = aws_iam_role.pathtaker.name
  policy_arn = aws_iam_policy.pathtaker_logging.arn
}

resource "aws_lambda_function" "ferjepathtaker" {
  image_uri     = "${var.ecr_repository_url}/${var.application_name}:${var.docker_image_tag}"
  package_type  = "Image"
  function_name = local.qualified_name
  role          = aws_iam_role.pathtaker.arn
  # This has to match the filename and function name in ../../ferjeimporter/main.py
  # That is to be executed
  handler       = null
  timeout = 20
  memory_size = 128

  runtime = null

  tags = var.tags

  environment {
    variables = {
      foo = "bar"
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.pathtaker_allow_logs,
    aws_cloudwatch_log_group.pathtaker_logging,
  ]
}

////
//
// ferje-pathtaker-ingest
//
////

resource "aws_iam_role" "pathtaker_ingest" {
  name = "${local.qualified_name}-ingest-role"

  assume_role_policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": "sts:AssumeRole",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Effect": "Allow",
      "Sid": ""
    }
  ]
}
EOF

  tags = var.tags
}


# This is to optionally manage the CloudWatch Log Group for the Lambda Function.
# If skipping this resource configuration, also add "logs:CreateLogGroup" to the IAM policy below.
resource "aws_cloudwatch_log_group" "pathtaker_ingest_logging" {
  name              = "/aws/lambda/${local.qualified_name}-ingest"
  retention_in_days = 7
  tags = var.tags
}

# See also the following AWS managed policy: AWSLambdaBasicExecutionRole
resource "aws_iam_policy" "pathtaker_ingest_logging" {
  name        = "${local.qualified_name}-ingest-lambda-logging"
  path        = "/"
  description = "IAM policy for logging from a lambda"

  policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*",
      "Effect": "Allow"
    }
  ]
}
EOF
}

resource "aws_iam_role_policy_attachment" "pathtaker_ingest_allow_logs" {
  role       = aws_iam_role.pathtaker_ingest.name
  policy_arn = aws_iam_policy.pathtaker_ingest_logging.arn
}

resource "aws_lambda_function" "ferjepathtaker_ingest" {
  image_uri     = "${var.ecr_repository_url}/${var.application_name}-ingest:${var.docker_image_tag}"
  package_type  = "Image"
  function_name = "${local.qualified_name}-ingest"
  role          = aws_iam_role.pathtaker.arn
  # This has to match the filename and function name in ../../ferjeimporter/main.py
  # That is to be executed
  handler       = null
  timeout = 20
  memory_size = 128

  # The filebase64sha256() function is available in Terraform 0.11.12 and later
  # For Terraform 0.11.11 and earlier, use the base64sha256() function and the file() function:
  # source_code_hash = "${base64sha256(file("lambda_function_payload.zip"))}"
//  source_code_hash = data.archive_file.source.output_base64sha256

  runtime = null

  tags = var.tags

  environment {
    variables = {
      foo = "bar"
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.pathtaker_ingest_allow_logs,
    aws_cloudwatch_log_group.pathtaker_ingest_logging,
  ]
}

////
//
// Elasticsearch (Database)
//
////

resource "aws_elasticsearch_domain" "waypoints" {
  domain_name = replace("${local.qualified_name}-waypoints", "-", "")
  elasticsearch_version = "7.9"

  cluster_config {
    instance_count = 1
    instance_type = "t3.small.elasticsearch"
    dedicated_master_enabled = false
    zone_awareness_enabled = false
  }

  snapshot_options {
    automated_snapshot_start_hour = 0
  }

  domain_endpoint_options {
    enforce_https = true
    tls_security_policy = "Policy-Min-TLS-1-2-2019-07"
  }

  ebs_options {
    ebs_enabled = true
    volume_size = 10
  }

  tags = var.tags
}

# See also the following AWS managed policy: AWSLambdaBasicExecutionRole
resource "aws_iam_policy" "elasticsearch_manage" {
  name        = "${local.qualified_name}-es-manage"
  path        = "/"
  description = "IAM policy for managing elasticsearch domain"

  policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": [
        "es:ESHttpDelete",
        "es:ESHttpGet",
        "es:ESHttpHead",
        "es:ESHttpPost",
        "es:ESHttpPut"
      ],
      "Resource": "*",
      "Effect": "Allow"
    }
  ]
}
EOF
}

resource "aws_iam_role_policy_attachment" "elasticsearch_manage_from_ingest" {
  role       = aws_iam_role.pathtaker_ingest.name
  policy_arn = aws_iam_policy.elasticsearch_manage.arn
}
