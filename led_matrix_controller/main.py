"""Displays track information on an RGB LED Matrix."""

from __future__ import annotations

from json import dumps, loads
from logging import DEBUG, getLogger
from typing import TYPE_CHECKING, Any

from paho.mqtt.publish import single
from wg_utilities.loggers import add_stream_handler

from led_matrix_controller.models import NULL_IMAGE, ArtworkImage, Matrix
from led_matrix_controller.utils import MQTT_CLIENT, const

if TYPE_CHECKING:
    from paho.mqtt.client import MQTTMessage


LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)
add_stream_handler(LOGGER)


LED_MATRIX = Matrix()

NONE_VALUES = (
    None,
    "",
    "None",
    "none",
    "null",
)


def handle_display_update_message(message: MQTTMessage) -> None:
    """Handle an MQTT message.

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
        LOGGER.debug("No album artwork URL found in payload, defaulting to `NULL_IMAGE`")
        artwork_image = NULL_IMAGE

    # Needs to be an `or` because None is valid as a value
    LED_MATRIX.artist = payload.get("artist") or ""  # type: ignore[assignment]
    LED_MATRIX.media_title = payload.get("title") or ""  # type: ignore[assignment]

    LED_MATRIX.artwork_image = artwork_image


def on_message(_: Any, __: Any, message: MQTTMessage) -> None:
    """Handle an MQTT message.

    Args:
        message (MQTTMessage): the message object from the MQTT subscription
    """

    if message.topic == const.HA_LED_MATRIX_PAYLOAD_TOPIC:
        handle_display_update_message(
            message,
        )
    elif message.topic == const.HA_LED_MATRIX_BRIGHTNESS_TOPIC:
        LOGGER.debug("Received brightness update: %s", message.payload.decode())
        LED_MATRIX.brightness = int(message.payload.decode())
    else:
        LOGGER.warning(
            "Unknown topic: %s. Payload: %s", repr(message.topic), repr(message.payload)
        )


def main() -> None:
    """Connect and subscribe the MQTT client and initialize the display."""

    MQTT_CLIENT.subscribe(const.HA_LED_MATRIX_PAYLOAD_TOPIC)
    MQTT_CLIENT.subscribe(const.HA_LED_MATRIX_BRIGHTNESS_TOPIC)
    MQTT_CLIENT.on_message = on_message

    single(
        topic=const.HA_FORCE_UPDATE_TOPIC,
        payload=True,
        auth={"username": const.MQTT_USERNAME, "password": const.MQTT_PASSWORD},
        hostname=const.MQTT_HOST,
    )
    MQTT_CLIENT.loop_forever()


if __name__ == "__main__":
    main()
