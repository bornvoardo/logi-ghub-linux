"""Desktop notifications, through the freedesktop notification service.

Small on purpose: everything that wants to tell the user something uses this, so
the icon and the application name stay the same wherever the message comes from.
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)

APP_NAME = "Logitech G devices"


def notify(title: str, body: str = "", icon: str = "input-gaming", replaces: int = 0,
           expire_ms: int = 3000) -> int:
    """Show a desktop notification and return the id the service assigned.

    Failures are logged and ignored: a missing notification daemon must never stop
    a profile switch. ``replaces`` is an earlier id to overwrite, ``expire_ms`` how
    long the message stays (a negative value leaves it until dismissed).
    """
    try:
        import gi

        gi.require_version("Gio", "2.0")
        from gi.repository import Gio, GLib
    except (ImportError, ValueError) as e:  # pragma: no cover - depends on the host
        log.info("no notification support: %s", e)
        return 0
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        reply = bus.call_sync(
            "org.freedesktop.Notifications",
            "/org/freedesktop/Notifications",
            "org.freedesktop.Notifications",
            "Notify",
            GLib.Variant("(susssasa{sv}i)", (APP_NAME, replaces, icon, title, body, [], {}, expire_ms)),
            GLib.VariantType.new("(u)"), Gio.DBusCallFlags.NONE, 2000, None)
        return int(reply.unpack()[0])
    except GLib.Error as e:  # pragma: no cover - depends on the host
        log.info("notification failed: %s", e.message)
        return 0
