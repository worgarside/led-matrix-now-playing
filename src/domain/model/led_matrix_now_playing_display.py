"""Constants and class for managing the RGB LED Matrix"""

from __future__ import annotations

from json import dumps, loads
from logging import DEBUG, getLogger
from time import sleep
from typing import Any

from dotenv import load_dotenv
from paho.mqtt.client import MQTTMessage
from wg_utilities.loggers import add_stream_handler

from domain.model.artwork_image import NULL_IMAGE, ArtworkImage
from domain.model.text_label import FONT, Text

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
OPTIONS.brightness = 50
OPTIONS.gpio_slowdown = 0
OPTIONS.hardware_mapping = "adafruit-hat"
OPTIONS.inverse_colors = False
OPTIONS.led_rgb_sequence = "RGB"
OPTIONS.show_refresh_rate = False

MATRIX = RGBMatrix(options=OPTIONS)
CANVAS = MATRIX.CreateFrameCanvas()

IMAGE_SIZE = 40


class LedMatrixNowPlayingDisplay:
    """Class for displaying track information on an RGB LED Matrix"""

    MEDIA_TITLE_Y_POS = 52
    ARTIST_Y_POS = 62

    def __init__(self) -> None:
        self.media_title = Text("", self.MEDIA_TITLE_Y_POS, matrix_width=MATRIX.width)
        self.artist = Text("", self.ARTIST_Y_POS, matrix_width=MATRIX.width)

        self.artwork_image = NULL_IMAGE
        self.artwork_x_y_offset = (MATRIX.width - IMAGE_SIZE) / 2

        self.loop_active = False

    def handle_mqtt_message(self, _: Any, __: Any, message: MQTTMessage) -> None:
        """Handles an MQTT message

        Args:
            message (MQTTMessage): the message object from the MQTT subscription
        """

        payload = loads(message.payload.decode())

        LOGGER.debug("Received payload: %s", dumps(payload))

        self.update_display_values(
            payload.get("title"),
            payload.get("artist"),
            ArtworkImage(
                album=payload.get("album"),
                artist=payload.get("artist"),
                url=payload.get("album_artwork_url"),
            ),
        )

    def start_loop(self) -> None:
        """Starts the loop for displaying the track information"""
        self.loop_active = True

        while self.loop_active:
            LOGGER.info("LOOPING")
            MATRIX.Clear()
            CANVAS.SetImage(
                self.artwork_image.get_image(IMAGE_SIZE, convert="RGB"),
                offset_x=self.artwork_x_y_offset,
                offset_y=(self.artwork_x_y_offset / 2) - 3,
            )

            DrawText(
                canvas=CANVAS,
                font=FONT,
                x=self.media_title.get_next_x_pos(),
                y=self.media_title.y_pos,
                color=self.media_title.color,
                text=self.media_title.content,
            )
            DrawText(
                canvas=CANVAS,
                font=FONT,
                x=self.artist.get_next_x_pos(),
                y=self.artist.y_pos,
                color=self.artist.color,
                text=self.artist.content,
            )

            MATRIX.SwapOnVSync(CANVAS)

            if self.media_title.scrollable or self.artist.scrollable:
                sleep(0.5)
            else:
                current_media_title_content = self.media_title.content
                current_artist_content = self.artist.content
                while (
                    (not self.media_title.scrollable and not self.artist.scrollable)
                    or self.media_title.content != current_media_title_content
                    or self.artist.content != current_artist_content
                ):
                    sleep(0.1)

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

        self.media_title.content = title or ""
        self.artist.content = artist or ""

        self.artwork_image = artwork_image or NULL_IMAGE

        self.media_title.reset_x_pos()
        self.artist.reset_x_pos()
