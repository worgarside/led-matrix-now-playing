"""
This is a separate service to download and cache the artwork images. This has been
split into a second service because I kept getting permissions issues when trying to
create files or directories within the `rgb_led_matrix` controller, due to the need to
run it as sudo. This service is run as the `pi` user and has the correct permissions.
"""
from json import dumps, loads
from logging import DEBUG, getLogger
from pathlib import Path
from sys import path

from paho.mqtt.client import Client, MQTTMessage
from wg_utilities.loggers import add_stream_handler

path.append(str(Path(__file__).parents[2]))

# pylint: disable=wrong-import-position
from application.handler.mqtt import HA_LED_MATRIX_ARTWORK_CACHE_TOPIC, MQTT_CLIENT
from domain.model.artwork_image import ArtworkImage

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)
add_stream_handler(LOGGER)


def on_message(_: Client, __: dict[str, object], message: MQTTMessage) -> None:
    """Downloads the artwork from the payload for the display service to use

    Args:
        message: an instance of MQTTMessage.
        This is a class with members topic, payload, qos, retain.
    """
    payload = loads(message.payload.decode())

    LOGGER.debug(dumps(payload))

    ArtworkImage(
        album=payload.get("album"),
        artist=payload.get("artist"),
        url=payload.get("album_artwork_url"),
    ).download()


def main() -> None:
    """Connect and subscribe the MQTT client"""
    MQTT_CLIENT.on_message = on_message
    MQTT_CLIENT.subscribe(HA_LED_MATRIX_ARTWORK_CACHE_TOPIC)

    MQTT_CLIENT.loop_forever()


if __name__ == "__main__":
    main()
