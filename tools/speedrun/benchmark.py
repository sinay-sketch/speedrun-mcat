#!/usr/bin/env python3
# License: GNU AGPL v3 or later.
"""50,000-card speed benchmark against the spec's latency targets, measured on the
SHARED engine via the anki-ffi C ABI (what the apps actually call).

Targets (spec):
  button press ack (answer)      p95 < 50 ms
  next card after grading         p95 < 100 ms
  dashboard first load (mastery)  p95 < 1000 ms   (aggregate over all 50k cards)

Builds a 50k-card MCAT deck once (cached), reviews a sample so the dashboard does
real FSRS work, then times each op and reports p50/p95/worst vs target.

  PYTHONPATH=out/pylib out/pyenv/bin/python tools/speedrun/benchmark.py [out.txt]
"""
import ctypes
import json
import os
import sys
import time

from anki.collection import Collection

N_CARDS = 50_000
N_WARM = 800          # cards reviewed so they have FSRS memory states
CACHE = os.path.abspath("out/bench_50k.anki2")
LIB = os.path.abspath("target/debug/libanki_ffi.dylib")
DECK = "MCAT::Speedrun Starter"


def build_collection():
    if os.path.exists(CACHE):
        c = Collection(CACHE)
        n = len(c.find_cards(f'deck:"{DECK}"'))
        c.close()
        if n >= N_CARDS:
            print(f"using cached 50k collection ({n} cards)")
            return
        os.remove(CACHE)
    print(f"generating {N_CARDS} cards (one-time)…")
    for ext in ("", "-wal", "-shm"):
        try: os.remove(CACHE + ext)
        except FileNotFoundError: pass
    col = Collection(CACHE)
    did = col.decks.id(DECK)
    col.decks.set_current(did)
    m = col.models.by_name("Basic")
    m["did"] = did
    col.models.update_dict(m)
    t0 = time.time()
    for i in range(N_CARDS):
        note = col.new_note(m)
        note.fields[0] = f"MCAT question {i}: term {i}?"
        note.fields[1] = f"answer {i}"
        col.add_note(note, did)
        if i % 10000 == 0 and i:
            print(f"  {i}/{N_CARDS} ({time.time()-t0:.0f}s)")
    # enable FSRS so reviewed cards get memory states (matches the app)
    conf = col.decks.config_dict_for_deck_id(did)
    col._backend.update_deck_configs  # noqa (ensure attr exists)
    try:
        col.set_config("fsrs", True)
    except Exception:
        pass
    col.close()
    print(f"generated in {time.time()-t0:.0f}s -> {CACHE}")


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p / 100.0 * (len(xs) - 1))))]


def main():
    build_collection()
    lib = ctypes.CDLL(LIB)
    lib.speedrun_open.restype = ctypes.c_void_p; lib.speedrun_open.argtypes = [ctypes.c_char_p]
    lib.speedrun_deck_id.restype = ctypes.c_int64; lib.speedrun_deck_id.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    lib.speedrun_next_card.restype = ctypes.c_void_p; lib.speedrun_next_card.argtypes = [ctypes.c_void_p]
    lib.speedrun_answer.restype = ctypes.c_int32; lib.speedrun_answer.argtypes = [ctypes.c_void_p, ctypes.c_int64, ctypes.c_uint]
    lib.speedrun_mastery.restype = ctypes.c_void_p; lib.speedrun_mastery.argtypes = [ctypes.c_void_p, ctypes.c_int64]
    lib.speedrun_deck_counts.restype = ctypes.c_void_p; lib.speedrun_deck_counts.argtypes = [ctypes.c_void_p, ctypes.c_int64]
    lib.speedrun_free_string.argtypes = [ctypes.c_void_p]; lib.speedrun_close.argtypes = [ctypes.c_void_p]

    def take(p): s = ctypes.cast(p, ctypes.c_char_p).value.decode(); lib.speedrun_free_string(p); return s

    col = lib.speedrun_open(CACHE.encode())
    did = lib.speedrun_deck_id(col, DECK.encode())

    # warm up FSRS memory states + time the per-card ops (next_card, answer).
    t_next, t_answer = [], []
    for _ in range(N_WARM):
        t = time.perf_counter(); j = json.loads(take(lib.speedrun_next_card(col))); t_next.append((time.perf_counter()-t)*1000)
        if "card_id" not in j:
            break
        t = time.perf_counter(); lib.speedrun_answer(col, int(j["card_id"]), 3); t_answer.append((time.perf_counter()-t)*1000)

    # dashboard load: the mastery aggregate over all 50k cards.
    t_dash, t_counts = [], []
    for _ in range(20):
        t = time.perf_counter(); take(lib.speedrun_mastery(col, did)); t_dash.append((time.perf_counter()-t)*1000)
        t = time.perf_counter(); take(lib.speedrun_deck_counts(col, did)); t_counts.append((time.perf_counter()-t)*1000)
    lib.speedrun_close(col)

    rows = [
        ("answer (button ack)", t_answer, 50),
        ("next card", t_next, 100),
        ("dashboard load (mastery, 50k)", t_dash, 1000),
        ("deck counts (New/Learn/Due, 50k)", t_counts, 500),
    ]
    lines = []
    def pr(s=""): lines.append(s); print(s)
    pr(f"50k-card benchmark on the shared engine (anki-ffi). reviews sampled: {len(t_answer)}\n")
    pr(f"{'operation':34}{'p50':>9}{'p95':>9}{'worst':>9}{'target':>10}  result")
    pr("-" * 80)
    all_ok = True
    for name, xs, target in rows:
        if not xs:
            pr(f"{name:34}{'—':>9}"); continue
        p50, p95, worst = pct(xs, 50), pct(xs, 95), max(xs)
        ok = p95 < target
        all_ok &= ok
        pr(f"{name:34}{p50:8.2f}m{p95:8.2f}m{worst:8.2f}m{target:9d}m  {'PASS' if ok else 'FAIL'}")
    pr("\n(all times in ms; p95 vs target)")
    pr("BENCHMARK " + ("PASSED — all latency targets met at 50k cards." if all_ok else "had misses (see above)."))
    if len(sys.argv) > 1:
        open(sys.argv[1], "w").write("\n".join(lines) + "\n")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
