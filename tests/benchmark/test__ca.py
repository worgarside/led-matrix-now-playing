"""Benchmark the pre-commit hooks."""

from __future__ import annotations

from itertools import product
from typing import TYPE_CHECKING

import pytest
from rain import define_grid

if TYPE_CHECKING:
    from pytest_codspeed.plugin import BenchmarkFixture  # type: ignore[import-untyped]


@pytest.mark.parametrize(
    (
        "height",
        "limit",
    ),
    [
        pytest.param(height, limit, id=f"{limit} frames @ {height}x{height}")
        for height, limit in product(
            [8, 16, 32, 64], [1, 10, 100, 1000, 10000, 100000, 1000000]
        )
    ],
)
def test_ca(benchmark: BenchmarkFixture, height: int, limit: int) -> None:
    """Benchmark the CA."""
    grid = define_grid(height=height)

    benchmark(lambda: grid.run(limit=limit))
