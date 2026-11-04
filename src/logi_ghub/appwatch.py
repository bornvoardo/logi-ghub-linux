"""Per-application profiles: switch a device's profile when a window gets focus.

The pattern is the one logitune and gamerat use on KDE, and it exists because of a
Wayland limitation: a normal program cannot see which window has focus. KWin knows,
but only its own scripts may read that. So:

* a small KWin script (``data/kwin/logi-ghub-focus.js``) listens to
  ``workspace.windowActivated`` and calls a D-Bus method with the window's class,
  caption and .desktop name,
* this module owns that D-Bus service, matches the app against the rules, and
  writes the resulting profile into ``active.json``,
* the daemon already watches that file, so it applies the profile within a second.

KWin scripts cannot register D-Bus services of their own, which is why the service
lives here and the script only calls it.

The window's ``resourceClass`` is not always the name a .desktop file has (Zoom
reports ``zoom`` but installs ``us.zoom.Zoom.desktop``), so the class goes through
the same resolution chain logitune uses: the .desktop name KWin reports, then a
lookup in the .desktop directories, then the class itself.
"""

from __future__ import annotations

import configparser
import fnmatch
import json
import logging
import os
import shutil
import subprocess
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

SERVICE = "org.logi_ghub.Focus"
OBJECT = "/Focus"
INTERFACE = "org.logi_ghub.Focus"

# Shells and launchers take focus for a moment and then hand it back. Switching on
# them would flap the profile every time the launcher opens.
IGNORED = {
    "plasmashell", "org.kde.plasmashell", "kwin_wayland", "kwin_x11",
    "org.kde.krunner", "krunner", "gnome-shell", "org.gnome.shell",
    "org.gnome.shell.extensions", "org.kde.plasma-desktop",
}

# Where .desktop files live, in the order logitune searches them.
DESKTOP_DIRS = (
    "/usr/share/applications",
    "/usr/local/share/applications",
    "/var/lib/flatpak/exports/share/applications",
    "/var/lib/snapd/desktop/applications",
    str(Path.home() / ".local" / "share" / "applications"),
    str(Path.home() / ".local" / "share" / "flatpak" / "exports" / "share" / "applications"),
)

SERVICE_XML = f"""
<node>
  <interface name="{INTERFACE}">
    <method name="focusChanged">
      <arg type="s" direction="in" name="resourceClass"/>
      <arg type="s" direction="in" name="caption"/>
      <arg type="s" direction="in" name="desktopFileName"/>
    </method>
    <method name="focusLost"/>
    <method name="windowsReported">
      <arg type="s" direction="in" name="windows"/>
    </method>
  </interface>
</node>
"""


# -- rules ---------------------------------------------------------------------

@dataclass
class Rule:
    """One window-to-profile binding.

    ``match`` is a shell-style pattern (``steam_app_*``, ``firefox``). ``device``
    limits the rule to one model key; leaving it None applies it to every device
    that has a profile of that name. ``title`` narrows a match further and is off
    by default: captions change with the document and the menu, so they make poor
    triggers.
    """

    match: str
    profile: str
    device: str | None = None
    title: str | None = None
    # A name to show instead of the window class. The class is long and cryptic
    # ("org.kde.konsole", "steam_app_5335510"), so a rule can carry its own label
    # for the notification and the app. Empty means "use the window class".
    label: str | None = None
    # Whether this rule announces the switch. A rule that flips between two
    # profiles on a window you alt-tab through all day is the one case where the
    # message is noise, so it can be turned off per rule.
    notify: bool = True
    # No sound with the notification, but still shown. On by default: a profile
    # switch is a small piece of state, not an alarm.
    silent: bool = True

    def display_name(self, app_id: str) -> str:
        """What the notification and the app call this rule."""
        return (self.label or "").strip() or app_id

    def matches(self, app_id: str, caption: str) -> bool:
        if not fnmatch.fnmatchcase(app_id.lower(), self.match.lower()):
            return False
        if self.title and self.title.lower() not in (caption or "").lower():
            return False
        return True


@dataclass
class AppRules:
    """The rule file: rules in order, plus the profile each device falls back to."""

    rules: list[Rule] = field(default_factory=list)
    defaults: dict[str, str] = field(default_factory=dict)
    enabled: bool = True

    # -- disk ------------------------------------------------------------------
    @classmethod
    def load(cls, path: Path | None = None) -> "AppRules":
        path = path or rules_path()
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            return cls()
        rules = []
        for entry in data.get("rules") or []:
            try:
                rules.append(Rule(
                    match=str(entry["match"]),
                    profile=str(entry["profile"]),
                    device=(str(entry["device"]) if entry.get("device") else None),
                    title=(str(entry["title"]) if entry.get("title") else None),
                    label=(str(entry["label"]) if entry.get("label") else None),
                    # Old files have no such keys; a rule that never mentioned
                    # notifications should behave like the default one.
                    notify=bool(entry.get("notify", True)),
                    silent=bool(entry.get("silent", True)),
                ))
            except (KeyError, TypeError):
                log.warning("skipping a malformed rule: %r", entry)
        defaults = {str(k): str(v) for k, v in (data.get("defaults") or {}).items()}
        return cls(rules, defaults, bool(data.get("enabled", True)))

    def save(self, path: Path | None = None) -> Path:
        path = path or rules_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        body = {"enabled": self.enabled, "rules": [asdict(r) for r in self.rules], "defaults": dict(self.defaults)}
        path.write_text(json.dumps(body, indent=2) + "\n")
        return path

    # -- decisions -------------------------------------------------------------
    def profile_for(self, device: str, app_id: str, caption: str) -> str | None:
        """The profile this window should give ``device``, or None to leave it alone."""
        rule = self.rule_for(device, app_id, caption)
        if rule is not None:
            return rule.profile
        return self.defaults.get(device)

    def rule_for(self, device: str, app_id: str, caption: str) -> "Rule | None":
        """The rule that answers for this window, so its label can be shown."""
        for rule in self.rules:
            if rule.device not in (None, device):
                continue
            if rule.matches(app_id, caption):
                return rule
        return None

    def devices(self) -> set[str]:
        out = set(self.defaults)
        out.update(r.device for r in self.rules if r.device)
        return out

    # -- editing ---------------------------------------------------------------
    def add(self, match: str, profile: str, device: str | None = None, title: str | None = None,
            label: str | None = None, notify: bool = True, silent: bool = True) -> Rule:
        """Add a rule, or replace one with the same pattern in the same place.

        Rules are matched in order and the first match wins, so re-adding an
        existing pattern must not move it to the end: that silently changed which
        rule applied.
        """
        rule = Rule(match, profile, device, title, label, notify, silent)
        out = []
        replaced = False
        for existing in self.rules:
            if (existing.match, existing.device) == (match, device):
                if not replaced:
                    out.append(rule)
                    replaced = True
                continue
            out.append(existing)
        if not replaced:
            out.append(rule)
        self.rules = out
        return rule

    def move(self, match: str, device: str | None, delta: int) -> bool:
        """Swap a rule with its neighbour: -1 up, +1 down.

        Returns False at the edge of the list. The delta is clamped, because the
        only moves the app offers are one place at a time and a larger value would
        swap a rule with one further away, which is not what an arrow means.
        """
        index = self.index_of(match, device)
        if index is None:
            return False
        target = index + (1 if delta > 0 else -1)
        if not 0 <= target < len(self.rules):
            return False
        rules = list(self.rules)
        rules[index], rules[target] = rules[target], rules[index]
        self.rules = rules
        return True

    def index_of(self, match: str, device: str | None = None) -> int | None:
        """Where a rule sits in the match order, or None when it is not there."""
        for i, r in enumerate(self.rules):
            if (r.match, r.device) == (match, device):
                return i
        return None

    def move_to(self, match: str, device: str | None, index: int) -> bool:
        """Put a rule at a given position, used when its pattern was renamed."""
        current = self.index_of(match, device)
        if current is None:
            return False
        index = max(0, min(index, len(self.rules) - 1))
        rule = self.rules.pop(current)
        self.rules.insert(index, rule)
        return True

    def remove(self, match: str, device: str | None = None) -> int:
        before = len(self.rules)
        self.rules = [r for r in self.rules if (r.match, r.device) != (match, device)]
        return before - len(self.rules)


def rules_path() -> Path:
    from .config import config_dir

    return config_dir() / "app-profiles.json"


# -- the window list the app's picker shows ------------------------------------

SEP_FIELD = "\x01"
SEP_WINDOW = "\x02"


def windows_path() -> Path:
    from .config import config_dir

    return config_dir() / "windows.json"


def parse_windows(blob: str) -> list[dict]:
    """Split the string the KWin script sends into one record per window."""
    out = []
    for chunk in (blob or "").split(SEP_WINDOW):
        if not chunk:
            continue
        cls, _, rest = chunk.partition(SEP_FIELD)
        caption, _, desktop = rest.partition(SEP_FIELD)
        out.append({"class": cls, "title": caption, "desktop": desktop,
                    "app_id": resolve_app_id(cls, desktop)})
    return out


def save_windows(blob: str) -> list[dict]:
    """Keep the last list KWin sent, for the app to read without asking KWin."""
    windows = parse_windows(blob)
    try:
        path = windows_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"windows": windows}, indent=2) + "\n")
    except OSError as e:
        log.info("could not save the window list: %s", e)
    return windows


def load_windows() -> list[dict]:
    """The last window list the daemon saved, or an empty list."""
    try:
        data = json.loads(windows_path().read_text())
    except (OSError, ValueError):
        return []
    windows = data.get("windows")
    return windows if isinstance(windows, list) else []


def state_path() -> Path:
    from .config import config_dir

    return config_dir() / "app-state.json"


def save_last_switch(labels: dict[str, str], notify: dict[str, bool] | None = None,
                     silent: dict[str, bool] | None = None) -> None:
    """Record which rule label moved each device, for the app to display.

    The app cannot know on its own: a window change happens in the daemon, and on
    Wayland the app cannot read the focused window. One small file, written only
    when a switch actually happened, is cheaper than polling KWin.

    The rule's notification settings are stored here too, because the daemon that
    announces the switch is not the code that picked the rule: it only sees
    active.json change. Keeping them together means one write, one read.
    """
    try:
        path = state_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        body: dict[str, object] = {"by_app": labels}
        if notify is not None:
            body["notify"] = notify
        if silent is not None:
            body["silent"] = silent
        path.write_text(json.dumps(body, indent=2) + "\n")
    except OSError as e:
        log.info("could not save the application state: %s", e)


def load_notify_choice(device: str) -> tuple[bool, bool]:
    """Whether to announce a switch of this device, and whether to do it silently.

    Defaults are yes and silent: a rule that never said anything about
    notifications behaves like the one the app creates.
    """
    try:
        data = json.loads(state_path().read_text())
    except (OSError, ValueError):
        return True, True
    notify = data.get("notify")
    silent = data.get("silent")
    show = notify.get(device, True) if isinstance(notify, dict) else True
    quiet = silent.get(device, True) if isinstance(silent, dict) else True
    return bool(show), bool(quiet)


def load_last_switch() -> dict[str, str]:
    """Which rule moved each device, or an empty map."""
    try:
        data = json.loads(state_path().read_text())
    except (OSError, ValueError):
        return {}
    by_app = data.get("by_app")
    return by_app if isinstance(by_app, dict) else {}


# -- app identity --------------------------------------------------------------

_resolve_cache: dict[str, str] = {}


def resolve_app_id(resource_class: str, desktop_file_name: str = "") -> str:
    """The name a rule should match: a .desktop base name where one exists.

    KWin reports a window class, not an installed application. The three steps are
    the ones logitune arrived at: trust the .desktop name when KWin gives one, look
    the class up in the .desktop directories, and fall back to the class itself.
    """
    if desktop_file_name:
        # KWin reports the .desktop file without its extension ("org.kde.konsole"),
        # but a full path also arrives when the file is not installed system-wide.
        # Path.stem would cut "org.kde.konsole" down to "org.kde", so the extension
        # is only removed when it is really there.
        name = Path(desktop_file_name).name
        return name[: -len(".desktop")] if name.endswith(".desktop") else name
    if not resource_class:
        return ""
    key = resource_class.lower()
    if key in _resolve_cache:
        return _resolve_cache[key]
    found = _search_desktop_files(resource_class)
    _resolve_cache[key] = found
    return found


def _search_desktop_files(resource_class: str) -> str:
    want = resource_class.lower()
    for directory in DESKTOP_DIRS:
        try:
            entries = sorted(os.listdir(directory))
        except OSError:
            continue
        for name in entries:
            if not name.endswith(".desktop"):
                continue
            base = name[: -len(".desktop")]
            # "us.zoom.Zoom" also answers to "zoom"
            if base.rsplit(".", 1)[-1].lower() == want:
                return base
            if (_startup_wm_class(Path(directory) / name) or "").lower() == want:
                return base
    return resource_class


def _startup_wm_class(path: Path) -> str | None:
    """Read StartupWMClass without configparser's fussiness about .desktop files."""
    try:
        text = path.read_text(errors="replace")
    except OSError:
        return None
    in_entry = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_entry = stripped.lower() == "[desktop entry]"
            continue
        if in_entry and stripped.lower().startswith("startupwmclass"):
            _, _, value = stripped.partition("=")
            return value.strip()
    return None


# -- the watcher ---------------------------------------------------------------

# The KWin Scripting methods and the arguments they take. GLib needs plain values
# here: building GLib.Variant objects first and handing the tuple to another
# GLib.Variant raises "Must be string, not Variant".
KWIN_ARGS = {
    # method: (argument names, argument signature, reply signature)
    "loadScript": (("path", "plugin"), "ss", "i"),
    "unloadScript": (("plugin",), "s", ""),
    "start": ((), "", ""),
    "isScriptLoaded": (("plugin",), "s", "b"),
}


def _kwin_args(method: str, kwargs: dict) -> tuple[str, tuple, str]:
    """The argument signature, the plain values and the reply signature."""
    names, types, reply = KWIN_ARGS.get(method, ((), "", ""))
    values = tuple(kwargs[n] for n in names if n in kwargs)
    return f"({types[:len(values)]})", values, f"({reply})"


class Watcher:
    """Owns the D-Bus service the KWin script calls, and applies the rules."""

    def __init__(self, rules: AppRules | None = None, on_focus=None):
        self.rules = rules or AppRules.load()
        self.on_focus = on_focus or self._apply
        self.last_app: str | None = None
        self.last_caption = ""
        self.reason = "not started"
        try:
            self._rules_mtime = rules_path().stat().st_mtime_ns
        except OSError:
            self._rules_mtime = 0
        self._loop = None
        self._bus = None
        self._thread: threading.Thread | None = None
        self._script_id: int | None = None

    # -- lifecycle -------------------------------------------------------------
    def start(self) -> bool:
        """Register the service and load the KWin script. False if the desktop cannot host it."""
        self.reason = ""
        try:
            import gi

            gi.require_version("Gio", "2.0")
            from gi.repository import Gio, GLib
        except (ImportError, ValueError) as e:
            self.reason = f"PyGObject is missing ({e})"
            log.info("application profiles need PyGObject; not watching windows")
            return False
        if not os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
            self.reason = "no session bus address in the environment"
            log.info("application profiles need the session bus; not watching windows")
            return False
        # XDG_CURRENT_DESKTOP is not set in a systemd user service on every distro.
        # Absence is a hint, not a verdict: ask KWin whether it is there instead.
        desktop = os.environ.get("XDG_CURRENT_DESKTOP", "")
        if desktop and not desktop.lower().startswith(("kde", "plasma")):
            self.reason = f"this desktop is {desktop}, not KDE"
            log.info("application profiles are implemented for KDE; this desktop is %s", desktop)
            return False

        self._Gio, self._GLib = Gio, GLib
        self._bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        info = Gio.DBusNodeInfo.new_for_xml(SERVICE_XML)
        self._bus.register_object(OBJECT, info.interfaces[0], self._call, None, None)

        def owned(*_a):
            self._load_kwin_script()

        Gio.bus_own_name_on_connection(self._bus, SERVICE, Gio.BusNameOwnerFlags.NONE, owned, None)
        self._loop = GLib.MainLoop()
        self._thread = threading.Thread(target=self._loop.run, name="app-watch", daemon=True)
        self._thread.start()
        self.reason = "running"
        log.info("watching window focus for application profiles")
        return True

    def stop(self) -> None:
        if self._loop is not None:
            self._loop.quit()
            self._loop = None
        self._unload_kwin_script()
        self._bus = None

    # -- KWin script -----------------------------------------------------------
    def script_path(self) -> Path:
        """The KWin script, either beside the source tree or in the installed data dir."""
        from .config import data_dir

        candidates = (
            Path(__file__).resolve().parent.parent.parent / "data" / "kwin" / "logi-ghub-focus.js",
            Path(__file__).resolve().parent / "data" / "logi-ghub-focus.js",
            data_dir() / "kwin" / "logi-ghub-focus.js",
        )
        for path in candidates:
            if path.exists():
                return path
        return candidates[0]

    def _load_kwin_script(self) -> None:
        path = self.script_path()
        if not path.exists():
            log.warning("the KWin script is missing at %s; application profiles stay off", path)
            return
        result = self._kwin("loadScript", path=str(path), plugin="logi-ghub-focus")
        if result is None:
            return
        self._script_id = result
        self._kwin("start")

    def _unload_kwin_script(self) -> None:
        if self._script_id is not None:
            try:
                self._kwin("unloadScript", plugin="logi-ghub-focus")
            finally:
                self._script_id = None

    def _kwin(self, method: str, **kwargs):
        """Call a method of org.kde.kwin.Scripting, returning its first reply value."""
        Gio, GLib = self._Gio, self._GLib
        signature, values, reply_sig = _kwin_args(method, kwargs)
        try:
            reply = self._bus.call_sync(
                "org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting", method,
                GLib.Variant(signature, values) if values else None,
                GLib.VariantType.new(reply_sig),
                Gio.DBusCallFlags.NONE, 3000, None)
        except GLib.Error as e:
            log.info("KWin scripting refused %s: %s", method, e.message)
            return None
        values = reply.unpack()
        return values[0] if values else None

    # -- D-Bus method ----------------------------------------------------------
    def _call(self, _conn, _sender, _path, _iface, method, params, _invocation):
        if method == "focusChanged":
            resource_class, caption, desktop_name = params.unpack()
            self.focus_changed(resource_class, caption, desktop_name)
        elif method == "windowsReported":
            (blob,) = params.unpack()
            save_windows(blob)
        elif method == "focusLost":
            self.focus_changed("", "", "")
        return None

    def reload_rules(self) -> None:
        """Pick up an edited rules file without restarting the service.

        The rules were read once in __init__, so a rule added from the app did
        nothing until the service was restarted: the file changed, the rules in
        memory did not.
        """
        try:
            mtime = rules_path().stat().st_mtime_ns
        except OSError:
            mtime = 0
        if mtime == self._rules_mtime:
            return
        self._rules_mtime = mtime
        self.rules = AppRules.load()

    def focus_changed(self, resource_class: str, caption: str, desktop_name: str = "") -> None:
        """A window took focus: work out which profile each device should run."""
        self.reload_rules()
        if not self.rules.enabled:
            return
        if not resource_class:
            self.last_app = None
            return
        if resource_class.lower() in IGNORED:
            return
        app_id = resolve_app_id(resource_class, desktop_name)
        # Repeat only on the application, not on the title: the profile is chosen by
        # the class, so moving between two windows of the same application cannot
        # change it. Comparing titles as well fired on those moves and, when two
        # windows shared a title, missed a real switch.
        if app_id == self.last_app:
            self.last_caption = caption
            return
        self.last_app, self.last_caption = app_id, caption
        self.on_focus(app_id, caption)

    # -- applying --------------------------------------------------------------
    def _apply(self, app_id: str, caption: str) -> None:
        from . import profiles

        active = profiles.get_active()
        # Nothing to do when no rule and no default names a device: the daemon
        # leaves devices without an active profile alone, and a rules file that
        # only carries defaults must not switch devices by itself.
        targets = set(active) | self.rules.devices()
        if not targets:
            return
        wanted: dict[str, str] = {}
        labels: dict[str, str] = {}
        announce: dict[str, bool] = {}
        quiet: dict[str, bool] = {}
        for device in targets:
            rule = self.rules.rule_for(device, app_id, caption)
            name = rule.profile if rule is not None else self.rules.defaults.get(device)
            if name is None or active.get(device) == name:
                continue
            if not profile_exists(device, name):
                # A rule pointing at a deleted profile would switch the device to
                # nothing at all; keep the current profile and say so.
                log.warning("window %r: no profile %r for %s; leaving it as it is",
                            app_id, name, device)
                continue
            wanted[device] = name
            # The rule's own name, or the window class when it has none.
            labels[device] = rule.display_name(app_id) if rule is not None else app_id
            # A switch back to the default has no rule of its own; it keeps the
            # default settings rather than borrowing the last rule's.
            announce[device] = rule.notify if rule is not None else True
            quiet[device] = rule.silent if rule is not None else True
        if not wanted:
            return
        for device, name in wanted.items():
            profiles.set_active(device, name)
        # Remembered so the app can show what is running without asking KWin again,
        # and so the daemon knows whether this switch should be announced.
        save_last_switch(labels, announce, quiet)
        log.info("window %r: switched %s", app_id,
                 ", ".join(f"{d} -> {p}" for d, p in sorted(wanted.items())))


def profile_exists(device: str, name: str) -> bool:
    from . import profiles

    return any(p.name == name for p in profiles.list_profiles(device))


def kwin_available() -> bool:
    """Whether this session can host the watcher at all."""
    if not os.environ.get("XDG_CURRENT_DESKTOP", "").lower().startswith(("kde", "plasma")):
        return False
    if shutil.which("busctl") is None and shutil.which("dbus-send") is None:
        return True  # Gio still works
    tool = "busctl" if shutil.which("busctl") else "dbus-send"
    try:
        if tool == "busctl":
            probe = subprocess.run(["busctl", "--user", "status", "org.kde.KWin"], capture_output=True, timeout=5)
        else:
            probe = subprocess.run(["dbus-send", "--session", "--print-reply", "--dest=org.kde.KWin",
                                    "/Scripting", "org.freedesktop.DBus.Introspectable.Introspect"],
                                   capture_output=True, timeout=5)
        return probe.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False
