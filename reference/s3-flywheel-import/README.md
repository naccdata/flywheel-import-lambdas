# S3 Flywheel Import Lambda

Lambda function for automated copy-by-reference operations from S3 to Flywheel projects using the Flywheel Python SDK.

## Overview

This Lambda function integrates into the NACC LONI Data Pipeline, executing after LONITableData pulls fresh data to S3. It uses the `fw-client` Python SDK to import data into Flywheel projects via copy-by-reference, eliminating subprocess overhead and providing better error handling.

The function supports multiple study configurations and can import data into any number of Flywheel projects with flexible include/exclude filtering.

## Architecture

### SDK-Based Implementation

The refactored implementation uses:
- **ClientHandler**: Manages Flywheel API and AWS S3 interactions
- **FWClient SDK**: Direct API calls to Flywheel (no CLI subprocess calls)
- **Copy-by-Reference**: Files are imported by reference without data transfer
- **Generic Study Configuration**: Supports any number of studies without code changes

### Components

- `models.py` - Data models (StudyConfig, ImportConfig, ImportResult)
- `client_handler.py` - ClientHandler class for Flywheel/AWS operations
- `import_operations.py` - Import functions (import_study_metadata)
- `s3_flywheel_import.py` - Lambda handler (main function)

### Runtime Details

- **Runtime**: Python 3.12
- **Package Type**: Docker Image
- **Memory**: 512 MB
- **Timeout**: 900 seconds (15 minutes)
- **VPC**: Runs in VPC with security group sg-0503342ee72448012

## Configuration

### New Format (Recommended)

Configure multiple studies with flexible filtering:

```json
{
  "storage_id": "691c926ff8220b709983b848",
  "group": "loni",
  "api_key_path": "/flywheel/api-key",
  "studies": [
    {
      "project_label": "scan-metadata",
      "filter_pattern": "clariti",
      "filter_mode": "exclude"
    },
    {
      "project_label": "clariti-metadata",
      "filter_pattern": "clariti",
      "filter_mode": "include"
    }
  ]
}
```

**Configuration Parameters:**

- `storage_id` - Flywheel storage instance identifier
- `group` - Flywheel group name (e.g., "loni")
- `api_key_path` - SSM Parameter Store path for Flywheel API key
- `studies` - List of study configurations:
  - `project_label` - Flywheel project label (e.g., "scan-metadata")
  - `filter_pattern` - Path substring to filter files (e.g., "clariti")
  - `filter_mode` - Either "include" (only matching files) or "exclude" (all except matching)

### Legacy Format (Backward Compatible)

The function still supports the original configuration format:

```json
{
  "storage_id": "691c926ff8220b709983b848",
  "group": "loni",
  "api_key_path": "/flywheel/api-key",
  "scan_project_label": "scan-metadata",
  "clariti_project_label": "clariti-metadata",
  "clariti_pattern": "clariti"
}
```

This is automatically converted to the new format with two studies (SCAN with exclude mode, CLARITI with include mode).

### Environment Variables

Configuration can also be provided via environment variables (configured in template.yml):

- `STORAGE_ID` - Flywheel storage instance identifier
- `GROUP` - Flywheel group name
- `API_KEY_PATH` - SSM parameter path for Flywheel API key

Event parameters override environment variables.

### Dry Run Mode

Test configuration without executing imports:

```json
{
  "storage_id": "691c926ff8220b709983b848",
  "group": "loni",
  "api_key_path": "/flywheel/api-key",
  "studies": [...],
  "dry_run": true
}
```

When `dry_run` is `true`:
- All operations are logged but not executed
- No Flywheel API calls are made
- Returns success status with file_count of zero
- Useful for validating configuration and testing logic

## Development

### Setup

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv sync

# Generate requirements.txt for SAM build
uv pip compile pyproject.toml -o requirements.txt
```

### Code Quality

```bash
# Format code
uv run ruff format .

# Lint code
uv run ruff check .

# Type check
uv run mypy .

# Run tests with coverage
uv run pytest --cov=. --cov-report=html
```

### Local Testing

Create a test event file (`test-event.json`):

```json
{
  "storage_id": "691c926ff8220b709983b848",
  "group": "loni",
  "api_key_path": "/flywheel/api-key",
  "studies": [
    {
      "project_label": "scan-metadata",
      "filter_pattern": "clariti",
      "filter_mode": "exclude"
    },
    {
      "project_label": "clariti-metadata",
      "filter_pattern": "clariti",
      "filter_mode": "include"
    }
  ],
  "dry_run": true
}
```

Test locally with SAM CLI (requires Docker):

```bash
# Build Docker image
sam build

# Invoke locally with test event
sam local invoke -e test-event.json
```

**Note**: Local testing requires:
- Docker running
- AWS credentials configured
- Access to SSM Parameter Store
- VPC connectivity (if testing against real Flywheel API)

### Build and Deploy

```bash
# Build Docker image
sam build

# Deploy to AWS
sam deploy
```

The deployment uses the configuration in `samconfig.toml`.

## ClientHandler Usage

The `ClientHandler` class encapsulates all Flywheel and AWS operations:

```python
from client_handler import ClientHandler

# Initialize with API key and storage ID
client = ClientHandler(
    fw_api_key="your-api-key",
    fw_storage_id="691c926ff8220b709983b848",
    dry_run=False
)

# Lookup project ID
project_id = client.get_project_id(group="loni", label="scan-metadata")

# Filter S3 objects (exclude pattern)
for obj in client.filter_objects(exclude_pattern="clariti"):
    # Import file to Flywheel
    result = client.import_to_flywheel(project_id, obj)
```

**Key Methods:**

- `get_project_id(group, label)` - Lookup Flywheel project ID by group/label
- `filter_objects(include_pattern, exclude_pattern)` - Filter S3 objects by pattern
- `import_to_flywheel(project_id, file)` - Import file via copy-by-reference

## Result Structure

The function returns structured results with detailed metrics:

```json
{
  "status": "success",
  "study_results": [
    {
      "project_label": "scan-metadata",
      "duration": 45.2,
      "file_count": 150,
      "filter_pattern": "clariti",
      "filter_mode": "exclude"
    },
    {
      "project_label": "clariti-metadata",
      "duration": 12.8,
      "file_count": 50,
      "filter_pattern": "clariti",
      "filter_mode": "include"
    }
  ],
  "total_duration": 58.0,
  "total_file_count": 200
}
```

On error:

```json
{
  "status": "failed",
  "study_results": [...],
  "total_duration": 30.5,
  "total_file_count": 100,
  "error_message": "Project not found: loni/invalid-project",
  "error_type": "SDKError"
}
```

**Error Types:**
- `ConfigurationError` - Invalid configuration parameters
- `AuthenticationError` - SSM parameter not found or access denied
- `SDKError` - Flywheel API error
- `UnexpectedError` - Other unexpected errors

## Migration from CLI-Based Implementation

The SDK-based implementation provides several improvements over the CLI-based version:

- **Performance**: No subprocess overhead, direct API calls
- **Error Handling**: Structured error responses with detailed context
- **Extensibility**: Generic study configuration supports any number of projects
- **Observability**: File-level tracking and per-study metrics
- **Maintainability**: Cleaner code structure with separate modules
- **Testing**: Better testability with mockable SDK clients

The function maintains backward compatibility with existing configurations, so no immediate changes are required for deployment.
