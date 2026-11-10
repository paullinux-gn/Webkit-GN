#!/bin/sh
set -eu
cd "$(dirname "$0")"
exec ./scripts/webkit-env.sh /usr/bin/python3 webkit/app.py "$@"
