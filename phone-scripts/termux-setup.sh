#!/data/data/com.termux/files/usr/bin/bash
set -e
pkg update && pkg upgrade -y
pkg install -y root-repo docker termux-api termux-services jq mosquitto
mkdir -p $HOME/docker-data
mkdir -p $HOME/.termux/boot
mkdir -p /data/data/com.termux/files/usr/etc/docker
cat > /data/data/com.termux/files/usr/etc/docker/daemon.json <<EOF
{
  "data-root": "$HOME/docker-data"
}
EOF
sv-enable docker || true
nohup dockerd --host=unix:///data/data/com.termux/files/usr/var/run/docker.sock > $HOME/docker.log 2>&1 &
sleep 5
mkdir -p $HOME/home-automation/mosquitto/config
cat > $HOME/home-automation/mosquitto/config/mosquitto.conf <<'EOF'
listener 1883
allow_anonymous true
EOF
