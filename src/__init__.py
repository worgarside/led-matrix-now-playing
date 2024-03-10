from __future__ import annotations

try:
    from rgbmatrix import RGBMatrix, RGBMatrixOptions  # type: ignore[import-not-found]
    from rgbmatrix.graphics import (  # type: ignore[import-not-found]
        Color,
        DrawText,
        Font,
    )
except ImportError as exc:
    from sys import platform

    if platform == "linux":
        raise

    from logging import warning

    warning("Could not import `rgbmatrix`, using emulator instead: %s", repr(exc))

    from RGBMatrixEmulator import (  # type: ignore[import-untyped]
        RGBMatrix,
        RGBMatrixOptions,
    )
    from RGBMatrixEmulator.graphics import (  # type: ignore[import-untyped]
        Color,
        DrawText,
        Font,
    )


__all__ = ["Color", "Font", "RGBMatrix", "RGBMatrixOptions", "DrawText"]
