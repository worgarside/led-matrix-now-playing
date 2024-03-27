"""Benchmark the pre-commit hooks."""

from __future__ import annotations

from itertools import product
from math import ceil
from typing import TYPE_CHECKING

import pytest
from rain import RainingGrid

if TYPE_CHECKING:
    from pytest_codspeed import BenchmarkFixture  # type: ignore[import-untyped]


@pytest.mark.parametrize(
    (
        "height",
        "limit",
    ),
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
        for count, _ in enumerate(grid.frames):
            if count >= limit:
                break
