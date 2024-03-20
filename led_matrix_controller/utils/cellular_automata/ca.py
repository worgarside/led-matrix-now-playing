"""Cellular Automata module."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from itertools import islice
from typing import Any, Callable, ClassVar, Generator, Self

import numpy as np
from numpy.typing import DTypeLike, NDArray

_BY_VALUE: dict[int, StateBase] = {}


# TODO can this be an ABC?
class StateBase(Enum):
    """Base class for the states of a cell."""

    def __init__(
        self, value: int, char: str, color: tuple[int, int, int] = (0, 0, 0)
    ) -> None:
        self._value_ = value
        self.state = value  # This is only really for type checkers, _value_ is the same but has a different type
        self.char = char
        self.color = color

        _BY_VALUE[value] = self

    @classmethod
    def by_value(cls, value: int | np.int_) -> StateBase:
        """Return the state by its value."""
        return _BY_VALUE[int(value)]

    def __eq__(self, __value: object) -> bool:
        """Check if a value (either another State or an int) is equal to this State."""
        if isinstance(__value, int):
            return bool(self.value == __value)

        if not isinstance(__value, StateBase):
            return False

        return bool(self.value == __value.value)

    def __hash__(self) -> int:
        """Return the hash of the value of the state."""
        return hash(self.value)


TargetSliceDecVal = slice | int | tuple[int | slice, int | slice]
TargetSlice = tuple[slice, slice]
Mask = NDArray[np.bool_]


@dataclass
class Grid:
    """Base class for a grid of cells."""

    height: int
    width: int = -1

    frame_index: int = 0

    _RULES: ClassVar[list[tuple[TargetSliceDecVal, Callable[..., Mask], StateBase]]] = []

    Rule: ClassVar = Callable[[Self], Mask]

    def __post_init__(self) -> None:
        """Set the calculated attributes of the Grid."""
        if self.width == -1:
            self.width = self.height

        self._grid: NDArray[np.int_] = self.zeros()

    @classmethod
    def rule(
        cls,
        to_state: StateBase,
        *,
        target_slice: TargetSliceDecVal | None = None,
    ) -> Callable[[Callable[..., Mask]], Callable[..., Mask]]:
        """Decorator to add a rule to the grid.

        Args:
            to_state (StateBase): The state to change to.
            target_slice (TargetSliceDecVal | None, optional): The slice to target. Defaults to entire grid.
        """
        if target_slice is None:
            target_slice = (slice(None), slice(None))

        def decorator(func: Callable[..., Mask]) -> Grid.Rule:
            if "target_slice" in inspect.signature(func).parameters:

                @wraps(func)
                def wrapper(self: Grid) -> Mask:
                    return func(self, target_slice)
            else:

                @wraps(func)
                def wrapper(self: Grid) -> Mask:
                    return func(self)

            cls._RULES.append((target_slice, wrapper, to_state))
            return wrapper

        return decorator

    def run(self, limit: int) -> Generator[NDArray[np.int_], None, None]:
        """Run the simulation for a given number of frames."""
        yield from islice(self.frames, limit)

    def fresh_mask(self) -> Mask:
        """Return a fresh mask."""
        return self.zeros(dtype=np.bool_)

    def zeros(self, *, dtype: DTypeLike = np.int_) -> NDArray[Any]:
        """Return a grid of zeros."""
        return np.zeros((self.height, self.width), dtype=dtype)

    @property
    def frames(self) -> Generator[NDArray[np.int_], None, None]:
        """Generate the frames of the grid."""
        while True:
            updates = []
            for target_slice, rule, to_state in self._RULES:
                updates.append((target_slice, rule(self), to_state))

            for target_slice, mask, state in updates:
                self._grid[target_slice][mask] = state.value

            yield self._grid

    @property
    def str_repr(self) -> str:
        """Return a string representation of the grid."""
        return "\n".join(" ".join(state.char for state in row) for row in self._grid)
