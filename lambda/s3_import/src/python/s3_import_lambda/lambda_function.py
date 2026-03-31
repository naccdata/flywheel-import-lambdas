"""Lambda handler for S3-to-Flywheel copy-by-reference import.

Parses an ImportConfig from the Lambda event, retrieves the Flywheel API
key from SSM Parameter Store, initializes a ClientHandler, and processes
each PrefixPathPair sequentially.  Returns a structured ImportResult.

Fatal errors (invalid configuration, authentication failures, SDK errors)
are raised as exceptions so that Step Functions can catch them via Catch/Retry
blocks.  Only operational results (including partial pair failures) are
returned as structured responses.
"""

import time
import traceback
from typing import Any

import boto3
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext
from flywheel_client.client_handler import ClientHandler
from s3_import_models.models import ImportConfig, ImportResult, PairImportResult

from s3_import_lambda.import_operations import import_pair_files

logger = Logger(__name__)


def get_api_key(api_key_path: str, aws_profile: str | None = None) -> str:
    """Retrieve Flywheel API key from SSM Parameter Store.

    Args:
        api_key_path: SSM parameter path for the API key.
        aws_profile: Optional AWS profile name for the boto3 session.

    Returns:
        The API key string.

    Raises:
        RuntimeError: If parameter retrieval fails for any reason.
    """
    logger.info("Retrieving API key from SSM", api_key_path=api_key_path)
    session = boto3.Session(profile_name=aws_profile)
    ssm = session.client("ssm")

    try:
        response = ssm.get_parameter(Name=api_key_path, WithDecryption=True)
        logger.info("API key retrieved successfully")
        return str(response["Parameter"]["Value"])
    except ssm.exceptions.ParameterNotFound as exc:
        msg = (
            f"Parameter not found in SSM Parameter Store: {api_key_path}. "
            "Ensure the parameter exists and the path is correct."
        )
        logger.error(msg)
        raise RuntimeError(msg) from exc
    except ssm.exceptions.AccessDeniedException as exc:
        msg = (
            f"Access denied when retrieving parameter: {api_key_path}. "
            "Ensure the Lambda IAM role has ssm:GetParameter permission."
        )
        logger.error(msg)
        raise RuntimeError(msg) from exc
    except Exception as exc:
        msg = f"Failed to retrieve parameter {api_key_path} from SSM: {exc}"
        logger.error(msg)
        raise RuntimeError(msg) from exc


def lambda_handler(event: dict[str, Any], context: LambdaContext) -> dict[str, Any]:
    """Lambda entry point for S3-to-Flywheel import.

    Parses the event into an ImportConfig, retrieves the API key,
    initialises a ClientHandler, and processes each prefix-path pair.

    Fatal errors (validation, authentication, SDK) are raised as exceptions
    so that Step Functions Catch/Retry blocks can handle them.  Only
    operational results (including partial pair failures) are returned as
    structured ImportResult responses.

    Args:
        event: Lambda event payload matching ImportConfig schema.
        context: Lambda runtime context.

    Returns:
        Serialised ImportResult dictionary.

    Raises:
        ValidationError: If the event payload fails ImportConfig validation.
        RuntimeError: If SSM parameter retrieval fails.
        HTTPError: If the Flywheel SDK raises an HTTP error during init.
    """
    start_time = time.time()

    logger.info(
        "Lambda started",
        aws_request_id=context.aws_request_id,
        function_name=context.function_name,
        memory_limit_in_mb=context.memory_limit_in_mb,
        event=event,
    )

    # Steps 1-3 are not wrapped in try/except — fatal errors propagate
    # to the Lambda runtime so Step Functions can catch them.

    # Step 1: Parse and validate configuration
    config = ImportConfig(**event)

    # Step 2: Retrieve API key from SSM
    api_key = get_api_key(config.api_key_path, config.aws_profile)

    # Step 3: Initialise ClientHandler
    client = ClientHandler(
        fw_api_key=api_key,
        fw_storage_id=config.storage_id,
        aws_profile=config.aws_profile,
        dry_run=config.dry_run,
    )

    # Step 4: Process each prefix-path pair
    pair_results: list[PairImportResult] = []
    total_file_count = 0

    for idx, pair in enumerate(config.prefix_path_pairs, 1):
        try:
            pair_result = import_pair_files(client=client, pair=pair)
            pair_results.append(pair_result)
            total_file_count += pair_result.file_count
        except Exception as exc:
            error_msg = f"{type(exc).__name__}: {exc}"
            logger.error(
                "Pair processing failed, continuing to next pair",
                pair_index=idx,
                fw_project=pair.fw_project,
                error=traceback.format_exc(),
            )
            pair_results.append(
                PairImportResult(
                    fw_project=pair.fw_project,
                    duration=0.0,
                    file_count=0,
                    failed_files=[{"key": pair.s3_prefix, "error": error_msg}],
                    include_patterns=pair.include_patterns,
                    exclude_patterns=pair.exclude_patterns,
                )
            )

    # Step 5: Build success result
    total_duration = time.time() - start_time
    total_failures = sum(len(r.failed_files) for r in pair_results)

    logger.info(
        "Import completed",
        total_pairs=len(pair_results),
        total_files=total_file_count,
        total_failures=total_failures,
        total_duration=f"{total_duration:.2f}s",
    )

    result = ImportResult(
        status="success",
        pair_results=pair_results,
        total_duration=total_duration,
        total_file_count=total_file_count,
    )
    return result.model_dump()
