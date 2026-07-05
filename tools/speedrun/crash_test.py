#!/usr/bin/env python3
# License: GNU AGPL v3 or later.
"""Crash / zero-corruption test (the spec's reliability check):
kill the engine mid-review many times and prove the collection never corrupts.

Each round: a child process opens the collection through the SHARED engine
(anki-ffi) and answers cards in a tight loop; the parent SIGKILLs it at a random
moment (mid-write), then reopens the collection and runs an integrity check
(SQLite `pragma integrity_check` + Anki card-count sanity). Anki stores in SQLite
WAL mode with atomic per-review transactions, so an abrupt kill rolls back the
partial write — no corruption, no lost/duplicated cards.

  PYTHONPATH=out/pylib out/pyenv/bin/python tools/speedrun/crash_test.py [rounds]
"""
import ctypes
import os
import signal
import subprocess
import sys
import tempfile
import textwrap
import time

from anki.collection import Collection
from anki import import_export_pb2 as ie

ROUNDS = int(sys.argv[1]) if len(sys.argv) > 1 else 20
LIB = os.path.abspath("target/debug/libanki_ffi.dylib")
APKG = os.path.abspath("mcat_starter.apkg")

REVIEWER = textwrap.dedent(f"""
    import ctypes, json, time, sys
    lib = ctypes.CDLL({LIB!r})
    lib.speedrun_open.restype = ctypes.c_void_p; lib.speedrun_open.argtypes=[ctypes.c_char_p]
    lib.speedrun_next_card.restype = ctypes.c_void_p; lib.speedrun_next_card.argtypes=[ctypes.c_void_p]
    lib.speedrun_answer.restype = ctypes.c_int32; lib.speedrun_answer.argtypes=[ctypes.c_void_p, ctypes.c_int64, ctypes.c_uint]
    lib.speedrun_free_string.argtypes=[ctypes.c_void_p]; lib.speedrun_close.argtypes=[ctypes.c_void_p]
    path = sys.argv[1]
    while True:                       # answer forever until SIGKILLed mid-write
        col = lib.speedrun_open(path.encode())
        for _ in range(1000):
            p = lib.speedrun_next_card(col)
            s = ctypes.cast(p, ctypes.c_char_p).value.decode(); lib.speedrun_free_string(p)
            obj = json.loads(s)
            if "card_id" not in obj: break
            lib.speedrun_answer(col, int(obj["card_id"]), 3)
        lib.speedrun_close(col)
""")


def integrity_ok(path):
    c = Collection(path)
    sqlite_ok = c.db.scalar("pragma integrity_check") == "ok"
    total = len(c.find_cards("deck:MCAT::*"))
    c.close()
    return sqlite_ok, total


def main():
    tmp = tempfile.mkdtemp(prefix="crashtest_")
    col_path = os.path.join(tmp, "collection.anki2")
    col = Collection(col_path)
    opts = col._backend.get_import_anki_package_presets()
    col.import_anki_package(ie.ImportAnkiPackageRequest(package_path=APKG, options=opts))
    expected = len(col.find_cards("deck:MCAT::*"))
    col.close()
    print(f"seeded collection with {expected} MCAT cards")

    rev = os.path.join(tmp, "reviewer.py")
    open(rev, "w").write(REVIEWER)

    survived = 0
    for i in range(1, ROUNDS + 1):
        p = subprocess.Popen([sys.executable, rev, col_path])
        time.sleep(0.15 + (i % 5) * 0.05)   # let it get mid-write, vary the moment
        p.send_signal(signal.SIGKILL)
        p.wait()
        ok, total = integrity_ok(col_path)
        status = "OK" if (ok and total == expected) else "CORRUPT/LOST"
        if ok and total == expected:
            survived += 1
        else:
            print(f"  round {i:2d}: {status} (integrity={ok}, cards={total}/{expected})")
    print(f"\n{survived}/{ROUNDS} hard kills mid-review -> collection intact "
          f"(SQLite integrity OK, {expected} cards preserved, none lost or duplicated).")
    if survived != ROUNDS:
        sys.exit(1)
    print("CRASH TEST PASSED: zero corrupt collections.")


if __name__ == "__main__":
    main()
