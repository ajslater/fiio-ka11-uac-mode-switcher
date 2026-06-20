# ka11uac

A tiny command-line tool to switch a **FiiO KA11** USB DAC between **UAC2.0** and **UAC1.0** mode — without the FiiO Control app.

```
python3 ka11uac.py status   # show the stored mode
python3 ka11uac.py 1        # switch to UAC1.0
python3 ka11uac.py 2        # switch to UAC2.0
```

## Why this exists

The KA11 has two USB Audio Class modes:

- **UAC2.0** (default) — up to 384kHz/32-bit, but needs a host that speaks UAC2.
- **UAC1.0** — capped at 96kHz, but **plug-and-play on a PS5 / PS4 / Nintendo Switch** and other devices that only do UAC1.

Switching modes is normally only possible through the **FiiO Control app**, which is Android-only for this feature (the iOS app and the [web version](https://fiiocontrol.fiio.com/) don't expose it). If you don't have an Android phone, you're stuck. This tool does the one thing you actually need from a desktop.

## What it does

`ka11uac.py` talks to the KA11's USB-HID control interface and sends the same command the official FiiO Control Android app sends to change UAC mode. It can also read back the currently-stored mode to confirm the change took.

## Requirements

- Python 3
- [hidapi](https://github.com/libusb/hidapi) (the C library)
- the [`hid`](https://pypi.org/project/hid/) Python binding

### macOS

```sh
brew install hidapi
pip install hid
```

The script auto-locates the Homebrew `libhidapi.dylib`, so no extra environment setup is needed.

### Linux / Windows (untested)

It *should* work anywhere `hid` + hidapi run, but I've only tested macOS. On Linux you'll likely need hidapi installed (`libhidapi-hidraw0`) and a udev rule (or `sudo`) to allow non-root HID access to vendor `2972`. The dylib-loading shim at the top of the script is macOS-specific; on other platforms it's a harmless no-op as long as hidapi is on the system library path.

## Usage

```sh
# read the mode currently stored on the device
python3 ka11uac.py status
#   stored mode: UAC2.0

# switch to UAC1.0 (for PS5 / Switch / etc.)
python3 ka11uac.py 1
#   FIIO KA11: set UAC1.0  (confirmed)
#   Unplug and replug the KA11 for the change to take effect.
```

After switching, **unplug and replug the KA11** (or replug it into the target device). The mode is written to the DAC and applied on the next USB enumeration.

## ⚠️ Limitations after switching to UAC1.0

This is the important part. **Read it before you switch.**

- **The change is reversible** — `python3 ka11uac.py 2` puts it back to UAC2.0 — **but only from a host that can still see the KA11's HID control interface.**
- **In UAC1.0 mode, some computers stop detecting the KA11 entirely.** On the machine I tested (macOS), after switching to UAC1.0 the KA11 no longer appeared as an audio device *or* as a HID device — even though the PS5 happily used it for audio. UAC1.0 mode seems tuned for simple console hosts, and the vendor HID control interface this tool relies on appears to drop in that mode on at least some hosts.
- **Consequence:** if your computer can't see the KA11 while it's in UAC1.0, **this tool can't switch it back.** You'd then need either:
  1. the **FiiO Control Android app** (plug the KA11 into an Android phone and switch to UAC2.0), or
  2. a different computer that *does* still enumerate the KA11's HID interface in UAC1.0.

So: switching **to** UAC1.0 is easy and works great for consoles. Switching **back** may require an Android phone, depending on your computer. Don't switch to UAC1.0 expecting to flip it back from the same machine unless you've confirmed that machine still detects the DAC afterward.

## How it works

The control channel is a USB-HID `SET_REPORT` (`bmRequestType=0x21`, `bRequest=0x09`, `wValue=0x0200`, `wIndex=0`) carrying a 16-byte report. The UAC command id is `0x47`:

```
Write (switch):  0B 11 A0 A2 00 47 01 MM 00 00 00 00 00 00 00 00
Read  (query):   0B 12 E4 A2 00 47 01 00 ...   -> reply byte[8] = current mode
                       │           │  │  └ MM: 01 = UAC1.0, 02 = UAC2.0
                       │           │  └ arg count
                       │           └ command id (0x47)
                       └ 0x11/0xA0 = write framing, 0x12/0xE4 = read framing
```

The command was reverse-engineered from the FiiO Control Android app and verified against real KA11 hardware (write → read-back round-trips correctly and is fully reversible).

## Compatibility

- **Tested:** FiiO **KA11**, on **macOS**.
- **Not tested:** every other FiiO DAC, and every other OS.

FiiO uses a shared HID protocol family across many of its dongles/DACs, and the USB vendor id (`0x2972`) is the same, so this *might* work on other models — **but I have no idea, and I haven't tried it.** If you run it against a different FiiO device, the `0x47` command may mean something else entirely. Use `status` first; if it doesn't cleanly report `UAC1.0`/`UAC2.0`, don't send switch commands. Reports of what works (or doesn't) on other models are welcome.

## Disclaimer

This is an unofficial tool, not affiliated with or endorsed by FiiO. It sends low-level USB commands to your hardware. It worked on my KA11, but you run it at your own risk. No warranty.
