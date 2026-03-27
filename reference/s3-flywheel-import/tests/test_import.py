"""Unit tests for import operations."""

from unittest.mock import Mock

import pytest

from import_operations import import_study_metadata
from models import StudyConfig, StudyImportResult


class TestImportStudyMetadata:
    """Tests for import_study_metadata function."""

    def test_import_with_include_mode(self) -> None:
        """Test successful import with include filter mode."""
        # Mock ClientHandler
        mock_client = Mock()
        mock_client.get_project_id.return_value = "project-123"

        # Mock S3 objects
        mock_file1 = Mock()
        mock_file1.key = "test-prefix/clariti/file1.txt"
        mock_file1.size = 1024

        mock_file2 = Mock()
        mock_file2.key = "test-prefix/clariti/file2.txt"
        mock_file2.size = 2048

        mock_client.filter_objects.return_value = iter([mock_file1, mock_file2])
        mock_client.import_to_flywheel.return_value = {"status": "success"}

        # Create study config with include mode
        study_config = StudyConfig(
            project_label="clariti-metadata",
            filter_pattern="clariti",
            filter_mode="include",
        )

        # Import study metadata
        result = import_study_metadata(
            client=mock_client,
            group="loni",
            study_config=study_config,
        )

        # Verify get_project_id was called
        mock_client.get_project_id.assert_called_once_with("loni", "clariti-metadata")

        # Verify filter_objects was called with include pattern
        mock_client.filter_objects.assert_called_once_with(include_pattern="clariti")

        # Verify import_to_flywheel was called for each file
        assert mock_client.import_to_flywheel.call_count == 2
        mock_client.import_to_flywheel.assert_any_call("project-123", mock_file1)
        mock_client.import_to_flywheel.assert_any_call("project-123", mock_file2)

        # Verify result
        assert isinstance(result, StudyImportResult)
        assert result.project_label == "clariti-metadata"
        assert result.file_count == 2
        assert result.duration >= 0
        assert result.filter_pattern == "clariti"
        assert result.filter_mode == "include"

    def test_import_with_exclude_mode(self) -> None:
        """Test successful import with exclude filter mode."""
        # Mock ClientHandler
        mock_client = Mock()
        mock_client.get_project_id.return_value = "project-456"

        # Mock S3 objects
        mock_file1 = Mock()
        mock_file1.key = "test-prefix/scan/file1.txt"
        mock_file1.size = 1024

        mock_file2 = Mock()
        mock_file2.key = "test-prefix/scan/file2.txt"
        mock_file2.size = 2048

        mock_file3 = Mock()
        mock_file3.key = "test-prefix/scan/file3.txt"
        mock_file3.size = 3072

        mock_client.filter_objects.return_value = iter(
            [mock_file1, mock_file2, mock_file3]
        )
        mock_client.import_to_flywheel.return_value = {"status": "success"}

        # Create study config with exclude mode
        study_config = StudyConfig(
            project_label="scan-metadata",
            filter_pattern="clariti",
            filter_mode="exclude",
        )

        # Import study metadata
        result = import_study_metadata(
            client=mock_client,
            group="loni",
            study_config=study_config,
        )

        # Verify get_project_id was called
        mock_client.get_project_id.assert_called_once_with("loni", "scan-metadata")

        # Verify filter_objects was called with exclude pattern
        mock_client.filter_objects.assert_called_once_with(exclude_pattern="clariti")

        # Verify import_to_flywheel was called for each file
        assert mock_client.import_to_flywheel.call_count == 3

        # Verify result
        assert isinstance(result, StudyImportResult)
        assert result.project_label == "scan-metadata"
        assert result.file_count == 3
        assert result.duration >= 0
        assert result.filter_pattern == "clariti"
        assert result.filter_mode == "exclude"

    def test_import_with_empty_result_set(self) -> None:
        """Test import when no files match filter."""
        # Mock ClientHandler
        mock_client = Mock()
        mock_client.get_project_id.return_value = "project-789"

        # Mock empty S3 objects list
        mock_client.filter_objects.return_value = iter([])

        # Create study config
        study_config = StudyConfig(
            project_label="test-metadata",
            filter_pattern="nonexistent",
            filter_mode="include",
        )

        # Import study metadata
        result = import_study_metadata(
            client=mock_client,
            group="loni",
            study_config=study_config,
        )

        # Verify get_project_id was called
        mock_client.get_project_id.assert_called_once_with("loni", "test-metadata")

        # Verify filter_objects was called
        mock_client.filter_objects.assert_called_once_with(
            include_pattern="nonexistent"
        )

        # Verify import_to_flywheel was NOT called
        mock_client.import_to_flywheel.assert_not_called()

        # Verify result
        assert isinstance(result, StudyImportResult)
        assert result.project_label == "test-metadata"
        assert result.file_count == 0
        assert result.duration >= 0
        assert result.filter_pattern == "nonexistent"
        assert result.filter_mode == "include"

    def test_import_tracks_file_count(self) -> None:
        """Test that file count is accurately tracked."""
        # Mock ClientHandler
        mock_client = Mock()
        mock_client.get_project_id.return_value = "project-123"

        # Mock 5 S3 objects
        mock_files = []
        for i in range(5):
            mock_file = Mock()
            mock_file.key = f"test-prefix/file{i}.txt"
            mock_file.size = 1024 * (i + 1)
            mock_files.append(mock_file)

        mock_client.filter_objects.return_value = iter(mock_files)
        mock_client.import_to_flywheel.return_value = {"status": "success"}

        # Create study config
        study_config = StudyConfig(
            project_label="test-metadata",
            filter_pattern="test",
            filter_mode="include",
        )

        # Import study metadata
        result = import_study_metadata(
            client=mock_client,
            group="loni",
            study_config=study_config,
        )

        # Verify file count
        assert result.file_count == 5

        # Verify import_to_flywheel was called 5 times
        assert mock_client.import_to_flywheel.call_count == 5

    def test_import_tracks_duration(self) -> None:
        """Test that duration is tracked and non-negative."""
        # Mock ClientHandler
        mock_client = Mock()
        mock_client.get_project_id.return_value = "project-123"

        # Mock S3 objects
        mock_file = Mock()
        mock_file.key = "test-prefix/file1.txt"
        mock_file.size = 1024

        mock_client.filter_objects.return_value = iter([mock_file])
        mock_client.import_to_flywheel.return_value = {"status": "success"}

        # Create study config
        study_config = StudyConfig(
            project_label="test-metadata",
            filter_pattern="test",
            filter_mode="include",
        )

        # Import study metadata
        result = import_study_metadata(
            client=mock_client,
            group="loni",
            study_config=study_config,
        )

        # Verify duration is non-negative
        assert result.duration >= 0

        # Verify duration is reasonable (should be very small for mocked operations)
        assert result.duration < 10  # Should complete in less than 10 seconds

    def test_import_with_different_study_configs(self) -> None:
        """Test import works with any study configuration."""
        # Mock ClientHandler
        mock_client = Mock()
        mock_client.get_project_id.return_value = "project-999"

        # Mock S3 objects
        mock_file = Mock()
        mock_file.key = "test-prefix/custom/file1.txt"
        mock_file.size = 1024

        mock_client.filter_objects.return_value = iter([mock_file])
        mock_client.import_to_flywheel.return_value = {"status": "success"}

        # Create custom study config
        study_config = StudyConfig(
            project_label="custom-project",
            filter_pattern="custom-pattern",
            filter_mode="include",
        )

        # Import study metadata
        result = import_study_metadata(
            client=mock_client,
            group="custom-group",
            study_config=study_config,
        )

        # Verify get_project_id was called with custom values
        mock_client.get_project_id.assert_called_once_with(
            "custom-group", "custom-project"
        )

        # Verify filter_objects was called with custom pattern
        mock_client.filter_objects.assert_called_once_with(
            include_pattern="custom-pattern"
        )

        # Verify result contains custom values
        assert result.project_label == "custom-project"
        assert result.filter_pattern == "custom-pattern"
        assert result.filter_mode == "include"

    def test_import_with_invalid_filter_mode(self) -> None:
        """Test import raises ValueError for invalid filter_mode."""
        # Mock ClientHandler
        mock_client = Mock()
        mock_client.get_project_id.return_value = "project-123"

        # Create study config with invalid filter_mode
        # Note: This bypasses validation for testing purposes
        study_config = StudyConfig(
            project_label="test-metadata",
            filter_pattern="test",
            filter_mode="invalid",
        )

        # Verify ValueError is raised
        with pytest.raises(ValueError, match="Invalid filter_mode"):
            import_study_metadata(
                client=mock_client,
                group="loni",
                study_config=study_config,
            )

    def test_import_preserves_configuration_details(self) -> None:
        """Test that result preserves all configuration details."""
        # Mock ClientHandler
        mock_client = Mock()
        mock_client.get_project_id.return_value = "project-123"

        # Mock S3 objects
        mock_file = Mock()
        mock_file.key = "test-prefix/file1.txt"
        mock_file.size = 1024

        mock_client.filter_objects.return_value = iter([mock_file])
        mock_client.import_to_flywheel.return_value = {"status": "success"}

        # Create study config with specific values
        study_config = StudyConfig(
            project_label="specific-project",
            filter_pattern="specific-pattern",
            filter_mode="exclude",
        )

        # Import study metadata
        result = import_study_metadata(
            client=mock_client,
            group="loni",
            study_config=study_config,
        )

        # Verify all configuration details are preserved in result
        assert result.project_label == "specific-project"
        assert result.filter_pattern == "specific-pattern"
        assert result.filter_mode == "exclude"
        assert result.file_count == 1
        assert result.duration >= 0

    def test_import_with_multiple_files(self) -> None:
        """Test import with multiple files of varying sizes."""
        # Mock ClientHandler
        mock_client = Mock()
        mock_client.get_project_id.return_value = "project-123"

        # Mock 10 S3 objects with different sizes
        mock_files = []
        for i in range(10):
            mock_file = Mock()
            mock_file.key = f"test-prefix/batch/file{i:03d}.txt"
            mock_file.size = 1024 * (i + 1)
            mock_files.append(mock_file)

        mock_client.filter_objects.return_value = iter(mock_files)
        mock_client.import_to_flywheel.return_value = {"status": "success"}

        # Create study config
        study_config = StudyConfig(
            project_label="batch-metadata",
            filter_pattern="batch",
            filter_mode="include",
        )

        # Import study metadata
        result = import_study_metadata(
            client=mock_client,
            group="loni",
            study_config=study_config,
        )

        # Verify all files were imported
        assert result.file_count == 10
        assert mock_client.import_to_flywheel.call_count == 10

        # Verify each file was imported with correct project_id
        for mock_file in mock_files:
            mock_client.import_to_flywheel.assert_any_call("project-123", mock_file)
