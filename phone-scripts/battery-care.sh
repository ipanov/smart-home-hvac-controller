#!/system/bin/sh
# Intended to run as root every minute via crond
CAP=$(cat /sys/class/power_supply/battery/capacity 2>/dev/null)
if [ -z "$CAP" ]; then
    echo "ERROR: cannot read battery capacity" >&2
    exit 1
fi
NODE=/sys/class/power_supply/battery/batt_slate_mode
if [ -w "$NODE" ]; then
    if [ "$CAP" -ge 80 ]; then
        echo 1 > "$NODE"
    elif [ "$CAP" -le 20 ]; then
        echo 0 > "$NODE"
    fi
else
    echo "WARNING: $NODE not writable, use relay fallback" >&2
    exit 2
fi
