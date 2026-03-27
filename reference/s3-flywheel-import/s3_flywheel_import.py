"""
S3 Flywheel Import Lambda Function

This Lambda function performs automated copy-by-reference operations from S3
to Flywheel projects. It imports data into two separate Flywheel projects:
- scan-metadata: General SCAN data (excluding CLARiTI)
- clariti-metadata: CLARiTI-specific data only

The function executes after LONITableData pulls fresh data to S3 and runs
independently without blocking other pipeline tasks.
"""

import logging
import time
from typing import Any, Dict

import boto3
from httpx import HTTPError

from client_handler import ClientHandler
from import_operations import import_study_metadata
from models import ImportConfig, ImportResult

# Configure logging
logging.basicConfig(level=logging.INFO, force=True)
log = logging.getLogger()

# Constants (kept for backward compatibility with environment variables)
DEFAULT_STORAGE_ID = "691c926ff8220b709983b848"
DEFAULT_GROUP = "loni"
DEFAULT_SCAN_PROJECT_LABEL = "scan-metadata"
DEFAULT_CLARITI_PROJECT_LABEL = "clariti-metadata"
DEFAULT_CLARITI_PATTERN = "clariti"
DEFAULT_API_KEY_PATH = "/prod/flywheel/gearbot/apikey"




def get_parameters(param_prefix: str) -> str:
    """
    Get parameter value from AWS SSM Parameter Store.

    Follows the pattern established in loni_table_data.py and
    generate_public_table.py for consistency.

    Parameters
    ----------
    param_prefix : str
        Path for the parameter to get from SSM

    Returns
    -------
    str
        Parameter value from SSM

    Raises
    ------
    RuntimeError
        If parameter retrieval fails, with error_type "AuthenticationError"
    """
    log.info(f"Retrieving parameter from SSM: {param_prefix}")
    ssm = boto3.client("ssm")

    try:
        response = ssm.get_parameter(Name=param_prefix, WithDecryption=True)
        parameter_value = response["Parameter"]["Value"]
        log.info(f"Successfully retrieved parameter: {param_prefix}")
        return parameter_value
    except ssm.exceptions.ParameterNotFound as e:
        error_msg = (
            f"Parameter not found in SSM Parameter Store: {param_prefix}. "
            f"Ensure the parameter exists and the path is correct. "
            f"error_type: AuthenticationError"
        )
        log.error(error_msg)
        raise RuntimeError(error_msg) from e
    except ssm.exceptions.AccessDeniedException as e:
        error_msg = (
            f"Access denied when retrieving parameter: {param_prefix}. "
            f"Ensure the Lambda IAM role has ssm:GetParameter permission. "
            f"error_type: AuthenticationError"
        )
        log.error(error_msg)
        raise RuntimeError(error_msg) from e
    except Exception as e:
        error_msg = f"Failed to retrieve parameter {param_prefix} from SSM: {str(e)}"
        log.error(error_msg)
        raise RuntimeError(error_msg) from e
def main(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for S3 to Flywheel import operations.

    Executes imports for all configured studies using the SDK-based approach.
    Supports both legacy format (scan_project_label, clariti_project_label)
    and new format (studies list) for backward compatibility.

    Parameters
    ----------
    event : dict
        Lambda event object, may contain configuration overrides:
        - storage_id: Flywheel storage instance ID
        - group: Flywheel group name
        - studies: List of study configurations (new format)
        - scan_project_label: SCAN project label (legacy format)
        - clariti_project_label: CLARiTI project label (legacy format)
        - clariti_pattern: Path filter for CLARiTI data (legacy format)
        - api_key_path: SSM parameter path for API key
        - aws_profile: AWS profile name (optional)
        - dry_run: If True, log operations without executing
    context : object
        Lambda context object

    Returns
    -------
    dict
        Execution result with status and details

    Raises
    ------
    ValueError
        If configuration validation fails (ConfigurationError)
    HTTPError
        If Flywheel API calls fail (SDKError)
    Exception
        For unexpected errors (UnexpectedError)
    """
    start_time = time.time()

    # Log Lambda initialization
    log.info("=" * 80)
    log.info("S3 Flywheel Import Lambda started")
    log.info(
        f"Start time: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(start_time))}"
    )
    log.info(
        f"Lambda request ID: "
        f"{getattr(context, 'aws_request_id', 'N/A') if context else 'N/A'}"
    )
    log.info(
        f"Lambda function name: "
        f"{getattr(context, 'function_name', 'N/A') if context else 'N/A'}"
    )
    log.info(
        f"Lambda memory limit: "
        f"{getattr(context, 'memory_limit_in_mb', 'N/A') if context else 'N/A'} MB"
    )
    log.info(f"Event: {event}")
    log.info("=" * 80)

    study_results = []
    total_file_count = 0

    try:
        # Step 1: Parse and validate configuration
        log.info("Parsing configuration from event...")
        config = ImportConfig.from_event(event)

        # Log configuration (sanitize API key path)
        log.info("Configuration loaded:")
        log.info(f"  Storage ID: {config.storage_id}")
        log.info(f"  Group: {config.group}")
        log.info(f"  Number of studies: {len(config.studies)}")
        for i, study in enumerate(config.studies, 1):
            log.info(
                f"  Study {i}: {study.project_label} "
                f"(filter_mode={study.filter_mode}, "
                f"filter_pattern='{study.filter_pattern}')"
            )
        log.info(f"  API key path: {config.api_key_path} (value will not be logged)")
        log.info(f"  AWS profile: {config.aws_profile or 'default'}")
        log.info(f"  Dry run: {config.dry_run}")

        # Validate configuration
        log.info("Validating configuration parameters...")
        config.validate()
        log.info("Configuration validation passed")

        # Step 2: Retrieve API key from SSM
        log.info("Retrieving Flywheel API key from Parameter Store...")
        api_key = get_parameters(config.api_key_path)
        log.info("API key retrieved successfully")

        # Step 3: Initialize ClientHandler
        log.info("Initializing ClientHandler...")
        client = ClientHandler(
            fw_api_key=api_key,
            fw_storage_id=config.storage_id,
            aws_profile=config.aws_profile,
            dry_run=config.dry_run,
        )
        log.info("ClientHandler initialized successfully")
        log.info(f"  Storage prefix: {client.fw_storage_prefix}")
        log.info(f"  Provider ID: {client.fw_provider_id}")

        # Step 4: Import each study's metadata
        log.info(f"Starting import for {len(config.studies)} studies...")
        for i, study_config in enumerate(config.studies, 1):
            log.info("=" * 80)
            log.info(
                f"Processing study {i}/{len(config.studies)}: "
                f"{study_config.project_label}"
            )

            try:
                study_result = import_study_metadata(
                    client=client,
                    group=config.group,
                    study_config=study_config,
                )

                study_results.append(study_result)
                total_file_count += study_result.file_count

                log.info(
                    f"Study {i} completed: {study_result.file_count} files "
                    f"in {study_result.duration:.2f} seconds"
                )

            except Exception as e:
                # Log error but continue with remaining studies
                log.error(
                    f"Study {i} ({study_config.project_label}) failed: {str(e)}"
                )
                log.error("Continuing with remaining studies...")
                # Continue processing remaining studies

        # Step 5: Create success result
        total_duration = time.time() - start_time

        result = ImportResult(
            status="success",
            study_results=study_results,
            total_duration=total_duration,
            total_file_count=total_file_count,
        )

        # Log final summary
        log.info("=" * 80)
        log.info("S3 Flywheel Import completed successfully")
        log.info(f"  Total studies processed: {len(study_results)}")
        total_failed = 0
        for i, study_result in enumerate(study_results, 1):
            log.info(
                f"  Study {i} ({study_result.project_label}): "
                f"{study_result.file_count} succeeded, "
                f"{study_result.failed_count} failed, "
                f"{study_result.duration:.2f} seconds"
            )
            total_failed += study_result.failed_count
        log.info(f"  Total files imported: {total_file_count}")
        if total_failed > 0:
            log.error(f"  Total files failed: {total_failed}")
        log.info(f"  Total execution time: {total_duration:.2f} seconds")
        log.info(f"  Total execution time: {total_duration:.2f} seconds")
        log.info(f"  End time: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
        log.info("=" * 80)

        return result.to_dict()

    except ValueError as e:
        # Configuration validation errors
        total_duration = time.time() - start_time
        error_msg = str(e)

        log.error("=" * 80)
        log.error("Configuration validation failed")
        log.error("  Error type: ConfigurationError")
        log.error(f"  Error message: {error_msg}")
        log.error(f"  Total duration: {total_duration:.2f} seconds")
        log.error("=" * 80)

        result = ImportResult(
            status="failed",
            study_results=study_results,
            total_duration=total_duration,
            total_file_count=total_file_count,
            error_message=error_msg,
            error_type="ConfigurationError",
            context={
                "operation": "configuration_validation",
                "details": (
                    "One or more required configuration parameters are invalid"
                ),
            },
        )

        return result.to_dict()

    except HTTPError as e:
        # Flywheel API errors (SDK errors)
        total_duration = time.time() - start_time
        error_msg = str(e)

        log.error("=" * 80)
        log.error("Flywheel API error occurred")
        log.error("  Error type: SDKError")
        log.error(f"  Error message: {error_msg}")
        log.error(f"  Studies completed: {len(study_results)}")
        log.error(f"  Total files imported: {total_file_count}")
        log.error(f"  Total duration: {total_duration:.2f} seconds")

        # Log stack trace for debugging
        import traceback

        log.error("Stack trace:")
        log.error(traceback.format_exc())
        log.error("=" * 80)

        result = ImportResult(
            status="failed",
            study_results=study_results,
            total_duration=total_duration,
            total_file_count=total_file_count,
            error_message=error_msg,
            error_type="SDKError",
            context={
                "operation": "flywheel_api_call",
                "details": "Flywheel API request failed",
            },
        )

        return result.to_dict()

    except Exception as e:
        # Unexpected errors
        total_duration = time.time() - start_time
        error_msg = str(e)

        log.error("=" * 80)
        log.error("Unexpected error occurred")
        log.error("  Error type: UnexpectedError")
        log.error(f"  Error message: {error_msg}")
        log.error(f"  Studies completed: {len(study_results)}")
        log.error(f"  Total files imported: {total_file_count}")
        log.error(f"  Total duration: {total_duration:.2f} seconds")

        # Log stack trace for debugging
        import traceback

        log.error("Stack trace:")
        log.error(traceback.format_exc())
        log.error("=" * 80)

        # Create failure result
        result = ImportResult(
            status="failed",
            study_results=study_results,
            total_duration=total_duration,
            total_file_count=total_file_count,
            error_message=error_msg,
            error_type="UnexpectedError",
            context={
                "operation": "unknown",
                "details": "An unexpected error occurred during execution",
            },
        )

        return result.to_dict()
