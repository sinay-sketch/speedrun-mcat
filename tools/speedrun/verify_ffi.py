#!/usr/bin/env python3
# License: GNU AGPL v3 or later.
"""Verify the anki-ffi shared-engine bridge (the same C ABI the iOS app calls):
open the bundled MCAT collection, run a review loop, and read the Memory score.

  out/pyenv/bin/python tools/speedrun/verify_ffi.py
"""
import ctypes
import json
import os
import shutil
import tempfile

LIB = os.path.abspath("target/debug/libanki_ffi.dylib")
SRC_COL = os.path.abspath("ios/SpeedrunMCAT/Resources/collection.anki2")
DID = int(open("ios/SpeedrunMCAT/Resources/deck_id.txt").read().strip())

lib = ctypes.CDLL(LIB)
lib.speedrun_open.restype = ctypes.c_void_p
lib.speedrun_open.argtypes = [ctypes.c_char_p]
lib.speedrun_next_card.restype = ctypes.c_void_p
lib.speedrun_next_card.argtypes = [ctypes.c_void_p]
lib.speedrun_answer.restype = ctypes.c_int32
lib.speedrun_answer.argtypes = [ctypes.c_void_p, ctypes.c_int64, ctypes.c_uint]
lib.speedrun_mastery.restype = ctypes.c_void_p
lib.speedrun_mastery.argtypes = [ctypes.c_void_p, ctypes.c_int64]
lib.speedrun_free_string.argtypes = [ctypes.c_void_p]
lib.speedrun_close.argtypes = [ctypes.c_void_p]


def take_str(ptr: int) -> str:
    if not ptr:
        return ""
    s = ctypes.cast(ptr, ctypes.c_char_p).value.decode()
    lib.speedrun_free_string(ptr)
    return s


def main() -> None:
    tmp = tempfile.mkdtemp(prefix="ffi_")
    col_path = os.path.join(tmp, "collection.anki2")
    shutil.copy(SRC_COL, col_path)

    col = lib.speedrun_open(col_path.encode())
    assert col, "speedrun_open failed"
    print("opened collection via FFI")

    reviewed = 0
    for _ in range(8):
        card = json.loads(take_str(lib.speedrun_next_card(col)) or "{}")
        if not card:
            print("  (no more due cards)")
            break
        q = " ".join(card["question"].split())[:70]
        print(f"  card {card['card_id']}: {q!r}")
        rc = lib.speedrun_answer(col, int(card["card_id"]), 3)  # 3 = Good
        assert rc == 0, f"answer failed rc={rc}"
        reviewed += 1
    print(f"review loop via FFI: answered {reviewed} cards")

    m = json.loads(take_str(lib.speedrun_mastery(col, DID)) or "{}")
    print("Memory score via FFI (MasteryForDeck):", m)

    lib.speedrun_close(col)
    print("OK — shared engine driven through the iOS C ABI")


if __name__ == "__main__":
    main()
