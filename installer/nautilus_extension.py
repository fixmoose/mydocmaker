# Nautilus extension for MyDocMaker (v1.16+).
#
# Adds a top-level right-click entry "Add to MyDocMaker" in GNOME
# Files (Nautilus) for selected files. Unlike "Open With", this appears
# as its own entry — no submenu navigation needed.
#
# Behavior: shells out to `mydocmaker <selected files...>`.
# The existing single-instance IPC inside the main app does the rest:
#   • If the app is already running → files are appended to the open
#     window and the window is raised.
#   • If the app is not running → it launches with those files queued.
#
# Installed by the .deb to:
#   /usr/share/nautilus-python/extensions/mydocmaker.py
#
# Requires the `python3-nautilus` package, which the .deb declares as a
# Recommends so apt usually installs it alongside. If absent, the
# extension simply doesn't load — no error visible to the user, and
# the rest of the app still works.

import os
import subprocess

try:
    import gi
    gi.require_version("Nautilus", "3.0")
    from gi.repository import Nautilus, GObject
except Exception:
    # gi or Nautilus typelib missing — extension won't load, which is
    # the right behavior. The main app keeps working.
    raise

# File extensions the app actually accepts (mirror of ALL_SUPPORTED in
# mydocmaker.py). Kept here to avoid importing the main app at
# extension-load time (Nautilus would block on slow imports).
_ACCEPTED_EXTS = {
    # Images
    ".png", ".jpg", ".jpeg", ".jpe", ".bmp", ".gif", ".tiff", ".tif",
    ".webp", ".ico", ".ppm", ".pgm", ".pbm", ".pnm", ".tga", ".dds",
    ".heic", ".heif", ".hif", ".avif",
    # PDFs + text + Office
    ".pdf",
    ".txt", ".md", ".csv", ".log", ".py", ".js", ".ts", ".html", ".htm",
    ".css", ".json", ".xml", ".yaml", ".yml", ".ini", ".cfg", ".sh",
    ".doc", ".docx", ".odt", ".rtf", ".xls", ".xlsx", ".ods",
    ".ppt", ".pptx", ".odp",
}

_LAUNCHER = "mydocmaker"


def _file_paths(files):
    """Extract local POSIX paths from Nautilus.FileInfo objects."""
    paths = []
    for f in files:
        try:
            loc = f.get_location()
            if loc is None:
                continue
            p = loc.get_path()
            if p:
                paths.append(p)
        except Exception:
            continue
    return paths


def _has_supported(files):
    """True if at least one selected entry is a supported file or a
    directory (we recurse directories at add-time inside the app)."""
    for f in files:
        try:
            if f.is_directory():
                return True
            name = f.get_name() or ""
            ext = os.path.splitext(name)[1].lower()
            if ext in _ACCEPTED_EXTS:
                return True
        except Exception:
            continue
    return False


class DDPdfMenuProvider(GObject.GObject, Nautilus.MenuProvider):
    def get_file_items(self, *args):
        # Nautilus 3.x: (window, files). Nautilus 43+: just (files,).
        # Take the last arg either way — it's always the selection.
        files = args[-1]
        if not files or not _has_supported(files):
            return []
        item = Nautilus.MenuItem(
            name="DDPdfCreator::AddToList",
            label="Add to MyDocMaker",
            tip="Append these files to MyDocMaker (opens it if not running)",
            # icon: freedesktop icon name — Nautilus looks it up in the
            # user's icon theme. We ship 256+512 PNGs under
            # /usr/share/icons/hicolor/.../apps/mydocmaker.png
            # via the .deb postinst, so this resolves to our red MyDocMaker
            # circle in the right-click menu.
            icon="mydocmaker",
        )
        item.connect("activate", self._on_activate, files)
        return [item]

    # Older Nautilus also asks for background-area items (right-click in
    # empty space) — we have nothing useful to add there, but the method
    # is expected to exist on the provider.
    def get_background_items(self, *args):
        return []

    def _on_activate(self, _menu, files):
        paths = _file_paths(files)
        if not paths:
            return
        try:
            # Detach via Popen so Nautilus isn't blocked by our process.
            subprocess.Popen(
                [_LAUNCHER, *paths],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            # If the launcher isn't on PATH, the menu entry effectively
            # becomes a no-op — better than a crash dialog from Nautilus.
            pass
