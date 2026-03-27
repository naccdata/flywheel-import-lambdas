"""ClientHandler for Flywheel and AWS operations."""

from typing import Any, Dict, Iterator, Optional

import boto3
from fw_client import FWClient  # type: ignore[attr-defined]


class ClientHandler:
    """Handles Flywheel API and AWS S3 operations for import workflow."""

    def __init__(
        self,
        fw_api_key: str,
        fw_storage_id: str,
        aws_profile: Optional[str] = None,
        dry_run: bool = False,
    ) -> None:
        """Initialize ClientHandler with Flywheel and AWS clients.

        Args:
            fw_api_key: Flywheel API key for authentication
            fw_storage_id: Flywheel storage ID to use for imports
            aws_profile: Optional AWS profile name for S3 access
            dry_run: If True, log operations without executing them

        Raises:
            HTTPError: If Flywheel API calls fail
            ClientError: If AWS S3 operations fail
        """
        # Initialize Flywheel client
        self.__fw_client = FWClient(api_key=fw_api_key)

        # Retrieve storage configuration from Flywheel
        storage_response: Any = self.__fw_client.get(
            f"/xfer/storages/{fw_storage_id}"
        )
        self.__fw_storage = storage_response

        # Initialize S3 bucket client
        session = boto3.Session(profile_name=aws_profile)
        s3_resource = session.resource("s3")
        self.__aws_source_bucket = s3_resource.Bucket(
            self.__fw_storage.config.bucket
        )

        # Store dry_run flag
        self.__dry_run = dry_run


    @property
    def fw_storage_prefix(self) -> str:
        """Return the Flywheel storage prefix.

        Returns:
            Storage prefix path from Flywheel storage configuration
        """
        return str(self.__fw_storage.config.prefix)

    @property
    def fw_provider_id(self) -> str:
        """Return the Flywheel storage provider ID.

        Returns:
            Provider ID from Flywheel storage configuration
        """
        return str(self.__fw_storage.provider)


    def get_project_id(self, group: str, label: str) -> str:
        """Find Flywheel project ID by group name and project label.

        Uses the POST /xfer/upload/lookup API endpoint to retrieve the project ID
        for a given group and label combination.

        Args:
            group: Project group name (e.g., "loni")
            label: Project label (e.g., "scan-metadata")

        Returns:
            Flywheel project ID string

        Raises:
            HTTPError: If project lookup fails or project not found
        """
        import logging

        logger = logging.getLogger(__name__)
        logger.info(f"Looking up project ID for group='{group}', label='{label}'")

        # Use POST /xfer/upload/lookup API endpoint
        url = "/xfer/upload/lookup"
        payload = {"group": {"id": group}, "project": {"label": label}}

        # Make API request
        response: Any = self.__fw_client.post(url, json=payload)

        # Extract project_id from response object
        # The response is an object with a 'project' attribute that has an '_id' field
        try:
            project_id = response.project._id
        except AttributeError as e:
            error_msg = f"Project not found for group='{group}', label='{label}'"
            logger.error(error_msg)
            raise ValueError(error_msg) from e

        logger.info(f"Found project ID: {project_id}")
        return str(project_id)

    def filter_objects(
        self,
        include_pattern: Optional[str] = None,
        exclude_pattern: Optional[str] = None,
    ) -> Iterator[Any]:
        """Filter S3 objects by include/exclude patterns.

        Uses lazy iteration (generator) to minimize memory usage. Filters objects
        based on case-sensitive substring matching on the full S3 key.

        Args:
            include_pattern: Path substring to include (e.g., "clariti").
                Only objects containing this pattern in their key are yielded.
            exclude_pattern: Path substring to exclude (e.g., "clariti").
                Objects containing this pattern in their key are skipped.

        Yields:
            s3.ObjectSummary: Filtered S3 object summaries

        Notes:
            - If include_pattern is specified, only objects matching that
              pattern are yielded
            - If exclude_pattern is specified, objects matching that
              pattern are skipped
            - Patterns are case-sensitive substring matches on the full
              S3 key
            - If neither pattern is specified, all objects with storage
              prefix are yielded
        """
        import logging

        logger = logging.getLogger(__name__)

        # Get all objects with the storage prefix
        objects = self.__aws_source_bucket.objects.filter(
            Prefix=self.fw_storage_prefix
        )

        # Apply filtering based on patterns
        for obj in objects:
            # Include pattern: yield only if pattern is in key
            if include_pattern is not None:
                if include_pattern in obj.key:
                    logger.debug(
                        f"Including object: {obj.key} "
                        f"(matches pattern '{include_pattern}')"
                    )
                    yield obj
                else:
                    logger.debug(
                        f"Skipping object: {obj.key} "
                        f"(does not match pattern '{include_pattern}')"
                    )
            # Exclude pattern: yield only if pattern is NOT in key
            elif exclude_pattern is not None:
                if exclude_pattern not in obj.key:
                    logger.debug(
                        f"Including object: {obj.key} "
                        f"(does not match exclude pattern "
                        f"'{exclude_pattern}')"
                    )
                    yield obj
                else:
                    logger.debug(
                        f"Excluding object: {obj.key} "
                        f"(matches exclude pattern '{exclude_pattern}')"
                    )
            # No pattern: yield all objects
            else:
                logger.debug(f"Including object: {obj.key} (no filter pattern)")
                yield obj
    def import_to_flywheel(self, project_id: str, file: Any) -> Dict[str, Any]:
        """Import S3 file to Flywheel project via copy-by-reference.

        Uses the two-step upload ticket process:
        1. POST /xfer/upload to create upload ticket
        2. POST to ticket["finish_url"] to finalize import

        Args:
            project_id: Target Flywheel project ID
            file: S3 ObjectSummary to import

        Returns:
            API response payload with ticket information

        Raises:
            HTTPError: If API call fails
            ValueError: If response doesn't contain reference=True
        """
        import logging

        logger = logging.getLogger(__name__)

        # If dry_run mode, log operation and return empty dict
        if self.__dry_run:
            logger.info(
                f"[DRY RUN] Would import file: {file.key} "
                f"(size={file.size}) to project {project_id}"
            )
            return {}

        logger.info(f"Importing file: {file.key} to project {project_id}")

        # Step 1: POST /xfer/upload to create upload ticket
        # Calculate the path relative to storage prefix
        file_path = file.key
        if self.fw_storage_prefix:
            file_path = file.key.replace(f'{self.fw_storage_prefix}/', '', 1)

        upload_payload: Dict[str, Any] = {
            "project": {
                "id": project_id
            },
            "file": {
                "name": file.key.split('/')[-1],
                "path": file_path,
                "size": file.size,
                "provider_id": self.fw_provider_id,
                "reference": True,
            },
            "conflict_strategy": "update"
        }

        logger.info(f"Creating upload ticket for: {file.key}")
        logger.debug(f"Upload payload: {upload_payload}")
        ticket: Any = self.__fw_client.post("/xfer/upload", json=upload_payload)

        # The response IS the ticket - no nested ticket field
        # Get finish_url from ticket
        if hasattr(ticket, "get"):
            finish_url = ticket.get("finish_url")
        else:
            finish_url = getattr(ticket, "finish_url", None)

        if not finish_url:
            error_msg = f"No finish_url in ticket for file: {file.key}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.info(f"Upload ticket created for: {file.key}")

        # Step 2: POST to ticket["finish_url"] to finalize
        if hasattr(ticket, "get"):
            ticket_id = ticket.get("_id")
        else:
            ticket_id = getattr(ticket, "_id", None)

        logger.info(f"Finalizing upload for: {file.key}")
        finalize_response: Any = self.__fw_client.post(
            finish_url, json={"_id": ticket_id}
        )

        # Verify response contains reference=True
        if hasattr(ticket, "get"):
            file_info = ticket.get("file", {})
        else:
            file_info = getattr(ticket, "file", {})

        if hasattr(file_info, "get"):
            is_reference = file_info.get("reference", False)
        else:
            is_reference = getattr(file_info, "reference", False)

        if not is_reference:
            error_msg = (
                f"Import did not create reference for file: {file.key}. "
                f"Expected reference=True, got reference={is_reference}"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.info(
            f"Successfully imported file: {file.key} "
            f"(reference=True, size={file.size})"
        )

        # Return API response payload
        if hasattr(finalize_response, "__dict__"):
            return dict(finalize_response)
        return {}  # Return empty dict if response is not dict-like

    def post(self, url: str, json: Dict[str, Any]) -> Dict[str, Any]:
        """Post request to Flywheel API.

        Wraps FWClient POST requests with logging. Does not log the payload
        to avoid logging sensitive data.

        Args:
            url: API endpoint path (e.g., "/xfer/upload")
            json: Request payload

        Returns:
            API response as dictionary

        Raises:
            HTTPError: If API request fails
        """
        import logging

        logger = logging.getLogger(__name__)

        # Log request URL only (not payload to avoid logging sensitive data)
        logger.debug(f"POST request to: {url}")

        # Make POST request using FWClient
        response: Any = self.__fw_client.post(url, json=json)

        logger.debug(f"POST response received from: {url}")

        return dict(response)





