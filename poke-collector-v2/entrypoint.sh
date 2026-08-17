#!/bin/sh
set -e

PUID="${PUID:-1000}"
PGID="${PGID:-1000}"

if [ "$(id -u appuser)" != "$PUID" ]; then
    usermod -o -u "$PUID" appuser
fi
if [ "$(id -g appuser)" != "$PGID" ]; then
    groupmod -o -g "$PGID" appuser
fi

mkdir -p /app/data/db /app/data/catalog
chown -R appuser:appuser /app/data

exec setpriv --reuid="$PUID" --regid="$PGID" --init-groups "$@"
