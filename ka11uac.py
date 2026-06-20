#!/usr/bin/env python3
"""
ka11uac — switch a FiiO KA11 USB DAC between UAC1.0 and UAC2.0 mode.

UAC2.0 : default, up to 384kHz/32bit (needs a UAC2 host).
UAC1.0 : "compatibility" mode, up to 96kHz, plug-and-play on PS5 / Switch / etc.

Protocol reverse-engineered from the FiiO Control Android app (com.fiio.control).
The control channel is a USB-HID SET_REPORT (bmRequestType=0x21, bRequest=0x09,
wValue=0x0200, wIndex=0) carrying a 16-byte report. hidapi's write() issues the
same SET_REPORT under the hood on macOS.

    Frame (16 bytes):  LEN 0x11 A0 A2 00 CMD ARG DATA <pad to 16>
      switch UAC : LEN=0x0B CMD=0x47 ARG=0x01 DATA=mode(1|2)
      read  UAC  : sent as 0x12 E4 A2 .. then the reply's byte[8] is the mode

Usage:
    python3 ka11uac.py status     # read current mode (non-destructive)
    python3 ka11uac.py 1          # switch to UAC1.0
    python3 ka11uac.py 2          # switch to UAC2.0
"""

import os
import sys
import time
import ctypes.util

# hidapi from Homebrew isn't on the default dylib search path; help the loader.
if not ctypes.util.find_library("hidapi"):
    for p in ("/opt/homebrew/lib", "/usr/local/lib"):
        if os.path.exists(os.path.join(p, "libhidapi.dylib")):
            os.environ["DYLD_LIBRARY_PATH"] = (
                p + os.pathsep + os.environ.get("DYLD_LIBRARY_PATH", "")
            )
            try:
                ctypes.CDLL(os.path.join(p, "libhidapi.dylib"))
            except OSError:
                pass
            break

import hid

FIIO_VID = 0x2972
KA11_PID = 0x0081
PRODUCT_MATCH = "KA11"


# --- command frames (16-byte HID reports) ---------------------------------
def _switch_frame(mode: int) -> bytes:
    # bb.d(11, {0,0x47}, mode) from the app
    f = bytearray(16)
    f[0] = 0x0B  # response length (v8.b)
    f[1] = 0x11
    f[2] = 0xA0
    f[3] = 0xA2
    f[4] = 0x00  # command id hi  (f6383m = {0,71})
    f[5] = 0x47  #            lo  = 71
    f[6] = 0x01  # arg count (v8.a)
    f[7] = mode & 0xFF  # 1 = UAC1.0, 2 = UAC2.0
    return bytes(f)


def _read_request_frame() -> bytes:
    # read-request for the stored UAC mode: same command 0x47, GET framing
    # (byte[1]=0x12,[2]=0xE4 mark a read; the reply's byte[8] is the mode)
    f = bytearray(16)
    f[0] = 0x0B  # v8.b({0,0x47}) = 11
    f[1] = 0x12
    f[2] = 0xE4
    f[3] = 0xA2
    f[4] = 0x00  # command id hi  (f6383m = {0,71})
    f[5] = 0x47  #            lo  = 71
    f[6] = 0x01  # v8.a = 1
    return bytes(f)


# --- device plumbing -------------------------------------------------------
def _find():
    for d in hid.enumerate():
        if d["vendor_id"] == FIIO_VID and (
            d["product_id"] == KA11_PID
            or PRODUCT_MATCH in (d.get("product_string") or "").upper()
        ):
            return d
    return None


def _open():
    info = _find()
    if not info:
        sys.exit("error: no FiiO KA11 found (VID 0x2972). Is it plugged in?")
    h = hid.Device(path=info["path"])
    return h, info


def _write(h, frame: bytes):
    # leading 0x00 = HID report id 0 (unnumbered); hidapi sends the 16 data bytes
    h.write(b"\x00" + frame)


def _read_uac(h):
    """Return the device's stored UAC mode (1 or 2), or None."""
    while h.read(32, 1):  # drain any buffered/stale input reports
        pass
    _write(h, _read_request_frame())
    time.sleep(0.05)  # let the reply land
    data = h.read(32, 400)
    if data and len(data) > 8 and data[6] == 0x0B and data[7] == 0x01:
        return data[8]
    return None


# --- actions ---------------------------------------------------------------
def status():
    h, info = _open()
    try:
        mode = _read_uac(h)
        label = {1: "UAC1.0", 2: "UAC2.0"}.get(mode, f"unknown({mode})")
        print(f"stored mode: {label}")
    finally:
        h.close()


def switch(mode: int):
    h, info = _open()
    try:
        label = "UAC1.0" if mode == 1 else "UAC2.0"
        _write(h, _switch_frame(mode))
        time.sleep(0.1)
        stored = _read_uac(h)  # confirm it took
        name = info.get("product_string", "KA11")
        if stored == mode:
            print(f"{name}: set {label}  (confirmed)")
        else:
            print(f"{name}: sent {label}, but read-back={stored} — retrying once")
            _write(h, _switch_frame(mode))
            time.sleep(0.1)
            stored = _read_uac(h)
            print(
                f"{name}: set {label}  ({'confirmed' if stored == mode else 'read-back=' + str(stored)})"
            )
        print("Unplug and replug the KA11 for the change to take effect.")
    finally:
        h.close()


def main():
    arg = (sys.argv[1] if len(sys.argv) > 1 else "status").lower()
    if arg in ("status", "-s", "--status", "get"):
        status()
    elif arg in ("1", "uac1", "uac1.0"):
        switch(1)
    elif arg in ("2", "uac2", "uac2.0"):
        switch(2)
    else:
        sys.exit(f"usage: {sys.argv[0]} [status|1|2]")


if __name__ == "__main__":
    main()
