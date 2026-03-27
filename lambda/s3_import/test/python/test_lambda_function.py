"""Unit tests for lambda_function handler and get_api_key."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from httpx import HTTPError
from s3_import_lambda.lambda_function import get_api_key, lambda_handler
from s3_import_models.models import PairImportResult


def _valid_event(**overrides: Any) -> dict[str, Any]:
    """Build a valid Lambda event payload with sensible defaults."""
    event: dict[str, Any] = {
        "storage_id": "stor-123",
        "api_key_path": "/prod/flywheel/apikey",
        "prefix_path_pairs": [
            {
                "s3_prefix": "data/center1",
                "fw_group": "grp",
                "fw_project": "proj",
            }
        ],
    }
    event.update(overrides)
    return event


# ---------------------------------------------------------------------------
# End-to-end handler flow
# ---------------------------------------------------------------------------


class TestLambdaHandlerFlow:
    """Test the happy-path handler flow with mocked dependencies."""

    @patch("s3_import_lambda.lambda_function.import_pair_files")
    @patch("s3_import_lambda.lambda_function.ClientHandler")
    @patch("s3_import_lambda.lambda_function.get_api_key")
    def test_successful_single_pair_import(
        self,
        mock_get_key: MagicMock,
        mock_ch_cls: MagicMock,
        mock_import: MagicMock,
        mock_lambda_context: MagicMock,
    ) -> None:
        mock_get_key.return_value = "fake-api-key"
        mock_import.return_value = PairImportResult(
            fw_project="proj",
            duration=1.5,
            file_count=3,
        )

        result = lambda_handler(_valid_event(), mock_lambda_context)

        assert result["status"] == "success"
        assert result["total_file_count"] == 3
        assert len(result["pair_results"]) == 1
        mock_get_key.assert_called_once_with("/prod/flywheel/apikey", None)
        mock_ch_cls.assert_called_once()

    @patch("s3_import_lambda.lambda_function.import_pair_files")
    @patch("s3_import_lambda.lambda_function.ClientHandler")
    @patch("s3_import_lambda.lambda_function.get_api_key")
    def test_multiple_pairs_all_succeed(
        self,
        mock_get_key: MagicMock,
        mock_ch_cls: MagicMock,
        mock_import: MagicMock,
        mock_lambda_context: MagicMock,
    ) -> None:
        mock_get_key.return_value = "key"
        mock_import.side_effect = [
            PairImportResult(fw_project="p1", duration=1.0, file_count=2),
            PairImportResult(fw_project="p2", duration=2.0, file_count=5),
        ]

        event = _valid_event(
            prefix_path_pairs=[
                {"s3_prefix": "a/", "fw_group": "g1", "fw_project": "p1"},
                {"s3_prefix": "b/", "fw_group": "g2", "fw_project": "p2"},
            ]
        )
        result = lambda_handler(event, mock_lambda_context)

        assert result["status"] == "success"
        assert result["total_file_count"] == 7
        assert len(result["pair_results"]) == 2


# ---------------------------------------------------------------------------
# Error classification
# ---------------------------------------------------------------------------


class TestErrorClassification:
    """Test that different exceptions map to correct error_type values."""

    def test_invalid_event_returns_configuration_error(
        self, mock_lambda_context: MagicMock
    ) -> None:
        bad_event: dict[str, Any] = {"storage_id": "", "api_key_path": "no-slash"}
        result = lambda_handler(bad_event, mock_lambda_context)

        assert result["status"] == "failed"
        assert result["error_type"] == "ConfigurationError"

    @patch("s3_import_lambda.lambda_function.get_api_key")
    def test_ssm_failure_returns_authentication_error(
        self,
        mock_get_key: MagicMock,
        mock_lambda_context: MagicMock,
    ) -> None:
        mock_get_key.side_effect = RuntimeError("Parameter not found")
        result = lambda_handler(_valid_event(), mock_lambda_context)

        assert result["status"] == "failed"
        assert result["error_type"] == "AuthenticationError"
        assert "Parameter not found" in result["error_message"]

    @patch("s3_import_lambda.lambda_function.ClientHandler")
    @patch("s3_import_lambda.lambda_function.get_api_key")
    def test_flywheel_http_error_returns_sdk_error(
        self,
        mock_get_key: MagicMock,
        mock_ch_cls: MagicMock,
        mock_lambda_context: MagicMock,
    ) -> None:
        mock_get_key.return_value = "key"
        # Create HTTPError and set .request so str() doesn't raise
        from httpx import Request

        err = HTTPError("Flywheel API error")
        err.request = Request("GET", "https://flywheel.example.com/api")  # type: ignore[assignment]
        mock_ch_cls.side_effect = err
        result = lambda_handler(_valid_event(), mock_lambda_context)

        assert result["status"] == "failed"
        assert result["error_type"] == "SDKError"

    @patch("s3_import_lambda.lambda_function.ClientHandler")
    @patch("s3_import_lambda.lambda_function.get_api_key")
    def test_unexpected_exception_returns_unexpected_error(
        self,
        mock_get_key: MagicMock,
        mock_ch_cls: MagicMock,
        mock_lambda_context: MagicMock,
    ) -> None:
        mock_get_key.return_value = "key"
        mock_ch_cls.side_effect = TypeError("something weird")
        result = lambda_handler(_valid_event(), mock_lambda_context)

        assert result["status"] == "failed"
        assert result["error_type"] == "UnexpectedError"
        assert "something weird" in result["error_message"]


# ---------------------------------------------------------------------------
# Pair-level fault isolation
# ---------------------------------------------------------------------------


class TestPairFaultIsolation:
    """Test that one pair failing doesn't prevent others from running."""

    @patch("s3_import_lambda.lambda_function.import_pair_files")
    @patch("s3_import_lambda.lambda_function.ClientHandler")
    @patch("s3_import_lambda.lambda_function.get_api_key")
    def test_failed_pair_does_not_block_others(
        self,
        mock_get_key: MagicMock,
        mock_ch_cls: MagicMock,
        mock_import: MagicMock,
        mock_lambda_context: MagicMock,
    ) -> None:
        mock_get_key.return_value = "key"
        mock_import.side_effect = [
            PairImportResult(fw_project="p1", duration=1.0, file_count=2),
            ValueError("project lookup failed"),
            PairImportResult(fw_project="p3", duration=1.0, file_count=4),
        ]

        event = _valid_event(
            prefix_path_pairs=[
                {"s3_prefix": "a/", "fw_group": "g1", "fw_project": "p1"},
                {"s3_prefix": "b/", "fw_group": "g2", "fw_project": "p2"},
                {"s3_prefix": "c/", "fw_group": "g3", "fw_project": "p3"},
            ]
        )
        result = lambda_handler(event, mock_lambda_context)

        assert result["status"] == "success"
        # All 3 pairs are represented (pair 2 recorded as failed)
        assert len(result["pair_results"]) == 3
        assert result["total_file_count"] == 6
        # All 3 pairs were attempted
        assert mock_import.call_count == 3

        # The failed pair has file_count=0 and a failure entry
        failed_pair = result["pair_results"][1]
        assert failed_pair["file_count"] == 0
        assert failed_pair["fw_project"] == "p2"
        assert len(failed_pair["failed_files"]) == 1
        assert "project lookup failed" in failed_pair["failed_files"][0]["error"]


# ---------------------------------------------------------------------------
# get_api_key
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Mock SSM exception classes (must be real classes so `except` can catch them)
# ---------------------------------------------------------------------------


class _ParameterNotFound(Exception):
    pass


class _AccessDeniedException(Exception):
    pass


class TestGetApiKey:
    """Tests for SSM parameter retrieval."""

    @staticmethod
    def _wire_ssm_exceptions(mock_ssm: MagicMock) -> None:
        """Attach mock SSM exception classes to a mock SSM client."""
        mock_ssm.exceptions.ParameterNotFound = _ParameterNotFound
        mock_ssm.exceptions.AccessDeniedException = _AccessDeniedException

    @patch("s3_import_lambda.lambda_function.boto3")
    def test_successful_retrieval(self, mock_boto: MagicMock) -> None:
        mock_ssm = MagicMock()
        mock_boto.Session.return_value.client.return_value = mock_ssm
        mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "my-api-key"}}

        result = get_api_key("/prod/flywheel/apikey")

        assert result == "my-api-key"
        mock_ssm.get_parameter.assert_called_once_with(
            Name="/prod/flywheel/apikey", WithDecryption=True
        )

    @patch("s3_import_lambda.lambda_function.boto3")
    def test_parameter_not_found_raises_runtime_error(
        self, mock_boto: MagicMock
    ) -> None:
        mock_ssm = MagicMock()
        mock_boto.Session.return_value.client.return_value = mock_ssm
        self._wire_ssm_exceptions(mock_ssm)

        mock_ssm.get_parameter.side_effect = _ParameterNotFound("not found")

        with pytest.raises(RuntimeError, match="Parameter not found"):
            get_api_key("/missing/path")

    @patch("s3_import_lambda.lambda_function.boto3")
    def test_access_denied_raises_runtime_error(self, mock_boto: MagicMock) -> None:
        mock_ssm = MagicMock()
        mock_boto.Session.return_value.client.return_value = mock_ssm
        self._wire_ssm_exceptions(mock_ssm)

        mock_ssm.get_parameter.side_effect = _AccessDeniedException("access denied")

        with pytest.raises(RuntimeError, match="Access denied"):
            get_api_key("/restricted/path")

    @patch("s3_import_lambda.lambda_function.boto3")
    def test_aws_profile_forwarded_to_session(self, mock_boto: MagicMock) -> None:
        mock_ssm = MagicMock()
        mock_boto.Session.return_value.client.return_value = mock_ssm
        mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "key"}}

        get_api_key("/path", aws_profile="my-profile")

        mock_boto.Session.assert_called_once_with(profile_name="my-profile")
