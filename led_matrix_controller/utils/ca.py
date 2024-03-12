"""Simple implementation of a 2D cellular automaton."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from functools import cached_property, lru_cache
from random import random
from time import sleep
from typing import Any, Callable, Collection, Generator, Literal, overload


class State(StrEnum):
    """The state of a cell."""

    NULL = "."
    RAINDROP = "O"
    SPLASHDROP = "o"
    SPLASH_LEFT = "*"
    SPLASH_RIGHT = "*"

    _UNSET = "!"
    OFF_GRID = " "


@dataclass
class Cell:
    """A cell in a grid."""

    x: int
    y: int
    grid: Grid

    def __post_init__(self) -> None:
        """Set the calculated attributes of the Cell."""
        self.frame_index = self.grid.frame_index

        self.is_top = self.y == 0
        self.is_bottom = self.y == self.grid.height - 1
        self.is_left = self.x == 0
        self.is_right = self.x == self.grid.width - 1

    _state: State = State.NULL
    last_state_change: State = State._UNSET
    previous_frame_state: State = State._UNSET

    @overload
    def get_relative_cell(self, x: int, y: int) -> Cell | None: ...

    @overload
    def get_relative_cell(
        self, x: int, y: int, *, no_exist_ok: Literal[True]
    ) -> Cell | None: ...

    @overload
    def get_relative_cell(
        self, x: int, y: int, *, no_exist_ok: Literal[False]
    ) -> Cell: ...

    def get_relative_cell(
        self, x: int, y: int, *, no_exist_ok: bool = True
    ) -> Cell | None:
        """Return the cell at the given relative coordinates. If the cell does not exist, return None."""
        if cell := self.grid.get(self.x + x, self.y + y):
            return cell

        if no_exist_ok:
            return None

        raise ValueError(f"Cell at {self.x + x}, {self.y + y} does not exist")

    @cached_property
    def cell_above(self) -> Cell | None:
        """Return the cell above this one. If this is the top cell, return None."""
        return self.get_relative_cell(0, -1)

    @cached_property
    def cell_below(self) -> Cell | None:
        """Return the cell below this one. If this is the bottom cell, return None."""
        return self.get_relative_cell(0, 1)

    @cached_property
    def cell_left(self) -> Cell | None:
        """Return the cell to the left of this one. If this is the leftmost cell, return None."""
        return self.get_relative_cell(-1, 0)

    @cached_property
    def cell_right(self) -> Cell | None:
        """Return the cell to the right of this one. If this is the rightmost cell, return None."""
        return self.get_relative_cell(1, 0)

    def _get_state(self, other: Cell | None) -> State:
        if other is None:
            return State.OFF_GRID

        if other.frame_index == self.frame_index + 1:
            return other.previous_frame_state

        if other.frame_index == self.frame_index:
            return other.state

        raise ValueError(f"Other: {other.frame_index}; This: {self.frame_index}")

    @property
    def state_above(self) -> State:
        """Return the state of the cell above of this one. If there is no cell above, return OFF_GRID."""
        return self._get_state(self.cell_above)

    @property
    def state_below(self) -> State:
        """Return the state of the below this one. If there is no below, return OFF_GRID."""
        return self._get_state(self.cell_below)

    @property
    def state_left(self) -> State:
        """Return the state of the cell to the left of this one. If there is no cell, return OFF_GRID."""
        return self._get_state(self.cell_left)

    @property
    def state_right(self) -> State:
        """Return the state of the cell to the right of this one. If there is no cell, return OFF_GRID."""
        return self._get_state(self.cell_right)

    @property
    def state(self) -> State:
        """Return the state of the cell."""
        return self._state

    @state.setter
    def state(self, value: State) -> None:
        self.last_state_change = self._state
        self._state = value

    def has_state(self, state: State) -> bool:
        """Return whether the cell has the given state."""
        # TODO this dpesn't work properly (set SPLASH_LEFT/RIGHT to L and R)
        return self.state is state

    def __str__(self) -> str:
        """Return the string representation of the cell."""
        return self.state


class Rule:
    """A rule that can be applied to a cell."""

    def __init__(
        self,
        *,
        conditions: Collection[Condition | Condition.Function] = (),
        assign: State = State._UNSET,
    ) -> None:
        self.conditions = tuple(conditions)
        self.assign = assign

    def __call__(self, cell: Cell) -> Any:
        """Apply the rule to the cell."""
        if self.assign is not State._UNSET:
            cell.state = self.assign

    def is_applicable(self, cell: Cell) -> bool:
        """Return whether the rule is applicable to the cell."""
        return all(condition(cell) for condition in self.conditions)


Rows = tuple[tuple[Cell, ...], ...]


class Condition:
    """A condition that can be used to determine if a rule is applicable."""

    Function = Callable[[Cell], bool]

    def __init__(self, cond: Function, /, *, default: bool) -> None:
        self.cond = cond
        self.default = default

    def __call__(self, cell: Cell, /) -> bool:
        """Return the result of the condition. If the condition raises an exception, return the default value."""
        try:
            return self.cond(cell)
        except Exception:
            return self.default

    @lru_cache(maxsize=None)
    @staticmethod
    def at_height(height: int, /) -> Function:
        """Return a condition that checks if the cell is at the given height."""

        def _check_height(cell: Cell) -> bool:
            if height < 0:
                return cell.y == cell.grid.height + height

            return cell.y == height

        return _check_height

    @staticmethod
    def percentage_chance(chance: float, /) -> Function:
        """Return a condition that has a `chance` percentage of being True."""
        return lambda _: random() < chance  # noqa: S311


@dataclass
class Grid:
    """A grid of cells."""

    height: int
    width: int = -1

    frame_index: int = 0

    rules: dict[State, Collection[Rule]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Create the rows of cells."""
        if self.width == -1:
            self.width = self.height

        self.rows: Rows = tuple(
            tuple(Cell(x, y, self) for x in range(self.width)) for y in range(self.height)
        )

    def get(self, x: int, y: int, /) -> Cell | None:
        """Return the cell at the given coordinates. If the coordinates are out of bounds, return None."""
        if x < 0 or y < 0:
            return None

        try:
            return self.rows[y][x]
        except IndexError:
            return None

    def frames(self) -> Generator[str, None, None]:
        """Generate the frames of the grid."""
        while True:
            next_frame_number = self.frame_index + 1
            for row in self.rows:
                for cell in row:
                    applicable_rules = [
                        rule
                        for rule in self.rules.get(cell.state, ())
                        if rule.is_applicable(cell)
                    ]

                    cell.previous_frame_state = cell.state

                    if applicable_rules:
                        applicable_rules[0](cell)

                    cell.frame_index = next_frame_number

            self.frame_index = next_frame_number
            yield self.frame

    def run(self, limit: int, time_period: float) -> None:
        """Run the simulation."""
        for fr in self.frames():
            print(fr)
            print("\n\n")

            if self.frame_index > limit:
                break

            sleep(time_period)

    @property
    def frame(self) -> str:
        """Return the current frame of the grid."""
        return str(self)

    def __str__(self) -> str:
        """Return the string representation of the grid."""
        return "\n".join(" ".join(map(str, row)) for row in self.rows)


def main() -> None:
    """Run the simulation."""
    raindrop_generator = Rule(
        conditions=(
            lambda c: c.is_top,
            Condition.percentage_chance(0.01),
        ),
        assign=State.RAINDROP,
    )

    bottom_of_rain_down = Rule(
        conditions=(lambda c: c.state_above is State.RAINDROP,),
        assign=State.RAINDROP,
    )

    splashdrop_down = Rule(
        conditions=(lambda c: c.state_above is State.SPLASHDROP,),
        assign=State.SPLASHDROP,
    )

    top_of_raindrop_down = Rule(
        conditions=(
            lambda c: c.state_below in (State.RAINDROP, State.OFF_GRID),
            lambda c: c.state_above in (State.NULL, State.OFF_GRID),
        ),
        assign=State.NULL,
    )

    nullify = Rule(assign=State.NULL)

    splash_left = Rule(
        conditions=[
            Condition(
                lambda c: c.get_relative_cell(1, 1, no_exist_ok=False).has_state(
                    State.RAINDROP
                ),
                default=False,
            ),
            lambda c: c.y == c.grid.height - 2,
        ],
        assign=State.SPLASH_LEFT,
    )

    splash_left_high = Rule(
        conditions=[
            lambda c: c.state_below is State.NULL,
            Condition(
                lambda c: c.get_relative_cell(1, 1, no_exist_ok=False).has_state(
                    State.SPLASH_LEFT
                ),
                default=False,
            ),
            Condition.at_height(-3),
        ],
        assign=State.SPLASH_LEFT,
    )

    splash_right = Rule(
        conditions=[
            lambda c: c.state_below is State.NULL,
            Condition(
                lambda c: c.get_relative_cell(-1, 1, no_exist_ok=False).has_state(
                    State.RAINDROP
                ),
                default=False,
            ),
            Condition.at_height(-2),
        ],
        assign=State.SPLASH_RIGHT,
    )

    splash_right_high = Rule(
        conditions=[
            lambda c: c.state_below is State.NULL,
            Condition(
                lambda c: c.get_relative_cell(-1, 1, no_exist_ok=False).has_state(
                    State.SPLASH_RIGHT
                ),
                default=False,
            ),
            Condition.at_height(-3),
        ],
        assign=State.SPLASH_RIGHT,
    )

    remove_splash_low = Rule(
        conditions=(Condition.at_height(-2),),
        assign=State.NULL,
    )

    remove_splash_high = Rule(
        conditions=(Condition.at_height(-3),),
        assign=State.SPLASHDROP,
    )

    grid = Grid(
        32,
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

    grid.run(limit=1000, time_period=0.035)


if __name__ == "__main__":
    main()
