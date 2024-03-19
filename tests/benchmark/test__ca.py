"""Benchmark the pre-commit hooks."""

from __future__ import annotations

from itertools import product
from typing import TYPE_CHECKING

import pytest
from rain import RainingGrid

if TYPE_CHECKING:
    from pytest_codspeed.plugin import BenchmarkFixture  # type: ignore[import-untyped]


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
        for height, limit in product([8, 16, 32, 64], [1, 10, 100, 1000, 10000])
    ],
)
def test_ca(benchmark: BenchmarkFixture, height: int, limit: int) -> None:
    """Benchmark the CA."""
    grid = RainingGrid(height)

    benchmark(lambda: grid.run(limit=limit))
