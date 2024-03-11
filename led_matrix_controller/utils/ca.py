from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from random import random
from time import sleep
from typing import Any, Callable, Collection, Generator


class State(Enum):
    NULL = auto()
    RAINDROP = auto()

    _UNSET = auto()
    OFF_GRID = auto()


@dataclass
class Cell:
    x: int
    y: int
    grid: Grid

    def __post_init__(self) -> None:
        self.frame_index = self.grid.frame_index

    _state: State = State.NULL
    last_state_change: State = State._UNSET
    previous_frame_state: State = State._UNSET

    @property
    def cell_above(self) -> Cell | None:
        if self.is_top:
            return None

        return self.grid.get(self.x, self.y - 1)

    @property
    def cell_below(self) -> Cell | None:
        if self.is_bottom:
            return None

        return self.grid.get(self.x, self.y + 1)

    @property
    def cell_left(self) -> Cell | None:
        if self.is_left:
            return None

        return self.grid.get(self.x - 1, self.y)

    @property
    def cell_right(self) -> Cell | None:
        if self.is_right:
            return None

        return self.grid.get(self.x + 1, self.y)

    @property
    def is_top(self) -> bool:
        return self.y == 0

    @property
    def is_bottom(self) -> bool:
        return self.y == self.grid.height - 1

    @property
    def is_left(self) -> bool:
        return self.x == 0

    @property
    def is_right(self) -> bool:
        return self.x == self.grid.width - 1

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
        return self._get_state(self.cell_above)

    @property
    def state_below(self) -> State:
        return self._get_state(self.cell_below)

    @property
    def state_left(self) -> State:
        return self._get_state(self.cell_left)

    @property
    def state_right(self) -> State:
        return self._get_state(self.cell_right)

    @property
    def state(self) -> State:
        return self._state

    @state.setter
    def state(self, value: State) -> None:
        self.last_state_change = self._state
        self._state = value

    def __str__(self) -> str:
        # return f" {self.x},{self.y} "
        return {
            State.NULL: ".",
            State.RAINDROP: "O",
        }[self.state]


class Rule:
    def __init__(
        self,
        conditions: tuple[Callable[[Cell], bool], ...],
        action: Callable[[Cell], Any],
    ) -> None:
        self.conditions = conditions
        self.action = action

    def __call__(self, cell: Cell) -> Any:
        return self.action(cell)

    def is_applicable(self, cell: Cell) -> bool:
        return all(condition(cell) for condition in self.conditions)


Rows = tuple[tuple[Cell, ...], ...]


@dataclass
class Grid:
    height: int
    width: int = -1

    frame_index: int = 0

    rules: dict[State, Collection[Rule]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.width == -1:
            self.width = self.height

        self.rows: Rows = tuple(
            tuple(Cell(x, y, self) for x in range(self.width)) for y in range(self.height)
        )

    def get(self, x: int, y: int, /) -> Cell:
        return self.rows[y][x]

    def frames(self) -> Generator[str, None, None]:
        while True:
            next_frame_number = self.frame_index + 1
            for y, row in enumerate(self.rows):
                for x, cell in enumerate(row):
                    if (
                        len(
                            applicable_rules := [
                                rule
                                for rule in self.rules.get(cell.state, ())
                                if rule.is_applicable(cell)
                            ]
                        )
                        > 1
                    ):
                        raise ValueError("Multiple rules apply to cell")

                    cell.previous_frame_state = cell.state

                    if applicable_rules:
                        applicable_rules[0](cell)

                    cell.frame_index = next_frame_number

            self.frame_index = next_frame_number
            yield self.frame

    def run(self, limit: int, time_period: float) -> None:
        for fr in self.frames():
            print(fr)
            print("\n\n")

            if self.frame_index > limit:
                break

            sleep(time_period)

    @property
    def frame(self) -> str:
        return str(self)

    def __str__(self) -> str:
        return "\n".join(" ".join(map(str, row)) for row in self.rows)


class Assign:
    def __init__(self, value: State) -> None:
        self.value = value

    def __call__(self, cell: Cell) -> None:
        cell.state = self.value


def main() -> None:
    raindrop_generator = Rule(
        conditions=(
            lambda c: c.is_top,
            lambda c: c.state == State.NULL,
            lambda c: random() < 0.1,
        ),
        action=Assign(State.RAINDROP),
    )

    bottom_of_rain_down = Rule(
        conditions=(
            lambda c: c.state_above is State.RAINDROP,
            # lambda c: c.grid.frame_index % 3 == 0,
        ),
        action=Assign(State.RAINDROP),
    )

    top_of_raindrop_down = Rule(
        conditions=(
            lambda c: c.state_below in (State.RAINDROP, State.OFF_GRID),
            # lambda c: c.grid.frame_index % 3 == 0,
            lambda c: c.state_above in (State.NULL, State.OFF_GRID),
        ),
        action=Assign(State.NULL),
    )

    grid = Grid(
        64,
        rules={
            State.NULL: [raindrop_generator, bottom_of_rain_down],
            State.RAINDROP: [top_of_raindrop_down],
        },
    )

    grid.run(limit=500, time_period=0.05)


if __name__ == "__main__":
    main()
