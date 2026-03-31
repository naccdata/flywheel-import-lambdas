"""Pydantic data models for S3 Flywheel Import Lambda function."""

from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class PrefixPathPair(BaseModel):
    """A single S3-prefix-to-Flywheel-project mapping.

    Maps an S3 prefix (relative to the storage bucket root) to a
    Flywheel group/project destination, with optional include/exclude
    substring filters.
    """

    s3_prefix: str
    """S3 path relative to storage bucket root."""

    fw_group: str
    """Flywheel group name."""

    fw_project: str
    """Flywheel project label."""

    include_patterns: list[str] = []
    """Substring include filters."""

    exclude_patterns: list[str] = []
    """Substring exclude filters."""

    @field_validator("s3_prefix")
    @classmethod
    def normalize_s3_prefix(cls, v: str) -> str:
        """Normalize s3_prefix: strip whitespace, allow empty (bucket root)."""
        return v.strip()

    @field_validator("fw_group", "fw_project")
    @classmethod
    def must_be_non_empty(cls, v: str) -> str:
        """Validate that string fields are non-empty."""
        if not v or not v.strip():
            raise ValueError("must be a non-empty string")
        return v


class ImportConfig(BaseModel):
    """Configuration for the full Lambda event payload.

    Contains the storage ID, SSM path for the API key, and a list of
    prefix-path pairs defining the S3-to-Flywheel mappings.
    """

    storage_id: str
    """Flywheel storage ID (identifies S3 bucket)."""

    api_key_path: str
    """SSM parameter path (must start with '/')."""

    prefix_path_pairs: list[PrefixPathPair]
    """At least one pair required."""

    dry_run: bool = False
    """Skip Flywheel API calls when True."""

    aws_profile: str | None = None
    """Optional boto3 profile name."""

    @field_validator("storage_id")
    @classmethod
    def storage_id_non_empty(cls, v: str) -> str:
        """Validate that storage_id is non-empty."""
        if not v or not v.strip():
            raise ValueError("storage_id must be a non-empty string")
        return v

    @field_validator("api_key_path")
    @classmethod
    def api_key_path_must_start_with_slash(cls, v: str) -> str:
        """Validate that api_key_path starts with '/'."""
        if not v.startswith("/"):
            raise ValueError("api_key_path must start with '/'")
        return v

    @field_validator("prefix_path_pairs")
    @classmethod
    def at_least_one_pair(cls, v: list[PrefixPathPair]) -> list[PrefixPathPair]:
        """Validate that at least one prefix-path pair is provided."""
        if not v:
            raise ValueError("prefix_path_pairs must contain at least one entry")
        return v


class TicketFile(BaseModel):
    """File metadata within an upload ticket response."""

    reference: bool = False
    """Whether the upload is a copy-by-reference."""


class UploadTicket(BaseModel):
    """Parsed response from POST /xfer/upload.

    Normalizes the Flywheel API response (which may be a dict or an
    object with attributes) into a typed model for clean access.
    """

    model_config = {"populate_by_name": True}

    id: str | None = Field(default=None, alias="_id")
    """Ticket identifier."""

    finish_url: str | None = None
    """URL to POST to finalize the upload."""

    file: TicketFile = TicketFile()
    """File metadata from the ticket response."""

    @staticmethod
    def from_response(response: Any) -> "UploadTicket":
        """Build an UploadTicket from a raw API response.

        Handles both dict-like and object-like responses from FWClient.
        """
        if isinstance(response, dict):
            return UploadTicket(**response)

        data: dict[str, Any] = {}
        for field_name in ("_id", "finish_url", "file"):
            if hasattr(response, field_name):
                val = getattr(response, field_name)
                if hasattr(val, "__dict__"):
                    val = vars(val)
                data[field_name] = val
        return UploadTicket(**data)


class PairImportResult(BaseModel):
    """Result of importing files for a single PrefixPathPair.

    Tracks the target project, duration, file count, any per-file
    failures, and the filter patterns that were applied.
    """

    fw_project: str
    """Target project label."""

    duration: float
    """Seconds elapsed (must be >= 0)."""

    file_count: int
    """Number of successfully imported files (must be >= 0)."""

    failed_files: list[dict[str, str]] = []
    """List of failed files, each with 'key' and 'error'."""

    include_patterns: list[str] = []
    """Include patterns used."""

    exclude_patterns: list[str] = []
    """Exclude patterns used."""

    @field_validator("duration")
    @classmethod
    def duration_non_negative(cls, v: float) -> float:
        """Validate that duration is non-negative."""
        if v < 0:
            raise ValueError(f"duration must be non-negative, got: {v}")
        return v

    @field_validator("file_count")
    @classmethod
    def file_count_non_negative(cls, v: int) -> int:
        """Validate that file_count is non-negative."""
        if v < 0:
            raise ValueError(f"file_count must be non-negative, got: {v}")
        return v


class ImportResult(BaseModel):
    """Overall Lambda response for the import operation.

    Contains the status, per-pair results, aggregate totals, and
    optional error information.
    """

    status: str
    """Execution status: 'success' or 'failed'."""

    pair_results: list[PairImportResult] = []
    """Results for each pair import."""

    total_duration: float = 0.0
    """Total execution duration in seconds."""

    total_file_count: int = 0
    """Total files imported across all pairs."""

    error_message: str | None = None
    """Error message if status is 'failed'."""

    error_type: str | None = None
    """Error classification (e.g. ConfigurationError, SDKError)."""

    context: dict[str, Any] | None = None
    """Additional context information about the error."""

    @model_validator(mode="after")
    def validate_total_file_count(self) -> "ImportResult":
        """Validate that total_file_count equals sum of pair file_counts."""
        expected = sum(r.file_count for r in self.pair_results)
        if self.total_file_count != expected:
            raise ValueError(
                f"total_file_count ({self.total_file_count}) must equal sum of "
                f"file_count from all pair_results ({expected})"
            )
        return self
