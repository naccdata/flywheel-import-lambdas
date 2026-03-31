# Requirements Document

## Introduction

This document specifies the requirements for a generalized AWS Lambda function that imports files from S3 into Flywheel projects via copy-by-reference. The Lambda accepts a list of prefix-path pairs mapping S3 prefixes to Flywheel group/project destinations, with optional include/exclude filtering per pair. The implementation generalizes the existing LONI-specific lambda (originally in the `naccdata/loni-table-data` repo) to work with any S3 bucket and any set of Flywheel projects, structured for the Pants monorepo build system.

## Glossary

- **Lambda**: The AWS Lambda function that orchestrates the S3-to-Flywheel import process
- **Import_Config**: The configuration model that defines the full set of parameters for a Lambda invocation, including storage ID, API key path, and the list of Prefix_Path_Pairs
- **Prefix_Path_Pair**: A single mapping from an S3 prefix to a Flywheel group/project destination, with optional include/exclude filter patterns
- **Client_Handler**: The module that wraps Flywheel SDK (`fw-client`) and `boto3` S3 operations, providing methods for project lookup, object listing/filtering, and copy-by-reference import
- **Copy_By_Reference**: The Flywheel upload mechanism that registers an S3 object in Flywheel without transferring the actual file data, using the two-step upload ticket flow
- **Upload_Ticket**: A Flywheel API object created via `POST /xfer/upload` that represents a pending copy-by-reference import; finalized via `POST {finish_url}`
- **Storage_Config**: The Flywheel storage configuration retrieved via `GET /xfer/storages/{storage_id}`, containing the S3 bucket name, prefix, and provider ID
- **Filter_Pattern**: A substring pattern used to include or exclude S3 objects by matching against the object key
- **Import_Result**: The structured response returned by the Lambda, containing per-pair metrics, error details, and aggregate totals
- **Pair_Import_Result**: The result of importing files for a single Prefix_Path_Pair, including file count, duration, and any per-file failures
- **SSM_Parameter_Store**: AWS Systems Manager Parameter Store, used to securely retrieve the Flywheel API key at runtime

## Requirements

### Requirement 1: Lambda Event Configuration Parsing

**User Story:** As a pipeline operator, I want to configure the Lambda with a list of S3-to-Flywheel prefix-path pairs, so that a single invocation can import files into multiple Flywheel projects from different S3 prefixes.

#### Acceptance Criteria

1. WHEN a Lambda event containing a `prefix_path_pairs` list is received, THE Import_Config SHALL parse each entry into a Prefix_Path_Pair with fields: `s3_prefix`, `fw_group`, `fw_project`, and optional `include_patterns` and `exclude_patterns`
2. WHEN a Lambda event contains `storage_id`, `api_key_path`, and `prefix_path_pairs` fields, THE Import_Config SHALL validate that `storage_id` is non-empty, `api_key_path` starts with `/`, and `prefix_path_pairs` contains at least one entry
3. IF a required configuration field is missing or invalid, THEN THE Import_Config SHALL raise a validation error with a message identifying the invalid field
8. THE `storage_id` SHALL identify a Flywheel storage that corresponds to the S3 bucket containing all `s3_prefix` paths in the prefix-path pairs (e.g., a storage pointing at `s3://naccquickaccess` for prefixes like `centers/1florida`). The `s3_prefix` values are paths relative to the storage bucket root.
4. WHEN a Prefix_Path_Pair entry omits `include_patterns` and `exclude_patterns`, THE Import_Config SHALL default both to empty lists, meaning no filtering is applied
5. WHEN a Prefix_Path_Pair entry specifies both `include_patterns` and `exclude_patterns`, THE Import_Config SHALL accept the configuration and apply include patterns first, then exclude patterns
6. WHEN a Lambda event contains an optional `dry_run` field set to true, THE Import_Config SHALL set the dry run flag so that no Flywheel API import calls are executed
7. WHEN a Lambda event contains an optional `aws_profile` field, THE Import_Config SHALL pass the profile name to the boto3 session for S3 and SSM access

### Requirement 2: Flywheel API Key Retrieval

**User Story:** As a pipeline operator, I want the Lambda to retrieve the Flywheel API key from AWS SSM Parameter Store, so that credentials are managed securely and not embedded in the Lambda configuration.

#### Acceptance Criteria

1. WHEN the Lambda starts execution with a valid Import_Config, THE Lambda SHALL retrieve the Flywheel API key from SSM Parameter Store using the path specified in `api_key_path`
2. IF the SSM parameter is not found at the specified path, THEN THE Lambda SHALL return an Import_Result with status "failed", error_type "AuthenticationError", and a message identifying the missing parameter path
3. IF the Lambda IAM role lacks permission to read the SSM parameter, THEN THE Lambda SHALL return an Import_Result with status "failed", error_type "AuthenticationError", and a message indicating insufficient permissions

### Requirement 3: Client Handler Initialization

**User Story:** As a pipeline operator, I want the Lambda to initialize a Flywheel client using the retrieved API key and storage configuration, so that subsequent import operations have authenticated access to both Flywheel and S3.

#### Acceptance Criteria

1. WHEN the API key is retrieved successfully, THE Client_Handler SHALL initialize a Flywheel SDK client (`FWClient`) with the API key and retrieve the Storage_Config from Flywheel using the `storage_id`
2. WHEN the Client_Handler is initialized, THE Client_Handler SHALL create a boto3 S3 resource using the bucket name from the Storage_Config and the optional `aws_profile`
3. THE Client_Handler SHALL expose the storage prefix and provider ID from the Storage_Config as read-only properties
4. IF the Flywheel storage configuration retrieval fails, THEN THE Lambda SHALL return an Import_Result with status "failed" and error_type "SDKError"

### Requirement 4: S3 Object Listing and Filtering

**User Story:** As a pipeline operator, I want each prefix-path pair to list and filter S3 objects under its prefix, so that only the intended files are imported into the target Flywheel project.

#### Acceptance Criteria

1. WHEN processing a Prefix_Path_Pair, THE Client_Handler SHALL list all S3 objects under the `s3_prefix` path within the storage bucket
2. WHEN a Prefix_Path_Pair specifies `include_patterns`, THE Client_Handler SHALL yield only objects whose S3 key contains at least one of the include pattern substrings
3. WHEN a Prefix_Path_Pair specifies `exclude_patterns`, THE Client_Handler SHALL skip objects whose S3 key contains any of the exclude pattern substrings
4. WHEN a Prefix_Path_Pair specifies both `include_patterns` and `exclude_patterns`, THE Client_Handler SHALL first filter to objects matching any include pattern, then remove objects matching any exclude pattern
5. WHEN an S3 object has a size of zero bytes, THE Client_Handler SHALL skip the object as it represents a directory marker
6. THE Client_Handler SHALL use lazy iteration (generator) when yielding filtered S3 objects to minimize memory usage

### Requirement 5: Copy-by-Reference Import

**User Story:** As a pipeline operator, I want each matched S3 file to be imported into Flywheel via copy-by-reference, so that files are registered in Flywheel without transferring the actual data.

#### Acceptance Criteria

1. WHEN importing a file, THE Client_Handler SHALL look up the Flywheel project ID using `POST /xfer/upload/lookup` with the `fw_group` and `fw_project` from the Prefix_Path_Pair
2. WHEN importing a file, THE Client_Handler SHALL create an Upload_Ticket via `POST /xfer/upload` with the project ID, file name, file path relative to the storage prefix, file size, provider ID, and `reference: true`
3. WHEN an Upload_Ticket is created, THE Client_Handler SHALL finalize the import by posting to the ticket `finish_url`
4. IF the Upload_Ticket response does not contain `reference: true`, THEN THE Client_Handler SHALL raise an error indicating the import did not create a reference
5. WHILE `dry_run` is enabled, THE Client_Handler SHALL log the intended import operation and skip the Flywheel API calls for upload ticket creation and finalization

### Requirement 6: Per-Pair Import Orchestration

**User Story:** As a pipeline operator, I want each prefix-path pair to be processed independently with per-file error tracking, so that a failure in one file does not prevent the remaining files or pairs from being imported.

#### Acceptance Criteria

1. WHEN processing a Prefix_Path_Pair, THE Lambda SHALL import each filtered S3 object into the target Flywheel project and track the count of successfully imported files
2. IF a single file import fails, THEN THE Lambda SHALL log the error with the file key and error message, record the failure in the Pair_Import_Result, and continue processing the remaining files
3. WHEN all files for a Prefix_Path_Pair are processed, THE Lambda SHALL produce a Pair_Import_Result containing the project label, duration, successful file count, failed file list, and the filter patterns used
4. WHEN processing multiple Prefix_Path_Pairs, THE Lambda SHALL process each pair sequentially and continue to the next pair even if the current pair encounters an error during project lookup or filtering

### Requirement 7: Structured Result Reporting

**User Story:** As a pipeline operator, I want the Lambda to return a structured result with per-pair metrics and aggregate totals, so that I can monitor import outcomes and diagnose failures.

#### Acceptance Criteria

1. WHEN all Prefix_Path_Pairs are processed successfully, THE Lambda SHALL return an Import_Result with status "success", a list of Pair_Import_Results, total duration, and total file count
2. THE Import_Result SHALL validate that `total_file_count` equals the sum of `file_count` from all Pair_Import_Results
3. WHEN a configuration validation error occurs, THE Lambda SHALL return an Import_Result with status "failed", error_type "ConfigurationError", and the validation error message
4. WHEN a Flywheel API error occurs, THE Lambda SHALL return an Import_Result with status "failed", error_type "SDKError", and the API error message
5. WHEN an unexpected error occurs, THE Lambda SHALL return an Import_Result with status "failed", error_type "UnexpectedError", and the error message with stack trace context
6. THE Import_Result SHALL serialize to a dictionary containing `status`, `pair_results`, `total_duration`, `total_file_count`, `error_message`, `error_type`, and `context` fields

### Requirement 8: Monorepo Structure Compliance

**User Story:** As a developer, I want the Lambda to follow the Pants monorepo conventions, so that it integrates with the existing build, test, and packaging workflows.

#### Acceptance Criteria

1. THE Lambda SHALL be structured under `lambda/s3_import/src/python/s3_import_lambda/` with a `BUILD` file defining `python_sources`, `python_aws_lambda_function`, and `python_aws_lambda_layer` targets
2. THE Lambda SHALL place shared modules (Client_Handler, models) under `common/src/python/` with their own `BUILD` files defining `python_sources` targets
3. THE Lambda SHALL place tests under `lambda/s3_import/test/python/` and `common/test/python/` with `BUILD` files defining `python_tests` targets
4. THE Lambda SHALL use Python 3.12 as the runtime for both the `python_aws_lambda_function` and `python_aws_lambda_layer` targets
5. THE Lambda layer SHALL declare dependencies on shared common modules via `//common/src/python/<module>:lib` and external packages via `//:root#<package>`

### Requirement 9: Logging and Observability

**User Story:** As a pipeline operator, I want the Lambda to produce structured logs at each stage of execution, so that I can trace the import process and diagnose issues in CloudWatch.

#### Acceptance Criteria

1. WHEN the Lambda starts, THE Lambda SHALL log the Lambda request ID, function name, memory limit, and the received event
2. WHEN processing each Prefix_Path_Pair, THE Lambda SHALL log the pair index, S3 prefix, target Flywheel group/project, and filter patterns
3. WHEN importing each file, THE Lambda SHALL log the file key, file size, and target project ID
4. WHEN a file import succeeds, THE Lambda SHALL log a success message with the file key
5. WHEN a file import fails, THE Lambda SHALL log an error message with the file key and error details
6. WHEN all processing completes, THE Lambda SHALL log a summary with total pairs processed, total files imported, total failures, and total execution time
