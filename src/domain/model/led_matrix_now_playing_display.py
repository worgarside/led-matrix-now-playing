"""Constants and class for managing the RGB LED Matrix."""

from __future__ import annotations

from json import dumps
from logging import DEBUG, getLogger
from math import ceil
from threading import Thread
from time import sleep, time
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
    from rgbmatrix import RGBMatrix, RGBMatrixOptions  # type: ignore[import]
    from rgbmatrix.graphics import DrawText  # type: ignore[import]
except ImportError as _rgb_matrix_import_exc:
    LOGGER.warning(
        "Could not import `rgbmatrix`, using emulator instead: %s",
        repr(_rgb_matrix_import_exc),
    )

    from RGBMatrixEmulator import RGBMatrix, RGBMatrixOptions  # type: ignore[import]
    from RGBMatrixEmulator.graphics import DrawText  # type: ignore[import]


class LedMatrixOptionsInfo(TypedDict):
    """Typing info for the matrix options."""

    cols: int
    rows: int
    brightness: int
    gpio_slowdown: int
    hardware_mapping: Literal["adafruit-hat"]
    inverse_colors: bool
    led_rgb_sequence: Literal["RGB"]
    show_refresh_rate: bool


class HAPendingUpdatesInfo(TypedDict):
    """Typing info for the record of pending attribute updates."""

    artist: bool
    entity_picture: bool
    media_title: bool


class HAPayloadInfo(TypedDict):
    """Typing info for the payload of the MQTT message to Home Assistant."""

    state: bool
    media_title: str | None
    artist: str | None
    album: str | None
    album_artwork_url: str | None


class LedMatrixNowPlayingDisplay:
    """Class for displaying track information on an RGB LED Matrix."""

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

    @on_exception()
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

        self._media_title: Text = Text(
            "-", media_title_y_pos, matrix_width=self.matrix.width
        )
        self._artist: Text = Text("-", artist_y_pos, matrix_width=self.matrix.width)
        self._artwork_image: ArtworkImage = NULL_IMAGE

        self.scroll_thread = Thread(target=self._scroll_worker)
        self.ha_update_thread = Thread(target=self._update_ha_worker)

        self._pending_ha_updates: HAPendingUpdatesInfo = {
            "media_title": False,
            "artist": False,
            "entity_picture": False,
        }
        self._ha_last_updated = time()

    @on_exception()
    def _clear_text(self, text: Text, update_canvas: bool = False) -> None:
        """Clear a line on the canvas by writing a line of black "█" characters.

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

    @on_exception()
    def _scroll_worker(self) -> None:
        """Actively scrolls the media title and artist text when required."""

        while self.scrollable_content:
            if self.artist.scrollable:
                self.write_artist(clear_first=True)

            if self.media_title.scrollable:
                self.write_media_title(clear_first=True)

            self.matrix.SwapOnVSync(self.canvas)
            sleep(0.5)

        LOGGER.debug("Scroll worker exiting")

    @on_exception()
    def _start_update_ha_worker(self) -> None:
        """Start the HA update worker thread if it is not already running."""
        try:
            if self.ha_update_thread.is_alive():
                LOGGER.warning("HA update thread is already running")
            else:
                self.ha_update_thread.start()
                LOGGER.debug("HA update thread is dead, restarted")
        except (RuntimeError, AttributeError) as exc:
            LOGGER.debug("Recreating HA update thread: %s", repr(exc))
            self.ha_update_thread = Thread(target=self._update_ha_worker)
            self.ha_update_thread.start()

    @on_exception()
    def _start_scroll_worker(self) -> None:
        """Start the scroll worker thread if it is not already running."""
        try:
            if self.scroll_thread.is_alive():
                LOGGER.warning("Scroll thread is already running")
            else:
                self.scroll_thread.start()
                LOGGER.debug("Scroll thread is dead, restarted")
        except (RuntimeError, AttributeError) as exc:
            LOGGER.debug("Recreating scroll thread: %s", repr(exc))
            self.scroll_thread = Thread(target=self._scroll_worker)
            self.scroll_thread.start()

    @on_exception()
    def _update_ha_worker(self) -> None:
        start_time = time()

        # Wait up to 2.5 seconds
        while time() < start_time + 2.5 and not all(self.pending_ha_updates.values()):
            sleep(0.1)

        if not all(self.pending_ha_updates.values()):
            LOGGER.warning(
                "Timed out waiting for pending Home Assistant updates, sending current"
                " values"
            )

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

        LOGGER.debug(
            "Sent all pending updates to HA: %s", dumps(self.home_assistant_payload)
        )

    @on_exception()
    def clear_artist(self, update_canvas: bool = False) -> None:
        """Clear the artist text.

        Args:
            update_canvas (bool, optional): whether to update the canvas after clearing
                the text. Defaults to False.
        """
        self._clear_text(self.artist, update_canvas)

    @on_exception()
    def clear_media_title(self, update_canvas: bool = False) -> None:
        """Clear the media title text.

        Args:
            update_canvas (bool, optional): whether to update the canvas after clearing
                the text. Defaults to False.
        """
        self._clear_text(self.media_title, update_canvas)

    @on_exception()
    def write_artist(
        self, *, clear_first: bool = False, swap_on_vsync: bool = False
    ) -> None:
        """Force the artist to be written to the canvas.

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

    @on_exception()
    def write_artwork_image(self, swap_on_vsync: bool = False) -> None:
        """Write the artwork image to the canvas.

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

    @on_exception()
    def write_media_title(
        self, *, clear_first: bool = False, swap_on_vsync: bool = False
    ) -> None:
        """Force the media title to be written to the canvas.

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
        """Returns the media title content."""
        return self._artist

    @artist.setter
    def artist(self, value: str) -> None:
        """Set the artist text content."""
        if not isinstance(value, str):
            raise TypeError(f"Value for `artist` must be a string: {repr(value)}")

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
        """Returns the current artwork image.

        Returns:
            Image: the current artwork image
        """
        return self._artwork_image

    @artwork_image.setter
    def artwork_image(self, image: ArtworkImage) -> None:
        """Set the current artwork image.

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
    def brightness(self) -> float:
        """Gets the brightness of the display.

        Returns:
            float: the brightness of the display
        """
        return float(self.matrix.brightness)

    @brightness.setter
    def brightness(self, value: int) -> None:
        """Set the brightness of the display.

        Force updates all canvas content to apply the brightness.

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
        """Creates the payload to send to Home Assistant for sensor updates.

        Returns:
            HAPayloadInfo: the payload to send to Home Assistant for sensor updates
        """

        if self.artwork_image == NULL_IMAGE:
            album = None
            album_artwork_url = None
        else:
            album = self.artwork_image.album
            album_artwork_url = self.artwork_image.url

        return {
            "state": any(
                [
                    self.artwork_image != NULL_IMAGE,
                    self.artist.display_content != "",
                    self.media_title.display_content != "",
                ]
            ),
            "media_title": self.media_title.original_content or None,
            "artist": self.artist.original_content or None,
            "album": album,
            "album_artwork_url": album_artwork_url,
        }

    @property
    def media_title(self) -> Text:
        """Returns the media title content."""
        return self._media_title

    @media_title.setter
    def media_title(self, value: str) -> None:
        """Set the media title content."""
        if not isinstance(value, str):
            raise TypeError(f"Value for `media_title` must be a string: {repr(value)}")

        if value == self.media_title.display_content:
            return

        LOGGER.debug("Setting media title to: %s", value)

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
    def pending_ha_updates(self) -> HAPendingUpdatesInfo:
        """Returns a record of any pending attribute updates.

        Returns:
            HAPendingUpdatesInfo: a record of any pending attribute updates
        """
        return self._pending_ha_updates

    @pending_ha_updates.setter
    def pending_ha_updates(self, value: HAPendingUpdatesInfo) -> None:
        """Update the HA pending updates record and then send updates to HA.

        Args:
            value (dict): this must be the entire dict: updating a single value will not
                trigger this setter method and the updates won't be sent to HA
        """
        self._pending_ha_updates = value

        if any(self._pending_ha_updates.values()):
            self._start_update_ha_worker()

            if (
                not self.home_assistant_payload.get("media_title")
                and not self.home_assistant_payload.get("artist")
                and self.artwork_image == NULL_IMAGE
            ):
                LOGGER.info("No content found, clearing matrix")
                self.matrix.Clear()

    @property
    def ha_updates_available(self) -> bool:
        """Checks whether there are any pending HA updates.

        Returns:
            bool: True if any of the pending HA updates are True
        """
        return any(self.pending_ha_updates.values())

    @property
    def scrollable_content(self) -> bool:
        """Returns whether the display has any scrollable content.

        Returns:
            bool: True if there is scrollable content, False otherwise
        """
        return bool(self.media_title.scrollable or self.artist.scrollable)
