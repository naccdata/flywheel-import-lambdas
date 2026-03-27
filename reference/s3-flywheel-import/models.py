"""Data models for S3 Flywheel Import Lambda function."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class StudyConfig:
    """Configuration for a single study import."""

    project_label: str
    """Flywheel project label (e.g., "scan-metadata", "clariti-metadata")"""

    filter_pattern: str
    """Path filter pattern for this study's data (e.g., "scan", "clariti")"""

    filter_mode: str = "include"
    """Filter mode: "include" (only files matching pattern) or
    "exclude" (all files except pattern)"""

    def validate(self) -> None:
        """
        Validate study configuration.

        Raises
        ------
        ValueError
            If project_label is empty, filter_pattern is empty, or
            filter_mode is invalid
        """
        if not self.project_label:
            raise ValueError("project_label is required and cannot be empty")
        if not self.filter_pattern:
            raise ValueError("filter_pattern is required and cannot be empty")
        if self.filter_mode not in ("include", "exclude"):
            raise ValueError(
                f"filter_mode must be 'include' or 'exclude', got: {self.filter_mode}"
            )


@dataclass
class ImportConfig:
    """Configuration for S3 to Flywheel import operations."""

    storage_id: str
    """Flywheel storage instance identifier
    (e.g., 691c926ff8220b709983b848)"""

    group: str
    """Flywheel group name (e.g., "loni")"""

    studies: List[StudyConfig]
    """List of study configurations to import"""

    api_key_path: str
    """SSM Parameter Store path for Flywheel API key"""

    aws_profile: Optional[str] = None
    """AWS profile name for boto3 session (optional, defaults to Lambda
    execution role)"""

    dry_run: bool = False
    """If True, log operations without executing API calls"""

    @classmethod
    def from_event(cls, event: Dict[str, Any]) -> "ImportConfig":
        """
        Create configuration from Lambda event and environment variables.

        Supports both legacy format (scan_project_label,
        clariti_project_label, clariti_pattern) and new format
        (studies list) for backward compatibility.

        Parameters
        ----------
        event : dict
            Lambda event object with optional configuration overrides

        Returns
        -------
        ImportConfig
            Validated configuration object

        Notes
        -----
        Event parameters override environment variables.
        Legacy format is automatically converted to new format:
        - scan_project_label + clariti_pattern -> SCAN study with exclude mode
        - clariti_project_label + clariti_pattern -> CLARITI study with include mode
        """
        import os

        # Step Functions passes None when the preceding state (TableData)
        # fails and the error is caught. Default to empty dict so the
        # legacy path below falls through to environment variables.
        if event is None:
            event = {}

        # Helper function to get value from event or environment
        def get_value(key: str, default: Optional[str] = None) -> Optional[str]:
            return event.get(key, os.environ.get(key.upper(), default))

        # Check if using new format (studies list provided)
        if "studies" in event:
            # New format: use studies list directly
            studies_data = event["studies"]
            studies = [
                StudyConfig(
                    project_label=s["project_label"],
                    filter_pattern=s["filter_pattern"],
                    filter_mode=s.get("filter_mode", "include"),
                )
                for s in studies_data
            ]
        elif os.environ.get("STUDIES"):
            # New format via environment variable (JSON string)
            import json

            studies_data = json.loads(os.environ["STUDIES"])
            studies = [
                StudyConfig(
                    project_label=s["project_label"],
                    filter_pattern=s["filter_pattern"],
                    filter_mode=s.get("filter_mode", "include"),
                )
                for s in studies_data
            ]
        else:
            # Legacy format: convert to new format
            scan_project_label = get_value("scan_project_label")
            clariti_project_label = get_value("clariti_project_label")
            clariti_pattern = get_value("clariti_pattern") or "clariti"

            studies = []
            if scan_project_label:
                # SCAN study: exclude clariti pattern
                studies.append(
                    StudyConfig(
                        project_label=scan_project_label,
                        filter_pattern=clariti_pattern,
                        filter_mode="exclude",
                    )
                )
            if clariti_project_label:
                # CLARITI study: include clariti pattern
                studies.append(
                    StudyConfig(
                        project_label=clariti_project_label,
                        filter_pattern=clariti_pattern,
                        filter_mode="include",
                    )
                )

        # Get other configuration values
        storage_id = get_value("storage_id") or ""
        group = get_value("group") or ""
        api_key_path = get_value("api_key_path") or ""
        aws_profile = get_value("aws_profile")
        dry_run = event.get(
            "dry_run", os.environ.get("DRY_RUN", "false").lower() == "true"
        )

        return cls(
            storage_id=storage_id,
            group=group,
            studies=studies,
            api_key_path=api_key_path,
            aws_profile=aws_profile,
            dry_run=dry_run,
        )

    def validate(self) -> None:
        """
        Validate that all required parameters are non-empty.

        Raises
        ------
        ValueError
            If any required parameter is empty or invalid
        """
        if not self.storage_id:
            raise ValueError("storage_id is required and cannot be empty")
        if not self.group:
            raise ValueError("group is required and cannot be empty")
        if not self.studies:
            raise ValueError("studies list is required and cannot be empty")
        if not self.api_key_path:
            raise ValueError("api_key_path is required and cannot be empty")
        if not self.api_key_path.startswith("/"):
            raise ValueError("api_key_path must start with '/'")

        # Validate each study configuration
        for study in self.studies:
            study.validate()


@dataclass
class StudyImportResult:
    """Result of a single study import operation."""

    project_label: str
    """Project label that was imported"""

    duration: float
    """Duration of import in seconds"""

    file_count: int
    """Number of files successfully imported"""

    filter_pattern: str
    """Filter pattern used for this import"""

    filter_mode: str
    """Filter mode used: 'include' or 'exclude'"""

    failed_files: Optional[List[Dict[str, str]]] = None
    """List of files that failed to import, each with 'key' and 'error'"""

    @property
    def failed_count(self) -> int:
        """Number of files that failed to import."""
        return len(self.failed_files) if self.failed_files else 0

    def __post_init__(self) -> None:
        """
        Validate that numeric fields are non-negative.

        Raises
        ------
        ValueError
            If duration or file_count is negative
        """
        if self.duration < 0:
            raise ValueError(f"duration must be non-negative, got: {self.duration}")
        if self.file_count < 0:
            raise ValueError(f"file_count must be non-negative, got: {self.file_count}")


@dataclass
class ImportResult:
    """Result of import operations."""

    status: str
    """Execution status: 'success' or 'failed'"""

    study_results: List[StudyImportResult]
    """Results for each study import"""

    total_duration: float
    """Total execution duration in seconds"""

    total_file_count: int
    """Total number of files imported across all studies"""

    error_message: Optional[str] = None
    """Error message if status is 'failed'"""

    error_type: Optional[str] = None
    """Error type: SDKError, AuthenticationError, ImportError, ConfigurationError"""

    context: Optional[Dict[str, Any]] = None
    """Additional context information about the error"""

    def __post_init__(self) -> None:
        """
        Validate result fields and ensure consistency.

        Raises
        ------
        ValueError
            If total_duration is negative, total_file_count is negative,
            or total_file_count doesn't match sum of study file counts
        """
        if self.total_duration < 0:
            raise ValueError(
                f"total_duration must be non-negative, got: {self.total_duration}"
            )
        if self.total_file_count < 0:
            raise ValueError(
                f"total_file_count must be non-negative, got: {self.total_file_count}"
            )

        # Ensure total_file_count equals sum of file_count from all study_results
        expected_total = sum(result.file_count for result in self.study_results)
        if self.total_file_count != expected_total:
            raise ValueError(
                f"total_file_count ({self.total_file_count}) must equal sum of "
                f"file_count from all study_results ({expected_total})"
            )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert result to dictionary for Lambda response.

        Returns
        -------
        dict
            Dictionary representation with serialized study_results
        """
        return {
            "status": self.status,
            "study_results": [
                {
                    "project_label": result.project_label,
                    "duration": result.duration,
                    "file_count": result.file_count,
                    "failed_count": result.failed_count,
                    "failed_files": result.failed_files or [],
                    "filter_pattern": result.filter_pattern,
                    "filter_mode": result.filter_mode,
                }
                for result in self.study_results
            ],
            "total_duration": self.total_duration,
            "total_file_count": self.total_file_count,
            "error_message": self.error_message,
            "error_type": self.error_type,
            "context": self.context,
        }
