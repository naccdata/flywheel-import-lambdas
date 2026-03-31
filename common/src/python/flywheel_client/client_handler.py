"""ClientHandler for Flywheel and AWS operations."""

from collections.abc import Iterator
from typing import Any

import boto3
from aws_lambda_powertools import Logger
from fw_client import FWClient  # type: ignore[attr-defined]
from s3_import_models.models import UploadTicket

logger = Logger(__name__)


class ClientHandler:
    """Handles Flywheel API and AWS S3 operations for import workflow."""

    def __init__(
        self,
        fw_api_key: str,
        fw_storage_id: str,
        aws_profile: str | None = None,
        dry_run: bool = False,
    ) -> None:
        """Initialize ClientHandler with Flywheel and AWS clients.

        Args:
            fw_api_key: Flywheel API key for authentication.
            fw_storage_id: Flywheel storage ID to use for imports.
            aws_profile: Optional AWS profile name for S3 access.
            dry_run: If True, log operations without executing them.

        Raises:
            HTTPError: If Flywheel API calls fail.
            ClientError: If AWS S3 operations fail.
        """
        self.__fw_client = FWClient(api_key=fw_api_key)

        storage_response: Any = self.__fw_client.get(f"/xfer/storages/{fw_storage_id}")
        self.__fw_storage = storage_response

        session = boto3.Session(profile_name=aws_profile)
        s3_resource = session.resource("s3")
        self.__aws_source_bucket = s3_resource.Bucket(self.__fw_storage.config.bucket)

        self.__dry_run = dry_run

    @property
    def fw_storage_prefix(self) -> str:
        """Return the Flywheel storage prefix."""
        return str(self.__fw_storage.config.prefix)

    @property
    def fw_provider_id(self) -> str:
        """Return the Flywheel storage provider ID."""
        return str(self.__fw_storage.provider)

    def get_project_id(self, group: str, label: str) -> str:
        """Find Flywheel project ID by group name and project label.

        Uses the POST /xfer/upload/lookup API endpoint to retrieve the
        project ID for a given group and label combination.

        Args:
            group: Project group name.
            label: Project label.

        Returns:
            Flywheel project ID string.

        Raises:
            HTTPError: If project lookup fails or project not found.
        """
        logger.info("Looking up project ID", group=group, label=label)

        url = "/xfer/upload/lookup"
        payload = {"group": {"id": group}, "project": {"label": label}}

        response: Any = self.__fw_client.post(url, json=payload)

        try:
            project_id = response.project._id  # noqa: SLF001
        except AttributeError as e:
            error_msg = f"Project not found for group='{group}', label='{label}'"
            logger.error(error_msg)
            raise ValueError(error_msg) from e

        logger.info("Found project ID", project_id=project_id)
        return str(project_id)

    def filter_objects(
        self,
        s3_prefix: str,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> Iterator[Any]:
        """List S3 objects under s3_prefix, apply include then exclude filters.

        Uses lazy iteration (generator) to minimize memory usage. Skips
        zero-byte objects (directory markers). Applies include-first-then-
        exclude filtering semantics.

        Args:
            s3_prefix: S3 path within the bucket to list objects under.
            include_patterns: If non-empty, keep only objects whose key
                contains at least one pattern as a substring.
            exclude_patterns: If non-empty, remove objects whose key
                contains any pattern as a substring.

        Yields:
            S3 ObjectSummary instances matching the filter criteria.
        """
        objects = self.__aws_source_bucket.objects.filter(Prefix=s3_prefix)

        for obj in objects:
            if obj.size == 0:
                logger.debug("Skipping zero-byte object", key=obj.key)
                continue

            if include_patterns and not any(
                pattern in obj.key for pattern in include_patterns
            ):
                logger.debug("Skipping object (no include match)", key=obj.key)
                continue

            if exclude_patterns and any(
                pattern in obj.key for pattern in exclude_patterns
            ):
                logger.debug("Excluding object (exclude match)", key=obj.key)
                continue

            yield obj

    def import_to_flywheel(self, project_id: str, file: Any) -> dict[str, Any]:
        """Import S3 file to Flywheel project via copy-by-reference.

        Uses the two-step upload ticket process:
        1. POST /xfer/upload to create upload ticket
        2. POST to ticket finish_url to finalize import

        Args:
            project_id: Target Flywheel project ID.
            file: S3 ObjectSummary to import.

        Returns:
            API response payload with ticket information.

        Raises:
            HTTPError: If API call fails.
            ValueError: If response doesn't contain reference=True.
        """
        if self.__dry_run:
            logger.info(
                "DRY RUN: would import file",
                key=file.key,
                size=file.size,
                project_id=project_id,
            )
            return {}

        logger.info("Importing file", key=file.key, project_id=project_id)

        file_path = file.key
        if self.fw_storage_prefix:
            file_path = file.key.replace(f"{self.fw_storage_prefix}/", "", 1)

        upload_payload: dict[str, Any] = {
            "project": {"id": project_id},
            "file": {
                "name": file.key.split("/")[-1],
                "path": file_path,
                "size": file.size,
                "provider_id": self.fw_provider_id,
                "reference": True,
            },
            "conflict_strategy": "update",
        }

        logger.info("Creating upload ticket", key=file.key)
        raw_ticket: Any = self.__fw_client.post("/xfer/upload", json=upload_payload)
        ticket = UploadTicket.from_response(raw_ticket)

        if not ticket.finish_url:
            error_msg = f"No finish_url in ticket for file: {file.key}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        if not ticket.file.reference:
            error_msg = (
                f"Import did not create reference for file: {file.key}. "
                f"Expected reference=True, got reference={ticket.file.reference}"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.info("Finalizing upload", key=file.key)
        self.__fw_client.post(ticket.finish_url, json={"_id": ticket.id})

        logger.info(
            "Successfully imported file",
            key=file.key,
            size=file.size,
        )

        return ticket.model_dump()
