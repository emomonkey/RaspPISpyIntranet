#!/bin/bash
echo 17 > /sys/class/gpio/export
sudo sh -c "echo in > /sys/class/gpio/gpio17/direction"
