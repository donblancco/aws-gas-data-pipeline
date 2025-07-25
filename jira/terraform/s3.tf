# S3 Bucket for JIRA exports
resource "aws_s3_bucket" "jira_exports" {
  bucket = var.s3_bucket_name
  tags   = var.tags
}

# S3 Bucket versioning
resource "aws_s3_bucket_versioning" "jira_exports_versioning" {
  bucket = aws_s3_bucket.jira_exports.id
  versioning_configuration {
    status = "Enabled"
  }
}

# S3 Bucket server-side encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "jira_exports_encryption" {
  bucket = aws_s3_bucket.jira_exports.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# S3 Bucket public access block
resource "aws_s3_bucket_public_access_block" "jira_exports_pab" {
  bucket = aws_s3_bucket.jira_exports.id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

# S3 Bucket policy for public read access to latest.csv
resource "aws_s3_bucket_policy" "jira_exports_policy" {
  bucket = aws_s3_bucket.jira_exports.id
  depends_on = [aws_s3_bucket_public_access_block.jira_exports_pab]

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "PublicReadGetObject"
        Effect    = "Allow"
        Principal = "*"
        Action    = "s3:GetObject"
        Resource  = "${aws_s3_bucket.jira_exports.arn}/${var.s3_prefix}latest.csv"
      }
    ]
  })
}

# S3 Bucket CORS configuration
resource "aws_s3_bucket_cors_configuration" "jira_exports_cors" {
  bucket = aws_s3_bucket.jira_exports.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET"]
    allowed_origins = ["*"]
    max_age_seconds = 3000
  }
}

# S3 Bucket lifecycle configuration
resource "aws_s3_bucket_lifecycle_configuration" "jira_exports_lifecycle" {
  bucket = aws_s3_bucket.jira_exports.id

  rule {
    id     = "daily_exports_cleanup"
    status = "Enabled"

    filter {
      prefix = "${var.s3_prefix}daily/"
    }

    expiration {
      days = 90  # 3ヶ月後に削除
    }

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
  
}