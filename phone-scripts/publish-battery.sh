#!/data/data/com.termux/files/usr/bin/bash
BATT=$(termux-battery-status)
mqtt_pub -h 127.0.0.1 -t "home/phone/battery" -m "$BATT"
