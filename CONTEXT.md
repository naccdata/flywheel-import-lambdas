# Context: Generalizing the S3-to-Flywheel Import Lambda

## Goal

Create a generalized AWS Lambda in this repo that imports files from S3 into Flywheel projects via copy-by-reference. The implementation should be extracted and generalized from the existing lambda at `naccdata/loni-table-data` in the `s3-flywheel-import/` directory.

The existing lambda is tightly coupled to the LONI data pipeline. The generalized version should work for any S3 bucket and any set of Flywheel projects, not just LONI.

## Source Lambda Overview

A reference copy of the source lambda is included in this repo at `reference/s3-flywheel-import/`. The original lives in the `naccdata/loni-table-data` GitHub repo under `s3-flywheel-import/`. It is a SAM-deployed Docker-based Python 3.12 Lambda.

> The `reference/` directory is not part of the project — it exists solely as context for the refactor. It should be removed once the generalized lambda is implemented.

### What it does

1. Reads configuration from the Lambda event (or environment variables)
2. Retrieves a Flywheel API key from AWS SSM Parameter Store
3. Initializes a `ClientHandler` that wraps `fw-client` (Flywheel Python SDK) and `boto3` S3 access
4. For each configured "study":
   - Looks up the Flywheel project ID by group + label
   - Lists S3 objects under the Flywheel storage prefix
   - Filters objects by include/exclude substring pattern
   - Imports each file into Flywheel via the two-step upload ticket process (copy-by-reference, no data transfer)
5. Returns structured results with per-study metrics and error tracking

### Key components (all in `reference/s3-flywheel-import/`)

- `models.py` — `StudyConfig`, `ImportConfig`, `StudyImportResult`, `ImportResult` dataclasses. `ImportConfig.from_event()` parses the Lambda event with legacy format support.
- `client_handler.py` — `ClientHandler` class wrapping `FWClient` and `boto3`. Methods: `get_project_id()`, `filter_objects()`, `import_to_flywheel()`.
- `import_operations.py` — `import_study_metadata()` orchestrates the import for a single study config.
- `s3_flywheel_import.py` — Lambda handler (`main`). Parses config, gets API key from SSM, initializes `ClientHandler`, loops over studies, returns results.
- `tests/` — Unit tests for all modules.

### Dependencies

- `fw-client>=0.1.0` — Flywheel Python SDK (uses `FWClient`, HTTP-based)
- `boto3>=1.34.0` — AWS SDK (S3 object listing, SSM parameter retrieval)
- `awslambdaric>=2.0.0` — AWS Lambda runtime interface client (for Docker-based lambdas)

### Flywheel API calls used

- `GET /xfer/storages/{storage_id}` — get storage config (bucket name, prefix, provider ID)
- `POST /xfer/upload/lookup` — look up project ID by group + label
- `POST /xfer/upload` — create upload ticket for copy-by-reference
- `POST {finish_url}` — finalize the upload

### LONI-specific things to generalize

- The `ImportConfig.from_event()` has a legacy format path for `scan_project_label` / `clariti_project_label` / `clariti_pattern` — this is LONI-specific and can be dropped.
- Environment variable defaults reference LONI-specific values (storage ID, group "loni", SSM path).
- The SAM template (`template.yml`) hardcodes LONI-specific IAM policies, VPC config, and environment variables.
- S3 bucket IAM policy is scoped to `loni-table-data` bucket.

### What should stay generic

- The `ClientHandler` class is already fairly generic — it just needs the API key, storage ID, and optional AWS profile.
- The `StudyConfig` / study-based filtering model is generic.
- The two-step upload ticket flow for copy-by-reference is the core reusable logic.
- The structured result/error reporting pattern is good.

## This Repo Structure

This repo was created from `naccdata/lambda-monorepo-template`. It uses:

- **Pants** build system (`pants.toml`, `BUILD` files)
- **Devcontainer** for development (`.devcontainer/`)
- **Terraform** for infrastructure (see `templates/lambda-example/` in the template repo for patterns)
- **Kiro Pants Power** for build automation (`.kiro/settings/mcp.json`)

### Current layout

```
flywheel-import-lambdas/
├── .devcontainer/          # Dev container config
├── .kiro/settings/         # Kiro MCP settings (pants power)
├── bin/                    # Dev scripts (build, start, stop, terminal, exec, set-venv)
├── docs/                   # Template documentation
├── examples/               # Example lambda implementations
│   ├── simple-lambda/      # Basic lambda pattern
│   ├── database-lambda/    # Lambda with DB connectivity
│   └── common/             # Shared code example
├── BUILD                   # Root Pants BUILD file
├── get-pants.sh            # Pants installer
├── pants.toml              # Pants configuration
├── requirements.txt        # Python dependencies
└── ruff.toml               # Ruff linter config
```

### How lambdas are structured in this monorepo

Following the template pattern, each lambda lives under a `lambda/` directory:

```
lambda/<lambda_name>/
├── src/python/<lambda_name>_lambda/
│   ├── BUILD
│   └── lambda_function.py
├── test/python/
│   ├── BUILD
│   └── test_lambda_function.py
└── main.tf                 # Terraform for this lambda
```

Shared code goes in `common/src/python/<module>/`.

## What Needs to Happen

1. Extract the core copy-by-reference logic from the LONI lambda into a generalized lambda in this repo
2. Drop LONI-specific configuration and legacy format support
3. Structure it to follow the Pants monorepo conventions (BUILD files, source roots, etc.)
4. The `ClientHandler` and upload ticket flow are the core pieces to preserve
5. Configuration should be generic: any S3 bucket, any Flywheel group/project, any SSM path for the API key
6. Terraform should be parameterized rather than hardcoded to LONI resources
