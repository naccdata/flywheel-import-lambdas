"""Import operations for S3 to Flywheel data transfer."""

import time

from aws_lambda_powertools import Logger
from flywheel_client.client_handler import ClientHandler
from s3_import_models.models import PairImportResult, PrefixPathPair

logger = Logger(__name__)


def import_pair_files(
    client: ClientHandler,
    pair: PrefixPathPair,
) -> PairImportResult:
    """Import all matching S3 objects for a single prefix-path pair.

    Looks up the Flywheel project, lists and filters S3 objects under
    the pair's prefix, and imports each file via copy-by-reference.
    Individual file failures are logged and tracked but do not stop
    the remaining files from being processed.

    Args:
        client: Initialized ClientHandler instance.
        pair: PrefixPathPair with S3 prefix, Flywheel group/project,
            and optional include/exclude filter patterns.

    Returns:
        PairImportResult with duration, file count, and any failures.

    Raises:
        HTTPError: If Flywheel API calls fail during project lookup.
        ValueError: If project not found or configuration invalid.
    """
    start_time = time.time()
    file_count = 0
    failed_files: list[dict[str, str]] = []

    logger.info(
        "Starting import for pair",
        s3_prefix=pair.s3_prefix,
        fw_group=pair.fw_group,
        fw_project=pair.fw_project,
        include_patterns=pair.include_patterns,
        exclude_patterns=pair.exclude_patterns,
    )

    # Step 1: Get project ID
    project_id = client.get_project_id(pair.fw_group, pair.fw_project)
    logger.info(
        "Resolved project ID",
        fw_project=pair.fw_project,
        project_id=project_id,
    )

    # Step 2: Filter S3 objects based on include/exclude patterns
    objects = client.filter_objects(
        pair.s3_prefix,
        pair.include_patterns,
        pair.exclude_patterns,
    )

    # Step 3: Import each file, tracking successes and failures individually
    for file in objects:
        file_num = file_count + len(failed_files) + 1
        logger.info(
            "Importing file",
            file_num=file_num,
            key=file.key,
            size=file.size,
            project_id=project_id,
        )

        try:
            client.import_to_flywheel(project_id, file)
            file_count += 1
            logger.info("File imported successfully", file_num=file_num, key=file.key)
        except Exception as e:
            error_msg = f"{type(e).__name__}: {e}"
            logger.error(
                "File import failed",
                file_num=file_num,
                key=file.key,
                error=error_msg,
            )
            failed_files.append({"key": file.key, "error": error_msg})

    duration = time.time() - start_time
    logger.info(
        "Completed import for pair",
        fw_project=pair.fw_project,
        file_count=file_count,
        failed_count=len(failed_files),
        duration=f"{duration:.2f}s",
    )

    return PairImportResult(
        fw_project=pair.fw_project,
        duration=duration,
        file_count=file_count,
        failed_files=failed_files,
        include_patterns=pair.include_patterns,
        exclude_patterns=pair.exclude_patterns,
    )
