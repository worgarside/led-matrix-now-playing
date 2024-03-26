"""Rain simulation."""

from __future__ import annotations

from enum import unique
from functools import lru_cache
from typing import TYPE_CHECKING, ClassVar, Literal

import numpy as np
from models import RGBMatrix, RGBMatrixOptions
from utils import const
from utils.cellular_automata.ca import Direction, Grid, Mask, StateBase, TargetSlice

if TYPE_CHECKING:
    from models.matrix import LedMatrixOptionsInfo
    from numpy.typing import NDArray


@unique
class State(StateBase):
    """Enum representing the state of a cell."""

    NULL = 0, " "
    RAINDROP = 1, "O", (13, 94, 255)
    SPLASHDROP = 2, "o", (107, 155, 250)
    SPLASH_LEFT = 3, "*", (170, 197, 250)
    SPLASH_RIGHT = 4, "*", (170, 197, 250)

    @lru_cache(maxsize=1)
    @staticmethod
    def active_splashes() -> tuple[int, int]:
        """Return the active splash states."""
        return State.SPLASH_LEFT.state, State.SPLASH_RIGHT.state

    @lru_cache(maxsize=1)
    @staticmethod
    def any_splash() -> tuple[int, int, int]:
        """Return any splash state."""
        return State.SPLASH_LEFT.state, State.SPLASH_RIGHT.state, State.SPLASHDROP.state


class RainingGrid(Grid):
    """Basic rain simulation."""

    @Grid.rule(State.RAINDROP, target_slice=0)
    def generate_raindrops(self, target_slice: TargetSlice) -> Mask:
        """Generate raindrops at the top of the grid."""
        return const.RNG.random(self[*target_slice].shape) < 0.025  # noqa: PLR2004

    @Grid.rule(State.RAINDROP, target_slice=(slice(1, None), slice(None)))
    def move_rain_down(self, target_slice: TargetSlice) -> Mask:
        """Move raindrops down one cell."""
        lower_slice = self[target_slice]
        upper_slice = self[self.translate_slice(target_slice, vrt=Direction.UP)]

        return (upper_slice == State.RAINDROP) & (lower_slice == State.NULL)  # type: ignore[no-any-return]

    @Grid.rule(State.NULL)
    def top_of_rain_down(self, _: TargetSlice) -> Mask:
        """Move the top of a raindrop down."""
        middle_slice = self[slice(1, -1), slice(None)]
        above_slice = self[slice(None, -2), slice(None)]
        below_slice = self[slice(2, None), slice(None)]

        return np.vstack(
            (
                (self[0] == State.RAINDROP) & (self[1] == State.RAINDROP),
                (
                    (middle_slice == State.RAINDROP)
                    & (below_slice == State.RAINDROP)
                    & (above_slice != State.RAINDROP)
                ),
                (self[-1] == State.RAINDROP) & (self[-2] != State.RAINDROP),
            )
        )

    def _splash(
        self,
        target_slice: TargetSlice,
        *,
        source_slice_direction: Literal[Direction.LEFT, Direction.RIGHT],
    ) -> Mask:
        # TODO this would be better as "will be NULL", instead of "is NULL"
        source_slice = self[
            self.translate_slice(
                target_slice, vrt=Direction.DOWN, hrz=source_slice_direction
            )
        ]
        splashing = source_slice == State.RAINDROP
        free_splash_spots = self[target_slice] == State.NULL
        clear_below = (
            self[self.translate_slice(target_slice, vrt=Direction.DOWN)] == State.NULL
        )

        return splashing & free_splash_spots & clear_below  # type: ignore[no-any-return]

    @Grid.rule(State.SPLASH_LEFT, target_slice=(-2, slice(None, -1)))
    def splash_left(self, target_slice: TargetSlice) -> Mask:
        """Create a splash to the left."""
        return self._splash(target_slice, source_slice_direction=Direction.RIGHT)

    @Grid.rule(State.SPLASH_RIGHT, target_slice=(-2, slice(1, None)))
    def splash_right(self, target_slice: TargetSlice) -> Mask:
        """Create a splash to the right."""
        return self._splash(target_slice, source_slice_direction=Direction.LEFT)

    def _splash_high(
        self,
        target_slice: TargetSlice,
        *,
        splash_state: State,
        source_slice_direction: Literal[Direction.LEFT, Direction.RIGHT],
    ) -> Mask:
        source_slice = self[
            self.translate_slice(
                target_slice,
                vrt=Direction.DOWN,
                hrz=source_slice_direction,
            )
        ]

        return (  # type: ignore[no-any-return]
            source_slice == splash_state
        )  # & self[target_slice] will be NULL

    @Grid.rule(State.SPLASH_LEFT, target_slice=(-3, slice(None, -1)))
    def splash_left_high(self, target_slice: TargetSlice) -> Mask:
        """Continue the splash to the left."""
        return self._splash_high(
            target_slice,
            splash_state=State.SPLASH_LEFT,
            source_slice_direction=Direction.RIGHT,
        )

    @Grid.rule(State.SPLASH_RIGHT, target_slice=(-3, slice(1, None)))
    def splash_right_high(self, target_slice: TargetSlice) -> Mask:
        """Continue the splash to the right."""
        return self._splash_high(
            target_slice,
            splash_state=State.SPLASH_RIGHT,
            source_slice_direction=Direction.LEFT,
        )

    @Grid.rule(State.NULL, target_slice=(slice(-3, None), slice(None)))
    def remove_splashes(self, target_slice: TargetSlice) -> Mask:
        """Remove any splashes - they only last one frame."""
        return np.isin(self[target_slice], State.any_splash())

    @Grid.rule(State.SPLASHDROP, target_slice=-3)
    def create_splashdrop(self, target_slice: TargetSlice) -> Mask:
        """Convert a splash to a splashdrop."""
        return np.isin(self[target_slice], State.active_splashes())

    @Grid.rule(State.SPLASHDROP, target_slice=(slice(-3, None)))
    def move_splashdrop_down(self, target_slice: TargetSlice) -> Mask:
        """Move the splashdrop down."""
        source_slice = self[self.translate_slice(target_slice, vrt=Direction.UP)]

        return source_slice == State.SPLASHDROP  # type: ignore[no-any-return]
        # & self[target_slice] will be State.NULL


class Matrix:
    """Class for displaying track information on an RGB LED Matrix."""

    OPTIONS: ClassVar[LedMatrixOptionsInfo] = {
        "cols": 64,
        "rows": 64,
        "brightness": 80,
        "gpio_slowdown": 4,
        "hardware_mapping": "adafruit-hat-pwm",
        "inverse_colors": False,
        "led_rgb_sequence": "RGB",
        "show_refresh_rate": False,
    }

    def __init__(self) -> None:
        options = RGBMatrixOptions()

        for name, value in self.OPTIONS.items():
            if getattr(options, name, None) != value:
                setattr(options, name, value)

        self.matrix = RGBMatrix(options=options)
        self.canvas = self.matrix.CreateFrameCanvas()

    def render_array(self, array: NDArray[np.int_]) -> None:
        """Render the array to the LED matrix."""
        for (y, x), state in np.ndenumerate(array):
            self.canvas.SetPixel(x, y, *State.by_value(state).color)

        self.matrix.SwapOnVSync(self.canvas)


def main() -> None:
    """Run the rain simulation."""
    matrix = Matrix()

    size = 64

    grid = RainingGrid(size, size)

    for frame in grid.frames:
        matrix.render_array(frame)


if __name__ == "__main__":
    main()
