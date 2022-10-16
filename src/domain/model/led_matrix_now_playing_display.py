"""Constants and class for managing the RGB LED Matrix"""

from __future__ import annotations

from json import dumps
from logging import DEBUG, getLogger
from math import ceil
from threading import Thread
from time import sleep
from typing import Literal, TypedDict

from dotenv import load_dotenv
from paho.mqtt.publish import multiple
from wg_utilities.exceptions import on_exception
from wg_utilities.loggers import add_stream_handler

from application.handler.mqtt import (
    HA_LED_MATRIX_STATE_TOPIC,
    HA_MTRXPI_CONTENT_TOPIC,
    MQTT_HOST,
    MQTT_PASSWORD,
    MQTT_USERNAME,
)
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


class HAPendingUpdatesInfo(TypedDict):
    """Typing info for the record of pending attribute updates"""

    artist: bool
    entity_picture: bool
    media_title: bool


class HAPayloadInfo(TypedDict):
    """Typing info for the payload of the MQTT message to Home Assistant"""

    state: bool
    media_title: str
    artist: str
    album: str
    album_artwork_url: str


class LedMatrixNowPlayingDisplay:
    """Class for displaying track information on an RGB LED Matrix"""

    OPTIONS: LedMatrixOptionsInfo = {
        "cols": 64,
        "rows": 64,
        "brightness": 80,
        "gpio_slowdown": 4,
        "hardware_mapping": "adafruit-hat",
        "inverse_colors": False,
        "led_rgb_sequence": "RGB",
        "show_refresh_rate": False,
    }

    @on_exception()  # type: ignore[misc]
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

        self._media_title = Text("", media_title_y_pos, matrix_width=self.matrix.width)
        self._artist = Text("", artist_y_pos, matrix_width=self.matrix.width)
        self._artwork_image = NULL_IMAGE

        self.scroll_thread = Thread(target=self._scroll_worker)

        self._pending_ha_updates: HAPendingUpdatesInfo = {
            "media_title": False,
            "artist": False,
            "entity_picture": False,
        }

    @on_exception()  # type: ignore[misc]
    def _clear_text(self, text: Text, update_canvas: bool = False) -> None:
        """Clears a lines of text on the canvas by writing a line of black "█"
        characters

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

    @on_exception()  # type: ignore[misc]
    def _scroll_worker(self) -> None:
        """Actively scrolls the media title and artist text when required"""

        while self.scrollable_content:
            if self.artist.scrollable:
                self.write_artist(clear_first=True)

            if self.media_title.scrollable:
                self.write_media_title(clear_first=True)

            self.matrix.SwapOnVSync(self.canvas)
            sleep(0.5)

        LOGGER.debug("Scroll worker exiting")

    @on_exception()  # type: ignore[misc]
    def _start_scroll_worker(self) -> None:
        """Starts the scroll worker thread if it is not already running"""
        try:
            if not self.scroll_thread.is_alive():
                self.scroll_thread.start()
                LOGGER.debug("Scroll thread is dead, restarted")
        except (RuntimeError, AttributeError) as exc:
            LOGGER.debug("Recreating scroll thread: %s", repr(exc))
            self.scroll_thread = Thread(target=self._scroll_worker)
            self.scroll_thread.start()

    @on_exception()  # type: ignore[misc]
    def clear_artist(self, update_canvas: bool = False) -> None:
        """Clears the artist text

        Args:
            update_canvas (bool, optional): whether to update the canvas after clearing
                the text. Defaults to False.
        """
        self._clear_text(self.artist, update_canvas)

    @on_exception()  # type: ignore[misc]
    def clear_media_title(self, update_canvas: bool = False) -> None:
        """Clears the media title text

        Args:
            update_canvas (bool, optional): whether to update the canvas after clearing
                the text. Defaults to False.
        """
        self._clear_text(self.media_title, update_canvas)

    @on_exception()  # type: ignore[misc]
    def write_artwork_image(self, swap_on_vsync: bool = False) -> None:
        """Writes the artwork image to the canvas

        Args:
            swap_on_vsync (bool, optional): whether to swap the canvas on vsync.
                Defaults to False.
        """
        self.canvas.SetImage(
            self.artwork_image.get_image(
                self.image_size,
            ).convert("RGB"),
            offset_x=self.image_x_pos,
            offset_y=self.image_y_pos,
        )

        if swap_on_vsync:
            self.matrix.SwapOnVSync(self.canvas)

    @on_exception()  # type: ignore[misc]
    def write_artist(
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

    @on_exception()  # type: ignore[misc]
    def write_media_title(
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

    @property
    def artist(self) -> Text:
        """Returns the media title content"""
        return self._artist

    @artist.setter
    def artist(self, value: str) -> None:
        """Sets the artist text content"""
        if not isinstance(value, str):
            raise TypeError("Value for `artist` must be a string")

        if value == self.artist.original_content:
            return

        self._artist.display_content = value
        self.write_artist(clear_first=True, swap_on_vsync=True)

        self.pending_ha_updates = {
            "artist": True,
            "entity_picture": self.pending_ha_updates["entity_picture"],
            "media_title": self.pending_ha_updates["media_title"],
        }

        if self.artist.scrollable:
            LOGGER.debug("Sending request to start scroll thread from artist setter")
            self._start_scroll_worker()

    @property
    def artwork_image(self) -> ArtworkImage:
        """Returns the current artwork image

        Returns:
            Image: the current artwork image
        """
        return self._artwork_image

    @artwork_image.setter
    def artwork_image(self, image: ArtworkImage) -> None:
        """Sets the current artwork image

        Args:
            image (ArtworkImage): the new artwork image
        """
        if image == self._artwork_image:
            return

        self._artwork_image = image

        self.write_artwork_image()

        self.pending_ha_updates = {
            "artist": self.pending_ha_updates["artist"],
            "entity_picture": True,
            "media_title": self.pending_ha_updates["media_title"],
        }

    @property
    def media_title(self) -> Text:
        """Returns the media title content"""
        return self._media_title

    @media_title.setter
    def media_title(self, value: str) -> None:
        """Sets the media title content"""
        if not isinstance(value, str):
            raise TypeError("Value for `media_title` must be a string")

        if value == self.media_title.display_content:
            return

        self.media_title.display_content = value
        self.write_media_title(clear_first=True, swap_on_vsync=True)

        self.pending_ha_updates = {
            "artist": self.pending_ha_updates["artist"],
            "entity_picture": self.pending_ha_updates["entity_picture"],
            "media_title": True,
        }

        if self.media_title.scrollable:
            LOGGER.debug(
                "Sending request to start scroll thread from media_title setter"
            )
            self._start_scroll_worker()

    @property
    def brightness(self) -> float:
        """Gets the brightness of the display

        Returns:
            float: the brightness of the display
        """
        return float(self.matrix.brightness)

    @brightness.setter
    def brightness(self, value: int) -> None:
        """Sets the brightness of the display. Force updates all canvas content to
        apply the brightness

        Args:
            value (int): the brightness of the display
        """
        self.matrix.brightness = value

        self.write_artwork_image()

        if not self.artist.scrollable:
            # It'll get written in <=0.5s anyway, so no need to write it again. This
            # also causes a brief overlap glitch on the matrix with scrolling text
            self.write_artist()

        if not self.media_title.scrollable:
            self.write_media_title()

        self.matrix.SwapOnVSync(self.canvas)

    @property
    def home_assistant_payload(self) -> HAPayloadInfo:
        """
        Returns:
            HAPayloadInfo: the payload to send to Home Assistant for sensor updates
        """
        return {
            "state": any(
                [
                    self.artwork_image != NULL_IMAGE,
                    self.artist.display_content != "",
                    self.media_title.display_content != "",
                ]
            ),
            "media_title": self.media_title.original_content,
            "artist": self.artist.original_content,
            "album": self.artwork_image.album,
            "album_artwork_url": self.artwork_image.url,
        }

    @property
    def pending_ha_updates(self) -> HAPendingUpdatesInfo:
        """
        Returns:
            HAPendingUpdatesInfo: a record of any pending attribute updates
        """
        return self._pending_ha_updates

    @pending_ha_updates.setter
    def pending_ha_updates(self, value: HAPendingUpdatesInfo) -> None:
        """Updates the HA pending updates record and then sends the updates to HA if all
         attributes are waiting to be updated

        Args:
            value (dict): this must be the entire dict: updating a single value will not
                trigger this setter method and the updates won't be sent to HA
        """
        self._pending_ha_updates = value

        if all(self._pending_ha_updates.values()):
            multiple(
                msgs=[
                    {
                        "topic": HA_LED_MATRIX_STATE_TOPIC,
                        "payload": "ON"
                        if any(
                            [
                                self.artwork_image != NULL_IMAGE,
                                self.artist.display_content != "",
                                self.media_title.display_content != "",
                            ]
                        )
                        else "OFF",
                    },
                    {
                        "topic": HA_MTRXPI_CONTENT_TOPIC,
                        "payload": dumps(self.home_assistant_payload),
                    },
                ],
                auth={"username": MQTT_USERNAME, "password": MQTT_PASSWORD},
                hostname=MQTT_HOST,
            )

            self._pending_ha_updates = {
                "entity_picture": False,
                "media_title": False,
                "artist": False,
            }

            # TODO if display is "off", clear the matrix?

    @property
    def scrollable_content(self) -> bool:
        """Returns whether the display has any scrollable content

        Returns:
            bool: True if there is scrollable content, False otherwise
        """
        return bool(self.media_title.scrollable or self.artist.scrollable)
