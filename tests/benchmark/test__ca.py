"""Benchmark the pre-commit hooks."""

from __future__ import annotations

from copy import deepcopy
from itertools import islice, product
from math import ceil
from typing import TYPE_CHECKING, Callable

import pytest
from rain import RainingGrid

if TYPE_CHECKING:
    from pytest_codspeed import BenchmarkFixture  # type: ignore[import-untyped]
    from utils.cellular_automata.ca import Mask


@pytest.mark.parametrize(
    ("height", "limit"),
    [
        pytest.param(
            height,
            limit,
            id=f"{limit} frame{'s' if limit > 1 else ''} @ {height}x{height}",
            marks=pytest.mark.xdist_group(f"{height}-{limit}"),
        )
        for height, limit in product(
            [8, 16, 32, 64], [ceil((10**i) / 2) for i in range(4)]
        )
    ],
)
def test_raining_grid_simulation(
    benchmark: BenchmarkFixture,
    height: int,
    limit: int,
) -> None:
    """Benchmark the CA."""
    grid = RainingGrid(height)

    @benchmark  # type: ignore[misc]
    def bench() -> None:
        for _ in grid.run(limit=limit):
            pass


@pytest.mark.parametrize(
    ("height", "limit", "rule"),
    [
        pytest.param(
            height,
            limit,
            rule,
            id=f"{rule.__name__} for {limit} frame{'s' if limit > 1 else ''} @ {height}x{height}",
            marks=pytest.mark.xdist_group(f"{height}-{limit}-{rule.__name__}"),
        )
        for height, limit, rule in product(
            [8, 16, 32, 64],
            [ceil((10**i) / 2) for i in range(4)],
            RainingGrid._RULE_METHODS,
        )
    ],
)
def test_rules(
    benchmark: BenchmarkFixture,
    height: int,
    limit: int,
    rule: Callable[..., Mask],
) -> None:
    """Test/benchmark each individual rule."""
    grid = RainingGrid(height)

    # Discard the first H frames so all rules are effective (e.g. splashing)
    for _ in islice(grid.frames, height + 10):
        pass

    expected_frame_index = height + 9
    assert grid.frame_index == expected_frame_index
    expected_frame_index += 1

    grids_to_eval = [deepcopy(grid) for _ in islice(grid.frames, limit)]

    for g in grids_to_eval:
        assert g.frame_index == expected_frame_index
        expected_frame_index += 1

    @benchmark  # type: ignore[misc]
    def bench() -> None:
        for grid in grids_to_eval:
            rule(grid)
