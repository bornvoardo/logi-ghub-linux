"""logi-ghubd: runs host-mode profiles (what G HUB does while it is open).

For each device that has an active computer profile (``logi-ghub-cli profile
activate NAME``) the daemon:

* switches the device out of on-board mode and applies DPI and report rate,
* for mice with Mouse Button Spy (0x8110): makes buttons whose action is not a
  plain mouse button silent, watches button presses and performs the action
  (keys, media keys, DPI changes, DPI shift, G-Shift layer, macros),
* claims lighting and applies the profile's effects and per-key colours,
* for keyboards with key assignments: takes the keyboard's input device and
  performs the assigned actions (see keyremap.py),
* re-applies everything when the device reconnects after sleep, and hands the
  device back to its on-board profile when it exits.

Devices without an active profile are left alone.
"""

from __future__ import annotations

import json

import argparse
import logging
import os
import queue
import signal
import threading
import time

from . import handback, keyremap, keys, lightfx, profiles
from .config import config_dir
from .actions import Action
from .device import LogiDevice, find_devices
from .features import lighting
from .features import onboard as ob
from .features.inputs import bitmask_changes
from .hidpp import DeviceOffline, HIDPPError, Message
from .hidpp.protocol import DAEMON_SW_ID
from .hidpp import features as F
from .macros import Macro
from .uinput import VirtualInput

log = logging.getLogger("logi-ghubd")


class MacroRunner:
    """Plays macros on the virtual input device; one thread per running macro."""

    def __init__(self, vinput: VirtualInput | None):
        self.vinput = vinput
        self._running: dict[str, threading.Event] = {}
        self._lock = threading.Lock()

    def _play_once(self, macro: Macro, stop: threading.Event) -> None:
        held: list[int] = []
        try:
            for ev, arg in macro.events():
                if stop.is_set() and macro.repeat != "once":
                    break
                if ev == "delay":
                    stop.wait(int(arg) / 1000)
                elif ev in ("key_down", "key_up"):
                    code = keys.HID_TO_EVDEV[keys.hid_for(str(arg))]
                    self._key(code, ev == "key_down", held)
                elif ev in ("mouse_down", "mouse_up"):
                    code = keys.MOUSE_BUTTONS[int(arg)][1]
                    self._key(code, ev == "mouse_down", held)
                elif ev == "consumer":
                    code = keys.CONSUMER_BY_NAME[str(arg)][1]
                    self._key(code, True, held)
                    self._key(code, False, held)
        finally:
            for code in held:  # never leave a key stuck down
                self._key(code, False, [])

    def _key(self, code: int, down: bool, held: list[int]) -> None:
        if self.vinput is None:
            return
        self.vinput.key(code, down)
        if down:
            held.append(code)
        elif code in held:
            held.remove(code)

    def press(self, key: str, macro: Macro) -> None:
        with self._lock:
            running = self._running.get(key)
            if macro.repeat == "toggle" and running is not None:
                running.set()
                return
            if running is not None and not running.is_set():
                return  # already playing
            stop = threading.Event()
            self._running[key] = stop

        def run():
            held: list[int] = []
            try:
                for name in macro.hold:  # e.g. Alt stays down while Tab repeats
                    self._key(keys.HID_TO_EVDEV[keys.hid_for(name)], True, held)
                while True:
                    self._play_once(macro, stop)
                    if macro.repeat == "once" or stop.is_set():
                        break
                    if macro.interval_ms and stop.wait(macro.interval_ms / 1000):
                        break
            finally:
                for code in reversed(held):
                    self._key(code, False, [])
                with self._lock:
                    if self._running.get(key) is stop:
                        del self._running[key]

        threading.Thread(target=run, name=f"macro-{macro.name}", daemon=True).start()

    def release(self, key: str, macro: Macro) -> None:
        if macro.repeat == "while_held":
            with self._lock:
                stop = self._running.get(key)
            if stop:
                stop.set()

    def stop_all(self) -> None:
        with self._lock:
            for stop in self._running.values():
                stop.set()


class GShift:
    """The G-Shift layer, shared by every device.

    Its whole purpose is that a key held on one device changes the other: pressing
    the keyboard's trigger must change the mouse's buttons. So the flag cannot live
    on a session. The keyboard reader and the mouse listener are separate threads,
    hence the lock.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._open = False
        self._listeners: list = []

    @property
    def open(self) -> bool:
        with self._lock:
            return self._open

    def set(self, on: bool) -> bool:
        """Open or close the layer. Returns whether it actually changed."""
        with self._lock:
            if on == self._open:
                return False
            self._open = on
            listeners = list(self._listeners)
        for fn in listeners:
            fn(on)
        return True

    def listen(self, fn) -> None:
        with self._lock:
            self._listeners.append(fn)


class Session:
    """A device running a host profile."""

    def __init__(self, dev: LogiDevice, profile: profiles.Profile, events: queue.Queue, runner: MacroRunner,
                 vinput: VirtualInput | None, gshift: "GShift | None" = None):
        self.dev = dev
        self.profile = profile
        self.events = events
        self.runner = runner
        self.vinput = vinput
        self.buttons_down = 0
        # Shared with every other device, so one trigger moves the whole desk.
        self.gshift_state = gshift or GShift()
        self.dpi_index = profile.default_dpi
        self.held_codes: dict[int, list[int]] = {}
        self.pressed: dict[int, Action] = {}  # action used at press time, so release matches it
        self.spy = dev.button_spy
        self.profile_mtime = 0.0
        self.lighting_claimed = False
        self.lights_off = False
        self.animator: lightfx.Animator | None = None
        self.remapper: keyremap.KeyRemapper | None = None
        self.keys_warned = False
        self.slots = dev.binding_count() or (self.spy.count if self.spy else 0)
        self.rom: ob.OnboardProfile | None = None
        if dev.onboard:
            try:
                self.rom = dev.onboard.read_profile(ob.ROM_BASE + 1)
            except (HIDPPError, TimeoutError):
                self.rom = None

    # -- setup / teardown ------------------------------------------------------
    def apply(self) -> None:
        dev, p = self.dev, self.profile
        if dev.onboard:
            dev.onboard.set_mode(ob.MODE_HOST)
        if dev.dpi and p.dpi_stages:
            self.dpi_index = min(p.default_dpi, len(p.dpi_stages) - 1)
            dev.dpi.set(p.dpi_stages[self.dpi_index])
        if dev.report_rate and p.report_rate:
            try:
                dev.report_rate.set_hz(p.report_rate)
            except (HIDPPError, KeyError) as e:
                log.warning("%s: report rate %s not applied: %s", dev.name, p.report_rate, e)
        if self.spy:
            self.spy.set_remapping(self._remap_table())
            self.spy.start()
        self._apply_lighting()
        self.ensure_keys()
        log.info("%s: profile '%s' applied in host mode", dev.name, p.name)

    def ensure_keys(self) -> None:
        """Start key remapping if the profile has key assignments and it isn't running (again after a reconnect)."""
        if self.vinput is None or getattr(self.dev, "fake_model", None) is not None:
            return
        if not (self.profile.key_actions or self.profile.gshift_key_actions):
            return
        if self.remapper is not None and (self.remapper.running or self.remapper.panicked):
            return  # after the escape keys, stay off until the profile is saved or activated again
        mapping = keyremap.resolve(self.profile.key_actions)
        # The second layer may name keys the first does not, so it decides on its
        # own whether there is anything to remap.
        gshift_mapping = keyremap.resolve(self.profile.gshift_key_actions)
        if not mapping and not gshift_mapping:
            return
        info = self.dev.info
        nodes = keyremap.find_event_nodes(info.path, info.behind_receiver)
        if not nodes:
            self._keys_problem("no keyboard input device found next to %s; key assignments not active", info.path)
            return
        remapper = keyremap.KeyRemapper(self.dev.name, nodes, mapping, pointer=self.vinput, runner=self.runner,
                                        macros={m.name: m for m in self.profile.macros}, tag=f"{self.dev.key}:keys",
                                        gshift_mapping=gshift_mapping, on_layer=self.on_gshift)
        try:
            remapper.start()
        except PermissionError as e:
            self._keys_problem("cannot open the keyboard's input device (%s); reinstall the udev rule "
                               "(scripts/install.sh --udev) for key assignments", e)
            return
        except OSError as e:
            self._keys_problem("key assignments not active: %s", e)
            return
        self.remapper = remapper

    def on_gshift(self, on: bool) -> None:
        """The keyboard's G-Shift key opened or closed its second layer.

        The layer belongs to the machine, not to this session: every device has to
        follow, so the flag is set on the shared object and each session redraws
        its own remapping. Called on the key reader thread, so nothing here waits
        on a device.
        """
        self.gshift_state.set(on)
        self.events.put(("gshift", self, on))

    def _keys_problem(self, msg: str, *args) -> None:
        """ensure_keys runs again on every rescan; say what's wrong once."""
        (log.debug if self.keys_warned else log.warning)("%s: " + msg, self.dev.name, *args)
        self.keys_warned = True

    def _apply_lighting(self) -> None:
        light = self.profile.lighting or {}
        if self.animator:
            self.animator.stop()
            self.animator = None
        if self.dev.rgb and (light.get("zones") or light.get("keys") or (light.get("animation") or {}).get("enabled")):
            self.animator = lightfx.apply(self.dev, light, claim=not self.lighting_claimed)
            self.lighting_claimed = True
        elif self.dev.brightness and light.get("brightness") is not None:
            self.dev.brightness.set(int(light["brightness"]))

    def release(self) -> bool:
        """Hand the device back to its on-board profile. False if it didn't answer (asleep or unplugged)."""
        dev = self.dev
        ok = True
        if self.remapper is not None:
            self.remapper.stop()
            self.remapper = None
        try:
            if self.spy:
                self.spy.stop()
                self.spy.set_remapping(self.spy.identity())
            if self.animator:
                self.animator.stop()
                self.animator = None
            if self.lighting_claimed:
                if self.lights_off:  # idle: switch the LEDs back on, or they stay dark after the hand-back
                    dev.rgb.power(True)
                    self.lights_off = False
                dev.rgb.release()
                lightfx.clear_applied(dev.key)
                self.lighting_claimed = False
            elif dev.onboard:
                dev.onboard.set_mode(ob.MODE_ONBOARD)
        except (HIDPPError, DeviceOffline, TimeoutError, OSError) as e:
            log.info("%s: could not hand back now (%s); will do it when it is next online", dev.name, e)
            ok = False
        self.release_all_keys()
        return ok

    def on_activity(self, active: bool) -> None:
        """Switch LEDs off when the firmware reports the user idle, back on when they return."""
        rgb = self.dev.rgb
        if not active and not self.lights_off:
            if self.animator:
                self.animator.paused.set()
            rgb.power(False)
            self.lights_off = True
            log.info("%s: idle, lighting off", self.dev.name)
        elif active and self.lights_off:
            rgb.power(True)
            rgb.claim()
            self.lights_off = False
            self._apply_lighting()
            log.info("%s: active, lighting restored", self.dev.name)

    def release_all_keys(self) -> None:
        for codes in self.held_codes.values():
            for code in codes:
                if self.vinput:
                    self.vinput.key(code, False)
        self.held_codes.clear()

    # -- button handling --------------------------------------------------------
    # -- the shared layer -------------------------------------------------------
    @property
    def gshift(self) -> bool:
        """Whether the second layer is open, wherever the trigger was pressed."""
        return self.gshift_state.open

    @gshift.setter
    def gshift(self, on: bool) -> None:
        self.set_gshift(on)

    def set_gshift(self, on: bool) -> None:
        """Open or close the shared layer, and make this device follow it."""
        if self.gshift_state.set(on):
            self.apply_remapping()

    def apply_remapping(self) -> None:
        """Tell the device which buttons it now answers itself.

        Called when the layer changes: a button that went from a plain click to a
        keystroke must stop being sent by the device, and one that went the other
        way must start.
        """
        if self.spy is None:
            return
        try:
            table = self._remap_table()
            log.info("%s: remapping table %s (layer %s, count %s)", self.dev.name, table, self.gshift,
                     self.spy.count)
            self.spy.set_remapping(table)
        except (HIDPPError, DeviceOffline, TimeoutError, OSError) as e:
            log.info("%s: could not update the button remapping: %s", self.dev.name, e)

    def action_for(self, index: int) -> Action:
        layer = self.profile.gshift_buttons if self.gshift else self.profile.buttons
        a = layer.get(index)
        if a is None and self.gshift:
            a = self.profile.buttons.get(index)
        if (a is None or a.kind == "default") and self.rom is not None:
            a = self.rom.button(index)
        return a or Action("default")

    def _remap_table(self) -> list[int]:
        """Physical buttons whose action is a plain mouse button keep sending it natively."""
        table = []
        for i in range(self.spy.count):
            a = self.action_for(i)
            table.append(a.button if a.kind == "mouse" and not self._gshift_differs(i) else 0)
        return table

    def _gshift_differs(self, i: int) -> bool:
        g = self.profile.gshift_buttons.get(i)
        return g is not None and g.kind not in ("default",) and g != self.profile.buttons.get(i)

    def on_message(self, msg: Message) -> None:
        if self.spy:
            mask = self.spy.parse(msg)
            if mask is not None:
                pressed, released = bitmask_changes(self.buttons_down, mask, self.spy.count)
                self.buttons_down = mask
                for i in pressed:
                    self.press(i)
                for i in released:
                    self.release_button(i)
                return
        if self.lighting_claimed and isinstance(self.dev.rgb, lighting.RGBEffects):
            active = self.dev.rgb.activity(msg)
            if active is not None:
                self.events.put(("activity", self, active))
                return
        if self.dev.has(F.WIRELESS_DEVICE_STATUS) and msg.sub_id == self.dev.hidpp.features[F.WIRELESS_DEVICE_STATUS] and msg.swid == 0:
            log.info("%s: reconnected, re-applying profile", self.dev.name)
            self.events.put(("reapply", self))

    def press(self, i: int) -> None:
        a = self.action_for(i)
        self.pressed[i] = a
        k = a.kind
        log.info("%s: button %s pressed -> %s (layer %s)", self.dev.name, i, a.label(), self.gshift)
        codes: list[int] = []
        if k == "mouse":
            if self._remap_table()[i] == 0:
                codes = [keys.MOUSE_BUTTONS.get(a.button, ("", 0x110))[1]]
        elif k == "key":
            codes = [keys.HID_TO_EVDEV[keys.hid_for(keys.MODIFIERS[b])] for b in range(8) if a.modifiers & (1 << b)]
            if a.key in keys.HID_TO_EVDEV:
                codes.append(keys.HID_TO_EVDEV[a.key])
        elif k == "consumer":
            ev = keys.CONSUMER_TO_EVDEV.get(a.usage)
            codes = [ev] if ev else []
        elif k == "special":
            self._special(a, True)
        elif k == "macro":
            macro = self.profile.macro(a.macro)
            if macro:
                self.runner.press(f"{self.dev.key}:{i}", macro)
        if codes and self.vinput:
            for c in codes:
                self.vinput.key(c, True)
            self.held_codes[i] = codes

    def release_button(self, i: int) -> None:
        codes = self.held_codes.pop(i, [])
        for c in reversed(codes):
            if self.vinput:
                self.vinput.key(c, False)
        a = self.pressed.pop(i, None) or self.action_for(i)
        if a.kind == "special":
            self._special(a, False)
        elif a.kind == "macro":
            macro = self.profile.macro(a.macro)
            if macro:
                self.runner.release(f"{self.dev.key}:{i}", macro)

    def _special(self, a: Action, down: bool) -> None:
        f = a.function
        stages = self.profile.dpi_stages
        dpi = self.dev.dpi
        if f == 0x0B:  # G-Shift while held
            self.gshift = down
            return
        if f == 0x07 and dpi:  # DPI shift while held
            dpi.set(self.profile.shift_dpi if down else stages[self.dpi_index])
            return
        if not down:
            return
        if f in (0x03, 0x04, 0x05, 0x06) and dpi and stages:
            if f == 0x03:
                self.dpi_index = min(self.dpi_index + 1, len(stages) - 1)
            elif f == 0x04:
                self.dpi_index = max(self.dpi_index - 1, 0)
            elif f == 0x05:
                self.dpi_index = (self.dpi_index + 1) % len(stages)
            else:
                self.dpi_index = self.profile.default_dpi
            dpi.set(stages[self.dpi_index])
            log.info("%s: DPI %d", self.dev.name, stages[self.dpi_index])
        elif f in (0x01, 0x02, 0x10, 0x11) and self.vinput:
            horizontal = f in (0x01, 0x02)
            self.vinput.wheel(-1 if f in (0x01, 0x10) else 1, horizontal)


def _file_mtime(path) -> int:
    try:
        return os.stat(path).st_mtime_ns
    except OSError:
        return 0


def _profile_mtime(model_key: str, name: str) -> int:
    try:
        # Nanoseconds: two saves within the same second must still differ, or the
        # daemon keeps running the older assignments until the fallback scan.
        return os.stat(profiles.profile_dir(model_key) / f"{profiles._slug(name)}.json").st_mtime_ns
    except OSError:
        return 0


class Daemon:
    def __init__(self, fake: bool = False):
        self.fake = fake
        self.events: queue.Queue = queue.Queue()
        self.sessions: dict[str, Session] = {}
        # One layer for the machine: a key held on the keyboard must change the
        # mouse's buttons too.
        self.gshift = GShift()
        self.stop = threading.Event()
        try:
            self.vinput = VirtualInput()
        except OSError as e:
            log.warning("no virtual input device (%s); key actions and macros will not work", e)
            self.vinput = None
        self.runner = MacroRunner(self.vinput)
        self._active_mtime = 0
        self._last_scan = 0.0
        self._toast_id = 0
        # Application profiles: a KWin script reports the focused window, and the
        # rules in app-profiles.json decide which profile each device should run.
        # Off unless the rules file exists, so a plain install behaves as before.
        self.watcher = None
        # A layer change has to reach every device, not only the one that was
        # triggered: this runs on whichever thread held the trigger.
        self.gshift.listen(self._layer_changed)

    def _layer_changed(self, on: bool) -> None:
        """Every running profile redraws its button remapping for the new layer."""
        for session in list(self.sessions.values()):
            session.apply_remapping()
            # The keyboard's layer lives in its key remapper, not in the button
            # table, so a mouse trigger has to reach it explicitly.
            remapper = session.remapper
            if remapper is not None:
                remapper.set_layer_from_outside(on)
        self._publish_layer(on)

    def _publish_layer(self, on: bool) -> None:
        """Tell the tray the layer is open.

        The tray is a separate process, so it cannot read this flag. It watches
        this small file with GLib.FileMonitor instead, which reports the change
        within a few milliseconds and costs nothing while the layer is idle.
        """
        path = config_dir() / "gshift-state.json"
        try:
            path.write_text(json.dumps({"open": bool(on)}))
        except OSError as e:
            log.info("could not write the layer state: %s", e)

    def _devices(self) -> list[LogiDevice]:
        if self.fake:
            from .hidpp.fake import fake_devices

            return fake_devices()
        return find_devices()

    def scan(self) -> None:
        active = profiles.get_active()
        # Drop sessions whose profile was deactivated or changed.
        for key, s in list(self.sessions.items()):
            if active.get(key) != s.profile.name or s.profile_mtime != _profile_mtime(key, s.profile.name):
                self.end(key)
        for s in self.sessions.values():
            s.ensure_keys()
        wanted = {k: v for k, v in active.items() if k not in self.sessions}
        stale = handback.pending() - set(active)  # left in host mode while asleep, now without a profile
        if not wanted and not stale:
            return
        for dev in self._devices():
            name = wanted.get(dev.key)
            if dev.online and dev.key in stale and not name and handback.hand_back(dev):
                handback.clear(dev.key)
                log.info("%s: handed back to its on-board profile", dev.name)
            if not name or not dev.online:
                dev.close()
                continue
            if dev.hidpp is None:
                log.warning("%s: host mode is not supported on this device; it keeps its on-board profiles", dev.name)
                dev.close()
                continue
            try:
                profile = profiles.load_profile(dev.key, name)
                dev.hidpp.swid = DAEMON_SW_ID
                session = Session(dev, profile, self.events, self.runner, self.vinput, gshift=self.gshift)
                session.profile_mtime = _profile_mtime(dev.key, name)
                dev.hidpp.add_handler(lambda m, s=session: self.events.put(("msg", s, m)))
                dev.hidpp.start_listener()
                session.apply()
                handback.clear(dev.key)  # a new session ends with its own hand-back
                self.sessions[dev.key] = session
                # Announce only after apply() returned, so a profile that failed to
                # load is never named as the running one.
                self._announce(dev.name, name, dev.key)
            except (OSError, HIDPPError, DeviceOffline, TimeoutError, ValueError) as e:
                log.warning("%s: cannot start profile '%s': %s", dev.name, name, e)
                dev.close()

    def end(self, key: str) -> None:
        s = self.sessions.pop(key, None)
        if s:
            if not s.release():
                handback.mark(key)
            s.dev.close()
            log.info("%s: released", s.dev.name)

    def _watched_mtime(self, active: dict) -> int:
        """A value that changes whenever active.json or any running profile changes.

        The daemon used to watch active.json alone, so pressing Save in the app
        wrote the profile but the running session kept the old assignments until
        the ten-second fallback scan. Mixing the profile files in makes the change
        visible on the next loop, about a second later.
        """
        value = _file_mtime(profiles._active_path())
        for key, name in active.items():
            value = max(value, _profile_mtime(key, name))
        return value

    def run(self) -> None:
        log.info("logi-ghubd started")
        self.start_app_watch()
        while not self.stop.is_set():
            now = time.monotonic()
            try:
                mtime = self._watched_mtime(profiles.get_active())
            except (OSError, ValueError):
                mtime = 0
            if mtime != self._active_mtime or now - self._last_scan > 10:
                self._active_mtime = mtime
                self._last_scan = now
                self.scan()
            try:
                item = self.events.get(timeout=1.0)
            except queue.Empty:
                continue
            try:
                if item[0] == "msg":
                    item[1].on_message(item[2])
                elif item[0] == "activity":
                    item[1].on_activity(item[2])
                elif item[0] == "reapply":
                    item[1].apply()
                elif item[0] == "reload":
                    for key in list(self.sessions):
                        self.end(key)
                    self.scan()
            except (HIDPPError, DeviceOffline, TimeoutError) as e:
                log.warning("device request failed: %s", e)
            except OSError as e:
                s = item[1]
                log.warning("%s: lost (%s)", s.dev.name, e)
                self.sessions.pop(s.dev.key, None)
        self.shutdown()

    def _announce(self, device_name: str, profile_name: str, device_key: str = "") -> None:
        """Say which profile is now running: "device — profile".

        Called after the session applied, so the message never names a profile that
        failed to load. Every switch notifies, including the first one after start,
        which is what made the notification look intermittent before.

        A window rule can switch notifications off for itself, and can ask for a
        silent one; the rule that moved this device recorded its choice when the
        watcher applied it. Switching back to the default has no rule, so it keeps
        the defaults: shown, and silent.
        """
        from . import appwatch
        from .notify import notify

        show, silent = appwatch.load_notify_choice(device_key) if device_key else (True, True)
        if not show:
            return
        notify(f"{device_name} — {profile_name}", silent=silent)

    def start_app_watch(self) -> None:
        """Start watching the focused window.

        This used to return early when app-profiles.json did not exist yet, so a rule
        added from the app while the service was running needed a restart before
        anything happened. The watcher now always runs: with no rules it simply does
        nothing, and the first rule takes effect on the next focus change.
        """
        from . import appwatch

        try:
            watcher = appwatch.Watcher()
            if watcher.start():
                self.watcher = watcher
            else:
                log.warning("application profiles are off: %s", watcher.reason)
        except Exception as e:  # noqa: BLE001 - window tracking must never stop the profiles
            log.warning("application profiles unavailable: %s", e)

    def shutdown(self) -> None:
        self.runner.stop_all()
        if self.watcher is not None:
            self.watcher.stop()
            self.watcher = None
        for key in list(self.sessions):
            self.end(key)
        if self.vinput:
            self.vinput.close()
        log.info("logi-ghubd stopped")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="logi-ghubd", description="Run host-mode Logitech profiles")
    ap.add_argument("--fake", action="store_true", help="use simulated devices")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.fake:
        from .config import use_sandbox

        use_sandbox()
    d = Daemon(fake=args.fake)
    signal.signal(signal.SIGTERM, lambda *_: d.stop.set())
    signal.signal(signal.SIGINT, lambda *_: d.stop.set())
    signal.signal(signal.SIGHUP, lambda *_: d.events.put(("reload",)))
    d.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
