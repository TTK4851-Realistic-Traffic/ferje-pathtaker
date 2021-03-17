data "aws_caller_identity" "current" {}

locals {
  qualified_name = "${var.application_name}-${var.environment}"
  elasticsearch_domain_name = replace("${local.qualified_name}-waypoints", "-", "")
}

data "aws_region" "current" {}

// Used to give clients
resource "random_password" "api_auth_secret" {
  length           = 32
  special          = false
  min_lower = 3
  min_numeric = 5
  min_upper = 3
}

// Store the contents locally
resource "local_file" "api_auth_credentials" {
  filename = "../../${var.environment}-secrets.env"
  sensitive_content = <<EOF
API_CLIENT_ID=gemini
API_CLIENT_SECRET=${random_password.api_auth_secret.result}
EOF
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
  name = "/aws/lambda/${local.qualified_name}"
  retention_in_days = 7
  tags = var.tags
}

# See also the following AWS managed policy: AWSLambdaBasicExecutionRole
resource "aws_iam_policy" "pathtaker_logging" {
  name = "${local.qualified_name}-lambda-logging"
  path = "/"
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
  role = aws_iam_role.pathtaker.name
  policy_arn = aws_iam_policy.pathtaker_logging.arn
}

resource "aws_api_gateway_rest_api" "ferjepathtaker" {
  name = local.qualified_name
  description = "REST API that delivers realistic boat-traffic information from the Trondheim Area"
}

resource "aws_api_gateway_resource" "ferjepathtaker_get_waypoints" {
  rest_api_id = aws_api_gateway_rest_api.ferjepathtaker.id
  parent_id = aws_api_gateway_rest_api.ferjepathtaker.root_resource_id
  path_part = "waypoints"
}

resource "aws_api_gateway_method" "ferjepathtaker_get_waypoints" {
  rest_api_id = aws_api_gateway_rest_api.ferjepathtaker.id
  resource_id = aws_api_gateway_resource.ferjepathtaker_get_waypoints.id
  http_method = "GET"
  // Currently set to none, but will in the future use Lambda Authorizer for Bearer Auth
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "ferjepathtaker_get_waypoints" {
  rest_api_id = aws_api_gateway_rest_api.ferjepathtaker.id
  resource_id = aws_api_gateway_method.ferjepathtaker_get_waypoints.resource_id
  http_method = aws_api_gateway_method.ferjepathtaker_get_waypoints.http_method

  // Lambda can only be invoked via POST
  // https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/api_gateway_integration#integration_http_method
  integration_http_method = "POST"
  type = "AWS_PROXY"
  uri = aws_lambda_function.ferjepathtaker.invoke_arn
  timeout_milliseconds = 29000
}

resource "aws_api_gateway_deployment" "ferjepathtaker_get_waypoints" {
   depends_on = [
     aws_api_gateway_integration.ferjepathtaker_get_waypoints,
   ]

   rest_api_id = aws_api_gateway_rest_api.ferjepathtaker.id
   stage_name  = var.environment
}

resource "aws_lambda_permission" "ferjepathtaker_allow_any_subpaths" {
   statement_id  = "AllowAPIGatewayInvoke"
   action        = "lambda:InvokeFunction"
   function_name = aws_lambda_function.ferjepathtaker.function_name
   principal     = "apigateway.amazonaws.com"

   # The "/*/*" portion grants access from any method on any resource
   # within the API Gateway REST API.
   source_arn = "${aws_api_gateway_rest_api.ferjepathtaker.execution_arn}/*/*"
}

resource "aws_lambda_function" "ferjepathtaker" {
  image_uri = "${var.ecr_repository_url}/${var.application_name}:${var.docker_image_tag}"
  package_type = "Image"
  function_name = local.qualified_name
  role = aws_iam_role.pathtaker.arn
  # This has to match the filename and function name in ../../ferjeimporter/main.py
  # That is to be executed
  handler = null
  timeout = 20
  memory_size = 128

  runtime = null

  tags = var.tags

  environment {
    variables = {
      API_CLIENT_ID = "gemini"
      API_CLIENT_SECRET = random_password.api_auth_secret.result
      ELASTICSEARCH_HOSTNAME = aws_elasticsearch_domain.waypoints.endpoint
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
  name = "/aws/lambda/${local.qualified_name}-ingest"
  retention_in_days = 7
  tags = var.tags
}

# See also the following AWS managed policy: AWSLambdaBasicExecutionRole
resource "aws_iam_policy" "pathtaker_ingest_logging" {
  name = "${local.qualified_name}-ingest-lambda-logging"
  path = "/"
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
  role = aws_iam_role.pathtaker_ingest.name
  policy_arn = aws_iam_policy.pathtaker_ingest_logging.arn
}

resource "aws_lambda_function" "ferjepathtaker_ingest" {
  image_uri = "${var.ecr_repository_url}/${var.application_name}-ingest:${var.docker_image_tag}"
  package_type = "Image"
  function_name = "${local.qualified_name}-ingest"
  role = aws_iam_role.pathtaker_ingest.arn
  # This has to match the filename and function name in ../../ferjeimporter/main.py
  # That is to be executed
  handler = null
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
      ELASTICSEARCH_HOSTNAME = aws_elasticsearch_domain.waypoints.endpoint
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.pathtaker_ingest_allow_logs,
    aws_cloudwatch_log_group.pathtaker_ingest_logging,
  ]
}

// AWS Lambda Trigger

data "aws_sqs_queue" "lambda_trigger" {
  name = var.lambda_trigger_queue_name
}

// This is a role that give the necessary access to Trigger and read messages from an SQS-queue
resource "aws_iam_policy" "allow_to_trigger_on_queue_message" {
  name = "${local.qualified_name}-lambda-read-queue"
  path = "/"
  description = "IAM policy which allows lambda to push to an SQS queue"

  policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "SQSTriggerOnMessage",
      "Effect": "Allow",
      "Action": [
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:GetQueueAttributes"
      ],
      "Resource": [
        "${data.aws_sqs_queue.lambda_trigger.arn}"
      ]
    }
  ]
}
EOF
}

// Give ferje-pathaker-ingest the necessary access to trigger on new messagesin SQS
resource "aws_iam_role_policy_attachment" "ferje_ingest_trigger_on_queue" {
  role = aws_iam_role.pathtaker_ingest.name
  policy_arn = aws_iam_policy.allow_to_trigger_on_queue_message.arn
}

resource "aws_lambda_event_source_mapping" "trigger_on_message" {
  event_source_arn = data.aws_sqs_queue.lambda_trigger.arn
  function_name = aws_lambda_function.ferjepathtaker_ingest.arn
  enabled = true

  depends_on = [
    aws_iam_role_policy_attachment.ferje_ingest_trigger_on_queue]
}

////
//
// Elasticsearch (Database)
//
////

resource "aws_elasticsearch_domain" "waypoints" {
  domain_name = local.elasticsearch_domain_name
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

  access_policies = <<POLICY
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": ["es:*"],
      "Principal": {
        "AWS": ["${aws_iam_role.pathtaker_ingest.arn}"]
      },
      "Resource": "arn:aws:es:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:domain/${local.elasticsearch_domain_name}/*",
      "Effect": "Allow"
    }
  ]
}
POLICY
  tags = var.tags
}

//# See also the following AWS managed policy: AWSLambdaBasicExecutionRole
//resource "aws_iam_policy" "elasticsearch_manage" {
//  name        = "${local.qualified_name}-es-manage"
//  path        = "/"
//  description = "IAM policy for managing elasticsearch domain"
//
//  policy = <<EOF
//{
//  "Version": "2012-10-17",
//  "Statement": [
//    {
//      "Action": [
//        "es:ESHttpDelete",
//        "es:ESHttpGet",
//        "es:ESHttpHead",
//        "es:ESHttpPost",
//        "es:ESHttpPut"
//      ],
//      "Resource": "*",
//      "Effect": "Allow"
//    }
//  ]
//}
//EOF
//}
//
//resource "aws_iam_role_policy_attachment" "elasticsearch_manage_from_ingest" {
//  role       = aws_iam_role.pathtaker_ingest.name
//  policy_arn = aws_iam_policy.elasticsearch_manage.arn
//}
