"""Unit tests for the Grid class."""

from __future__ import annotations

import pytest
from utils.cellular_automata.ca import Grid, TargetSlice


@pytest.mark.parametrize(
    ("slice_", "x", "y", "expected"),
    [
        pytest.param(
            (slice(1, 5), slice(2, 6)),
            0,
            0,
            (slice(1, 5, None), slice(2, 6, None)),
            id="no_translation",
        ),
        pytest.param(
            (slice(1, 5), slice(2, 6)),
            2,
            3,
            (slice(3, 7, None), slice(5, 9, None)),
            id="positive_translation",
        ),
        pytest.param(
            (slice(3, 7), slice(5, 9)),
            -1,
            -1,
            (slice(2, 6, None), slice(4, 8, None)),
            id="negative_translation",
        ),
        pytest.param(
            (slice(1, 5), slice(5, 9)),
            3,
            -2,
            (slice(4, 8, None), slice(3, 7, None)),
            id="mixed_translation_positive_x_negative_y",
        ),
        pytest.param(
            (slice(1, 10, 2), slice(2, 8, 2)),
            2,
            2,
            (slice(3, 12, 2), slice(4, 10, 2)),
            id="step_verification",
        ),
        pytest.param(
            (slice(None, 5), slice(2, None)),
            1,
            1,
            (slice(None, 6, None), slice(3, None, None)),
            id="edge_cases_open_ended_slices",
        ),
        pytest.param(
            (slice(None, None, None), slice(None, None, None)),
            5,
            5,
            (slice(None, None, None), slice(None, None, None)),
            id="edge_cases_full_slice",
        ),
        pytest.param(
            (slice(-10, -5), slice(-8, -3)),
            2,
            2,
            (slice(-8, -3, None), slice(-6, -1, None)),
            id="edge_cases_negative_start_and_stop",
        ),
    ],
)
def test_translate_slice(
    slice_: TargetSlice, x: int, y: int, expected: TargetSlice
) -> None:
    """Test the slice translation helper function."""

    assert Grid.translate_slice(slice_, x, y) == expected
