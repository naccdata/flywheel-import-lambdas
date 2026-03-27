"""Unit tests for ClientHandler."""

from unittest.mock import Mock, patch

import pytest

from client_handler import ClientHandler


class TestClientHandlerInit:
    """Tests for ClientHandler initialization."""

    @patch("client_handler.FWClient")
    @patch("client_handler.boto3.Session")
    def test_init_success(
        self, mock_session: Mock, mock_fw_client_class: Mock
    ) -> None:
        """Test successful ClientHandler initialization."""
        # Mock FWClient instance
        mock_fw_client = Mock()
        mock_fw_client_class.return_value = mock_fw_client

        # Mock storage response
        mock_storage = Mock()
        mock_storage.id = "storage-123"
        mock_storage.config.bucket = "test-bucket"
        mock_storage.config.prefix = "test-prefix/"
        mock_storage.provider = "provider-456"
        mock_fw_client.get.return_value = mock_storage

        # Mock boto3 S3 bucket
        mock_bucket = Mock()
        mock_s3_resource = Mock()
        mock_s3_resource.Bucket.return_value = mock_bucket
        mock_session_instance = Mock()
        mock_session_instance.resource.return_value = mock_s3_resource
        mock_session.return_value = mock_session_instance

        # Initialize ClientHandler
        client = ClientHandler(
            fw_api_key="test-api-key",
            fw_storage_id="storage-123",
            aws_profile="test-profile",
            dry_run=False,
        )

        # Verify FWClient was initialized with API key
        mock_fw_client_class.assert_called_once_with(api_key="test-api-key")

        # Verify storage config was retrieved
        mock_fw_client.get.assert_called_once_with("/xfer/storages/storage-123")

        # Verify boto3 session was created with profile
        mock_session.assert_called_once_with(profile_name="test-profile")

        # Verify S3 bucket was created
        mock_s3_resource.Bucket.assert_called_once_with("test-bucket")

        # Verify properties work
        assert client.fw_storage_prefix == "test-prefix/"
        assert client.fw_provider_id == "provider-456"

    @patch("client_handler.FWClient")
    @patch("client_handler.boto3.Session")
    def test_init_without_aws_profile(
        self, mock_session: Mock, mock_fw_client_class: Mock
    ) -> None:
        """Test initialization without AWS profile uses default credentials."""
        # Mock FWClient instance
        mock_fw_client = Mock()
        mock_fw_client_class.return_value = mock_fw_client

        # Mock storage response
        mock_storage = Mock()
        mock_storage.id = "storage-123"
        mock_storage.config.bucket = "test-bucket"
        mock_storage.config.prefix = "test-prefix/"
        mock_storage.provider = "provider-456"
        mock_fw_client.get.return_value = mock_storage

        # Mock boto3 S3 bucket
        mock_bucket = Mock()
        mock_s3_resource = Mock()
        mock_s3_resource.Bucket.return_value = mock_bucket
        mock_session_instance = Mock()
        mock_session_instance.resource.return_value = mock_s3_resource
        mock_session.return_value = mock_session_instance

        # Initialize ClientHandler without aws_profile
        _ = ClientHandler(
            fw_api_key="test-api-key",
            fw_storage_id="storage-123",
        )

        # Verify boto3 session was created with None profile
        mock_session.assert_called_once_with(profile_name=None)

    @patch("client_handler.FWClient")
    @patch("client_handler.boto3.Session")
    def test_init_dry_run_mode(
        self, mock_session: Mock, mock_fw_client_class: Mock
    ) -> None:
        """Test initialization with dry_run=True."""
        # Mock FWClient instance
        mock_fw_client = Mock()
        mock_fw_client_class.return_value = mock_fw_client

        # Mock storage response
        mock_storage = Mock()
        mock_storage.id = "storage-123"
        mock_storage.config.bucket = "test-bucket"
        mock_storage.config.prefix = "test-prefix/"
        mock_storage.provider = "provider-456"
        mock_fw_client.get.return_value = mock_storage

        # Mock boto3 S3 bucket
        mock_bucket = Mock()
        mock_s3_resource = Mock()
        mock_s3_resource.Bucket.return_value = mock_bucket
        mock_session_instance = Mock()
        mock_session_instance.resource.return_value = mock_s3_resource
        mock_session.return_value = mock_session_instance

        # Initialize ClientHandler with dry_run=True
        client = ClientHandler(
            fw_api_key="test-api-key",
            fw_storage_id="storage-123",
            dry_run=True,
        )

        # Verify initialization succeeded
        assert client.fw_storage_prefix == "test-prefix/"


class TestGetProjectId:
    """Tests for get_project_id method."""

    @patch("client_handler.FWClient")
    @patch("client_handler.boto3.Session")
    def test_get_project_id_success(
        self, mock_session: Mock, mock_fw_client_class: Mock
    ) -> None:
        """Test successful project ID lookup."""
        # Setup mocks
        mock_fw_client = Mock()
        mock_fw_client_class.return_value = mock_fw_client

        mock_storage = Mock()
        mock_storage.id = "storage-123"
        mock_storage.config.bucket = "test-bucket"
        mock_storage.config.prefix = "test-prefix/"
        mock_storage.provider = "provider-456"
        mock_fw_client.get.return_value = mock_storage

        mock_bucket = Mock()
        mock_s3_resource = Mock()
        mock_s3_resource.Bucket.return_value = mock_bucket
        mock_session_instance = Mock()
        mock_session_instance.resource.return_value = mock_s3_resource
        mock_session.return_value = mock_session_instance

        # Mock project lookup response
        mock_fw_client.post.return_value = {"project_id": "project-789"}

        # Initialize client
        client = ClientHandler(
            fw_api_key="test-api-key",
            fw_storage_id="storage-123",
        )

        # Get project ID
        project_id = client.get_project_id("loni", "scan-metadata")

        # Verify API call
        mock_fw_client.post.assert_called_once_with(
            "/xfer/upload/lookup",
            json={"group": {"id": "loni"}, "project": {"label": "scan-metadata"}},
        )

        # Verify result
        assert project_id == "project-789"

    @patch("client_handler.FWClient")
    @patch("client_handler.boto3.Session")
    def test_get_project_id_not_found(
        self, mock_session: Mock, mock_fw_client_class: Mock
    ) -> None:
        """Test project ID lookup when project not found."""
        # Setup mocks
        mock_fw_client = Mock()
        mock_fw_client_class.return_value = mock_fw_client

        mock_storage = Mock()
        mock_storage.id = "storage-123"
        mock_storage.config.bucket = "test-bucket"
        mock_storage.config.prefix = "test-prefix/"
        mock_storage.provider = "provider-456"
        mock_fw_client.get.return_value = mock_storage

        mock_bucket = Mock()
        mock_s3_resource = Mock()
        mock_s3_resource.Bucket.return_value = mock_bucket
        mock_session_instance = Mock()
        mock_session_instance.resource.return_value = mock_s3_resource
        mock_session.return_value = mock_session_instance

        # Mock project lookup response with no project_id
        mock_fw_client.post.return_value = {}

        # Initialize client
        client = ClientHandler(
            fw_api_key="test-api-key",
            fw_storage_id="storage-123",
        )

        # Verify ValueError is raised
        with pytest.raises(ValueError, match="Project not found"):
            client.get_project_id("loni", "nonexistent-project")


class TestFilterObjects:
    """Tests for filter_objects method."""

    @patch("client_handler.FWClient")
    @patch("client_handler.boto3.Session")
    def test_filter_objects_include_pattern(
        self, mock_session: Mock, mock_fw_client_class: Mock
    ) -> None:
        """Test filtering objects with include pattern."""
        # Setup mocks
        mock_fw_client = Mock()
        mock_fw_client_class.return_value = mock_fw_client

        mock_storage = Mock()
        mock_storage.id = "storage-123"
        mock_storage.config.bucket = "test-bucket"
        mock_storage.config.prefix = "test-prefix/"
        mock_storage.provider = "provider-456"
        mock_fw_client.get.return_value = mock_storage

        # Mock S3 objects
        mock_obj1 = Mock()
        mock_obj1.key = "test-prefix/clariti/file1.txt"
        mock_obj2 = Mock()
        mock_obj2.key = "test-prefix/scan/file2.txt"
        mock_obj3 = Mock()
        mock_obj3.key = "test-prefix/clariti/file3.txt"

        mock_bucket = Mock()
        mock_bucket.objects.filter.return_value = [mock_obj1, mock_obj2, mock_obj3]

        mock_s3_resource = Mock()
        mock_s3_resource.Bucket.return_value = mock_bucket
        mock_session_instance = Mock()
        mock_session_instance.resource.return_value = mock_s3_resource
        mock_session.return_value = mock_session_instance

        # Initialize client
        client = ClientHandler(
            fw_api_key="test-api-key",
            fw_storage_id="storage-123",
        )

        # Filter objects with include pattern
        filtered = list(client.filter_objects(include_pattern="clariti"))

        # Verify only objects with "clariti" in key are returned
        assert len(filtered) == 2
        assert filtered[0].key == "test-prefix/clariti/file1.txt"
        assert filtered[1].key == "test-prefix/clariti/file3.txt"

    @patch("client_handler.FWClient")
    @patch("client_handler.boto3.Session")
    def test_filter_objects_exclude_pattern(
        self, mock_session: Mock, mock_fw_client_class: Mock
    ) -> None:
        """Test filtering objects with exclude pattern."""
        # Setup mocks
        mock_fw_client = Mock()
        mock_fw_client_class.return_value = mock_fw_client

        mock_storage = Mock()
        mock_storage.id = "storage-123"
        mock_storage.config.bucket = "test-bucket"
        mock_storage.config.prefix = "test-prefix/"
        mock_storage.provider = "provider-456"
        mock_fw_client.get.return_value = mock_storage

        # Mock S3 objects
        mock_obj1 = Mock()
        mock_obj1.key = "test-prefix/clariti/file1.txt"
        mock_obj2 = Mock()
        mock_obj2.key = "test-prefix/scan/file2.txt"
        mock_obj3 = Mock()
        mock_obj3.key = "test-prefix/scan/file3.txt"

        mock_bucket = Mock()
        mock_bucket.objects.filter.return_value = [mock_obj1, mock_obj2, mock_obj3]

        mock_s3_resource = Mock()
        mock_s3_resource.Bucket.return_value = mock_bucket
        mock_session_instance = Mock()
        mock_session_instance.resource.return_value = mock_s3_resource
        mock_session.return_value = mock_session_instance

        # Initialize client
        client = ClientHandler(
            fw_api_key="test-api-key",
            fw_storage_id="storage-123",
        )

        # Filter objects with exclude pattern
        filtered = list(client.filter_objects(exclude_pattern="clariti"))

        # Verify only objects without "clariti" in key are returned
        assert len(filtered) == 2
        assert filtered[0].key == "test-prefix/scan/file2.txt"
        assert filtered[1].key == "test-prefix/scan/file3.txt"

    @patch("client_handler.FWClient")
    @patch("client_handler.boto3.Session")
    def test_filter_objects_no_pattern(
        self, mock_session: Mock, mock_fw_client_class: Mock
    ) -> None:
        """Test filtering objects without any pattern returns all objects."""
        # Setup mocks
        mock_fw_client = Mock()
        mock_fw_client_class.return_value = mock_fw_client

        mock_storage = Mock()
        mock_storage.id = "storage-123"
        mock_storage.config.bucket = "test-bucket"
        mock_storage.config.prefix = "test-prefix/"
        mock_storage.provider = "provider-456"
        mock_fw_client.get.return_value = mock_storage

        # Mock S3 objects
        mock_obj1 = Mock()
        mock_obj1.key = "test-prefix/file1.txt"
        mock_obj2 = Mock()
        mock_obj2.key = "test-prefix/file2.txt"

        mock_bucket = Mock()
        mock_bucket.objects.filter.return_value = [mock_obj1, mock_obj2]

        mock_s3_resource = Mock()
        mock_s3_resource.Bucket.return_value = mock_bucket
        mock_session_instance = Mock()
        mock_session_instance.resource.return_value = mock_s3_resource
        mock_session.return_value = mock_session_instance

        # Initialize client
        client = ClientHandler(
            fw_api_key="test-api-key",
            fw_storage_id="storage-123",
        )

        # Filter objects without pattern
        filtered = list(client.filter_objects())

        # Verify all objects are returned
        assert len(filtered) == 2

    @patch("client_handler.FWClient")
    @patch("client_handler.boto3.Session")
    def test_filter_objects_empty_result(
        self, mock_session: Mock, mock_fw_client_class: Mock
    ) -> None:
        """Test filtering objects when no objects match pattern."""
        # Setup mocks
        mock_fw_client = Mock()
        mock_fw_client_class.return_value = mock_fw_client

        mock_storage = Mock()
        mock_storage.id = "storage-123"
        mock_storage.config.bucket = "test-bucket"
        mock_storage.config.prefix = "test-prefix/"
        mock_storage.provider = "provider-456"
        mock_fw_client.get.return_value = mock_storage

        # Mock S3 objects
        mock_obj1 = Mock()
        mock_obj1.key = "test-prefix/scan/file1.txt"

        mock_bucket = Mock()
        mock_bucket.objects.filter.return_value = [mock_obj1]

        mock_s3_resource = Mock()
        mock_s3_resource.Bucket.return_value = mock_bucket
        mock_session_instance = Mock()
        mock_session_instance.resource.return_value = mock_s3_resource
        mock_session.return_value = mock_session_instance

        # Initialize client
        client = ClientHandler(
            fw_api_key="test-api-key",
            fw_storage_id="storage-123",
        )

        # Filter objects with pattern that doesn't match
        filtered = list(client.filter_objects(include_pattern="clariti"))

        # Verify empty result
        assert len(filtered) == 0


class TestImportToFlywheel:
    """Tests for import_to_flywheel method."""

    @patch("client_handler.FWClient")
    @patch("client_handler.boto3.Session")
    def test_import_to_flywheel_success(
        self, mock_session: Mock, mock_fw_client_class: Mock
    ) -> None:
        """Test successful file import."""
        # Setup mocks
        mock_fw_client = Mock()
        mock_fw_client_class.return_value = mock_fw_client

        mock_storage = Mock()
        mock_storage.id = "storage-123"
        mock_storage.config.bucket = "test-bucket"
        mock_storage.config.prefix = "test-prefix/"
        mock_storage.provider = "provider-456"
        mock_fw_client.get.return_value = mock_storage

        mock_bucket = Mock()
        mock_s3_resource = Mock()
        mock_s3_resource.Bucket.return_value = mock_bucket
        mock_session_instance = Mock()
        mock_session_instance.resource.return_value = mock_s3_resource
        mock_session.return_value = mock_session_instance

        # Mock upload ticket response
        ticket_response = {
            "ticket": {
                "finish_url": "/xfer/upload/finish/ticket-123",
            }
        }

        # Mock finalize response
        finalize_response = {
            "file": {
                "reference": True,
                "name": "file1.txt",
            }
        }

        # Configure post to return different responses
        mock_fw_client.post.side_effect = [ticket_response, finalize_response]

        # Initialize client
        client = ClientHandler(
            fw_api_key="test-api-key",
            fw_storage_id="storage-123",
        )

        # Mock S3 file object
        mock_file = Mock()
        mock_file.key = "test-prefix/file1.txt"
        mock_file.size = 1024

        # Import file
        result = client.import_to_flywheel("project-789", mock_file)

        # Verify API calls
        assert mock_fw_client.post.call_count == 2

        # Verify first call (create ticket)
        first_call = mock_fw_client.post.call_args_list[0]
        assert first_call[0][0] == "/xfer/upload"
        assert first_call[1]["json"]["project_id"] == "project-789"
        assert first_call[1]["json"]["file_path"] == "test-prefix/file1.txt"
        assert first_call[1]["json"]["file_size"] == 1024
        assert first_call[1]["json"]["storage_id"] == "storage-123"
        assert first_call[1]["json"]["provider_id"] == "provider-456"

        # Verify second call (finalize)
        second_call = mock_fw_client.post.call_args_list[1]
        assert second_call[0][0] == "/xfer/upload/finish/ticket-123"

        # Verify result
        assert result["file"]["reference"] is True

    @patch("client_handler.FWClient")
    @patch("client_handler.boto3.Session")
    def test_import_to_flywheel_dry_run(
        self, mock_session: Mock, mock_fw_client_class: Mock
    ) -> None:
        """Test import in dry_run mode skips API calls."""
        # Setup mocks
        mock_fw_client = Mock()
        mock_fw_client_class.return_value = mock_fw_client

        mock_storage = Mock()
        mock_storage.id = "storage-123"
        mock_storage.config.bucket = "test-bucket"
        mock_storage.config.prefix = "test-prefix/"
        mock_storage.provider = "provider-456"
        mock_fw_client.get.return_value = mock_storage

        mock_bucket = Mock()
        mock_s3_resource = Mock()
        mock_s3_resource.Bucket.return_value = mock_bucket
        mock_session_instance = Mock()
        mock_session_instance.resource.return_value = mock_s3_resource
        mock_session.return_value = mock_session_instance

        # Initialize client with dry_run=True
        client = ClientHandler(
            fw_api_key="test-api-key",
            fw_storage_id="storage-123",
            dry_run=True,
        )

        # Mock S3 file object
        mock_file = Mock()
        mock_file.key = "test-prefix/file1.txt"
        mock_file.size = 1024

        # Import file in dry_run mode
        result = client.import_to_flywheel("project-789", mock_file)

        # Verify no API calls were made (only the initial get for storage config)
        assert mock_fw_client.post.call_count == 0

        # Verify empty result
        assert result == {}

    @patch("client_handler.FWClient")
    @patch("client_handler.boto3.Session")
    def test_import_to_flywheel_no_ticket(
        self, mock_session: Mock, mock_fw_client_class: Mock
    ) -> None:
        """Test import fails when no ticket in response."""
        # Setup mocks
        mock_fw_client = Mock()
        mock_fw_client_class.return_value = mock_fw_client

        mock_storage = Mock()
        mock_storage.id = "storage-123"
        mock_storage.config.bucket = "test-bucket"
        mock_storage.config.prefix = "test-prefix/"
        mock_storage.provider = "provider-456"
        mock_fw_client.get.return_value = mock_storage

        mock_bucket = Mock()
        mock_s3_resource = Mock()
        mock_s3_resource.Bucket.return_value = mock_bucket
        mock_session_instance = Mock()
        mock_session_instance.resource.return_value = mock_s3_resource
        mock_session.return_value = mock_session_instance

        # Mock upload response without ticket
        mock_fw_client.post.return_value = {}

        # Initialize client
        client = ClientHandler(
            fw_api_key="test-api-key",
            fw_storage_id="storage-123",
        )

        # Mock S3 file object
        mock_file = Mock()
        mock_file.key = "test-prefix/file1.txt"
        mock_file.size = 1024

        # Verify ValueError is raised
        with pytest.raises(ValueError, match="No ticket in upload response"):
            client.import_to_flywheel("project-789", mock_file)

    @patch("client_handler.FWClient")
    @patch("client_handler.boto3.Session")
    def test_import_to_flywheel_not_reference(
        self, mock_session: Mock, mock_fw_client_class: Mock
    ) -> None:
        """Test import fails when reference=False."""
        # Setup mocks
        mock_fw_client = Mock()
        mock_fw_client_class.return_value = mock_fw_client

        mock_storage = Mock()
        mock_storage.id = "storage-123"
        mock_storage.config.bucket = "test-bucket"
        mock_storage.config.prefix = "test-prefix/"
        mock_storage.provider = "provider-456"
        mock_fw_client.get.return_value = mock_storage

        mock_bucket = Mock()
        mock_s3_resource = Mock()
        mock_s3_resource.Bucket.return_value = mock_bucket
        mock_session_instance = Mock()
        mock_session_instance.resource.return_value = mock_s3_resource
        mock_session.return_value = mock_session_instance

        # Mock responses
        ticket_response = {
            "ticket": {
                "finish_url": "/xfer/upload/finish/ticket-123",
            }
        }

        finalize_response = {
            "file": {
                "reference": False,  # Not a reference import
            }
        }

        mock_fw_client.post.side_effect = [ticket_response, finalize_response]

        # Initialize client
        client = ClientHandler(
            fw_api_key="test-api-key",
            fw_storage_id="storage-123",
        )

        # Mock S3 file object
        mock_file = Mock()
        mock_file.key = "test-prefix/file1.txt"
        mock_file.size = 1024

        # Verify ValueError is raised
        with pytest.raises(ValueError, match="did not create reference"):
            client.import_to_flywheel("project-789", mock_file)


class TestPost:
    """Tests for post method."""

    @patch("client_handler.FWClient")
    @patch("client_handler.boto3.Session")
    def test_post_success(
        self, mock_session: Mock, mock_fw_client_class: Mock
    ) -> None:
        """Test successful POST request."""
        # Setup mocks
        mock_fw_client = Mock()
        mock_fw_client_class.return_value = mock_fw_client

        mock_storage = Mock()
        mock_storage.id = "storage-123"
        mock_storage.config.bucket = "test-bucket"
        mock_storage.config.prefix = "test-prefix/"
        mock_storage.provider = "provider-456"
        mock_fw_client.get.return_value = mock_storage

        mock_bucket = Mock()
        mock_s3_resource = Mock()
        mock_s3_resource.Bucket.return_value = mock_bucket
        mock_session_instance = Mock()
        mock_session_instance.resource.return_value = mock_s3_resource
        mock_session.return_value = mock_session_instance

        # Mock POST response
        mock_fw_client.post.return_value = {"result": "success"}

        # Initialize client
        client = ClientHandler(
            fw_api_key="test-api-key",
            fw_storage_id="storage-123",
        )

        # Make POST request
        result = client.post("/test/endpoint", json={"key": "value"})

        # Verify API call
        mock_fw_client.post.assert_called_with("/test/endpoint", json={"key": "value"})

        # Verify result
        assert result == {"result": "success"}
