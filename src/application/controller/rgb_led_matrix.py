"""Displays track information on an RGB LED Matrix"""
from __future__ import annotations

from json import dumps, loads
from logging import DEBUG, getLogger
from pathlib import Path
from sys import path
from typing import Any

from dotenv import load_dotenv
from paho.mqtt.client import MQTTMessage
from paho.mqtt.publish import single
from wg_utilities.exceptions import on_exception
from wg_utilities.loggers import add_stream_handler

path.append(str(Path(__file__).parents[2]))

# pylint: disable=wrong-import-position
from application.handler.mqtt import (
    HA_FORCE_UPDATE_TOPIC,
    HA_LED_MATRIX_BRIGHTNESS_TOPIC,
    HA_LED_MATRIX_PAYLOAD_TOPIC,
    MQTT_CLIENT,
    MQTT_HOST,
    MQTT_PASSWORD,
    MQTT_USERNAME,
)
from domain.model.artwork_image import NULL_IMAGE, ArtworkImage
from domain.model.led_matrix_now_playing_display import LedMatrixNowPlayingDisplay

load_dotenv()

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)
add_stream_handler(LOGGER)


LED_MATRIX = LedMatrixNowPlayingDisplay()

NONE_VALUES = (
    None,
    "",
    "None",
    "none",
    "null",
)


@on_exception()  # type: ignore[misc]
def handle_display_update_message(message: MQTTMessage) -> None:
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
        # noinspection PyArgumentEqualDefault
        artwork_image = ArtworkImage(
            album=payload.get("album"),
            artist=payload.get("artist"),
            url=album_artwork_url,
            # Pre-caching seems like it should be faster, at least a bit, but I
            # don't think the Pi Zero has enough power to cache the image in a
            # separate thread, so it actually makes it ~2x slower :(
            pre_cache=False,
            pre_cache_size=LED_MATRIX.image_size,
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
                    LED_MATRIX.artist.original_content
                    != (new_artist_content := payload.get("artist"))
                )
            ),
            (
                media_title_change := (
                    LED_MATRIX.media_title.original_content
                    != (new_media_title_content := payload.get("title"))
                )
            ),
            (
                artwork_change := (
                    LED_MATRIX.artwork_image.album != payload.get("album")
                )
            ),
        ]
    ):
        LOGGER.debug(
            "Artist change: %s; Media Title change: %s, Artwork change: %s",
            artist_change,
            media_title_change,
            artwork_change,
        )
        LED_MATRIX.update_display_values(
            new_media_title_content,
            new_artist_content,
            artwork_image,
        )


@on_exception()  # type: ignore[misc]
def on_message(_: Any, __: Any, message: MQTTMessage) -> None:
    """Callback method for updating env vars on MQTT message

    Args:
        message (MQTTMessage): the message object from the MQTT subscription
    """

    if message.topic == HA_LED_MATRIX_PAYLOAD_TOPIC:
        handle_display_update_message(
            message,
        )
    elif message.topic == HA_LED_MATRIX_BRIGHTNESS_TOPIC:
        LED_MATRIX.brightness = int(message.payload.decode())


@on_exception()  # type: ignore[misc]
def main() -> None:
    """Connect and subscribe the MQTT client and initialize the display"""

    MQTT_CLIENT.subscribe(HA_LED_MATRIX_PAYLOAD_TOPIC)

    MQTT_CLIENT.on_message = on_message

    MQTT_CLIENT.loop_start()
    single(
        topic=HA_FORCE_UPDATE_TOPIC,
        payload=True,
        auth={"username": MQTT_USERNAME, "password": MQTT_PASSWORD},
        hostname=MQTT_HOST,
    )
    LED_MATRIX.start_loop()


if __name__ == "__main__":
    main()
