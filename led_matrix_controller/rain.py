"""Rain simulation."""

from __future__ import annotations

from time import time
from typing import TYPE_CHECKING, Any, ClassVar
import numpy as np
from numpy.typing import NDArray
from models import RGBMatrix, RGBMatrixOptions
from utils.cellular_automata.ca import Cell, Condition, Grid, Rows, Rule
from utils.cellular_automata.ca2 import RainingGrid, State

if TYPE_CHECKING:
    from models.matrix import LedMatrixOptionsInfo


def print_with_newlines(frame: Rows, /) -> None:
    """Print the string with newlines before and after."""
    print()
    print("\n".join(" ".join(c.state.str_repr for c in row) for row in frame))
    print()


def define_grid(*, height: int) -> Grid:
    """Define the grid and its rules."""
    raindrop_generator = Rule(
        condition=lambda c: c.is_top and Condition.percentage_chance(0.025)(c),
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
        condition=lambda c: Condition.cell_at_height(c, -2)
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

    return Grid(
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

    def update_cell(self, cell: Cell, /) -> None:
        """Update the cell on the LED matrix."""
        if not cell.has_state(cell.previous_frame_state):
            self.canvas.SetPixel(cell.x, cell.y, cell.state.r, cell.state.g, cell.state.b)

    def render_frame(self, rows: Rows) -> None:
        """Render the frame to the LED matrix."""
        for row in rows:
            for cell in row:
                self.update_cell(cell)

        self.swap_on_vsync(None)

    def render_array(self, array: NDArray):
        colors = {
                1:(13, 94, 255),
                2:(107, 155, 250),
                3:(170, 197, 250),
                4:(170, 197, 250),
        }


        for (y, x), state in np.ndenumerate(array):
            self.canvas.SetPixel(x, y, *colors.get(state, (0, 0, 0)))

        self.swap_on_vsync(None)

    def swap_on_vsync(self, _: Any) -> None:
        """Swap the canvas on the vertical sync."""
        self.matrix.SwapOnVSync(self.canvas)


def main() -> None:
    """Run the rain simulation."""

    matrix = Matrix()

    size = 64

    grid = RainingGrid(size)

    for _ in range(1000):
        masks = [
            (grid.generate_raindrops(), State.RAINDROP),
            (grid.move_rain_down(), State.RAINDROP),
            (grid.top_of_rain_down(), State.NULL),
            (grid.splash_left(), State.SPLASH_LEFT),
            (grid.splash_left_high(), State.SPLASH_LEFT),
            (grid.remove_splash_left_lower(), State.NULL),
            (grid.remove_splash_left_higher(), State.SPLASHDROP),
            (grid.move_splashdrop_down(), State.SPLASHDROP),
            (grid.splash_right(), State.SPLASH_RIGHT),
            (grid.splash_right_high(), State.SPLASH_RIGHT),
        ]

        for mask, state in masks:
            grid._grid[mask] = state

        matrix.render_array(grid._grid)
        

def rough_benchmark() -> None:
    """Rough benchmark of the rain simulation."""
    matrix = Matrix()
    grid = define_grid(height=32)

    times = []

    for _ in range(10):
        start = time()
        grid.run(
            cell_callback=matrix.update_cell,
            frame_callback=matrix.swap_on_vsync,
            limit=1000,
        )
        times.append(time() - start)

        print(f"Rough benchmark: {times[-1]:.2f} seconds")

    print(f"Average time: {sum(times) / len(times):.2f} seconds")


if __name__ == "__main__":
    main()
