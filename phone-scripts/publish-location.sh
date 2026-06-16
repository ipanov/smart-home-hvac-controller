#!/data/data/com.termux/files/usr/bin/bash
LOC=$(termux-location)
LAT=$(echo "$LOC" | jq .latitude)
LON=$(echo "$LOC" | jq .longitude)
mqtt_pub -h 127.0.0.1 -t "home/phone/location" -m "{\"lat\":$LAT,\"lon\":$LON}"
