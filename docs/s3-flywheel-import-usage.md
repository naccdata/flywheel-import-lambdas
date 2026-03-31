# S3 Flywheel Import Lambda — Usage Guide

## Overview

The S3 Flywheel Import lambda copies files from S3 into Flywheel projects using copy-by-reference. A single deployment handles multiple scenarios — the S3 source, Flywheel destination, and filtering rules are all specified in the event payload at invocation time.

## Event Payload Schema

```json
{
  "storage_id": "string (required) — Flywheel storage ID identifying the S3 bucket",
  "api_key_path": "string (required) — SSM parameter path, must start with /",
  "dry_run": "boolean (optional, default: false) — log operations without executing",
  "aws_profile": "string (optional) — boto3 profile name",
  "prefix_path_pairs": [
    {
      "s3_prefix": "string (required) — S3 path relative to storage bucket root",
      "fw_group": "string (required) — Flywheel group name",
      "fw_project": "string (required) — Flywheel project label",
      "include_patterns": ["string (optional) — substring include filters"],
      "exclude_patterns": ["string (optional) — substring exclude filters"]
    }
  ]
}
```

### Filtering behavior

- If `include_patterns` is non-empty, only objects whose key contains at least one pattern are kept
- If `exclude_patterns` is non-empty, objects whose key contains any pattern are removed
- Include is applied first, then exclude
- Zero-byte objects (directory markers) are always skipped

## Example: Single source, single project

Import all files from one S3 prefix into one Flywheel project.

```json
{
  "storage_id": "691c926ff8220b709983b848",
  "api_key_path": "/prod/flywheel/gearbot/apikey",
  "prefix_path_pairs": [
    {
      "s3_prefix": "centers/site-a",
      "fw_group": "site-a",
      "fw_project": "ingest-data"
    }
  ]
}
```

## Example: Single source, multiple projects with filtering

Split files from one prefix into different projects based on content. This mirrors the original LONI lambda pattern.

```json
{
  "storage_id": "691c926ff8220b709983b848",
  "api_key_path": "/prod/flywheel/gearbot/apikey",
  "prefix_path_pairs": [
    {
      "s3_prefix": "centers/loni",
      "fw_group": "loni",
      "fw_project": "ingest-metadata-scan",
      "exclude_patterns": ["clariti"]
    },
    {
      "s3_prefix": "centers/loni",
      "fw_group": "loni",
      "fw_project": "ingest-metadata-clariti",
      "include_patterns": ["clariti"]
    }
  ]
}
```

## Example: Different source bucket

A different Flywheel storage ID points to a different S3 bucket. The lambda code doesn't change — just use the storage ID for the new bucket.

```json
{
  "storage_id": "abc123def456",
  "api_key_path": "/prod/flywheel/gearbot/apikey",
  "prefix_path_pairs": [
    {
      "s3_prefix": "exports/quarterly",
      "fw_group": "research",
      "fw_project": "quarterly-import",
      "include_patterns": [".csv", ".tsv"]
    }
  ]
}
```

## Example: Dry run

Test what would be imported without making any Flywheel API calls.

```json
{
  "storage_id": "691c926ff8220b709983b848",
  "api_key_path": "/prod/flywheel/gearbot/apikey",
  "dry_run": true,
  "prefix_path_pairs": [
    {
      "s3_prefix": "centers/new-site",
      "fw_group": "new-site",
      "fw_project": "pilot-import"
    }
  ]
}
```

## Response Format

```json
{
  "status": "success | failed",
  "total_duration": 45.2,
  "total_file_count": 150,
  "pair_results": [
    {
      "fw_project": "ingest-data",
      "duration": 30.1,
      "file_count": 100,
      "failed_files": [],
      "include_patterns": [],
      "exclude_patterns": []
    },
    {
      "fw_project": "ingest-clariti",
      "duration": 15.1,
      "file_count": 50,
      "failed_files": [
        {"key": "centers/loni/bad-file.csv", "error": "ValueError: ..."}
      ],
      "include_patterns": ["clariti"],
      "exclude_patterns": []
    }
  ],
  "error_message": null,
  "error_type": null
}
```

### Error types

| error_type | Cause |
|---|---|
| `ConfigurationError` | Invalid event payload (missing fields, bad values) |
| `AuthenticationError` | SSM parameter not found or access denied |
| `SDKError` | Flywheel API HTTP error |
| `UnexpectedError` | Anything else |

If a single pair fails during processing, it appears in `pair_results` with `file_count: 0` and the error in `failed_files`. Other pairs continue processing.

## Adding a New Scenario

To use this lambda with a new S3 bucket or SSM parameter:

### 1. Identify the Flywheel storage ID

The storage ID maps to a specific S3 bucket in Flywheel. Get it from the Flywheel admin UI or API:

```
GET /api/xfer/storages
```

### 2. Update IAM policy (if needed)

The lambda's IAM role must have access to the S3 bucket and SSM parameter. In `lambda/s3_import/variables.tf`, the relevant variables are:

- `s3_bucket_arn` — ARN of the source S3 bucket
- `ssm_parameter_arn` — ARN of the SSM parameter with the API key

If the new scenario uses a bucket or parameter not already in the policy, update the Terraform config. For multiple buckets, change the variables to lists:

```hcl
variable "s3_bucket_arns" {
  description = "ARNs of source S3 buckets"
  type        = list(string)
}
```

And update the IAM policy resource block accordingly.

### 3. Invoke with the new payload

No code changes or redeployment needed — just invoke the lambda with the appropriate event payload for the new scenario.

## Invocation Methods

### AWS CLI

```bash
aws lambda invoke \
  --function-name s3-flywheel-import \
  --qualifier dev \
  --payload file://event.json \
  response.json
```

### EventBridge scheduled rule

Attach a scheduled rule that passes the event payload as a constant JSON input. Each schedule can target a different scenario.

### Step Functions

Use as a task in a Step Functions state machine, passing the event payload from the workflow input.
