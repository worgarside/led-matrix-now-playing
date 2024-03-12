"""Benchmark the pre-commit hooks."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from utils.cellular_automata.ca import Condition, Grid, Rule, State

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
    raindrop_generator = Rule(
        condition=lambda c: c.is_top and Condition.percentage_chance(0.01)(c),
        assign=State.RAINDROP,
    )

    bottom_of_rain_down = Rule(
        condition=lambda c: c.state_above is State.RAINDROP,
        assign=State.RAINDROP,
    )

    splashdrop_down = Rule(
        condition=lambda c: c.state_above is State.SPLASHDROP,
        assign=State.SPLASHDROP,
    )

    top_of_raindrop_down = Rule(
        condition=(
            lambda c: c.state_below in (State.RAINDROP, State.OFF_GRID)
            and c.state_above in (State.NULL, State.OFF_GRID)
        ),
        assign=State.NULL,
    )

    nullify = Rule(assign=State.NULL)

    splash_left = Rule(
        condition=lambda c: c.y == c.grid.height - 2
        and Condition(
            lambda c: c.get_relative_cell(1, 1, no_exist_ok=False).has_state(
                State.RAINDROP
            ),
            default=False,
        )(c),
        assign=State.SPLASH_LEFT,
    )

    splash_left_high = Rule(
        condition=lambda c: Condition.cell_at_height(c, -3)
        and c.state_below is State.NULL
        and Condition(
            lambda c: c.get_relative_cell(1, 1, no_exist_ok=False).has_state(
                State.SPLASH_LEFT
            ),
            default=False,
        )(c),
        assign=State.SPLASH_LEFT,
    )

    splash_right = Rule(
        condition=lambda c: Condition.cell_at_height(c, -2)
        and c.state_below is State.NULL
        and Condition(
            lambda c: c.get_relative_cell(-1, 1, no_exist_ok=False).has_state(
                State.RAINDROP
            ),
            default=False,
        )(c),
        assign=State.SPLASH_RIGHT,
    )

    splash_right_high = Rule(
        condition=lambda c: Condition.cell_at_height(c, -3)
        and c.state_below is State.NULL
        and Condition(
            lambda c: c.get_relative_cell(-1, 1, no_exist_ok=False).has_state(
                State.SPLASH_RIGHT
            ),
            default=False,
        )(c),
        assign=State.SPLASH_RIGHT,
    )

    remove_splash_low = Rule(
        condition=Condition.check_height(-2),
        assign=State.NULL,
    )

    remove_splash_high = Rule(
        condition=Condition.check_height(-3),
        assign=State.SPLASHDROP,
    )

    grid = Grid(
        height,
        rules={
            State.NULL: [
                raindrop_generator,
                bottom_of_rain_down,
                splashdrop_down,
                splash_left,
                splash_left_high,
                splash_right,
                splash_right_high,
            ],
            State.RAINDROP: [top_of_raindrop_down],
            State.SPLASHDROP: [nullify],
            State.SPLASH_LEFT: [remove_splash_low, remove_splash_high],
            State.SPLASH_RIGHT: [remove_splash_low, remove_splash_high],
        },
    )

    benchmark(lambda: grid.run(limit=limit, time_period=0))
