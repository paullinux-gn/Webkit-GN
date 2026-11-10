#!/usr/bin/env python3
"""Map rootless Debian WebKit libraries to their compiled paths in a private mount namespace.

No host files or sandbox settings are changed. WebKit's own child sandbox remains enabled.
Only needed in the selected cloud image; desktop installations use system packages.
"""
import os
from pathlib import Path
import subprocess
import sys
import shutil

tools = Path(os.environ.get("GNOME_WP_TOOLS", "/workspace/toolchains"))
local = tools/"gtk/usr/lib/x86_64-linux-gnu"
host = Path("/usr/lib/x86_64-linux-gnu")
mapping = tools/"webkit-library-map"
if mapping.exists():
    shutil.rmtree(mapping)
def merge(destination, relative=Path()):
    destination.mkdir()
    host_dir, local_dir = host/relative, local/relative
    names = {p.name for p in host_dir.iterdir()} if host_dir.is_dir() else set()
    if local_dir.is_dir():
        names.update(p.name for p in local_dir.iterdir())
    for name in names:
        item = relative/name
        if any(path.is_dir() and not path.is_symlink() for path in (host/item,local/item)):
            merge(destination/name,item)
        else:
            source = "gnome-wp-local-libraries" if (local/item).exists() or (local/item).is_symlink() else "gnome-wp-host-libraries"
            (destination/name).symlink_to("/usr/lib/"+source+"/"+str(item))
merge(mapping)
binary_mapping = tools/"webkit-binary-map"
if binary_mapping.exists():
    shutil.rmtree(binary_mapping)
binary_mapping.mkdir()
for source, prefix in ((Path("/usr/bin"), "/usr/lib/gnome-wp-host-bin"),
                       (tools/"gtk/usr/bin", "/usr/lib/gnome-wp-local-bin")):
    for entry in source.iterdir():
        destination=binary_mapping/entry.name
        if destination.is_symlink():
            destination.unlink()
        if not destination.exists():
            destination.symlink_to(prefix+"/"+entry.name)
# WebKit bind-mounts this helper into its own sandbox: its destination must be
# a regular file, not a symlink. Copy only this small packaged executable.
proxy=binary_mapping/"xdg-dbus-proxy"
if proxy.is_symlink():proxy.unlink()
shutil.copy2(tools/"gtk/usr/bin/xdg-dbus-proxy",proxy)
arguments = ["bwrap", "--ro-bind", "/", "/", "--bind", "/workspace", "/workspace",
             "--bind", "/tmp", "/tmp", "--dev-bind", "/dev", "/dev", "--proc", "/proc",
             "--tmpfs", "/usr/lib"]
for entry in Path("/usr/lib").iterdir():
    if entry.name not in ("x86_64-linux-gnu", "gnome-wp-host-libraries", "gnome-wp-local-libraries"):
        arguments += ["--ro-bind", str(entry), str(entry)]
arguments += ["--ro-bind", str(host), "/usr/lib/gnome-wp-host-libraries",
              "--ro-bind", str(local), "/usr/lib/gnome-wp-local-libraries",
              "--ro-bind", "/usr/bin", "/usr/lib/gnome-wp-host-bin",
              "--ro-bind", str(tools/"gtk/usr/bin"), "/usr/lib/gnome-wp-local-bin",
              "--ro-bind", str(mapping), str(host),
              "--ro-bind", str(binary_mapping), "/usr/bin", "--", *sys.argv[1:]]
raise SystemExit(subprocess.call(arguments))
