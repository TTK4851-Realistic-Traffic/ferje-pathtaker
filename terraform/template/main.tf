data "aws_caller_identity" "current" {}

locals {
  qualified_name = "${var.application_name}-${var.environment}"
}

resource "aws_iam_role" "iam_for_lambda" {
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
resource "aws_cloudwatch_log_group" "logs" {
  name              = "/aws/lambda/${local.qualified_name}"
  retention_in_days = 7
  tags = var.tags
}

# See also the following AWS managed policy: AWSLambdaBasicExecutionRole
resource "aws_iam_policy" "lambda_logging" {
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

resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.iam_for_lambda.name
  policy_arn = aws_iam_policy.lambda_logging.arn
}

resource "aws_s3_bucket" "ais_raw_files" {
  bucket = "${local.qualified_name}-ais-raw"
  tags = var.tags
}

resource "aws_lambda_function" "ferjeaisimporter" {
//  filename      = data.archive_file.source.output_path
  image_uri     = "${aws_ecr_repository.repo.repository_url}:${var.docker_image_tag}"
  package_type  = "Image"
  function_name = local.qualified_name
  role          = aws_iam_role.iam_for_lambda.arn
  # This has to match the filename and function name in ../../ferjeimporter/main.py
  # That is to be executed
  handler       = null
  timeout = 20
  memory_size = 512

  # The filebase64sha256() function is available in Terraform 0.11.12 and later
  # For Terraform 0.11.11 and earlier, use the base64sha256() function and the file() function:
  # source_code_hash = "${base64sha256(file("lambda_function_payload.zip"))}"
//  source_code_hash = data.archive_file.source.output_base64sha256

  runtime = null

  tags = var.tags

  environment {
    variables = {
      foo = "bar"
      SQS_QUEUE_URL = "https://sqs.${var.region}.amazonaws.com/${data.aws_caller_identity.current.account_id}/${aws_sqs_queue.pathtaker_source.name}"
    }
  }

  depends_on = [
    aws_ecr_repository.repo,
    aws_iam_role_policy_attachment.lambda_logs,
    aws_cloudwatch_log_group.logs,
  ]
}

resource "aws_lambda_permission" "allow_bucket_to_trigger_lambda" {
  statement_id  = "AllowExecutionFromS3Bucket"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ferjeaisimporter.arn
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.ais_raw_files.arn
}

resource "aws_s3_bucket_notification" "bucket_notification" {
  bucket = aws_s3_bucket.ais_raw_files.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.ferjeaisimporter.arn
    events              = ["s3:ObjectCreated:*"]
//    filter_prefix       = "AWSLogs/"
    filter_suffix       = ".csv"
  }

  depends_on = [aws_lambda_permission.allow_bucket_to_trigger_lambda]
}

# See also the following AWS managed policy: AWSLambdaBasicExecutionRole
resource "aws_iam_policy" "allow_managing_contents_in_bucket" {
  name        = "${local.qualified_name}-lambda-manage-bucket"
  path        = "/"
  description = "IAM policy which allows lambda to manage a bucket"

  policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ListObjectsInBucket",
      "Effect": "Allow",
      "Action": ["s3:ListBucket"],
      "Resource": ["arn:aws:s3:::${aws_s3_bucket.ais_raw_files.bucket}"]
    },
    {
      "Sid": "AllObjectActions",
      "Effect": "Allow",
      "Action": "s3:*Object",
      "Resource": ["arn:aws:s3:::${aws_s3_bucket.ais_raw_files.bucket}/*"]
    }
  ]
}
EOF
}

resource "aws_iam_role_policy_attachment" "lambda_to_bucket" {
  role       = aws_iam_role.iam_for_lambda.name
  policy_arn = aws_iam_policy.allow_managing_contents_in_bucket.arn
}

// This is the source of data for the Pathtaker microservice.
// Ferje-AIS-importer is the temporary owner of this resource,
// but this might move to ferje-pathtaker at a later moment
resource "aws_sqs_queue" "pathtaker_source" {
  name                      = "${local.qualified_name}-pathtaker-source"
  tags = var.tags
}

resource "aws_iam_policy" "write_to_queue" {
  name        = "${local.qualified_name}-lambda-write-queue"
  path        = "/"
  description = "IAM policy which allows lambda to push to an SQS queue"

  policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "SendMessageToQueue",
      "Effect": "Allow",
      "Action": [
        "sqs:SendMessage"
      ],
      "Resource": [
        "${aws_sqs_queue.pathtaker_source.arn}"
      ]
    }
  ]
}
EOF
}

resource "aws_iam_role_policy_attachment" "lambda_write_to_queue" {
  role       = aws_iam_role.iam_for_lambda.name
  policy_arn = aws_iam_policy.write_to_queue.arn
}