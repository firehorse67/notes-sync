#!/usr/bin/env python3
import os
import sys

# Prefer Wayland backend over X11/XWayland.
# On X11, GTK4's frame clock runs at a fixed 60 fps regardless of whether
# anything changed, consuming ~12% CPU at idle. On Wayland the compositor
# drives the frame clock, so idle cost drops to near zero.
# Safe to force: only applies when a Wayland socket is actually present.
if os.environ.get("WAYLAND_DISPLAY"):
    os.environ["GDK_BACKEND"] = "wayland"

from notes_app.main import main

if __name__ == "__main__":
    sys.exit(main())
