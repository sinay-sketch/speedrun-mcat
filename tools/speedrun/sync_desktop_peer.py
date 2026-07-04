#!/usr/bin/env python3
# License: GNU AGPL v3 or later.
"""Desktop peer for the iOS sync demo (drives the SAME shared Rust engine via
the anki-ffi C ABI). Run this AFTER the phone app taps "Sync with desktop"
(which full-uploads the phone's collection to the server):

  1. FULL DOWNLOAD the phone's collection from the server  -> proves phone->desktop.
  2. Review N previously-untouched cards on the desktop.
  3. NORMAL SYNC the reviews back up.

Then tap "Sync with desktop" on the phone again: it downloads these reviews,
and its Memory readout's "X of 46 cards have review history" jumps by N,
proving desktop->phone. Two-way sync, end to end, at the app level.

  PYTHONPATH=out/pylib out/pyenv/bin/python tools/speedrun/sync_desktop_peer.py [N]
"""
import ctypes
import os
import sys
import tempfile
import time

from anki.collection import Collection

ENDPOINT = "http://127.0.0.1:8080/"
USER, PW = "test", "test"
LIB = os.path.abspath("target/debug/libanki_ffi.dylib")
N = int(sys.argv[1]) if len(sys.argv) > 1 else 5

lib = ctypes.CDLL(LIB)
lib.speedrun_open.restype = ctypes.c_void_p
lib.speedrun_open.argtypes = [ctypes.c_char_p]
lib.speedrun_answer.restype = ctypes.c_int32
lib.speedrun_answer.argtypes = [ctypes.c_void_p, ctypes.c_int64, ctypes.c_uint]
lib.speedrun_sync.restype = ctypes.c_int32
lib.speedrun_sync.argtypes = [ctypes.c_char_p] * 4
lib.speedrun_close.argtypes = [ctypes.c_void_p]

SYNC_NAME = {0: "in-sync/normal", 1: "FULL UPLOAD", 2: "FULL DOWNLOAD", -1: "ERROR"}


def sync(path):
    return lib.speedrun_sync(path.encode(), ENDPOINT.encode(), USER.encode(), PW.encode())


def reviewed_count(path):
    c = Collection(path)
    n = sum(1 for cid in c.find_cards("deck:MCAT::*") if c.get_card(cid).reps > 0)
    unreviewed = [cid for cid in sorted(c.find_cards("deck:MCAT::*")) if c.get_card(cid).reps == 0]
    total = len(c.find_cards("deck:MCAT::*"))
    c.close()
    return n, unreviewed, total


def main():
    tmp = tempfile.mkdtemp(prefix="desktoppeer_")
    D = os.path.join(tmp, "desktop.anki2")

    print("desktop first sync ->", SYNC_NAME[sync(D)])
    n, unreviewed, total = reviewed_count(D)
    print(f"desktop received {total} cards from the phone; {n} already have review history")
    assert total > 0, "desktop did not receive the phone's deck (is the server seeded?)"

    targets = unreviewed[:N]
    print(f"desktop reviewing {len(targets)} previously-untouched cards (rating Good)...")
    col = lib.speedrun_open(D.encode())
    for cid in targets:
        lib.speedrun_answer(col, int(cid), 3)
        time.sleep(0.005)
    lib.speedrun_close(col)

    print("desktop sync ->", SYNC_NAME[sync(D)])
    n2, _, _ = reviewed_count(D)
    print(f"desktop now has {n2} reviewed (was {n}).")
    print(f"\nNow tap 'Sync with desktop' on the phone: its Memory readout should show "
          f"{n2} of {total} cards with review history.")


if __name__ == "__main__":
    main()
