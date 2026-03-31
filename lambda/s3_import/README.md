# S3 Flywheel Import Lambda

Copies files from S3 into Flywheel projects using copy-by-reference. No data is transferred — the Lambda registers S3 objects in Flywheel via upload tickets, so Flywheel reads directly from the source bucket.

## How It Works

1. Parse the event payload into an `ImportConfig` (Pydantic model)
2. Retrieve the Flywheel API key from SSM Parameter Store
3. Initialize a `ClientHandler` (wraps `fw-client` SDK and `boto3`)
4. For each prefix-path pair in the config:
   - Look up the Flywheel project ID
   - List and filter S3 objects under the prefix
   - Import each file via copy-by-reference upload ticket
5. Return a structured `ImportResult` with per-pair metrics

Individual file failures are tracked but don't stop processing. Individual pair failures are caught and recorded, and remaining pairs continue.

## Directory Structure

```text
lambda/s3_import/
├── src/python/s3_import_lambda/
│   ├── BUILD                  # Pants targets (lambda, layer)
│   ├── lambda_function.py     # Handler: event parsing, SSM retrieval, orchestration
│   └── import_operations.py   # Business logic: per-pair file import
├── test/python/
│   ├── BUILD
│   ├── conftest.py
│   ├── test_lambda_function.py
│   ├── test_import_operations.py
│   └── test_properties.py
├── docs/
│   └── s3-flywheel-import-usage.md   # Event payload schema and invocation examples
├── main.tf                    # Terraform: IAM, Lambda, layer, alarms
├── variables.tf               # Terraform variables with validation
├── outputs.tf                 # Terraform outputs
└── terraform.tfvars.example   # Example variable values
```

## Shared Dependencies

The Lambda depends on two shared modules under `common/src/python/`:

| Module | Purpose |
| --- | --- |
| `flywheel_client` | `ClientHandler` — wraps Flywheel SDK for project lookup, S3 object listing/filtering, and copy-by-reference import |
| `s3_import_models` | Pydantic models: `ImportConfig`, `PrefixPathPair`, `ImportResult`, `PairImportResult` |

## Build

```bash
./bin/start-devcontainer.sh
./bin/exec-in-devcontainer.sh pants package lambda/s3_import/src/python/s3_import_lambda::
```

Produces `dist/lambda.s3_import.src.python.s3_import_lambda/lambda.zip` (function code) and `layer.zip` (dependencies).

## Deploy

```bash
cd lambda/s3_import
terraform init                        # first time only
terraform plan -var-file="terraform.tfvars"
terraform apply -var-file="terraform.tfvars"
```

Copy `terraform.tfvars.example` to `terraform.tfvars` and customize. See [docs/deployment-guide.md](../../docs/deployment-guide.md) for full deployment details including IAM policy management.

## IAM Policies

The Terraform config creates an IAM role with inline policies for the specific resources the Lambda accesses. These are controlled by two variables — no `main.tf` edits needed when adding new buckets or parameters:

| Variable | Controls | Default |
| --- | --- | --- |
| `s3_bucket_arns` | S3 read access (`GetObject`, `ListBucket`) | `naccquickaccess`, `loni-table-data` |
| `ssm_parameter_arns` | SSM read access (`GetParameter`) | `/prod/flywheel/gearbot/apikey` |

Update these in your tfvars file when deploying against different resources. See the [usage guide](docs/s3-flywheel-import-usage.md#2-update-iam-policies-if-needed) for examples.

## Test

```bash
# All tests
./bin/exec-in-devcontainer.sh pants test lambda/s3_import/test/python::

# Specific test file
./bin/exec-in-devcontainer.sh pants test lambda/s3_import/test/python/test_lambda_function.py

# Specific test by name
./bin/exec-in-devcontainer.sh pants test lambda/s3_import/test/python/test_lambda_function.py -- -k test_successful_import
```

## Usage

See [docs/s3-flywheel-import-usage.md](docs/s3-flywheel-import-usage.md) for the full event payload schema, filtering behavior, invocation examples, and response format.

Quick example:

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

```bash
aws lambda invoke \
  --function-name s3-flywheel-import \
  --qualifier current \
  --payload file://event.json \
  response.json
```
