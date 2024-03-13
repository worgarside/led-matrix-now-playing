"""Benchmark the pre-commit hooks."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from rain import define_grid
from utils.cellular_automata.ca import Grid, Rows

if TYPE_CHECKING:
    from pytest_codspeed.plugin import BenchmarkFixture  # type: ignore[import-untyped]


@pytest.mark.parametrize(
    (
        "height",
        "limit",
    ),
    [
        (8, 100),
        (16, 100),
        (32, 100),
        (8, 1000),
        (16, 1000),
        (32, 1000),
        (8, 10000),
    ],
)
def test_ca(benchmark: BenchmarkFixture, height: int, limit: int) -> None:
    """Benchmark the CA."""
    grid = define_grid(height=height)

    def _cb(_: Rows) -> None:
        if grid.frame_index >= limit:
            raise Grid.Break

    benchmark(lambda: grid.run(_cb))
