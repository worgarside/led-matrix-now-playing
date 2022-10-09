"""Displays track information on an RGB LED Matrix"""
from __future__ import annotations

from logging import DEBUG, getLogger
from pathlib import Path
from sys import path

from dotenv import load_dotenv
from paho.mqtt.publish import single
from wg_utilities.loggers import add_stream_handler

path.append(str(Path(__file__).parents[2]))

# pylint: disable=wrong-import-position
from application.handler.mqtt import (
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


def main() -> None:
    """Connect and subscribe the MQTT client and initialize the display"""

    MQTT_CLIENT.subscribe(HA_LED_MATRIX_PAYLOAD_TOPIC)

    led_matrix = LedMatrixNowPlayingDisplay()
    MQTT_CLIENT.on_message = led_matrix.handle_mqtt_message

    MQTT_CLIENT.loop_start()
    single(
        topic="/home-assistant/script/crt_pi_update_display/run",
        payload=True,
        auth={"username": MQTT_USERNAME, "password": MQTT_PASSWORD},
        hostname=MQTT_HOST,
    )
    led_matrix.start_loop()


if __name__ == "__main__":
    main()
