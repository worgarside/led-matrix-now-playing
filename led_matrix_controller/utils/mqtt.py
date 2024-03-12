"""Module for holding the main controller function(s) for controlling the GUI."""

from __future__ import annotations

from logging import DEBUG, getLogger
from os import environ
from random import uniform
from sys import exit as sys_exit
from time import sleep

from paho.mqtt.client import Client
from wg_utilities.loggers import add_stream_handler

from .const import MQTT_HOST, MQTT_PASSWORD, MQTT_USERNAME

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)
add_stream_handler(LOGGER)


MQTT_CLIENT = Client()
MQTT_CLIENT.username_pw_set(username=MQTT_USERNAME, password=MQTT_PASSWORD)


def on_connect(
    client: Client, userdata: dict[str, object], flags: dict[str, object], rc: int
) -> None:
    """Log successful connection to MQTT broker.

    Called when the broker responds to the connection request.

    Args:
        client (Client): the client instance for this callback
        userdata (dict): the private user data as set in Client() or userdata_set()
        flags (dict): response flags sent by the broker
        rc (int): the connection result
    """
    _ = client, userdata, flags, rc
    LOGGER.debug("MQTT Client connected")


def on_disconnect(client: Client, userdata: dict[str, object], rc: int) -> None:
    """Reconnect to MQTT broker if disconnected.

    Called when the client disconnects from the broker.

    Args:
        client (Client): the client instance for this callback
        userdata (dict): the private user data as set in Client() or userdata_set()
        rc (int): the connection result
    """
    _ = client, userdata, rc

    LOGGER.debug("MQTT Client disconnected")
    try:
        for i in range(5):
            MQTT_CLIENT.connect(MQTT_HOST)
            if MQTT_CLIENT.is_connected():
                break
            LOGGER.error("MQTT Client failed to connect, retrying...")
            sleep(i * (1 + uniform(0, 1)))  # noqa: S311
        else:
            raise ConnectionError("MQTT Client failed to connect")  # noqa: TRY301
    except ConnectionError:
        # The above doesn't seem to cause a non-zero exit code, so we'll do it manually
        sys_exit(1)


MQTT_CLIENT.on_connect = on_connect  # type: ignore[assignment]
MQTT_CLIENT.on_disconnect = on_disconnect

if environ["MQTT_USERNAME"] != "test":
    MQTT_CLIENT.connect(MQTT_HOST)
