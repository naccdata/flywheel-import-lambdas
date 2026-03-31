"""Unit tests for S3 Flywheel Import Pydantic models."""

import pytest
from pydantic import ValidationError
from s3_import_models.models import (
    ImportConfig,
    ImportResult,
    PairImportResult,
    PrefixPathPair,
)


class TestPrefixPathPair:
    """Tests for PrefixPathPair model."""

    def test_valid_construction(self) -> None:
        pair = PrefixPathPair(
            s3_prefix="centers/1florida",
            fw_group="1florida",
            fw_project="distribution-data-freeze",
        )
        assert pair.s3_prefix == "centers/1florida"
        assert pair.fw_group == "1florida"
        assert pair.fw_project == "distribution-data-freeze"

    def test_default_empty_pattern_lists(self) -> None:
        pair = PrefixPathPair(
            s3_prefix="data/",
            fw_group="mygroup",
            fw_project="myproject",
        )
        assert pair.include_patterns == []
        assert pair.exclude_patterns == []

    def test_with_patterns(self) -> None:
        pair = PrefixPathPair(
            s3_prefix="data/",
            fw_group="mygroup",
            fw_project="myproject",
            include_patterns=[".csv", ".tsv"],
            exclude_patterns=["_backup"],
        )
        assert pair.include_patterns == [".csv", ".tsv"]
        assert pair.exclude_patterns == ["_backup"]

    def test_empty_s3_prefix_allowed(self) -> None:
        """Empty s3_prefix means bucket root — valid use case."""
        pair = PrefixPathPair(
            s3_prefix="",
            fw_group="group",
            fw_project="project",
        )
        assert pair.s3_prefix == ""

    def test_whitespace_s3_prefix_stripped_to_empty(self) -> None:
        """Whitespace-only s3_prefix is normalized to empty string."""
        pair = PrefixPathPair(
            s3_prefix="   ",
            fw_group="group",
            fw_project="project",
        )
        assert pair.s3_prefix == ""

    def test_empty_fw_group_raises(self) -> None:
        with pytest.raises(ValidationError, match="non-empty"):
            PrefixPathPair(
                s3_prefix="data/",
                fw_group="",
                fw_project="project",
            )

    def test_empty_fw_project_raises(self) -> None:
        with pytest.raises(ValidationError, match="non-empty"):
            PrefixPathPair(
                s3_prefix="data/",
                fw_group="group",
                fw_project="",
            )


class TestImportConfig:
    """Tests for ImportConfig model."""

    def test_valid_construction(self) -> None:
        config = ImportConfig(
            storage_id="abc123",
            api_key_path="/prod/flywheel/apikey",
            prefix_path_pairs=[
                PrefixPathPair(
                    s3_prefix="data/",
                    fw_group="grp",
                    fw_project="proj",
                )
            ],
        )
        assert config.storage_id == "abc123"
        assert config.api_key_path == "/prod/flywheel/apikey"
        assert len(config.prefix_path_pairs) == 1

    def test_default_dry_run_false(self) -> None:
        config = ImportConfig(
            storage_id="abc123",
            api_key_path="/key",
            prefix_path_pairs=[
                PrefixPathPair(s3_prefix="d/", fw_group="g", fw_project="p")
            ],
        )
        assert config.dry_run is False

    def test_default_aws_profile_none(self) -> None:
        config = ImportConfig(
            storage_id="abc123",
            api_key_path="/key",
            prefix_path_pairs=[
                PrefixPathPair(s3_prefix="d/", fw_group="g", fw_project="p")
            ],
        )
        assert config.aws_profile is None

    def test_empty_storage_id_raises(self) -> None:
        with pytest.raises(ValidationError, match="storage_id"):
            ImportConfig(
                storage_id="",
                api_key_path="/key",
                prefix_path_pairs=[
                    PrefixPathPair(s3_prefix="d/", fw_group="g", fw_project="p")
                ],
            )

    def test_whitespace_storage_id_raises(self) -> None:
        with pytest.raises(ValidationError, match="storage_id"):
            ImportConfig(
                storage_id="   ",
                api_key_path="/key",
                prefix_path_pairs=[
                    PrefixPathPair(s3_prefix="d/", fw_group="g", fw_project="p")
                ],
            )

    def test_api_key_path_not_starting_with_slash_raises(self) -> None:
        with pytest.raises(ValidationError, match="api_key_path"):
            ImportConfig(
                storage_id="abc123",
                api_key_path="no/leading/slash",
                prefix_path_pairs=[
                    PrefixPathPair(s3_prefix="d/", fw_group="g", fw_project="p")
                ],
            )

    def test_empty_prefix_path_pairs_raises(self) -> None:
        with pytest.raises(ValidationError, match="prefix_path_pairs"):
            ImportConfig(
                storage_id="abc123",
                api_key_path="/key",
                prefix_path_pairs=[],
            )


class TestPairImportResult:
    """Tests for PairImportResult model."""

    def test_valid_construction(self) -> None:
        result = PairImportResult(
            fw_project="myproject",
            duration=10.5,
            file_count=42,
        )
        assert result.fw_project == "myproject"
        assert result.duration == 10.5
        assert result.file_count == 42

    def test_default_empty_lists(self) -> None:
        result = PairImportResult(
            fw_project="proj",
            duration=0.0,
            file_count=0,
        )
        assert result.failed_files == []
        assert result.include_patterns == []
        assert result.exclude_patterns == []

    def test_negative_duration_raises(self) -> None:
        with pytest.raises(ValidationError, match="duration"):
            PairImportResult(
                fw_project="proj",
                duration=-1.0,
                file_count=0,
            )

    def test_negative_file_count_raises(self) -> None:
        with pytest.raises(ValidationError, match="file_count"):
            PairImportResult(
                fw_project="proj",
                duration=0.0,
                file_count=-1,
            )


class TestImportResult:
    """Tests for ImportResult model."""

    def test_valid_construction(self) -> None:
        result = ImportResult(status="success")
        assert result.status == "success"
        assert result.pair_results == []
        assert result.total_duration == 0.0
        assert result.total_file_count == 0
        assert result.error_message is None
        assert result.error_type is None
        assert result.context is None

    def test_valid_with_pair_results(self) -> None:
        pair = PairImportResult(
            fw_project="proj",
            duration=5.0,
            file_count=10,
        )
        result = ImportResult(
            status="success",
            pair_results=[pair],
            total_duration=5.0,
            total_file_count=10,
        )
        assert len(result.pair_results) == 1
        assert result.total_file_count == 10

    def test_total_file_count_mismatch_raises(self) -> None:
        pair = PairImportResult(
            fw_project="proj",
            duration=5.0,
            file_count=10,
        )
        with pytest.raises(ValidationError, match="total_file_count"):
            ImportResult(
                status="success",
                pair_results=[pair],
                total_file_count=999,
            )

    def test_total_file_count_sum_across_multiple_pairs(self) -> None:
        pair1 = PairImportResult(fw_project="proj1", duration=1.0, file_count=5)
        pair2 = PairImportResult(fw_project="proj2", duration=2.0, file_count=7)
        result = ImportResult(
            status="success",
            pair_results=[pair1, pair2],
            total_file_count=12,
        )
        assert result.total_file_count == 12

    def test_failed_status_with_error_fields(self) -> None:
        result = ImportResult(
            status="failed",
            error_message="Something went wrong",
            error_type="ConfigurationError",
            context={"detail": "bad config"},
        )
        assert result.status == "failed"
        assert result.error_message == "Something went wrong"
        assert result.error_type == "ConfigurationError"
        assert result.context == {"detail": "bad config"}
