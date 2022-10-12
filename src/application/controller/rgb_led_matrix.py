"""Displays track information on an RGB LED Matrix"""
from __future__ import annotations

from logging import DEBUG, getLogger
from pathlib import Path
from sys import path
from typing import Any

from dotenv import load_dotenv
from paho.mqtt.client import MQTTMessage
from paho.mqtt.publish import single
from wg_utilities.loggers import add_stream_handler

path.append(str(Path(__file__).parents[2]))

# pylint: disable=wrong-import-position
from application.handler.mqtt import (
    HA_LED_MATRIX_BRIGHTNESS_TOPIC,
    HA_LED_MATRIX_PAYLOAD_TOPIC,
    MQTT_CLIENT,
    MQTT_HOST,
    MQTT_PASSWORD,
    MQTT_USERNAME,
)
from domain.model.led_matrix_now_playing_display import LedMatrixNowPlayingDisplay

load_dotenv()

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)
add_stream_handler(LOGGER)


LED_MATRIX = LedMatrixNowPlayingDisplay()


def on_message(_: Any, __: Any, message: MQTTMessage) -> None:
    """Callback method for updating env vars on MQTT message

    Args:
        message (MQTTMessage): the message object from the MQTT subscription
    """

    if message.topic == HA_LED_MATRIX_PAYLOAD_TOPIC:
        LED_MATRIX.handle_mqtt_message(message)
    elif message.topic == HA_LED_MATRIX_BRIGHTNESS_TOPIC:
        LED_MATRIX.brightness = int(message.payload.decode())


def main() -> None:
    """Connect and subscribe the MQTT client and initialize the display"""

    MQTT_CLIENT.subscribe(HA_LED_MATRIX_PAYLOAD_TOPIC)

    MQTT_CLIENT.on_message = on_message

    MQTT_CLIENT.loop_start()
    single(
        topic="/home-assistant/script/crt_pi_update_display/run",
        payload=True,
        auth={"username": MQTT_USERNAME, "password": MQTT_PASSWORD},
        hostname=MQTT_HOST,
    )
    LED_MATRIX.start_loop()


if __name__ == "__main__":
    main()
