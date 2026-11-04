# Measured on the hardware

Values below were read from a G915 X WIRED full-size keyboard on Fedora 44
(kernel 7.2.13) with `lsusb`, `/proc/bus/input/devices` and `sudo evtest`.
They are measurements, not assumptions; anything not listed here is still
unverified.

## Identity

| Item | Value |
|---|---|
| USB id | `046d:c359` (bus 7, "Logitech G915 X") |
| Model ID (HID++) | `C35900000000` |
| Unit ID | per unit (`EB2C258F` on the measured keyboard) |
| Interfaces | 3 (`7-1.3:1.0`, `7-1.3:1.1`, and a third HID++ interface) |
| Kernel driver on all three | `hid-generic` — not `logitech-hidpp-device` |

The keyboard is wired, so it has no receiver node. The G502 X mouse on the same
machine does go through `logitech-hidpp-device` because it is paired to a
`046d:c547` Lightspeed receiver.

Input nodes of the keyboard:

| Node | Name | Role |
|---|---|---|
| `event4` | `Logitech G915 X` | the keyboard proper (all keys, LEDs) |
| `event5` | `Logitech G915 X Mouse` | the volume roller / media buttons as relative events |
| `event6` | `Logitech G915 X Consumer Control` | media keys |
| `event7` | `Logitech G915 X System Control` | power/sleep |

## G-keys

All nine G-keys arrive as ordinary function keys on `event4`. There is no
proprietary host-side path and no HID++ feature involved.

| Key | HID usage | evdev code | Key |
|---|---|---|---|
| G1 | 0x68 | 183 | `KEY_F13` |
| G2 | 0x69 | 184 | `KEY_F14` |
| G3 | 0x6A | 185 | `KEY_F15` |
| G4 | 0x6B | 186 | `KEY_F16` |
| G5 | 0x6C | 187 | `KEY_F17` |
| G6 | 0x6D | 188 | `KEY_F18` |
| G7 | 0x6E | 189 | `KEY_F19` |
| G8 | 0x6F | 190 | `KEY_F20` |
| G9 | 0x70 | 191 | `KEY_F21` |

The device also declares `KEY_F22`..`KEY_F24` (192..194) in its capability
bitmap, but no key sends them.

Physical placement, from the printed quick-start guide and confirmed by the
keys themselves: G1..G5 are a column on the left edge of the main block (normal
keycaps). G6..G9 are the four round rubber buttons in the strip above the F-row.

## Numpad

The keyboard reports the full numpad key set (`KEY_NUMLOCK`, `KEY_KPSLASH`,
`KEY_KPASTERISK`, `KEY_KPMINUS`, `KEY_KP7`..`KEY_KP9`, `KEY_KPPLUS`,
`KEY_KP4`..`KEY_KP6`, `KEY_KP1`..`KEY_KP3`, `KEY_KPENTER`, `KEY_KP0`,
`KEY_KPDOT`, `KEY_KPEQUAL`).

## Still unverified

- The per-key lighting zone ids of a full-size board. `SPECIAL_ZONES` has
  G1..G9 = 180..188 from the reverse-engineered 0x8081 LED map; only G1..G5
  were confirmed on a TKL. A `probe` run on this keyboard settles it.
- Whether the HID++ interface of the wired keyboard answers on one of
  `hidraw6`..`hidraw8`, and which one.
- Whether on-board profiles (0x8101) and per-key lighting (0x8081) are present
  on the wired variant at all.
