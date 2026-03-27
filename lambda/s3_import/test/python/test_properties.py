"""Property-based tests for import operations."""

# Feature: s3-flywheel-import
# Property 5: Import pair result tracks counts and failures correctly

from unittest.mock import MagicMock

from conftest import make_s3_object
from hypothesis import given, settings
from hypothesis import strategies as st
from s3_import_lambda.import_operations import import_pair_files
from s3_import_models.models import PrefixPathPair

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# File keys: printable, non-empty strings resembling S3 paths
_key_st = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P")),
    min_size=1,
    max_size=40,
).map(lambda k: f"data/{k}")

# File sizes: positive integers (real files, not directory markers)
_size_st = st.integers(min_value=1, max_value=10_000)


def _make_pair() -> PrefixPathPair:
    """Build a minimal PrefixPathPair for testing."""
    return PrefixPathPair(
        s3_prefix="data/center1",
        fw_group="grp",
        fw_project="proj",
    )


# ---------------------------------------------------------------------------
# Property test
# ---------------------------------------------------------------------------


# Validates: Requirements 6.1, 6.2, 6.3
@settings(max_examples=100, deadline=None)
@given(
    keys=st.lists(_key_st, min_size=0, max_size=15),
    sizes=st.lists(_size_st, min_size=0, max_size=15),
    fail_indices=st.frozensets(st.integers(min_value=0, max_value=14)),
)
def test_import_pair_result_tracks_counts_and_failures(
    keys: list[str],
    sizes: list[int],
    fail_indices: frozenset[int],
) -> None:
    """For any list of S3 file objects where a known subset of imports fail:

    1. file_count equals the number of successful imports
    2. failed_files contains exactly the failed file keys with error messages
    3. All files are attempted regardless of individual failures
    """
    # Align to the shorter list
    paired = list(zip(keys, sizes, strict=False))
    if not paired:
        return  # nothing to test for empty input

    s3_objects = [make_s3_object(k, s) for k, s in paired]
    n = len(s3_objects)

    # Determine which indices (within range) should fail
    actual_fail_indices = {i for i in fail_indices if i < n}
    expected_success_count = n - len(actual_fail_indices)

    # Build side effects: success returns {}, failure raises RuntimeError
    side_effects: list[dict | RuntimeError] = []
    for i in range(n):
        if i in actual_fail_indices:
            side_effects.append(RuntimeError(f"import error at index {i}"))
        else:
            side_effects.append({})

    # Build mock ClientHandler
    client = MagicMock()
    client.get_project_id.return_value = "proj-abc"
    client.filter_objects.return_value = iter(s3_objects)
    client.import_to_flywheel.side_effect = side_effects

    pair = _make_pair()
    result = import_pair_files(client, pair)

    # Property 1: file_count equals the number of successful imports
    assert result.file_count == expected_success_count, (
        f"Expected {expected_success_count} successes, got {result.file_count}"
    )

    # Property 2: failed_files contains exactly the failed file keys
    failed_keys = {f["key"] for f in result.failed_files}
    expected_failed_keys = {s3_objects[i].key for i in actual_fail_indices}
    assert failed_keys == expected_failed_keys, (
        f"Expected failed keys {expected_failed_keys}, got {failed_keys}"
    )

    # Verify each failed entry has an error message
    for entry in result.failed_files:
        assert "error" in entry, f"Missing 'error' key in failed entry: {entry}"
        assert entry["error"], f"Empty error message for key: {entry['key']}"

    # Property 3: All files are attempted regardless of individual failures
    assert client.import_to_flywheel.call_count == n, (
        f"Expected {n} import attempts, got {client.import_to_flywheel.call_count}"
    )
