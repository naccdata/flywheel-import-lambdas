"""Property-based tests for S3 object filtering correctness."""

# Feature: s3-flywheel-import, Property 3: S3 object filtering correctness

from typing import Any
from unittest.mock import MagicMock, patch

from hypothesis import given, settings
from hypothesis import strategies as st


def _make_s3_object(key: str, size: int) -> MagicMock:
    """Build a mock S3 ObjectSummary."""
    obj = MagicMock()
    obj.key = key
    obj.size = size
    return obj


def _filter_objects_with_mocks(
    objects: list[Any],
    s3_prefix: str,
    include_patterns: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
) -> list[Any]:
    """Build a ClientHandler with patched externals and call filter_objects."""
    from flywheel_client.client_handler import ClientHandler

    storage = MagicMock()
    storage.config.bucket = "test-bucket"
    storage.config.prefix = "pfx"
    storage.provider = "prov-1"

    mock_bucket = MagicMock()
    mock_bucket.objects.filter.return_value = objects

    with (
        patch("flywheel_client.client_handler.FWClient") as mock_fw,
        patch("flywheel_client.client_handler.boto3") as mock_boto,
    ):
        mock_fw.return_value.get.return_value = storage
        mock_boto.Session.return_value.resource.return_value.Bucket.return_value = (
            mock_bucket
        )

        client = ClientHandler(fw_api_key="key", fw_storage_id="sid")

        # Call filter_objects while patches are still active
        return list(
            client.filter_objects(
                s3_prefix=s3_prefix,
                include_patterns=include_patterns,
                exclude_patterns=exclude_patterns,
            )
        )


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Keys: printable, non-empty strings (avoid null bytes that confuse substring matching)
_key_st = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "S")),
    min_size=1,
    max_size=40,
)

# Sizes: 0 (directory marker) or positive
_size_st = st.integers(min_value=0, max_value=10_000)

# Pattern lists: short lists of short non-empty strings
_pattern_st = st.lists(
    st.text(
        alphabet=st.characters(whitelist_categories=("L", "N")),
        min_size=1,
        max_size=10,
    ),
    max_size=4,
)


def _apply_filter_sequentially(
    objects: list[Any],
    include_patterns: list[str],
    exclude_patterns: list[str],
) -> list[Any]:
    """Reference implementation: include-first-then-exclude, skip zero-byte."""
    result = [o for o in objects if o.size > 0]

    if include_patterns:
        result = [o for o in result if any(p in o.key for p in include_patterns)]

    if exclude_patterns:
        result = [o for o in result if not any(p in o.key for p in exclude_patterns)]

    return result


# ---------------------------------------------------------------------------
# Property test
# ---------------------------------------------------------------------------


# Validates: Requirements 4.2, 4.3, 4.4, 4.5
@settings(max_examples=100, deadline=None)
@given(
    keys=st.lists(_key_st, min_size=0, max_size=10),
    sizes=st.lists(_size_st, min_size=0, max_size=10),
    include_patterns=_pattern_st,
    exclude_patterns=_pattern_st,
)
def test_s3_object_filtering_correctness(
    keys: list[str],
    sizes: list[int],
    include_patterns: list[str],
    exclude_patterns: list[str],
) -> None:
    """For any list of S3 objects, include patterns, and exclude patterns the
    filtered output satisfies:

    1. Every yielded object has size > 0
    2. If include patterns are non-empty, every yielded key contains at
       least one include pattern as a substring
    3. No yielded key contains any exclude pattern as a substring
    4. The result equals applying include-first-then-exclude sequentially
    """
    # Align lengths — zip to the shorter list
    paired = list(zip(keys, sizes, strict=False))
    mock_objects = [_make_s3_object(k, s) for k, s in paired]

    filtered = _filter_objects_with_mocks(
        objects=mock_objects,
        s3_prefix="any/prefix",
        include_patterns=include_patterns or None,
        exclude_patterns=exclude_patterns or None,
    )

    # Property 1: every yielded object has size > 0
    for obj in filtered:
        assert obj.size > 0, f"Zero-byte object yielded: {obj.key}"

    # Property 2: include patterns respected
    if include_patterns:
        for obj in filtered:
            assert any(p in obj.key for p in include_patterns), (
                f"Object {obj.key!r} does not match any include pattern"
            )

    # Property 3: exclude patterns respected
    if exclude_patterns:
        for obj in filtered:
            assert not any(p in obj.key for p in exclude_patterns), (
                f"Object {obj.key!r} matches an exclude pattern"
            )

    # Property 4: same as sequential include-then-exclude
    expected = _apply_filter_sequentially(
        mock_objects, include_patterns, exclude_patterns
    )
    expected_keys = [o.key for o in expected]
    actual_keys = [o.key for o in filtered]
    assert actual_keys == expected_keys, (
        f"Sequential mismatch: expected {expected_keys}, got {actual_keys}"
    )
