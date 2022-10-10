#!/bin/bash

systemctl stop rgb_led_matrix.service || :
cp rgb_led_matrix.service /etc/systemd/system/
echo "Service file copied to /etc/systemd/system/rgb_led_matrix.service"
systemctl reenable rgb_led_matrix.service
systemctl start rgb_led_matrix.service
