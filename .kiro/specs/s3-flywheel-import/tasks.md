# Implementation Plan: S3 Flywheel Import Lambda

## Overview

Implement a generalized S3-to-Flywheel copy-by-reference Lambda by extracting and adapting the reference implementation into the Pants monorepo structure. Shared modules (models, client handler) go in `common/src/python/`, the Lambda handler and orchestration go in `lambda/s3_import/`. Reuse reference code as much as possible, replacing dataclasses with Pydantic and generalizing the configuration model.

## Tasks

- [x] 1. Create Pydantic models in common
  - [x] 1.1 Create `common/src/python/s3_import_models/models.py` with `PrefixPathPair`, `ImportConfig`, `PairImportResult`, and `ImportResult` Pydantic models
    - Adapt from `reference/s3-flywheel-import/models.py`, replacing dataclasses with Pydantic BaseModel
    - `PrefixPathPair`: `s3_prefix`, `fw_group`, `fw_project`, `include_patterns: list[str] = []`, `exclude_patterns: list[str] = []`
    - `ImportConfig`: `storage_id`, `api_key_path` (must start with `/`), `prefix_path_pairs` (min 1), `dry_run: bool = False`, `aws_profile: str | None = None`
    - `PairImportResult`: `fw_project`, `duration >= 0`, `file_count >= 0`, `failed_files`, `include_patterns`, `exclude_patterns`
    - `ImportResult`: `status`, `pair_results`, `total_duration`, `total_file_count` (validated as sum of pair file_counts), `error_message`, `error_type`, `context`
    - Create `common/src/python/s3_import_models/BUILD` with `python_sources(name="lib")`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 7.1, 7.2, 7.6_

  - [x] 1.2 Write unit tests for Pydantic models
    - Create `common/test/python/test_models.py` and `common/test/python/BUILD`
    - Test valid construction, default values, validation errors for missing/invalid fields
    - Test `ImportResult.total_file_count` sum validation
    - Test `PrefixPathPair` defaults for empty pattern lists
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 7.2_

  - [x] 1.3 Write property test: ImportConfig round-trip parsing
    - Create `common/test/python/test_model_properties.py`
    - **Property 1: ImportConfig round-trip parsing**
    - Use Hypothesis to generate valid ImportConfig instances, serialize to dict, parse back, assert equivalence
    - **Validates: Requirements 1.1**

  - [ ]* 1.4 Write property test: ImportConfig validation rejects invalid configs
    - **Property 2: ImportConfig validation rejects invalid configs with identifying messages**
    - Generate configs with empty `storage_id`, invalid `api_key_path`, or empty `prefix_path_pairs`; assert ValidationError with field name in message
    - **Validates: Requirements 1.2, 1.3**

  - [ ]* 1.5 Write property test: Total file count aggregation invariant
    - **Property 7: Total file count aggregation invariant**
    - Generate list of `PairImportResult` instances, construct `ImportResult` with mismatched `total_file_count`, assert validation error
    - **Validates: Requirements 7.2**

  - [ ]* 1.6 Write property test: ImportResult serialization completeness
    - **Property 8: ImportResult serialization completeness**
    - Generate valid `ImportResult` instances, call `model_dump()`, assert all required keys present
    - **Validates: Requirements 7.1, 7.6**

- [x] 2. Create ClientHandler in common
  - [x] 2.1 Create `common/src/python/flywheel_client/client_handler.py` with the `ClientHandler` class
    - Adapt from `reference/s3-flywheel-import/client_handler.py`
    - `__init__`: Initialize FWClient, retrieve storage config, create S3 bucket resource
    - Properties: `fw_storage_prefix`, `fw_provider_id`
    - `get_project_id(group, label)`: POST `/xfer/upload/lookup`
    - `filter_objects(s3_prefix, include_patterns, exclude_patterns)`: List objects under `s3_prefix`, skip zero-byte, apply include-first-then-exclude filtering with pattern lists
    - `import_to_flywheel(project_id, file)`: Two-step upload ticket flow, dry_run support
    - Create `common/src/python/flywheel_client/BUILD` with `python_sources(name="lib")`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 5.1, 5.2, 5.3, 5.4, 5.5_

  - [x] 2.2 Write unit tests for ClientHandler
    - Create `common/test/python/test_client_handler.py`
    - Mock FWClient and boto3; test init wiring, `get_project_id`, `filter_objects` with various pattern combos, `import_to_flywheel` ticket flow, dry_run behavior
    - _Requirements: 3.1, 3.2, 3.3, 4.1, 4.2, 4.3, 4.4, 4.5, 5.1, 5.2, 5.3, 5.4, 5.5_

  - [x] 2.3 Write property test: S3 object filtering correctness
    - **Property 3: S3 object filtering correctness**
    - Use Hypothesis to generate lists of mock S3 objects with varying keys/sizes, include/exclude pattern lists
    - Assert: all yielded objects have size > 0, include patterns respected, exclude patterns respected, include-first-then-exclude ordering
    - **Validates: Requirements 4.2, 4.3, 4.4, 4.5**

  - [ ]* 2.4 Write property test: Dry run skips Flywheel import API calls
    - **Property 4: Dry run skips Flywheel import API calls**
    - Mock FWClient, set dry_run=True, call import_to_flywheel with generated file objects, assert no upload/finalize calls made
    - **Validates: Requirements 5.5**

- [x] 3. Create Lambda handler and import operations
  - [x] 3.1 Create `lambda/s3_import/src/python/s3_import_lambda/import_operations.py` with `import_pair_files` function
    - Adapt from `reference/s3-flywheel-import/import_operations.py`
    - Accept `ClientHandler` and `PrefixPathPair`, return `PairImportResult`
    - Look up project ID, filter objects, import each file with per-file error tracking
    - Log pair index, prefix, group/project, filter patterns, per-file key/size/result
    - _Requirements: 6.1, 6.2, 6.3, 9.2, 9.3, 9.4, 9.5_

  - [x] 3.2 Create `lambda/s3_import/src/python/s3_import_lambda/lambda_function.py` with `lambda_handler` and `get_api_key`
    - Adapt from `reference/s3-flywheel-import/s3_flywheel_import.py`
    - `get_api_key(api_key_path, aws_profile)`: Retrieve API key from SSM, raise RuntimeError on failure
    - `lambda_handler(event, context)`: Parse ImportConfig (Pydantic), retrieve API key, init ClientHandler, loop over pairs calling `import_pair_files`, return ImportResult.model_dump()
    - Error handling: ValidationError → ConfigurationError, SSM errors → AuthenticationError, HTTPError → SDKError, Exception → UnexpectedError
    - Log Lambda request ID, function name, memory limit, event at start; summary at end
    - Pair-level fault isolation: continue to next pair on failure
    - Create `lambda/s3_import/src/python/s3_import_lambda/BUILD` with `python_sources`, `python_aws_lambda_function`, `python_aws_lambda_layer` targets
    - _Requirements: 2.1, 2.2, 2.3, 6.4, 7.1, 7.3, 7.4, 7.5, 8.1, 8.4, 8.5, 9.1, 9.6_

  - [x] 3.3 Write unit tests for import_operations
    - Create `lambda/s3_import/test/python/test_import_operations.py` and `lambda/s3_import/test/python/BUILD`
    - Create `lambda/s3_import/test/python/conftest.py` with shared fixtures (mock ClientHandler, mock S3 objects)
    - Test single pair import, partial file failures, empty result sets
    - _Requirements: 6.1, 6.2, 6.3_

  - [x] 3.4 Write unit tests for lambda_function
    - Create `lambda/s3_import/test/python/test_lambda_function.py`
    - Test end-to-end handler flow with mocked dependencies
    - Test error classification: ConfigurationError, AuthenticationError, SDKError, UnexpectedError
    - Test pair-level fault isolation (one pair fails, others succeed)
    - Test `get_api_key` SSM retrieval and error handling
    - _Requirements: 2.1, 2.2, 2.3, 6.4, 7.1, 7.3, 7.4, 7.5_

  - [x] 3.5 Write property test: Import pair result tracks counts and failures
    - Create `lambda/s3_import/test/python/test_properties.py`
    - **Property 5: Import pair result tracks counts and failures correctly**
    - Mock ClientHandler where a known subset of imports fail, assert file_count = successes, failed_files = failures, all files attempted
    - **Validates: Requirements 6.1, 6.2, 6.3**

  - [ ]* 3.6 Write property test: Pair-level fault isolation
    - **Property 6: Pair-level fault isolation**
    - Generate list of PrefixPathPair entries, mock some to fail during project lookup, assert remaining pairs still processed and results returned
    - **Validates: Requirements 6.4**

- [x] 4. Wire BUILD files and dependencies
  - [x] 4.1 Create `common/src/python/s3_import_models/__init__.py` and `common/src/python/flywheel_client/__init__.py`
    - Ensure packages are importable
    - _Requirements: 8.2_

  - [x] 4.2 Create `lambda/s3_import/src/python/s3_import_lambda/__init__.py`
    - Ensure package is importable
    - _Requirements: 8.1_

  - [x] 4.3 Verify all BUILD files have correct dependencies
    - Lambda BUILD: dependencies on `//common/src/python/s3_import_models:lib`, `//common/src/python/flywheel_client:lib`, `//:root#boto3`, `//:root#pydantic`, `//:root#fw-client`, `//:root#aws-lambda-powertools`
    - Test BUILD files: dependencies on source targets and `//:root#pytest`
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [x] 4.4 Add `hypothesis>=6.100.0` to `requirements.txt`
    - Required for property-based tests
    - _Requirements: 8.3_

## Notes

- **IMPORTANT**: Use the `kiro-pants-power` MCP tools for all build, lint, check, and test operations. Do not use manual `./bin/exec-in-devcontainer.sh` commands. The power automatically manages the devcontainer lifecycle.
- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- Reuse reference implementation code as much as possible — it's battle-tested
- The reference directory will be removed once the new lambda is complete
