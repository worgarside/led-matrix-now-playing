"""Constants and class for managing the RGB LED Matrix"""

from __future__ import annotations

from json import dumps, loads
from logging import DEBUG, getLogger
from math import ceil
from time import sleep
from typing import Literal, TypedDict

from dotenv import load_dotenv
from paho.mqtt.client import MQTTMessage
from wg_utilities.loggers import add_stream_handler

from domain.model.artwork_image import NULL_IMAGE, ArtworkImage
from domain.model.text_label import FONT, FONT_HEIGHT, FONT_WIDTH, Text

load_dotenv()

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)
add_stream_handler(LOGGER)


try:
    from rgbmatrix import RGBMatrix, RGBMatrixOptions
    from rgbmatrix.graphics import DrawText
except ImportError as _rgb_matrix_import_exc:
    LOGGER.warning(
        "Could not import `rgbmatrix`, using emulator instead: %s",
        repr(_rgb_matrix_import_exc),
    )

    from RGBMatrixEmulator import RGBMatrix, RGBMatrixOptions
    from RGBMatrixEmulator.graphics import DrawText


NONE_VALUES = (
    None,
    "",
    "None",
    "none",
    "null",
)


class LedMatrixOptionsInfo(TypedDict):
    """Typing info for the matrix options"""

    cols: int
    rows: int
    brightness: int
    gpio_slowdown: int
    hardware_mapping: Literal["adafruit-hat"]
    inverse_colors: bool
    led_rgb_sequence: Literal["RGB"]
    show_refresh_rate: bool


class LedMatrixNowPlayingDisplay:
    """Class for displaying track information on an RGB LED Matrix"""

    OPTIONS: LedMatrixOptionsInfo = {
        "cols": 64,
        "rows": 64,
        "brightness": 80,
        "gpio_slowdown": 0,
        "hardware_mapping": "adafruit-hat",
        "inverse_colors": False,
        "led_rgb_sequence": "RGB",
        "show_refresh_rate": False,
    }

    def __init__(self, brightness: int | None = None) -> None:
        options = RGBMatrixOptions()
        for k, v in self.OPTIONS.items():
            if k == "brightness" and brightness:
                options.brightness = brightness
                continue
            setattr(options, k, v)

        self.matrix = RGBMatrix(options=options)
        self.canvas = self.matrix.CreateFrameCanvas()

        artist_y_pos = self.matrix.height - 2
        media_title_y_pos = artist_y_pos - (FONT_HEIGHT + 1)

        self.image_size = media_title_y_pos - (FONT_HEIGHT + 3)
        self.image_x_pos = (self.matrix.width - self.image_size) / 2
        self.image_y_pos = (
            self.matrix.height - (FONT_HEIGHT * 2 + 2) - self.image_size
        ) / 2

        self.media_title = Text("", media_title_y_pos, matrix_width=self.matrix.width)
        self._next_media_title_content = self.media_title.display_content
        self.artist = Text("", artist_y_pos, matrix_width=self.matrix.width)
        self._next_artist_content = self.artist.display_content

        self.artwork_image = NULL_IMAGE
        self._next_artwork_image = NULL_IMAGE

        self._brightness: int = brightness or self.OPTIONS["brightness"]

        self.loop_active = False

    def _clear_text(self, text: Text, update_canvas: bool = False) -> None:
        """Clears a lines of text on the canvas by writing a line of "█" characters

        Args:
            text (str): the text instance to clear
            update_canvas (bool, optional): whether to update the canvas after clearing
                the text. Defaults to False.
        """
        DrawText(
            self.canvas,
            FONT,
            0,
            text.y_pos,
            text.CLEAR_TEXT_COLOR,
            "█" * ceil(self.matrix.width / FONT_WIDTH),
        )
        if update_canvas:
            self.matrix.SwapOnVSync(self.canvas)

    def clear_artist(self, update_canvas: bool = False) -> None:
        """Clears the artist text

        Args:
            update_canvas (bool, optional): whether to update the canvas after clearing
                the text. Defaults to False.
        """
        self._clear_text(self.artist, update_canvas)

    def clear_media_title(self, update_canvas: bool = False) -> None:
        """Clears the media title text

        Args:
            update_canvas (bool, optional): whether to update the canvas after clearing
                the text. Defaults to False.
        """
        self._clear_text(self.media_title, update_canvas)

    def force_write_artist(
        self, *, clear_first: bool = False, swap_on_vsync: bool = False
    ) -> None:
        """Forces the artist to be written to the canvas

        Args:
            clear_first (bool, optional): whether to clear the artist text before
                writing
            swap_on_vsync (bool, optional): update the canvas after writing the text
        """

        if clear_first:
            self.clear_artist()

        DrawText(
            self.canvas,
            FONT,
            self.artist.get_next_x_pos(),
            self.artist.y_pos,
            self.artist.color,
            self.artist.display_content,
        )

        if swap_on_vsync:
            self.matrix.SwapOnVSync(self.canvas)

    def force_write_artwork(self, *, swap_on_vsync: bool = False) -> None:
        """Forces the artwork to be written to the canvas

        Args:
            swap_on_vsync (bool, optional): update the canvas after writing the image

        Raises:
            Exception: if the `self.canvas.SetImage` call fails, and it's not due to a
                non-RGB image
        """
        try:
            self.canvas.SetImage(
                self.artwork_image.get_image(
                    self.image_size,
                ),
                offset_x=self.image_x_pos,
                offset_y=self.image_y_pos,
            )
        except Exception as exc:  # pylint: disable=broad-except
            if str(exc).startswith(
                "Currently, only RGB mode is supported for SetImage()."
            ):
                LOGGER.error(
                    "Unable to set image, RGB mode not supported."
                    ' Retrying with `.convert("RGB")`'
                )
                self.canvas.SetImage(
                    self.artwork_image.get_image(
                        self.image_size,
                    ).convert("RGB"),
                    offset_x=self.image_x_pos,
                    offset_y=self.image_y_pos,
                )
            else:
                raise

        if swap_on_vsync:
            self.matrix.SwapOnVSync(self.canvas)

    def force_write_media_title(
        self, *, clear_first: bool = False, swap_on_vsync: bool = False
    ) -> None:
        """Forces the media title to be written to the canvas

        Args:
            clear_first (bool, optional): whether to clear the media title text before
                writing
            swap_on_vsync (bool, optional): update the canvas after writing the text
        """
        if clear_first:
            self.clear_media_title()

        DrawText(
            self.canvas,
            FONT,
            self.media_title.get_next_x_pos(),
            self.media_title.y_pos,
            self.media_title.color,
            self.media_title.display_content,
        )

        if swap_on_vsync:
            self.matrix.SwapOnVSync(self.canvas)

    def handle_mqtt_message(self, message: MQTTMessage) -> None:
        """Handles an MQTT message

        Args:
            message (MQTTMessage): the message object from the MQTT subscription
        """

        payload = loads(message.payload.decode())

        LOGGER.debug("Received payload: %s", dumps(payload))

        for k, v in payload.items():
            if v in NONE_VALUES:
                payload[k] = None

        if (album_artwork_url := payload.get("album_artwork_url")) is not None:
            artwork_image = ArtworkImage(
                album=payload.get("album"),
                artist=payload.get("artist"),
                url=album_artwork_url,
                # Pre-caching seems like it should be faster, at least a bit, but I
                # don't think the Pi Zero has enough power to cache the image in a
                # separate thread, so it actually makes it ~2x slower :(
                pre_cache=False,
                pre_cache_size=self.image_size,
            )
        else:
            LOGGER.debug(
                "No album artwork URL found in payload, defaulting to `NULL_IMAGE`"
            )
            artwork_image = NULL_IMAGE

        if any(
            [
                (
                    artist_change := (
                        self.artist.original_content
                        != (new_artist_content := payload.get("artist"))
                    )
                ),
                (
                    media_title_change := (
                        self.media_title.original_content
                        != (new_media_title_content := payload.get("title"))
                    )
                ),
                (artwork_change := (self.artwork_image.album != payload.get("album"))),
            ]
        ):
            LOGGER.debug(
                "Artist change: %s; Media Title change: %s, Artwork change: %s",
                artist_change,
                media_title_change,
                artwork_change,
            )
            self.update_display_values(
                new_media_title_content,
                new_artist_content,
                artwork_image,
            )

    def start_loop(self) -> None:
        """Starts the loop for displaying the track information

        Instead of using `self.matrix.Clear()` to clear the canvas, I "clear" the text
        by overwriting it with a string of black "█" characters, then write the
        new/scrolled text in place. This stops me from having to re-display the artwork
        and any unchanged text on each loop, and instead I only update the bits I need
        to!
        """
        self.loop_active = True

        while self.loop_active:
            if self._next_artwork_image != self.artwork_image:
                LOGGER.debug(
                    "Updating artwork image from %s to %s",
                    self.artwork_image,
                    self._next_artwork_image,
                )

                self.artwork_image = self._next_artwork_image
                self.force_write_artwork()

            self.force_write_artist(
                clear_first=(artist_scrollable := self.artist.scrollable)
            )
            self.force_write_media_title(
                clear_first=(media_title_scrollable := self.media_title.scrollable),
                swap_on_vsync=True,
            )

            if media_title_scrollable or artist_scrollable:
                # Wait 0.5s to refresh the screen
                sleep(0.5)
            else:
                # Wait until there's a change, no point refreshing the display if
                # nothing has changed
                while (
                    self._next_media_title_content == self.media_title.display_content
                    and self._next_artist_content == self.artist.display_content
                    and self._next_artwork_image == self.artwork_image
                    and self.loop_active
                ):
                    pass

            if self._next_media_title_content != self.media_title.original_content:
                LOGGER.debug(
                    "Updating media title from `%s` to `%s`",
                    self.media_title.display_content,
                    self._next_media_title_content,
                )
                self.clear_media_title()
                self.media_title.display_content = self._next_media_title_content

            if self._next_artist_content != self.artist.original_content:
                LOGGER.debug(
                    "Updating artist from `%s` to `%s`",
                    self.artist.display_content,
                    self._next_artist_content,
                )
                self.clear_artist()
                self.artist.display_content = self._next_artist_content

    def update_display_values(
        self,
        title: str | None,
        artist: str | None,
        artwork_image: ArtworkImage | None = None,
    ) -> None:
        """Updates the display values

        Args:
            title (str, optional): the title of the media
            artist (str, optional): the artist of the media
            artwork_image (ArtworkImage, optional): the artwork image of the media
        """
        LOGGER.debug("Updating display values: %s, %s", title, artist)

        self._next_media_title_content = title or ""
        self._next_artist_content = artist or ""
        self._next_artwork_image = artwork_image or NULL_IMAGE

        self.media_title.reset_x_pos()
        self.artist.reset_x_pos()

    @property
    def brightness(self) -> float:
        """Gets the brightness of the display

        Returns:
            int: the brightness of the display
        """
        return self._brightness

    @brightness.setter
    def brightness(self, value: int) -> None:
        """Sets the brightness of the display. Force updates all canvas content to
        apply the brightness

        Args:
            value (int): the brightness of the display
        """
        self._brightness = value
        self.matrix.brightness = value

        self.force_write_artwork()
        self.force_write_artist()
        self.force_write_media_title(swap_on_vsync=True)
