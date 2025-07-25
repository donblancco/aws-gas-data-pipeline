# JIRA S3 Exporter - Terraform Configuration

This Terraform configuration deploys AWS infrastructure for automatically exporting JIRA data to S3.

## Architecture

```
JIRA → Lambda → S3 → Google Apps Script → Google Sheets
```

## Resources Created

- **S3 Bucket**: Stores CSV exports with public read access for `latest.csv`
- **Lambda Function**: Executes JIRA data extraction and CSV generation
- **IAM Role & Policy**: Permissions for Lambda to access S3 and CloudWatch
- **EventBridge Rule**: Schedules Lambda execution (weekly)
- **CloudWatch Log Group**: Stores Lambda execution logs

## Prerequisites

1. AWS CLI configured with appropriate credentials
2. Terraform >= 1.0 installed
3. JIRA API credentials (URL, username, API token)

## Setup

1. **Copy configuration file:**
   ```bash
   cp terraform.tfvars.example terraform.tfvars
   ```

2. **Edit terraform.tfvars:**
   ```hcl
   # Required: Update with your actual values
   jira_url       = "https://your-domain.atlassian.net"
   jira_username  = "your-email@company.com"
   jira_api_token = "your-api-token"
   
   # Optional: Customize other settings
   s3_bucket_name = "your-company-exports"
   aws_region     = "us-east-1"
   ```

3. **Initialize Terraform:**
   ```bash
   terraform init
   ```

4. **Plan deployment:**
   ```bash
   terraform plan
   ```

5. **Apply configuration:**
   ```bash
   terraform apply
   ```

## Configuration Options

### Core Settings
- `jira_url`: Your JIRA instance URL
- `jira_username`: JIRA username (email)
- `jira_api_token`: JIRA API token ([create here](https://id.atlassian.com/manage-profile/security/api-tokens))

### AWS Resources
- `s3_bucket_name`: S3 bucket name (must be globally unique)
- `lambda_function_name`: Lambda function name
- `aws_region`: AWS region for deployment

### Schedule
- `schedule_expression`: CloudWatch Events cron expression
  - Default: `"cron(0 23 ? * SUN *)"` (Every Sunday 23:00 UTC)
  - JST equivalent: Monday 8:00 AM

## Outputs

After deployment, Terraform provides:
- `s3_bucket_name`: Created S3 bucket name
- `lambda_function_name`: Created Lambda function name
- `csv_public_url`: Public URL for accessing latest.csv
- `lambda_log_group_name`: CloudWatch log group for monitoring

## File Structure

```
terraform/
├── main.tf                 # Provider configuration
├── variables.tf            # Input variables
├── outputs.tf              # Output values
├── s3.tf                   # S3 bucket and policies
├── lambda.tf               # Lambda function
├── iam.tf                  # IAM roles and policies
├── scheduler.tf            # EventBridge scheduling
├── terraform.tfvars.example # Example configuration
└── README.md               # This file
```

## Security Features

- **IAM Least Privilege**: Lambda has minimal required permissions
- **S3 Encryption**: Server-side encryption enabled
- **Public Access**: Limited to `latest.csv` file only
- **Versioning**: S3 versioning enabled
- **Lifecycle Policy**: Automatic cleanup of old weekly exports

## Monitoring

- **CloudWatch Logs**: Lambda execution logs in `/aws/lambda/jira-csv-exporter`
- **EventBridge Events**: Scheduled execution monitoring
- **S3 Metrics**: Bucket access and storage metrics

## Troubleshooting

### Common Issues

1. **S3 Bucket Name Conflict:**
   ```
   Error: bucket already exists
   ```
   Solution: Change `s3_bucket_name` to a unique value

2. **JIRA Authentication:**
   ```
   Error: 401 Unauthorized
   ```
   Solution: Verify JIRA credentials and API token

3. **Lambda Timeout:**
   ```
   Error: Task timed out after 300.00 seconds
   ```
   Solution: Increase timeout or optimize query

### Useful Commands

```bash
# Check Lambda logs
aws logs tail /aws/lambda/jira-csv-exporter --follow

# Manual Lambda execution
aws lambda invoke \
  --function-name jira-csv-exporter \
  --payload '{}' \
  response.json

# Check S3 files
aws s3 ls s3://your-company-exports/project-exports/

# Verify CSV accessibility
curl "https://your-company-exports.s3.amazonaws.com/project-exports/latest.csv"
```

## Cleanup

To destroy all resources:
```bash
terraform destroy
```

## Integration with Google Apps Script

After deployment, use the output `csv_public_url` in your Google Apps Script configuration:

```javascript
const CONFIG = {
  CSV_URL: 'https://your-company-exports.s3.amazonaws.com/project-exports/latest.csv',
  // ... other config
};
```