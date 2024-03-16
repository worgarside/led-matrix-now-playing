from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from enum import IntEnum, unique
from time import sleep

import numpy as np
from numpy.typing import NDArray

CHARS: tuple[str, str, str, str] = (".", "O", "o", "*", "*", "!")

@unique
class State(IntEnum):
    """Enum representing the state of a cell."""

    NULL = 0
    RAINDROP = 1
    SPLASHDROP = 2
    SPLASH_LEFT = 3
    SPLASH_RIGHT = 4

    UNSET = 5




    # Update the original grid slice


    
def rule2(grid):
    """If the cell is 0 and the cell above it is 1 or 2, make it 1 or 2 respectively."""
    condition_for_1 = (grid[1:, :] == 0) & (grid[:-1, :] == 1)
    condition_for_2 = (grid[1:, :] == 0) & (grid[:-1, :] == 2)
    # Creating a combined mask for each condition, with the row index adjusted to fit the original grid size
    mask_for_1 = np.pad(condition_for_1, ((1, 0), (0, 0)), mode='constant', constant_values=False)
    mask_for_2 = np.pad(condition_for_2, ((1, 0), (0, 0)), mode='constant', constant_values=False)
    return [(mask_for_1, 1), (mask_for_2, 2)]
def rule3(grid):
    """If the cell is 1, the cell below is 1 and the cell above is 0, set it to 0."""
    condition = (grid[1:-1, :] == 1) & (grid[2:, :] == 1) & (grid[:-2, :] == 0)
    mask = np.pad(condition, ((1, 1), (0, 0)), mode='constant', constant_values=False)
    return [(mask, 0)]


@dataclass
class Grid:

    height: int
    width: int = -1

    frame_index: int = 0

    def __post_init__(self) -> None:
        """Set the calculated attributes of the Grid."""
        if self.width == -1:
            self.width = self.height

        self._grid = self.zeros()

    def zeros(self, *, dtype=np.int_) -> NDArray[np.int_]:
        """Return a grid of zeros."""
        return np.zeros((self.height, self.width), dtype=dtype)
    
    @property
    def str_repr(self) -> str:
        return "\n".join(" ".join(CHARS[state] for state in row) for row in self._grid)




class RainingGrid(Grid):


    def generate_raindrops(self):
        mask = self.zeros(dtype=np.bool_)
        
        mask[0] = np.random.rand(self.width) < 0.025

        return mask
    
    def move_rain_down(self):
        lower_slice = self._grid[1:, :]
        upper_slice = self._grid[:-1, :]
        
        mask = self.zeros(dtype=np.bool_)

        mask[1:, :] = (upper_slice == State.RAINDROP) & (lower_slice == State.NULL)

        return mask
    
    def top_of_rain_down(self):
        mask = self.zeros(dtype=np.bool_)

        middle_slice = self._grid[1:-1, :]  # Main slice, excluding the first and last row
        above_slice = self._grid[:-2, :]  # Above slice, shifted one row up from the middle
        below_slice = self._grid[2:, :]   # Below slice, shifted one row down from the middle

        mask[1:-1, :] = (middle_slice == State.RAINDROP) & (below_slice == State.RAINDROP) & (above_slice != State.RAINDROP)

        mask[0] = (self._grid[0] == State.RAINDROP) & (self._grid[1] == State.RAINDROP)
        mask[-1] = (self._grid[-1] == State.RAINDROP) & (self._grid[-2] != State.RAINDROP)

        return mask
    
    def splash_left(self):
        mask = self.zeros(dtype=np.bool_)
        
        above_splashable = self._grid[-2, 1:]
        splashable = self._grid[-1, 1:]
        splashing = (splashable == State.RAINDROP) & (above_splashable != State.RAINDROP)

        splash_spots = self._grid[-2, :-1]
        spots_are_free = splash_spots == State.NULL

        below_splashes = self._grid[-1, :-1]
        # TODO this would be better as "will be NULL", instead of "is NULL"
        clear_below = below_splashes == State.NULL

        mask[-2, :-1] = splashing & spots_are_free & clear_below

        return mask
    

    def splash_right(self):
        mask = self.zeros(dtype=np.bool_)
        
        above_splashable = self._grid[-2, :-1]
        splashable = self._grid[-1, :-1]
        splashing = (splashable == State.RAINDROP) & (above_splashable != State.RAINDROP)

        splash_spots = self._grid[-2, 1:]
        spots_are_free = splash_spots == State.NULL

        below_splashes = self._grid[-1, 1:]
        # TODO this would be better as "will be NULL", instead of "is NULL"
        clear_below = below_splashes == State.NULL

        mask[-2, 1:] = splashing & spots_are_free & clear_below

        return mask
    
    def splash_left_high(self):
        mask = self.zeros(dtype=np.bool_)

        splashing_spots = self._grid[-2, 1:] == State.SPLASH_LEFT

        mask[-3, :-1] =  splashing_spots # & self._grid[-3, :-1] will be NULL

        return mask
    
    def splash_right_high(self):
        mask = self.zeros(dtype=np.bool_)

        splashing_spots = self._grid[-2, :-1] == State.SPLASH_RIGHT

        mask[-3, 1:] =  splashing_spots

        return mask

    def remove_splash_left_lower(self):
        mask = self.zeros(dtype=np.bool_)
        splash_zone = self._grid[-3:, :]
        mask[-3:, :] = ( splash_zone == State.SPLASH_LEFT) |  ( splash_zone == State.SPLASHDROP) |  ( splash_zone == State.SPLASH_RIGHT)
        return mask
    
    def remove_splash_left_higher(self):
        mask = self.zeros(dtype=np.bool_)
        mask[-3] = (self._grid[-3] == State.SPLASH_LEFT) |  (self._grid[-3] == State.SPLASH_RIGHT)
        return mask
    
    def move_splashdrop_down(self):
        lower_slice = self._grid[1:, :]
        upper_slice = self._grid[:-1, :]
        
        mask = self.zeros(dtype=np.bool_)

        mask[1:, :] = (upper_slice == State.SPLASHDROP) & (lower_slice == State.NULL)

        return mask
        




def main() -> None:
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

        

        print(grid.str_repr)


        print("\n\n")
        sleep(0.075)


if __name__ == "__main__":
    main()

