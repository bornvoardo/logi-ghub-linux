"""Desktop notifications, through the freedesktop notification service.

Small on purpose: everything that wants to tell the user something uses this, so
the icon and the application name stay the same wherever the message comes from.
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)

APP_NAME = "Logitech G devices"
# Must match the installed .desktop file name, or the desktop cannot tie the
# notification to this app and will not offer to configure it.
DESKTOP_ENTRY = "io.github.theo_antonescu.LogiGhubLinux"


def notify(title: str, body: str = "", icon: str = "input-gaming", replaces: int = 0,
           expire_ms: int = 3000, silent: bool = False) -> int:
    """Show a desktop notification and return the id the service assigned.

    Failures are logged and ignored: a missing notification daemon must never stop
    a profile switch. ``replaces`` is an earlier id to overwrite, ``expire_ms`` how
    long the message stays (a negative value leaves it until dismissed).

    ``silent`` asks for no sound (the freedesktop ``suppress-sound`` hint).

    Every message is marked transient, so a profile switch is announced once and
    does not pile up in the notification history. KDE reads ``transient`` as
    TransientRole, "should not be kept in history" (Plasma 5.22 and later), and
    treats a message that carries ``desktop-entry`` as configurable — without that
    hint it would not be stored either, so both hints are sent together.
    """
    try:
        import gi

        gi.require_version("Gio", "2.0")
        from gi.repository import Gio, GLib
    except (ImportError, ValueError) as e:  # pragma: no cover - depends on the host
        log.info("no notification support: %s", e)
        return 0
    hints = {
        # Never kept in the notification history.
        "transient": GLib.Variant("b", True),
        # Lets the desktop file the notification under this app, so a user who
        # wants it can configure it; KDE only stores configurable messages.
        "desktop-entry": GLib.Variant("s", DESKTOP_ENTRY),
    }
    if silent:
        hints["suppress-sound"] = GLib.Variant("b", True)
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        reply = bus.call_sync(
            "org.freedesktop.Notifications",
            "/org/freedesktop/Notifications",
            "org.freedesktop.Notifications",
            "Notify",
            GLib.Variant("(susssasa{sv}i)", (APP_NAME, replaces, icon, title, body, [], hints, expire_ms)),
            GLib.VariantType.new("(u)"), Gio.DBusCallFlags.NONE, 2000, None)
        return int(reply.unpack()[0])
    except GLib.Error as e:  # pragma: no cover - depends on the host
        log.info("notification failed: %s", e.message)
        return 0
