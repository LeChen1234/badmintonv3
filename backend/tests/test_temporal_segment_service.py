import pytest

from app.services.temporal_segment_service import (
    ranges_overlap,
    validate_segment_range,
    validate_segment_taxonomy,
)


TAXONOMY = {
    "actions": [{"value": "smash", "label": "杀球"}],
    "phases": [{"value": "contact", "label": "击球"}],
}


def test_segment_range_accepts_single_and_multi_frame_ranges():
    validate_segment_range(1, 1, 20)
    validate_segment_range(3, 12, 20)


@pytest.mark.parametrize("start,end,total", [(0, 2, 20), (5, 4, 20), (5, 21, 20)])
def test_segment_range_rejects_invalid_ranges(start, end, total):
    with pytest.raises(ValueError):
        validate_segment_range(start, end, total)


def test_overlap_is_inclusive_at_boundaries():
    assert ranges_overlap(2, 5, 5, 8)
    assert not ranges_overlap(2, 4, 5, 8)


def test_segment_taxonomy_rejects_unknown_values():
    validate_segment_taxonomy("smash", "contact", TAXONOMY)
    with pytest.raises(ValueError):
        validate_segment_taxonomy("drop", None, TAXONOMY)
    with pytest.raises(ValueError):
        validate_segment_taxonomy("smash", "unknown", TAXONOMY)
