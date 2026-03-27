# Product Overview

Flywheel Import Lambdas is a Pants-managed monorepo containing AWS Lambda functions for importing files from S3 into Flywheel projects via copy-by-reference.

## Core Functionality

- **S3-to-Flywheel Import**: Copies files from S3 buckets into Flywheel projects using the copy-by-reference upload ticket flow (no data transfer)
- **Study-Based Configuration**: Each import run processes one or more "studies", each mapping an S3 prefix + filter pattern to a Flywheel group/project
- **SSM Parameter Store Integration**: Retrieves Flywheel API keys securely from AWS SSM
- **Structured Result Reporting**: Returns per-study metrics and error tracking

## Key Components

- **Lambda Functions**: Located under `lambda/` — each lambda has its own directory with source, tests, and Terraform
- **Common Libraries**: Shared code under `common/src/python/` — reusable modules across lambdas (e.g., Flywheel client handler, S3 operations, models)
- **Reference Implementation**: `reference/s3-flywheel-import/` contains the original LONI-specific lambda being generalized (for context only, not part of the build)

## Flywheel API Flow

The core import logic uses a two-step upload ticket process:
1. `POST /xfer/upload/lookup` — look up project ID by group + label
2. `POST /xfer/upload` — create upload ticket for copy-by-reference
3. `POST {finish_url}` — finalize the upload

## Key Dependencies

- `fw-client` — Flywheel Python SDK (HTTP-based)
- `boto3` — AWS SDK (S3 listing, SSM parameter retrieval)
- `pydantic` — Data validation and configuration models
- `aws-lambda-powertools` — Logging, tracing, and Lambda utilities

## Target Users

NACC teams and developers building data import pipelines that move files from S3 into Flywheel.
