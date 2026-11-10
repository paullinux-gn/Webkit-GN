#!/bin/sh
# Run inside scripts/webkit-env.sh with an available DISPLAY and X11 test tools.
set -eu
[ -n "${DISPLAY:-}" ] || { echo "Set DISPLAY to a disposable X11/Xvfb display." >&2; exit 1; }
cd "$(dirname "$0")/.."
mkdir -p .runtime/native
failed=0
for test_file in webkit/tests/gui_*.py; do
    name=$(basename "$test_file" .py)
    if timeout 120 dbus-run-session -- /usr/bin/python3 -u "$test_file" > ".runtime/native/$name.out" 2> ".runtime/native/$name.log"; then
        echo "PASS $name"
    else
        echo "FAIL $name (see .runtime/native/$name.log)"
        failed=$((failed+1))
    fi
done
[ "$failed" -eq 0 ]
