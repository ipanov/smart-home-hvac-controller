#!/data/data/com.termux/files/usr/bin/bash
set -e
cd /data/data/com.termux/files/home/home-automation
export DOCKER_HOST=unix:///data/data/com.termux/files/usr/var/run/docker.sock
docker compose up -d
