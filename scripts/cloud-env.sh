#!/bin/sh
# Execute a command with the cloud's locally installed runtime.
set -eu
project_root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
tools_root=${GNOME_WP_TOOLS:-/workspace/toolchains}
if [ -d "$tools_root/gtk/usr" ]; then
    export LD_LIBRARY_PATH="$tools_root/gtk/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    export GI_TYPELIB_PATH="$tools_root/gtk/usr/lib/x86_64-linux-gnu/girepository-1.0${GI_TYPELIB_PATH:+:$GI_TYPELIB_PATH}"
    export XDG_DATA_DIRS="$tools_root/gtk/usr/share:${XDG_DATA_DIRS:-/usr/local/share:/usr/share}"
    export GNOME_WP_GI_PATH="$tools_root/gtk/usr/lib/python3/dist-packages/gi"
    # The rootless cloud namespace keeps the host home read-only.
    export GNOME_WP_SETTINGS_FILE="${GNOME_WP_SETTINGS_FILE:-$project_root/.runtime/interface.json}"
fi
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-$project_root/.runtime/cache}"
mkdir -p "$XDG_CACHE_HOME"
exec "$@"
