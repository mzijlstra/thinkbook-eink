# thinkbook-eink

Linux support for the colour e-ink panel of the Lenovo ThinkBook Plus Gen 4 IRU (21JJ).

The panel is an ordinary second display, `eDP-2` on the Intel graphics, while its T-CON (an ITE
IT8951-family chip on USB `048d:8957`) is in a "MIPI mode" that follows the video signal. After
a full shutdown the T-CON comes up in a frozen mode; one USB command switches it to a live one.
`einkctl` sends that command and triggers full refreshes against ghosting.

## For other users

- **Hardware:** written and tested only on the ThinkBook Plus Gen 4 IRU, machine type 21JJ, BIOS
  LUCN53WW. Other ThinkBook Plus generations use different e-ink hardware. If yours shows a USB
  device `048d:8957` named "ITE T-CON" in `lsusb`, it may work; reports are welcome.
- **At your own risk:** `einkctl` only sends the T-CON's display-mode commands, which Lenovo's own
  software sends during normal use. It still talks to your hardware directly, without any warranty.
- **No Lenovo software or files:** this repository holds only independent code. The protocol was
  worked out by observing the hardware on Linux and studying how Lenovo's Windows software
  behaves, for interoperability.
- **After a restart from Windows** the panel may be missing until the next cold boot; see Status.

## Usage

```
einkctl on                 # live mode (browser): follows the screen, little ghosting
einkctl refresh            # full refresh, then back to the current mode
einkctl mode reader        # hold the current frame, sharp and still (refresh to update)
einkctl status             # MIPI mode and eDP-2 connector state
einkctl info               # T-CON identification and panel size
```

| Mode | Follows the screen | Notes |
|---|---|---|
| `browser` (2) | yes | default; little ghosting, clearest colour |
| `hybrid` (240) | yes | heavy ghosting that clears in about half a second |
| `fast-ui` (4) | yes | most ghosting; traces stay until a refresh |
| `reader` (0), `mixed` (1) | no | hold the frame from the last refresh |
| `fast-reader` (3) | no | the mode after power-on; looked grayscale |

## Install

Needs Python 3 and pyusb (`python-pyusb` on Arch, `python3-pyusb` on Fedora).

```
sudo install -m 755 einkctl /usr/local/bin/einkctl
sudo install -m 644 contrib/70-thinkbook-eink.rules /etc/udev/rules.d/
sudo install -m 644 contrib/einkctl-on.service /etc/systemd/system/
sudo udevadm control --reload && sudo udevadm trigger --subsystem-match=usb
```

The udev rule lets the logged-in user run `einkctl` without sudo, and starts
`einkctl-on.service` whenever the T-CON appears, so the panel is live after boot.

## Safety

Only the MIPI mode and refresh commands are implemented. The T-CON also accepts commands that
write its flash or change the panel's voltages (VCOM, PMIC, power sequence); those are
deliberately absent, and a test keeps the list of mailbox commands at the two vetted ones.

## Tests

```
python3 -m unittest discover -s tests
```

## Status

Works: live desktop on the e-ink panel in colour, mode switching, refresh.

Open:
- **Restart from Windows:** the Intel driver probes eDP-2 about 2 s into boot, before the T-CON is
  ready, and disables it for that boot. The T-CON is ready within about 2.5 minutes; stopping the
  display manager and rebinding i915 then brings the panel back (`echo 0000:00:02.0 >
  /sys/bus/pci/drivers/i915/unbind`, then `.../bind`). Doing this under a running desktop session
  breaks that session. A boot service that handles it automatically is planned.
- Swivel detection, and turning the keyboard and touchpad off when swivelled (ACPI WMI
  `LENOVO_TB_G4_CTRL`).

## License

MIT, see `LICENSE`.
