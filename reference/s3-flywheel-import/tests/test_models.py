"""Unit tests for data models."""

from typing import Any, Dict

import pytest

from models import ImportConfig, ImportResult, StudyConfig, StudyImportResult


class TestStudyConfig:
    """Tests for StudyConfig validation."""

    def test_valid_config(self) -> None:
        """Test that valid configuration passes validation."""
        config = StudyConfig(
            project_label="scan-metadata",
            filter_pattern="scan",
            filter_mode="include",
        )
        config.validate()  # Should not raise

    def test_empty_project_label(self) -> None:
        """Test that empty project_label raises ValueError."""
        config = StudyConfig(
            project_label="",
            filter_pattern="scan",
            filter_mode="include",
        )
        with pytest.raises(ValueError, match="project_label is required"):
            config.validate()

    def test_empty_filter_pattern(self) -> None:
        """Test that empty filter_pattern raises ValueError."""
        config = StudyConfig(
            project_label="scan-metadata",
            filter_pattern="",
            filter_mode="include",
        )
        with pytest.raises(ValueError, match="filter_pattern is required"):
            config.validate()

    def test_invalid_filter_mode(self) -> None:
        """Test that invalid filter_mode raises ValueError."""
        config = StudyConfig(
            project_label="scan-metadata",
            filter_pattern="scan",
            filter_mode="invalid",
        )
        with pytest.raises(ValueError, match="filter_mode must be"):
            config.validate()

    def test_exclude_filter_mode(self) -> None:
        """Test that 'exclude' filter_mode is valid."""
        config = StudyConfig(
            project_label="scan-metadata",
            filter_pattern="clariti",
            filter_mode="exclude",
        )
        config.validate()  # Should not raise


class TestImportConfig:
    """Tests for ImportConfig validation and creation."""

    def test_valid_new_format(self) -> None:
        """Test that valid new format configuration passes validation."""
        config = ImportConfig(
            storage_id="691c926ff8220b709983b848",
            group="loni",
            studies=[
                StudyConfig(
                    project_label="scan-metadata",
                    filter_pattern="scan",
                    filter_mode="include",
                )
            ],
            api_key_path="/flywheel/api-key",
        )
        config.validate()  # Should not raise

    def test_valid_legacy_format(self) -> None:
        """Test that valid legacy format configuration passes validation."""
        config = ImportConfig(
            storage_id="691c926ff8220b709983b848",
            group="loni",
            studies=[
                StudyConfig(
                    project_label="scan-metadata",
                    filter_pattern="clariti",
                    filter_mode="exclude",
                ),
                StudyConfig(
                    project_label="clariti-metadata",
                    filter_pattern="clariti",
                    filter_mode="include",
                ),
            ],
            api_key_path="/flywheel/api-key",
        )
        config.validate()  # Should not raise

    def test_empty_storage_id(self) -> None:
        """Test that empty storage_id raises ValueError."""
        config = ImportConfig(
            storage_id="",
            group="loni",
            studies=[
                StudyConfig(
                    project_label="scan-metadata",
                    filter_pattern="scan",
                    filter_mode="include",
                )
            ],
            api_key_path="/flywheel/api-key",
        )
        with pytest.raises(ValueError, match="storage_id is required"):
            config.validate()

    def test_empty_group(self) -> None:
        """Test that empty group raises ValueError."""
        config = ImportConfig(
            storage_id="691c926ff8220b709983b848",
            group="",
            studies=[
                StudyConfig(
                    project_label="scan-metadata",
                    filter_pattern="scan",
                    filter_mode="include",
                )
            ],
            api_key_path="/flywheel/api-key",
        )
        with pytest.raises(ValueError, match="group is required"):
            config.validate()

    def test_empty_studies_list(self) -> None:
        """Test that empty studies list raises ValueError."""
        config = ImportConfig(
            storage_id="691c926ff8220b709983b848",
            group="loni",
            studies=[],
            api_key_path="/flywheel/api-key",
        )
        with pytest.raises(ValueError, match="studies list is required"):
            config.validate()

    def test_invalid_ssm_path(self) -> None:
        """Test that SSM path not starting with '/' raises ValueError."""
        config = ImportConfig(
            storage_id="691c926ff8220b709983b848",
            group="loni",
            studies=[
                StudyConfig(
                    project_label="scan-metadata",
                    filter_pattern="scan",
                    filter_mode="include",
                )
            ],
            api_key_path="flywheel/api-key",
        )
        with pytest.raises(ValueError, match="api_key_path must start with"):
            config.validate()

    def test_empty_api_key_path(self) -> None:
        """Test that empty api_key_path raises ValueError."""
        config = ImportConfig(
            storage_id="691c926ff8220b709983b848",
            group="loni",
            studies=[
                StudyConfig(
                    project_label="scan-metadata",
                    filter_pattern="scan",
                    filter_mode="include",
                )
            ],
            api_key_path="",
        )
        with pytest.raises(ValueError, match="api_key_path is required"):
            config.validate()

    def test_from_event_new_format(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test ImportConfig.from_event() with new format."""
        event: Dict[str, Any] = {
            "storage_id": "691c926ff8220b709983b848",
            "group": "loni",
            "studies": [
                {
                    "project_label": "scan-metadata",
                    "filter_pattern": "scan",
                    "filter_mode": "include",
                }
            ],
            "api_key_path": "/flywheel/api-key",
        }

        config = ImportConfig.from_event(event)

        assert config.storage_id == "691c926ff8220b709983b848"
        assert config.group == "loni"
        assert len(config.studies) == 1
        assert config.studies[0].project_label == "scan-metadata"
        assert config.studies[0].filter_pattern == "scan"
        assert config.studies[0].filter_mode == "include"
        assert config.api_key_path == "/flywheel/api-key"
        assert config.dry_run is False

    def test_from_event_legacy_format(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test from_event() with legacy format creates two StudyConfig."""
        event: Dict[str, Any] = {
            "storage_id": "691c926ff8220b709983b848",
            "group": "loni",
            "scan_project_label": "scan-metadata",
            "clariti_project_label": "clariti-metadata",
            "clariti_pattern": "clariti",
            "api_key_path": "/flywheel/api-key",
        }

        config = ImportConfig.from_event(event)

        assert config.storage_id == "691c926ff8220b709983b848"
        assert config.group == "loni"
        assert len(config.studies) == 2

        # First study should be SCAN with exclude mode
        assert config.studies[0].project_label == "scan-metadata"
        assert config.studies[0].filter_pattern == "clariti"
        assert config.studies[0].filter_mode == "exclude"

        # Second study should be CLARITI with include mode
        assert config.studies[1].project_label == "clariti-metadata"
        assert config.studies[1].filter_pattern == "clariti"
        assert config.studies[1].filter_mode == "include"

    def test_from_event_with_environment_variables(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test ImportConfig.from_event() uses env vars as fallback."""
        monkeypatch.setenv("STORAGE_ID", "env-storage-id")
        monkeypatch.setenv("GROUP", "env-group")
        monkeypatch.setenv("SCAN_PROJECT_LABEL", "env-scan-metadata")
        monkeypatch.setenv("API_KEY_PATH", "/env/api-key")

        event: Dict[str, Any] = {}

        config = ImportConfig.from_event(event)

        assert config.storage_id == "env-storage-id"
        assert config.group == "env-group"
        assert len(config.studies) == 1
        assert config.studies[0].project_label == "env-scan-metadata"
        assert config.api_key_path == "/env/api-key"

    def test_from_event_overrides_environment(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that event parameters override environment variables."""
        monkeypatch.setenv("STORAGE_ID", "env-storage-id")
        monkeypatch.setenv("GROUP", "env-group")

        event: Dict[str, Any] = {
            "storage_id": "event-storage-id",
            "group": "event-group",
            "scan_project_label": "scan-metadata",
            "api_key_path": "/flywheel/api-key",
        }

        config = ImportConfig.from_event(event)

        assert config.storage_id == "event-storage-id"
        assert config.group == "event-group"

    def test_from_event_dry_run_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that dry_run flag is correctly parsed from event."""
        event: Dict[str, Any] = {
            "storage_id": "691c926ff8220b709983b848",
            "group": "loni",
            "scan_project_label": "scan-metadata",
            "api_key_path": "/flywheel/api-key",
            "dry_run": True,
        }

        config = ImportConfig.from_event(event)

        assert config.dry_run is True

    def test_from_event_dry_run_from_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that dry_run flag is correctly parsed from environment."""
        monkeypatch.setenv("DRY_RUN", "true")

        event: Dict[str, Any] = {
            "storage_id": "691c926ff8220b709983b848",
            "group": "loni",
            "scan_project_label": "scan-metadata",
            "api_key_path": "/flywheel/api-key",
        }

        config = ImportConfig.from_event(event)

        assert config.dry_run is True


class TestStudyImportResult:
    """Tests for StudyImportResult validation."""

    def test_valid_result(self) -> None:
        """Test that valid result is created successfully."""
        result = StudyImportResult(
            project_label="scan-metadata",
            duration=45.5,
            file_count=100,
            filter_pattern="scan",
            filter_mode="include",
        )
        assert result.project_label == "scan-metadata"
        assert result.duration == 45.5
        assert result.file_count == 100

    def test_negative_duration(self) -> None:
        """Test that negative duration raises ValueError."""
        with pytest.raises(ValueError, match="duration must be non-negative"):
            StudyImportResult(
                project_label="scan-metadata",
                duration=-1.0,
                file_count=100,
                filter_pattern="scan",
                filter_mode="include",
            )

    def test_negative_file_count(self) -> None:
        """Test that negative file_count raises ValueError."""
        with pytest.raises(ValueError, match="file_count must be non-negative"):
            StudyImportResult(
                project_label="scan-metadata",
                duration=45.5,
                file_count=-1,
                filter_pattern="scan",
                filter_mode="include",
            )

    def test_zero_values(self) -> None:
        """Test that zero values are valid."""
        result = StudyImportResult(
            project_label="scan-metadata",
            duration=0.0,
            file_count=0,
            filter_pattern="scan",
            filter_mode="include",
        )
        assert result.duration == 0.0
        assert result.file_count == 0


class TestImportResult:
    """Tests for ImportResult validation and serialization."""

    def test_valid_result(self) -> None:
        """Test that valid result is created successfully."""
        study_results = [
            StudyImportResult(
                project_label="scan-metadata",
                duration=45.5,
                file_count=100,
                filter_pattern="scan",
                filter_mode="include",
            ),
            StudyImportResult(
                project_label="clariti-metadata",
                duration=30.2,
                file_count=50,
                filter_pattern="clariti",
                filter_mode="include",
            ),
        ]

        result = ImportResult(
            status="success",
            study_results=study_results,
            total_duration=75.7,
            total_file_count=150,
        )

        assert result.status == "success"
        assert len(result.study_results) == 2
        assert result.total_duration == 75.7
        assert result.total_file_count == 150

    def test_negative_total_duration(self) -> None:
        """Test that negative total_duration raises ValueError."""
        study_results = [
            StudyImportResult(
                project_label="scan-metadata",
                duration=45.5,
                file_count=100,
                filter_pattern="scan",
                filter_mode="include",
            )
        ]

        with pytest.raises(ValueError, match="total_duration must be non-negative"):
            ImportResult(
                status="success",
                study_results=study_results,
                total_duration=-1.0,
                total_file_count=100,
            )

    def test_negative_total_file_count(self) -> None:
        """Test that negative total_file_count raises ValueError."""
        study_results = [
            StudyImportResult(
                project_label="scan-metadata",
                duration=45.5,
                file_count=100,
                filter_pattern="scan",
                filter_mode="include",
            )
        ]

        with pytest.raises(ValueError, match="total_file_count must be non-negative"):
            ImportResult(
                status="success",
                study_results=study_results,
                total_duration=45.5,
                total_file_count=-1,
            )

    def test_total_file_count_aggregation(self) -> None:
        """Test that total_file_count must equal sum of study file counts."""
        study_results = [
            StudyImportResult(
                project_label="scan-metadata",
                duration=45.5,
                file_count=100,
                filter_pattern="scan",
                filter_mode="include",
            ),
            StudyImportResult(
                project_label="clariti-metadata",
                duration=30.2,
                file_count=50,
                filter_pattern="clariti",
                filter_mode="include",
            ),
        ]

        # Correct total should be 150
        with pytest.raises(ValueError, match="total_file_count.*must equal sum"):
            ImportResult(
                status="success",
                study_results=study_results,
                total_duration=75.7,
                total_file_count=100,  # Wrong total
            )

    def test_to_dict_serialization(self) -> None:
        """Test ImportResult.to_dict() serialization."""
        study_results = [
            StudyImportResult(
                project_label="scan-metadata",
                duration=45.5,
                file_count=100,
                filter_pattern="scan",
                filter_mode="include",
            ),
            StudyImportResult(
                project_label="clariti-metadata",
                duration=30.2,
                file_count=50,
                filter_pattern="clariti",
                filter_mode="include",
            ),
        ]

        result = ImportResult(
            status="success",
            study_results=study_results,
            total_duration=75.7,
            total_file_count=150,
        )

        result_dict = result.to_dict()

        assert result_dict["status"] == "success"
        assert len(result_dict["study_results"]) == 2
        assert result_dict["study_results"][0]["project_label"] == "scan-metadata"
        assert result_dict["study_results"][0]["duration"] == 45.5
        assert result_dict["study_results"][0]["file_count"] == 100
        assert result_dict["study_results"][0]["filter_pattern"] == "scan"
        assert result_dict["study_results"][0]["filter_mode"] == "include"
        assert result_dict["study_results"][1]["project_label"] == "clariti-metadata"
        assert result_dict["total_duration"] == 75.7
        assert result_dict["total_file_count"] == 150
        assert result_dict["error_message"] is None
        assert result_dict["error_type"] is None
        assert result_dict["context"] is None

    def test_to_dict_with_error(self) -> None:
        """Test ImportResult.to_dict() serialization with error fields."""
        result = ImportResult(
            status="failed",
            study_results=[],
            total_duration=0.0,
            total_file_count=0,
            error_message="Authentication failed",
            error_type="AuthenticationError",
            context={"api_key_path": "/flywheel/api-key"},
        )

        result_dict = result.to_dict()

        assert result_dict["status"] == "failed"
        assert result_dict["error_message"] == "Authentication failed"
        assert result_dict["error_type"] == "AuthenticationError"
        assert result_dict["context"] == {"api_key_path": "/flywheel/api-key"}
