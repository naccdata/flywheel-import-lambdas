"""Unit tests for import_operations.import_pair_files."""

from typing import Any
from unittest.mock import MagicMock

from conftest import make_s3_object
from s3_import_lambda.import_operations import import_pair_files
from s3_import_models.models import PrefixPathPair


def _make_pair(**kwargs: object) -> PrefixPathPair:
    """Build a PrefixPathPair with sensible defaults."""
    defaults: dict[str, Any] = {
        "s3_prefix": "data/center1",
        "fw_group": "grp",
        "fw_project": "proj",
        "include_patterns": [],
        "exclude_patterns": [],
    }
    defaults.update(kwargs)
    return PrefixPathPair(**defaults)


class TestSinglePairImport:
    """Test importing files for a single prefix-path pair."""

    def test_successful_import_counts_files(
        self, mock_client_handler: MagicMock
    ) -> None:
        files = [
            make_s3_object("data/center1/a.csv", 100),
            make_s3_object("data/center1/b.csv", 200),
        ]
        mock_client_handler.filter_objects.return_value = iter(files)

        result = import_pair_files(mock_client_handler, _make_pair())

        assert result.file_count == 2
        assert result.failed_files == []
        assert result.fw_project == "proj"
        assert result.duration >= 0

    def test_project_id_lookup_called(self, mock_client_handler: MagicMock) -> None:
        mock_client_handler.filter_objects.return_value = iter([])
        import_pair_files(mock_client_handler, _make_pair())

        mock_client_handler.get_project_id.assert_called_once_with("grp", "proj")

    def test_filter_objects_called_with_pair_patterns(
        self, mock_client_handler: MagicMock
    ) -> None:
        pair = _make_pair(
            include_patterns=[".csv"],
            exclude_patterns=["_backup"],
        )
        mock_client_handler.filter_objects.return_value = iter([])
        import_pair_files(mock_client_handler, pair)

        mock_client_handler.filter_objects.assert_called_once_with(
            "data/center1",
            [".csv"],
            ["_backup"],
        )

    def test_result_includes_patterns(self, mock_client_handler: MagicMock) -> None:
        pair = _make_pair(
            include_patterns=[".csv"],
            exclude_patterns=["tmp"],
        )
        mock_client_handler.filter_objects.return_value = iter([])
        result = import_pair_files(mock_client_handler, pair)

        assert result.include_patterns == [".csv"]
        assert result.exclude_patterns == ["tmp"]


class TestPartialFileFailures:
    """Test that individual file failures don't stop remaining imports."""

    def test_some_files_fail_others_succeed(
        self, mock_client_handler: MagicMock
    ) -> None:
        files = [
            make_s3_object("data/ok1.csv", 100),
            make_s3_object("data/bad.csv", 200),
            make_s3_object("data/ok2.csv", 300),
        ]
        mock_client_handler.filter_objects.return_value = iter(files)

        # Second call to import_to_flywheel raises
        mock_client_handler.import_to_flywheel.side_effect = [
            {},
            RuntimeError("upload failed"),
            {},
        ]

        result = import_pair_files(mock_client_handler, _make_pair())

        assert result.file_count == 2
        assert len(result.failed_files) == 1
        assert result.failed_files[0]["key"] == "data/bad.csv"
        assert "upload failed" in result.failed_files[0]["error"]

    def test_all_files_attempted_despite_failures(
        self, mock_client_handler: MagicMock
    ) -> None:
        files = [
            make_s3_object("data/a.csv", 10),
            make_s3_object("data/b.csv", 20),
            make_s3_object("data/c.csv", 30),
        ]
        mock_client_handler.filter_objects.return_value = iter(files)
        mock_client_handler.import_to_flywheel.side_effect = [
            RuntimeError("fail"),
            {},
            RuntimeError("fail"),
        ]

        result = import_pair_files(mock_client_handler, _make_pair())

        assert result.file_count == 1
        assert len(result.failed_files) == 2
        # All three files were attempted
        assert mock_client_handler.import_to_flywheel.call_count == 3


class TestEmptyResultSet:
    """Test behavior when no files match the filter."""

    def test_empty_filter_result(self, mock_client_handler: MagicMock) -> None:
        mock_client_handler.filter_objects.return_value = iter([])

        result = import_pair_files(mock_client_handler, _make_pair())

        assert result.file_count == 0
        assert result.failed_files == []
        assert result.duration >= 0
        mock_client_handler.import_to_flywheel.assert_not_called()


class TestPairImportResultFields:
    """Verify PairImportResult has correct field values."""

    def test_result_has_correct_file_count(
        self, mock_client_handler: MagicMock
    ) -> None:
        files = [make_s3_object(f"data/f{i}.csv", 10) for i in range(5)]
        mock_client_handler.filter_objects.return_value = iter(files)

        result = import_pair_files(mock_client_handler, _make_pair())

        assert result.file_count == 5

    def test_result_duration_is_non_negative(
        self, mock_client_handler: MagicMock
    ) -> None:
        mock_client_handler.filter_objects.return_value = iter([])
        result = import_pair_files(mock_client_handler, _make_pair())

        assert result.duration >= 0
