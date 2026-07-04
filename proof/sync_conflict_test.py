#!/usr/bin/env python3
# License: GNU AGPL v3 or later.
"""Reproducible two-device sync + conflict test on the SHARED Rust engine.

Uses the anki-ffi C ABI (the phone app's real sync path: speedrun_sync) to sync
two collections ("desktop" + "phone") through a self-hosted sync server, then:
  - 10 offline reviews on the phone + 10 DIFFERENT on the desktop -> sync ->
    assert all 20 land once (none lost, none double-counted);
  - the SAME card reviewed offline on both -> sync -> assert deterministic
    convergence with BOTH reviews kept in the (append-only) revlog.

Prereq: a fresh sync server running, e.g.
  SYNC_USER1=test:test SYNC_BASE=/tmp/speedrun_syncbase cargo run -p anki-sync-server
Run:
  PYTHONPATH=out/pylib out/pyenv/bin/python tools/speedrun/sync_conflict_test.py
"""
import ctypes
import os
import tempfile
import time

from anki.collection import Collection
from anki import import_export_pb2 as ie

ENDPOINT = "http://127.0.0.1:8080/"
USER, PW = "test", "test"
APKG = os.path.abspath("mcat_starter.apkg")
LIB = os.path.abspath("target/debug/libanki_ffi.dylib")

lib = ctypes.CDLL(LIB)
lib.speedrun_open.restype = ctypes.c_void_p
lib.speedrun_open.argtypes = [ctypes.c_char_p]
lib.speedrun_answer.restype = ctypes.c_int32
lib.speedrun_answer.argtypes = [ctypes.c_void_p, ctypes.c_int64, ctypes.c_uint]
lib.speedrun_sync.restype = ctypes.c_int32
lib.speedrun_sync.argtypes = [ctypes.c_char_p] * 4
lib.speedrun_close.argtypes = [ctypes.c_void_p]

SYNC_NAME = {0: "in-sync/normal", 1: "FULL UPLOAD", 2: "FULL DOWNLOAD", -1: "ERROR"}


def sync(path: str) -> int:
    return lib.speedrun_sync(path.encode(), ENDPOINT.encode(), USER.encode(), PW.encode())


def review(path: str, cids, rating: int) -> int:
    col = lib.speedrun_open(path.encode())
    assert col, f"open failed: {path}"
    n = 0
    for cid in cids:
        if lib.speedrun_answer(col, int(cid), rating) == 0:
            n += 1
        time.sleep(0.005)  # distinct millisecond revlog ids (real taps are seconds apart)
    lib.speedrun_close(col)
    return n


def stats(path: str):
    c = Collection(path)
    reviewed = sum(1 for cid in c.find_cards("deck:MCAT::*") if c.get_card(cid).reps > 0)
    revlog = c.db.scalar("select count() from revlog")
    c.close()
    return reviewed, revlog


def main() -> None:
    tmp = tempfile.mkdtemp(prefix="synctest_")
    D = os.path.join(tmp, "desktop.anki2")
    P = os.path.join(tmp, "phone.anki2")

    # Desktop: create + import the MCAT deck; capture the (sorted) card ids.
    col = Collection(D)
    opts = col._backend.get_import_anki_package_presets()
    col.import_anki_package(ie.ImportAnkiPackageRequest(package_path=APKG, options=opts))
    cids = sorted(col.find_cards("deck:MCAT::*"))
    col.close()
    print(f"desktop imported {len(cids)} cards")

    # Seed the server from desktop, then full-download to the phone.
    print("desktop first sync ->", SYNC_NAME[sync(D)])
    print("phone   first sync ->", SYNC_NAME[sync(P)])
    cp = Collection(P); phone_cards = len(cp.find_cards("deck:MCAT::*")); cp.close()
    print(f"phone has {phone_cards} cards after download")
    assert phone_cards == len(cids), "phone did not receive the deck"

    # OFFLINE: desktop reviews cids[0:10]; phone reviews cids[10:20] (disjoint).
    print("desktop offline-reviewed:", review(D, cids[0:10], 3))
    print("phone   offline-reviewed:", review(P, cids[10:20], 3))

    # Sync both ways.
    print("phone sync ->", SYNC_NAME[sync(P)])
    print("desktop sync ->", SYNC_NAME[sync(D)])
    print("phone sync ->", SYNC_NAME[sync(P)])

    dr, drl = stats(D); pr, prl = stats(P)
    print(f"AFTER MERGE  desktop: reviewed={dr} revlog={drl} | phone: reviewed={pr} revlog={prl}")
    assert dr == 20 and pr == 20, f"not all 20 reviews landed (D={dr}, P={pr})"
    assert drl == 20 and prl == 20, f"revlog lost/double-counted (D={drl}, P={prl})"
    print("PASS #1: 10 phone + 10 desktop offline reviews merged -> 20 on both, none lost/double.\n")

    # SAME-CARD CONFLICT: card X reviewed offline on both, different grades.
    # Card mtime has 1-second granularity, so separate the two reviews in time
    # to make the winner deterministic (the later write wins).
    X = int(cids[20])
    review(D, [X], 1)  # desktop: Again (earlier)
    time.sleep(1.3)
    review(P, [X], 4)  # phone: Easy (later)
    print("conflict on one card: desktop=Again (earlier), phone=Easy (later)")
    # Converge: each client that pushed a conflicting change must also pull the
    # settled state. sync(P) -> sync(D) -> sync(P) -> sync(D).
    for who, path in [("P", P), ("D", D), ("P", P), ("D", D)]:
        print(f"  sync {who} ->", SYNC_NAME[sync(path)])

    def cardstate(path):
        c = Collection(path); card = c.get_card(X)
        state = (card.reps, card.ivl, int(card.queue))
        rows = c.db.scalar("select count() from revlog where cid=?", X)
        c.close()
        return state, rows

    # An independent observer pulls the server's authoritative state.
    O = os.path.join(os.path.dirname(D), "observer.anki2")
    print("  observer sync ->", SYNC_NAME[sync(O)])
    sd, rld = cardstate(D); sp, rlp = cardstate(P); so, rlo = cardstate(O)
    print(f"card X  desktop={sd} rl={rld} | phone={sp} rl={rlp} | server(observer)={so} rl={rlo}")
    winner = "Easy (later write)" if so[1] > 0 else "Again (earlier write)"
    assert sd == sp == so, "same-card conflict did not converge across devices+server"
    assert rld == rlp == rlo == 2, f"both reviews must be kept in revlog (D={rld},P={rlp},O={rlo})"
    print(f"PASS #2: same-card conflict converged to ONE winner on all 3 = {winner}; BOTH reviews kept in revlog (append-only).")
    print("\nALL SYNC TESTS PASSED (phone<->desktop two-way sync on the shared Rust engine).")


if __name__ == "__main__":
    main()
