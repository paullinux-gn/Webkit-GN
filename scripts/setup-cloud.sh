#!/bin/sh
# Rootless setup for the selected Debian 13 amd64 cloud image.
# Network commands retain the inherited proxy and certificate verification.
set -eu
project_root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
tools_root=${GNOME_WP_TOOLS:-/workspace/toolchains}
mkdir -p "$tools_root/apt/lists/partial" "$tools_root/apt/cache/archives/partial" "$tools_root/gtk"
cat > "$tools_root/apt/sources.list" <<'EOF'
deb https://deb.debian.org/debian trixie main
deb https://deb.debian.org/debian-security trixie-security main
EOF
apt_local() {
    /usr/bin/apt-get -o Debug::NoLocking=true \
        -o "Dir::Etc::sourcelist=$tools_root/apt/sources.list" -o Dir::Etc::sourceparts=- \
        -o "Dir::State::lists=$tools_root/apt/lists" -o "Dir::Cache=$tools_root/apt/cache" \
        -o "Acquire::https::Proxy=${HTTPS_PROXY:-}" "$@"
}
apt_local update
apt_local --download-only -y install gir1.2-gtk-4.0 gir1.2-adw-1 gir1.2-webkit-6.0 python3-gi-cairo poppler-utils xvfb xauth fonts-dejavu-core
for package in "$tools_root"/apt/cache/archives/*.deb; do
    dpkg-deb -x "$package" "$tools_root/gtk"
done
glib-compile-schemas "$tools_root/gtk/usr/share/glib-2.0/schemas"
cd "$project_root"
cd webkit
npm ci --cache "$tools_root/npm-cache" --no-audit --no-fund
npm test
npm run build
cd "$project_root"
"$project_root/scripts/cloud-env.sh" /usr/bin/python3 -c 'import gi; gi.require_version("Gtk", "4.0"); gi.require_version("Adw", "1"); gi.require_version("WebKit", "6.0"); from gi.repository import Gtk, Adw, WebKit; print("GTK", Gtk.get_major_version(), Gtk.get_minor_version(), "libadwaita", Adw.get_major_version(), Adw.get_minor_version(), "WebKit", WebKit.get_major_version(), WebKit.get_minor_version())'
/usr/bin/python3 -m unittest discover -s webkit/tests -v
