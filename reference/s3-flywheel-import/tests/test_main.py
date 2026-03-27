"""Unit tests for main Lambda handler."""

from typing import Any, Dict
from unittest.mock import Mock, patch

from models import StudyImportResult
from s3_flywheel_import import main


class TestMainHandler:
    """Tests for main Lambda handler."""

    @patch("s3_flywheel_import.import_study_metadata")
    @patch("s3_flywheel_import.ClientHandler")
    @patch("s3_flywheel_import.get_parameters")
    def test_main_success_new_format(
        self,
        mock_get_parameters: Mock,
        mock_client_handler_class: Mock,
        mock_import_study: Mock,
    ) -> None:
        """Test successful execution with new configuration format."""
        # Mock SSM parameter retrieval
        mock_get_parameters.return_value = "test-api-key"

        # Mock ClientHandler
        mock_client = Mock()
        mock_client.fw_storage_prefix = "test-prefix/"
        mock_client.fw_provider_id = "provider-123"
        mock_client_handler_class.return_value = mock_client

        # Mock import results
        study_result1 = StudyImportResult(
            project_label="scan-metadata",
            duration=45.5,
            file_count=100,
            filter_pattern="clariti",
            filter_mode="exclude",
        )
        study_result2 = StudyImportResult(
            project_label="clariti-metadata",
            duration=30.2,
            file_count=50,
            filter_pattern="clariti",
            filter_mode="include",
        )
        mock_import_study.side_effect = [study_result1, study_result2]

        # Create event with new format
        event: Dict[str, Any] = {
            "storage_id": "storage-123",
            "group": "loni",
            "studies": [
                {
                    "project_label": "scan-metadata",
                    "filter_pattern": "clariti",
                    "filter_mode": "exclude",
                },
                {
                    "project_label": "clariti-metadata",
                    "filter_pattern": "clariti",
                    "filter_mode": "include",
                },
            ],
            "api_key_path": "/test/api-key",
        }

        # Call main handler
        result = main(event, None)

        # Verify SSM parameter was retrieved
        mock_get_parameters.assert_called_once_with("/test/api-key")

        # Verify ClientHandler was initialized
        mock_client_handler_class.assert_called_once_with(
            fw_api_key="test-api-key",
            fw_storage_id="storage-123",
            aws_profile=None,
            dry_run=False,
        )

        # Verify import_study_metadata was called for each study
        assert mock_import_study.call_count == 2

        # Verify result
        assert result["status"] == "success"
        assert len(result["study_results"]) == 2
        assert result["total_file_count"] == 150
        assert result["total_duration"] >= 0
        assert result["error_message"] is None
        assert result["error_type"] is None

    @patch("s3_flywheel_import.import_study_metadata")
    @patch("s3_flywheel_import.ClientHandler")
    @patch("s3_flywheel_import.get_parameters")
    def test_main_success_legacy_format(
        self,
        mock_get_parameters: Mock,
        mock_client_handler_class: Mock,
        mock_import_study: Mock,
    ) -> None:
        """Test successful execution with legacy configuration format."""
        # Mock SSM parameter retrieval
        mock_get_parameters.return_value = "test-api-key"

        # Mock ClientHandler
        mock_client = Mock()
        mock_client.fw_storage_prefix = "test-prefix/"
        mock_client.fw_provider_id = "provider-123"
        mock_client_handler_class.return_value = mock_client

        # Mock import results
        study_result1 = StudyImportResult(
            project_label="scan-metadata",
            duration=45.5,
            file_count=100,
            filter_pattern="clariti",
            filter_mode="exclude",
        )
        study_result2 = StudyImportResult(
            project_label="clariti-metadata",
            duration=30.2,
            file_count=50,
            filter_pattern="clariti",
            filter_mode="include",
        )
        mock_import_study.side_effect = [study_result1, study_result2]

        # Create event with legacy format
        event: Dict[str, Any] = {
            "storage_id": "storage-123",
            "group": "loni",
            "scan_project_label": "scan-metadata",
            "clariti_project_label": "clariti-metadata",
            "clariti_pattern": "clariti",
            "api_key_path": "/test/api-key",
        }

        # Call main handler
        result = main(event, None)

        # Verify result
        assert result["status"] == "success"
        assert len(result["study_results"]) == 2
        assert result["total_file_count"] == 150

    @patch("s3_flywheel_import.import_study_metadata")
    @patch("s3_flywheel_import.ClientHandler")
    @patch("s3_flywheel_import.get_parameters")
    def test_main_with_multiple_studies(
        self,
        mock_get_parameters: Mock,
        mock_client_handler_class: Mock,
        mock_import_study: Mock,
    ) -> None:
        """Test execution with 3+ studies."""
        # Mock SSM parameter retrieval
        mock_get_parameters.return_value = "test-api-key"

        # Mock ClientHandler
        mock_client = Mock()
        mock_client.fw_storage_prefix = "test-prefix/"
        mock_client.fw_provider_id = "provider-123"
        mock_client_handler_class.return_value = mock_client

        # Mock import results for 3 studies
        study_result1 = StudyImportResult(
            project_label="study1",
            duration=10.0,
            file_count=50,
            filter_pattern="pattern1",
            filter_mode="include",
        )
        study_result2 = StudyImportResult(
            project_label="study2",
            duration=20.0,
            file_count=75,
            filter_pattern="pattern2",
            filter_mode="include",
        )
        study_result3 = StudyImportResult(
            project_label="study3",
            duration=15.0,
            file_count=25,
            filter_pattern="pattern3",
            filter_mode="exclude",
        )
        mock_import_study.side_effect = [study_result1, study_result2, study_result3]

        # Create event with 3 studies
        event: Dict[str, Any] = {
            "storage_id": "storage-123",
            "group": "loni",
            "studies": [
                {
                    "project_label": "study1",
                    "filter_pattern": "pattern1",
                    "filter_mode": "include",
                },
                {
                    "project_label": "study2",
                    "filter_pattern": "pattern2",
                    "filter_mode": "include",
                },
                {
                    "project_label": "study3",
                    "filter_pattern": "pattern3",
                    "filter_mode": "exclude",
                },
            ],
            "api_key_path": "/test/api-key",
        }

        # Call main handler
        result = main(event, None)

        # Verify import_study_metadata was called 3 times
        assert mock_import_study.call_count == 3

        # Verify result
        assert result["status"] == "success"
        assert len(result["study_results"]) == 3
        assert result["total_file_count"] == 150  # 50 + 75 + 25

    @patch("s3_flywheel_import.import_study_metadata")
    @patch("s3_flywheel_import.ClientHandler")
    @patch("s3_flywheel_import.get_parameters")
    def test_main_configuration_validation_failure(
        self,
        mock_get_parameters: Mock,
        mock_client_handler_class: Mock,
        mock_import_study: Mock,
    ) -> None:
        """Test configuration validation failure."""
        # Create event with invalid configuration (empty storage_id)
        event: Dict[str, Any] = {
            "storage_id": "",  # Invalid: empty
            "group": "loni",
            "studies": [
                {
                    "project_label": "scan-metadata",
                    "filter_pattern": "scan",
                    "filter_mode": "include",
                }
            ],
            "api_key_path": "/test/api-key",
        }

        # Call main handler
        result = main(event, None)

        # Verify error result
        assert result["status"] == "failed"
        assert result["error_type"] == "ConfigurationError"
        assert "storage_id" in result["error_message"]
        assert result["total_file_count"] == 0
        assert len(result["study_results"]) == 0

        # Verify SSM and ClientHandler were NOT called
        mock_get_parameters.assert_not_called()
        mock_client_handler_class.assert_not_called()

    @patch("s3_flywheel_import.import_study_metadata")
    @patch("s3_flywheel_import.ClientHandler")
    @patch("s3_flywheel_import.get_parameters")
    def test_main_ssm_authentication_failure(
        self,
        mock_get_parameters: Mock,
        mock_client_handler_class: Mock,
        mock_import_study: Mock,
    ) -> None:
        """Test SSM parameter retrieval failure."""
        # Mock SSM parameter retrieval to raise RuntimeError
        mock_get_parameters.side_effect = RuntimeError(
            "Parameter not found. error_type: AuthenticationError"
        )

        # Create valid event
        event: Dict[str, Any] = {
            "storage_id": "storage-123",
            "group": "loni",
            "studies": [
                {
                    "project_label": "scan-metadata",
                    "filter_pattern": "scan",
                    "filter_mode": "include",
                }
            ],
            "api_key_path": "/test/api-key",
        }

        # Call main handler
        result = main(event, None)

        # Verify error result
        assert result["status"] == "failed"
        assert result["error_type"] == "UnexpectedError"
        assert "Parameter not found" in result["error_message"]

        # Verify ClientHandler was NOT called
        mock_client_handler_class.assert_not_called()

    @patch("s3_flywheel_import.import_study_metadata")
    @patch("s3_flywheel_import.ClientHandler")
    @patch("s3_flywheel_import.get_parameters")
    def test_main_partial_success(
        self,
        mock_get_parameters: Mock,
        mock_client_handler_class: Mock,
        mock_import_study: Mock,
    ) -> None:
        """Test partial success when one study fails."""
        # Mock SSM parameter retrieval
        mock_get_parameters.return_value = "test-api-key"

        # Mock ClientHandler
        mock_client = Mock()
        mock_client.fw_storage_prefix = "test-prefix/"
        mock_client.fw_provider_id = "provider-123"
        mock_client_handler_class.return_value = mock_client

        # Mock import results: first succeeds, second fails, third succeeds
        study_result1 = StudyImportResult(
            project_label="study1",
            duration=10.0,
            file_count=50,
            filter_pattern="pattern1",
            filter_mode="include",
        )
        study_result3 = StudyImportResult(
            project_label="study3",
            duration=15.0,
            file_count=25,
            filter_pattern="pattern3",
            filter_mode="include",
        )

        mock_import_study.side_effect = [
            study_result1,
            ValueError("Project not found"),  # Second study fails
            study_result3,
        ]

        # Create event with 3 studies
        event: Dict[str, Any] = {
            "storage_id": "storage-123",
            "group": "loni",
            "studies": [
                {
                    "project_label": "study1",
                    "filter_pattern": "pattern1",
                    "filter_mode": "include",
                },
                {
                    "project_label": "study2",
                    "filter_pattern": "pattern2",
                    "filter_mode": "include",
                },
                {
                    "project_label": "study3",
                    "filter_pattern": "pattern3",
                    "filter_mode": "include",
                },
            ],
            "api_key_path": "/test/api-key",
        }

        # Call main handler
        result = main(event, None)

        # Verify import_study_metadata was called 3 times
        assert mock_import_study.call_count == 3

        # Verify result shows success with partial results
        assert result["status"] == "success"
        assert len(result["study_results"]) == 2  # Only 2 succeeded
        assert result["total_file_count"] == 75  # 50 + 25

    @patch("s3_flywheel_import.import_study_metadata")
    @patch("s3_flywheel_import.ClientHandler")
    @patch("s3_flywheel_import.get_parameters")
    def test_main_http_error(
        self,
        mock_get_parameters: Mock,
        mock_client_handler_class: Mock,
        mock_import_study: Mock,
    ) -> None:
        """Test Flywheel API error (HTTPError)."""
        # Import HTTPError from httpx
        from httpx import HTTPError, Request

        # Mock SSM parameter retrieval
        mock_get_parameters.return_value = "test-api-key"

        # Create a proper HTTPError with a request object
        request = Request("GET", "https://flywheel.example.com/api")
        http_error = HTTPError("API connection failed")
        http_error._request = request

        # Mock ClientHandler to raise HTTPError
        mock_client_handler_class.side_effect = http_error

        # Create valid event
        event: Dict[str, Any] = {
            "storage_id": "storage-123",
            "group": "loni",
            "studies": [
                {
                    "project_label": "scan-metadata",
                    "filter_pattern": "scan",
                    "filter_mode": "include",
                }
            ],
            "api_key_path": "/test/api-key",
        }

        # Call main handler
        result = main(event, None)

        # Verify error result
        assert result["status"] == "failed"
        assert result["error_type"] == "SDKError"
        assert "API connection failed" in result["error_message"]

    @patch("s3_flywheel_import.import_study_metadata")
    @patch("s3_flywheel_import.ClientHandler")
    @patch("s3_flywheel_import.get_parameters")
    def test_main_result_structure_validation(
        self,
        mock_get_parameters: Mock,
        mock_client_handler_class: Mock,
        mock_import_study: Mock,
    ) -> None:
        """Test that result structure is valid."""
        # Mock SSM parameter retrieval
        mock_get_parameters.return_value = "test-api-key"

        # Mock ClientHandler
        mock_client = Mock()
        mock_client.fw_storage_prefix = "test-prefix/"
        mock_client.fw_provider_id = "provider-123"
        mock_client_handler_class.return_value = mock_client

        # Mock import result
        study_result = StudyImportResult(
            project_label="scan-metadata",
            duration=45.5,
            file_count=100,
            filter_pattern="scan",
            filter_mode="include",
        )
        mock_import_study.return_value = study_result

        # Create event
        event: Dict[str, Any] = {
            "storage_id": "storage-123",
            "group": "loni",
            "studies": [
                {
                    "project_label": "scan-metadata",
                    "filter_pattern": "scan",
                    "filter_mode": "include",
                }
            ],
            "api_key_path": "/test/api-key",
        }

        # Call main handler
        result = main(event, None)

        # Verify result structure
        assert "status" in result
        assert "study_results" in result
        assert "total_duration" in result
        assert "total_file_count" in result
        assert "error_message" in result
        assert "error_type" in result
        assert "context" in result

        # Verify study_results structure
        assert len(result["study_results"]) == 1
        study = result["study_results"][0]
        assert "project_label" in study
        assert "duration" in study
        assert "file_count" in study
        assert "filter_pattern" in study
        assert "filter_mode" in study

    @patch("s3_flywheel_import.import_study_metadata")
    @patch("s3_flywheel_import.ClientHandler")
    @patch("s3_flywheel_import.get_parameters")
    def test_main_with_dry_run(
        self,
        mock_get_parameters: Mock,
        mock_client_handler_class: Mock,
        mock_import_study: Mock,
    ) -> None:
        """Test execution with dry_run=True."""
        # Mock SSM parameter retrieval
        mock_get_parameters.return_value = "test-api-key"

        # Mock ClientHandler
        mock_client = Mock()
        mock_client.fw_storage_prefix = "test-prefix/"
        mock_client.fw_provider_id = "provider-123"
        mock_client_handler_class.return_value = mock_client

        # Mock import result with zero files (dry run)
        study_result = StudyImportResult(
            project_label="scan-metadata",
            duration=1.0,
            file_count=0,
            filter_pattern="scan",
            filter_mode="include",
        )
        mock_import_study.return_value = study_result

        # Create event with dry_run=True
        event: Dict[str, Any] = {
            "storage_id": "storage-123",
            "group": "loni",
            "studies": [
                {
                    "project_label": "scan-metadata",
                    "filter_pattern": "scan",
                    "filter_mode": "include",
                }
            ],
            "api_key_path": "/test/api-key",
            "dry_run": True,
        }

        # Call main handler
        result = main(event, None)

        # Verify ClientHandler was initialized with dry_run=True
        mock_client_handler_class.assert_called_once_with(
            fw_api_key="test-api-key",
            fw_storage_id="storage-123",
            aws_profile=None,
            dry_run=True,
        )

        # Verify result
        assert result["status"] == "success"
        assert result["total_file_count"] == 0

    @patch("s3_flywheel_import.import_study_metadata")
    @patch("s3_flywheel_import.ClientHandler")
    @patch("s3_flywheel_import.get_parameters")
    def test_main_with_aws_profile(
        self,
        mock_get_parameters: Mock,
        mock_client_handler_class: Mock,
        mock_import_study: Mock,
    ) -> None:
        """Test execution with custom AWS profile."""
        # Mock SSM parameter retrieval
        mock_get_parameters.return_value = "test-api-key"

        # Mock ClientHandler
        mock_client = Mock()
        mock_client.fw_storage_prefix = "test-prefix/"
        mock_client.fw_provider_id = "provider-123"
        mock_client_handler_class.return_value = mock_client

        # Mock import result
        study_result = StudyImportResult(
            project_label="scan-metadata",
            duration=10.0,
            file_count=50,
            filter_pattern="scan",
            filter_mode="include",
        )
        mock_import_study.return_value = study_result

        # Create event with aws_profile
        event: Dict[str, Any] = {
            "storage_id": "storage-123",
            "group": "loni",
            "studies": [
                {
                    "project_label": "scan-metadata",
                    "filter_pattern": "scan",
                    "filter_mode": "include",
                }
            ],
            "api_key_path": "/test/api-key",
            "aws_profile": "custom-profile",
        }

        # Call main handler
        result = main(event, None)

        # Verify ClientHandler was initialized with custom profile
        mock_client_handler_class.assert_called_once_with(
            fw_api_key="test-api-key",
            fw_storage_id="storage-123",
            aws_profile="custom-profile",
            dry_run=False,
        )

        # Verify result
        assert result["status"] == "success"

    @patch("s3_flywheel_import.import_study_metadata")
    @patch("s3_flywheel_import.ClientHandler")
    @patch("s3_flywheel_import.get_parameters")
    def test_main_with_context_object(
        self,
        mock_get_parameters: Mock,
        mock_client_handler_class: Mock,
        mock_import_study: Mock,
    ) -> None:
        """Test execution with Lambda context object."""
        # Mock SSM parameter retrieval
        mock_get_parameters.return_value = "test-api-key"

        # Mock ClientHandler
        mock_client = Mock()
        mock_client.fw_storage_prefix = "test-prefix/"
        mock_client.fw_provider_id = "provider-123"
        mock_client_handler_class.return_value = mock_client

        # Mock import result
        study_result = StudyImportResult(
            project_label="scan-metadata",
            duration=10.0,
            file_count=50,
            filter_pattern="scan",
            filter_mode="include",
        )
        mock_import_study.return_value = study_result

        # Create event
        event: Dict[str, Any] = {
            "storage_id": "storage-123",
            "group": "loni",
            "studies": [
                {
                    "project_label": "scan-metadata",
                    "filter_pattern": "scan",
                    "filter_mode": "include",
                }
            ],
            "api_key_path": "/test/api-key",
        }

        # Create mock context
        mock_context = Mock()
        mock_context.aws_request_id = "test-request-123"
        mock_context.function_name = "test-function"
        mock_context.memory_limit_in_mb = 512

        # Call main handler with context
        result = main(event, mock_context)

        # Verify result (context is logged but doesn't affect result)
        assert result["status"] == "success"
