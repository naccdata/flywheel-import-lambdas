"""Import operations for S3 to Flywheel data transfer."""

import logging
import time
from typing import Dict, List

from client_handler import ClientHandler
from models import StudyConfig, StudyImportResult

logger = logging.getLogger(__name__)


def import_study_metadata(
    client: ClientHandler,
    group: str,
    study_config: StudyConfig,
) -> StudyImportResult:
    """Import study data to Flywheel project based on study configuration.

    Imports all matching S3 objects into the target Flywheel project.
    Individual file failures are logged and tracked but do not stop
    the remaining files from being processed.

    Args:
        client: Initialized ClientHandler instance
        group: Project group name (e.g., "loni")
        study_config: Study configuration with project label, filter pattern,
            and filter mode

    Returns:
        StudyImportResult containing duration, file count, and any failures

    Raises:
        HTTPError: If Flywheel API calls fail during setup (project lookup)
        ValueError: If project not found or configuration invalid
    """
    start_time = time.time()
    file_count = 0
    failed_files: List[Dict[str, str]] = []

    logger.info(
        f"Starting import for study: {study_config.project_label} "
        f"(filter_mode={study_config.filter_mode}, "
        f"filter_pattern='{study_config.filter_pattern}')"
    )

    # Step 1: Get project ID
    project_id = client.get_project_id(group, study_config.project_label)
    logger.info(f"Project ID for {study_config.project_label}: {project_id}")

    # Step 2: Filter S3 objects based on filter mode
    if study_config.filter_mode == "exclude":
        objects = client.filter_objects(exclude_pattern=study_config.filter_pattern)
        logger.info(
            f"Filtering objects: excluding pattern '{study_config.filter_pattern}'"
        )
    elif study_config.filter_mode == "include":
        objects = client.filter_objects(include_pattern=study_config.filter_pattern)
        logger.info(
            f"Filtering objects: including pattern '{study_config.filter_pattern}'"
        )
    else:
        raise ValueError(
            f"Invalid filter_mode: {study_config.filter_mode}. "
            "Must be 'include' or 'exclude'"
        )

    # Step 3: Import each file, tracking successes and failures individually
    for file in objects:
        if file.size == 0:
            logger.info(f"Skipping directory: {file.key}")
            continue

        file_num = file_count + len(failed_files) + 1
        logger.info(
            f"[File {file_num}] Importing: {file.key} "
            f"(size={file.size}) to project {project_id}"
        )

        try:
            client.import_to_flywheel(project_id, file)
            file_count += 1
            logger.info(f"[File {file_num}] Success: {file.key}")
        except Exception as e:
            error_msg = f"{type(e).__name__}: {e}"
            logger.error(
                f"[File {file_num}] FAILED: {file.key} - {error_msg}"
            )
            failed_files.append({"key": file.key, "error": error_msg})

    # Log summary
    duration = time.time() - start_time
    logger.info(
        f"Completed import for {study_config.project_label}: "
        f"{file_count} succeeded, {len(failed_files)} failed, "
        f"{duration:.2f} seconds"
    )
    if failed_files:
        logger.error(
            f"Failed files for {study_config.project_label}: "
            + ", ".join(f["key"] for f in failed_files)
        )

    return StudyImportResult(
        project_label=study_config.project_label,
        duration=duration,
        file_count=file_count,
        filter_pattern=study_config.filter_pattern,
        filter_mode=study_config.filter_mode,
        failed_files=failed_files if failed_files else None,
    )
