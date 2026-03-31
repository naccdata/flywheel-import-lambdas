"""Unit tests for ClientHandler."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from flywheel_client.client_handler import ClientHandler

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_storage_response(
    bucket: str = "test-bucket",
    prefix: str = "storage/prefix",
    provider: str = "provider-123",
) -> MagicMock:
    """Build a mock storage response returned by FWClient.get(...)."""
    config = MagicMock()
    config.bucket = bucket
    config.prefix = prefix
    resp = MagicMock()
    resp.config = config
    resp.provider = provider
    return resp


def _make_s3_object(key: str, size: int) -> MagicMock:
    """Build a mock S3 ObjectSummary."""
    obj = MagicMock()
    obj.key = key
    obj.size = size
    return obj


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def patch_externals() -> Any:
    """Patch FWClient and boto3.Session for ClientHandler construction."""
    storage = _make_storage_response()

    with (
        patch("flywheel_client.client_handler.FWClient") as mock_fw,
        patch("flywheel_client.client_handler.boto3") as mock_boto,
    ):
        mock_fw_instance = MagicMock()
        mock_fw.return_value = mock_fw_instance
        mock_fw_instance.get.return_value = storage

        mock_session = MagicMock()
        mock_boto.Session.return_value = mock_session
        mock_s3 = MagicMock()
        mock_session.resource.return_value = mock_s3
        mock_bucket = MagicMock()
        mock_s3.Bucket.return_value = mock_bucket

        yield {
            "FWClient": mock_fw,
            "fw_instance": mock_fw_instance,
            "boto3": mock_boto,
            "session": mock_session,
            "s3": mock_s3,
            "bucket": mock_bucket,
            "storage": storage,
        }


# ---------------------------------------------------------------------------
# Init wiring
# ---------------------------------------------------------------------------


class TestClientHandlerInit:
    """Verify __init__ wires FWClient, storage config, and S3 bucket."""

    def test_fw_client_created_with_api_key(self, patch_externals: Any) -> None:
        mocks = patch_externals
        ClientHandler(fw_api_key="my-key", fw_storage_id="stor-1")
        mocks["FWClient"].assert_called_once_with(api_key="my-key")

    def test_storage_config_retrieved(self, patch_externals: Any) -> None:
        mocks = patch_externals
        ClientHandler(fw_api_key="k", fw_storage_id="stor-1")
        mocks["fw_instance"].get.assert_called_once_with("/xfer/storages/stor-1")

    def test_s3_bucket_created_from_storage_config(self, patch_externals: Any) -> None:
        mocks = patch_externals
        ClientHandler(fw_api_key="k", fw_storage_id="stor-1")
        mocks["boto3"].Session.assert_called_once_with(profile_name=None)
        mocks["session"].resource.assert_called_once_with("s3")
        mocks["s3"].Bucket.assert_called_once_with("test-bucket")

    def test_aws_profile_forwarded_to_session(self, patch_externals: Any) -> None:
        mocks = patch_externals
        ClientHandler(fw_api_key="k", fw_storage_id="s", aws_profile="my-profile")
        mocks["boto3"].Session.assert_called_once_with(profile_name="my-profile")

    def test_properties_expose_storage_values(self, patch_externals: Any) -> None:
        handler = ClientHandler(fw_api_key="k", fw_storage_id="s")
        assert handler.fw_storage_prefix == "storage/prefix"
        assert handler.fw_provider_id == "provider-123"


# ---------------------------------------------------------------------------
# get_project_id
# ---------------------------------------------------------------------------


class TestGetProjectId:
    """Tests for get_project_id."""

    def test_successful_lookup_returns_project_id(self, patch_externals: Any) -> None:
        mocks = patch_externals
        response = MagicMock()
        response.project._id = "proj-abc"  # noqa: SLF001
        mocks["fw_instance"].post.return_value = response

        handler = ClientHandler(fw_api_key="k", fw_storage_id="s")
        result = handler.get_project_id("grp", "label")

        assert result == "proj-abc"
        mocks["fw_instance"].post.assert_called_once_with(
            "/xfer/upload/lookup",
            json={"group": {"id": "grp"}, "project": {"label": "label"}},
        )

    def test_failed_lookup_raises_value_error(self, patch_externals: Any) -> None:
        mocks = patch_externals
        # Simulate missing project attribute
        response = MagicMock(spec=[])  # empty spec → no .project attr
        mocks["fw_instance"].post.return_value = response

        handler = ClientHandler(fw_api_key="k", fw_storage_id="s")
        with pytest.raises(ValueError, match="Project not found"):
            handler.get_project_id("bad-group", "bad-label")


# ---------------------------------------------------------------------------
# filter_objects
# ---------------------------------------------------------------------------


class TestFilterObjects:
    """Tests for filter_objects with various pattern combinations."""

    def test_no_patterns_yields_all_nonzero_objects(self, patch_externals: Any) -> None:
        mocks = patch_externals
        objects = [
            _make_s3_object("prefix/a.csv", 100),
            _make_s3_object("prefix/b.csv", 200),
        ]
        mocks["bucket"].objects.filter.return_value = objects

        handler = ClientHandler(fw_api_key="k", fw_storage_id="s")
        result = list(handler.filter_objects("prefix/"))

        assert len(result) == 2
        assert result[0].key == "prefix/a.csv"
        assert result[1].key == "prefix/b.csv"

    def test_zero_byte_objects_always_skipped(self, patch_externals: Any) -> None:
        mocks = patch_externals
        objects = [
            _make_s3_object("prefix/dir/", 0),
            _make_s3_object("prefix/file.csv", 50),
            _make_s3_object("prefix/empty", 0),
        ]
        mocks["bucket"].objects.filter.return_value = objects

        handler = ClientHandler(fw_api_key="k", fw_storage_id="s")
        result = list(handler.filter_objects("prefix/"))

        assert len(result) == 1
        assert result[0].key == "prefix/file.csv"

    def test_include_patterns_only(self, patch_externals: Any) -> None:
        mocks = patch_externals
        objects = [
            _make_s3_object("prefix/data.csv", 10),
            _make_s3_object("prefix/data.tsv", 20),
            _make_s3_object("prefix/image.png", 30),
        ]
        mocks["bucket"].objects.filter.return_value = objects

        handler = ClientHandler(fw_api_key="k", fw_storage_id="s")
        result = list(
            handler.filter_objects("prefix/", include_patterns=[".csv", ".tsv"])
        )

        assert len(result) == 2
        keys = [o.key for o in result]
        assert "prefix/data.csv" in keys
        assert "prefix/data.tsv" in keys

    def test_exclude_patterns_only(self, patch_externals: Any) -> None:
        mocks = patch_externals
        objects = [
            _make_s3_object("prefix/data.csv", 10),
            _make_s3_object("prefix/backup.csv", 20),
            _make_s3_object("prefix/image.png", 30),
        ]
        mocks["bucket"].objects.filter.return_value = objects

        handler = ClientHandler(fw_api_key="k", fw_storage_id="s")
        result = list(handler.filter_objects("prefix/", exclude_patterns=["backup"]))

        assert len(result) == 2
        keys = [o.key for o in result]
        assert "prefix/data.csv" in keys
        assert "prefix/image.png" in keys

    def test_include_and_exclude_patterns(self, patch_externals: Any) -> None:
        """Include first, then exclude."""
        mocks = patch_externals
        objects = [
            _make_s3_object("prefix/data.csv", 10),
            _make_s3_object("prefix/backup.csv", 20),
            _make_s3_object("prefix/image.png", 30),
        ]
        mocks["bucket"].objects.filter.return_value = objects

        handler = ClientHandler(fw_api_key="k", fw_storage_id="s")
        result = list(
            handler.filter_objects(
                "prefix/",
                include_patterns=[".csv"],
                exclude_patterns=["backup"],
            )
        )

        assert len(result) == 1
        assert result[0].key == "prefix/data.csv"

    def test_empty_prefix_returns_no_objects(self, patch_externals: Any) -> None:
        mocks = patch_externals
        mocks["bucket"].objects.filter.return_value = []

        handler = ClientHandler(fw_api_key="k", fw_storage_id="s")
        result = list(handler.filter_objects(""))

        assert result == []


# ---------------------------------------------------------------------------
# import_to_flywheel
# ---------------------------------------------------------------------------


class TestImportToFlywheel:
    """Tests for import_to_flywheel."""

    def _make_ticket(
        self,
        finish_url: str = "/finish/123",
        ticket_id: str = "ticket-1",
        reference: bool = True,
    ) -> dict[str, Any]:
        """Build a dict-style upload ticket."""
        return {
            "finish_url": finish_url,
            "file": {"reference": reference},
            "_id": ticket_id,
        }

    def test_successful_ticket_creation_and_finalization(
        self, patch_externals: Any
    ) -> None:
        mocks = patch_externals
        ticket = self._make_ticket()
        finalize_resp = {"status": "ok"}

        mocks["fw_instance"].post.reset_mock()
        mocks["fw_instance"].post.side_effect = [ticket, finalize_resp]

        handler = ClientHandler(fw_api_key="k", fw_storage_id="s")
        s3_file = _make_s3_object("storage/prefix/path/file.csv", 1024)

        result = handler.import_to_flywheel("proj-1", s3_file)

        assert isinstance(result, dict)
        assert result["finish_url"] == "/finish/123"
        assert result["file"]["reference"] is True
        # Verify upload ticket was created
        create_call = mocks["fw_instance"].post.call_args_list[0]
        assert create_call[0][0] == "/xfer/upload"
        # Verify finalization was called
        finalize_call = mocks["fw_instance"].post.call_args_list[1]
        assert finalize_call[0][0] == "/finish/123"

    def test_dry_run_makes_no_api_calls(self, patch_externals: Any) -> None:
        mocks = patch_externals
        handler = ClientHandler(fw_api_key="k", fw_storage_id="s", dry_run=True)
        # Reset post call count after init
        mocks["fw_instance"].post.reset_mock()

        s3_file = _make_s3_object("prefix/file.csv", 512)
        result = handler.import_to_flywheel("proj-1", s3_file)

        assert result == {}
        mocks["fw_instance"].post.assert_not_called()

    def test_missing_reference_raises_value_error(self, patch_externals: Any) -> None:
        mocks = patch_externals
        ticket = self._make_ticket(reference=False)
        mocks["fw_instance"].post.reset_mock()
        mocks["fw_instance"].post.return_value = ticket

        handler = ClientHandler(fw_api_key="k", fw_storage_id="s")
        s3_file = _make_s3_object("prefix/file.csv", 100)

        with pytest.raises(ValueError, match="reference"):
            handler.import_to_flywheel("proj-1", s3_file)

    def test_missing_finish_url_raises_value_error(self, patch_externals: Any) -> None:
        mocks = patch_externals
        ticket = self._make_ticket(finish_url="")
        mocks["fw_instance"].post.reset_mock()
        mocks["fw_instance"].post.return_value = ticket

        handler = ClientHandler(fw_api_key="k", fw_storage_id="s")
        s3_file = _make_s3_object("prefix/file.csv", 100)

        with pytest.raises(ValueError, match="finish_url"):
            handler.import_to_flywheel("proj-1", s3_file)
