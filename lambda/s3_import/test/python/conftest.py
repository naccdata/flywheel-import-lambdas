"""Shared test fixtures for s3_import_lambda tests."""

from unittest.mock import MagicMock

import pytest


@pytest.fixture()
def mock_client_handler() -> MagicMock:
    """Create a mock ClientHandler with default method stubs.

    Methods:
        get_project_id: returns "proj-abc"
        filter_objects: returns empty list
        import_to_flywheel: returns empty dict
    """
    client = MagicMock()
    client.get_project_id.return_value = "proj-abc"
    client.filter_objects.return_value = iter([])
    client.import_to_flywheel.return_value = {}
    return client


def make_s3_object(key: str, size: int) -> MagicMock:
    """Build a mock S3 ObjectSummary with .key and .size attributes."""
    obj = MagicMock()
    obj.key = key
    obj.size = size
    return obj


@pytest.fixture()
def mock_lambda_context() -> MagicMock:
    """Create a mock LambdaContext with standard attributes."""
    ctx = MagicMock()
    ctx.aws_request_id = "test-request-id"
    ctx.function_name = "s3-import-lambda"
    ctx.memory_limit_in_mb = 256
    return ctx
