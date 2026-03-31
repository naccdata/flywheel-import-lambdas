"""Property-based tests for S3 Flywheel Import Pydantic models."""

# Feature: s3-flywheel-import, Property 1: ImportConfig round-trip parsing

from hypothesis import given, settings
from hypothesis import strategies as st
from s3_import_models.models import ImportConfig, PrefixPathPair


def prefix_path_pair_strategy() -> st.SearchStrategy[PrefixPathPair]:
    """Generate valid PrefixPathPair instances."""
    return st.builds(
        PrefixPathPair,
        s3_prefix=st.text(min_size=1).filter(lambda s: s.strip()),
        fw_group=st.text(min_size=1).filter(lambda s: s.strip()),
        fw_project=st.text(min_size=1).filter(lambda s: s.strip()),
        include_patterns=st.lists(st.text()),
        exclude_patterns=st.lists(st.text()),
    )


def import_config_strategy() -> st.SearchStrategy[ImportConfig]:
    """Generate valid ImportConfig instances."""
    return st.builds(
        ImportConfig,
        storage_id=st.text(min_size=1).filter(lambda s: s.strip()),
        api_key_path=st.text().map(lambda s: "/" + s),
        prefix_path_pairs=st.lists(prefix_path_pair_strategy(), min_size=1),
        dry_run=st.booleans(),
        aws_profile=st.one_of(st.none(), st.text()),
    )


# Validates: Requirements 1.1
@settings(max_examples=100)
@given(config=import_config_strategy())
def test_import_config_round_trip(config: ImportConfig) -> None:
    """For any valid ImportConfig, serializing to dict and parsing back
    produces an equivalent object."""
    dumped = config.model_dump()
    restored = ImportConfig(**dumped)
    assert restored == config
