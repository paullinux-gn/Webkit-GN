#!/bin/sh
# Build a local, single-file Flatpak bundle using the checked-in JS bundle.
set -eu
install_bundle=false
case "${1:-}" in
    --help|-h) echo "Usage: $0 [--install]"; exit 0 ;;
    --install) install_bundle=true ;;
    '') ;;
    *) echo "Usage: $0 [--install]" >&2; exit 2 ;;
esac
[ "$#" -le 1 ] || { echo "Too many arguments" >&2; exit 2; }
for tool in flatpak flatpak-builder; do
    command -v "$tool" >/dev/null 2>&1 || { echo "Install $tool first (Arch/CachyOS: sudo pacman -S flatpak flatpak-builder)." >&2; exit 127; }
done
cd "$(dirname "$0")/.."
app_id=io.github.paullinux_gn.WebkitGN
flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
flatpak-builder --user --assumeyes --install-deps-from=flathub --force-clean --repo=.flatpak-repo .flatpak-build "flatpak/$app_id.json"
mkdir -p dist
flatpak build-bundle --runtime-repo=https://dl.flathub.org/repo/flathub.flatpakrepo .flatpak-repo dist/Webkit-GN.flatpak "$app_id" stable
if "$install_bundle"; then flatpak install --user --reinstall -y dist/Webkit-GN.flatpak; fi
echo "Created dist/Webkit-GN.flatpak"
