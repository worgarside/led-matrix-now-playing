#!/bin/bash

systemctl stop artwork_cache.service || :
cp artwork_cache.service /etc/systemd/system/
echo "Service file copied to /etc/systemd/system/artwork_cache.service"
systemctl reenable artwork_cache.service
systemctl start artwork_cache.service

systemctl stop rgb_led_matrix.service || :
cp rgb_led_matrix.service /etc/systemd/system/
echo "Service file copied to /etc/systemd/system/rgb_led_matrix.service"
systemctl reenable rgb_led_matrix.service
systemctl start rgb_led_matrix.service
