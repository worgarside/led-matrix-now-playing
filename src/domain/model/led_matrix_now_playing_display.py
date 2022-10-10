"""Constants and class for managing the RGB LED Matrix"""

from __future__ import annotations

from json import dumps, loads
from logging import DEBUG, getLogger
from math import ceil
from socket import gethostname
from time import sleep
from typing import Any

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
except ImportError as exc:
    LOGGER.warning(
        "Could not import `rgbmatrix`, using emulator instead: %s", repr(exc)
    )

    from RGBMatrixEmulator import RGBMatrix, RGBMatrixOptions
    from RGBMatrixEmulator.graphics import DrawText


OPTIONS = RGBMatrixOptions()
OPTIONS.cols = 64
OPTIONS.rows = 64
OPTIONS.brightness = 100
OPTIONS.gpio_slowdown = 0
OPTIONS.hardware_mapping = "adafruit-hat"
OPTIONS.inverse_colors = False
OPTIONS.led_rgb_sequence = "RGB"
OPTIONS.show_refresh_rate = False

MATRIX = RGBMatrix(options=OPTIONS)
CANVAS = MATRIX.CreateFrameCanvas()


NONE_VALUES = (
    None,
    "",
    "None",
    "none",
    "null",
)


class LedMatrixNowPlayingDisplay:
    """Class for displaying track information on an RGB LED Matrix"""

    def __init__(self) -> None:
        artist_y_pos = MATRIX.height - 2
        media_title_y_pos = artist_y_pos - (FONT_HEIGHT + 1)

        self.image_size = media_title_y_pos - (FONT_HEIGHT + 3)
        self.image_x_pos = (MATRIX.width - self.image_size) / 2
        self.image_y_pos = (MATRIX.height - (FONT_HEIGHT * 2 + 2) - self.image_size) / 2

        self.media_title = Text("", media_title_y_pos, matrix_width=MATRIX.width)
        self._next_media_title_content = self.media_title.display_content
        self.artist = Text("", artist_y_pos, matrix_width=MATRIX.width)
        self._next_artist_content = self.artist.display_content

        self.artwork_image = NULL_IMAGE
        self._next_artwork_image = NULL_IMAGE

        self.loop_active = False

    @staticmethod
    def _clear_text(text: Text, update_canvas: bool = False) -> None:
        """Clears a lines of text on the canvas by writing a line of "█" characters

        Args:
            text (str): the text instance to clear
            update_canvas (bool, optional): whether to update the canvas after clearing
                the text. Defaults to False.
        """
        DrawText(
            CANVAS,
            FONT,
            0,
            text.y_pos,
            text.CLEAR_TEXT_COLOR,
            "█" * ceil(MATRIX.width / FONT_WIDTH),
        )
        if update_canvas:
            MATRIX.SwapOnVSync(CANVAS)

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

    def handle_mqtt_message(self, _: Any, __: Any, message: MQTTMessage) -> None:
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
            )
        else:
            LOGGER.debug(
                "No album artwork URL found in payload, defaulting to `NULL_IMAGE`"
            )
            artwork_image = NULL_IMAGE

        self.update_display_values(
            payload.get("title"),
            payload.get("artist"),
            artwork_image,
        )

    def start_loop(self) -> None:
        """Starts the loop for displaying the track information

        Instead of using `MATRIX.Clear()` to clear the canvas, I "clear" the text by
        overwriting it with a string of black "█" characters, then write the
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
                CANVAS.SetImage(
                    self.artwork_image.get_image(
                        self.image_size,
                        convert="RGB",
                        delay_download=5 if "pi" in gethostname() else 0,
                    ),
                    offset_x=self.image_x_pos,
                    offset_y=self.image_y_pos,
                )

            if media_title_scrollable := self.media_title.scrollable:
                self.clear_media_title()

            if artist_scrollable := self.artist.scrollable:
                self.clear_artist()

            DrawText(
                CANVAS,
                FONT,
                self.media_title.get_next_x_pos(),
                self.media_title.y_pos,
                self.media_title.color,
                self.media_title.display_content,
            )

            DrawText(
                CANVAS,
                FONT,
                self.artist.get_next_x_pos(),
                self.artist.y_pos,
                self.artist.color,
                self.artist.display_content,
            )

            MATRIX.SwapOnVSync(CANVAS)

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
                    sleep(0.1)

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
