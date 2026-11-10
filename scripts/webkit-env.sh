#!/bin/sh
set -eu
project_root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
tools_root=${GNOME_WP_TOOLS:-/workspace/toolchains}
if [ ! -x /usr/lib/x86_64-linux-gnu/webkitgtk-6.0/WebKitNetworkProcess ] &&
   [ -x "$tools_root/gtk/usr/lib/x86_64-linux-gnu/webkitgtk-6.0/WebKitNetworkProcess" ]; then
    exec "$project_root/scripts/cloud-env.sh" /usr/bin/python3 "$project_root/scripts/webkit-namespace.py" "$@"
fi
exec "$project_root/scripts/cloud-env.sh" "$@"
