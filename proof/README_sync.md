# Friday deliverable — phone ↔ desktop two-way sync (the 70% hard-cap item)

Two apps, **one shared Anki Rust engine**, real two-way sync with correct
conflict resolution. Everything below runs the *same* Rust sync code the
desktop app uses, reached from iOS through the `anki-ffi` C ABI
(`speedrun_sync`). No scheduler/sync logic was reimplemented in Swift.

## 1. Rigorous, reproducible engine-level test — `sync_conflict_test.py`

Self-hosted `anki-sync-server` on `127.0.0.1:8080`; two collections
("desktop" + "phone") driven through the FFI. See
`sync_conflict_test_results.txt` (full run) — both pass:

- **PASS #1 (the required 10+10 offline merge):** desktop reviews 10 cards and
  the phone reviews 10 *different* cards while offline → sync → **20 reviewed on
  both, revlog = 20/20 on both.** Nothing lost, nothing double-counted.
- **PASS #2 (same-card conflict):** the same card is reviewed offline on both
  (desktop = Again earlier, phone = Easy later) → sync →
  **all three (desktop, phone, server) converge to ONE winner = Easy (the later
  write)**, and **both reviews are preserved in the append-only revlog** (2 rows).

**Conflict rule (documented):** card scheduling state is last-writer-wins by the
sync order settled on the server, with card modification time as the tiebreak;
the review log (`revlog`) is append-only, so every review from every device is
merged and kept (Anki's USN + graves model). No review is ever destroyed by a
conflict — only the *current card state* resolves to a single winner.

Re-run: start a fresh server, then
`PYTHONPATH=out/pylib out/pyenv/bin/python tools/speedrun/sync_conflict_test.py`.

## 2. Same sync, driven from the iOS app (app-level, on the simulator)

The phone app has a **"Sync with desktop"** button (and an editable Sync-server
panel) that calls `speedrun_sync` on the shared engine. Screenshots:

1. `ios_home_with_sync.png` — Home with the Sync button; phone has 8 reviewed cards.
2. `ios_sync_tapped.png` — after tapping Sync against an empty server:
   **"Uploaded to server ✓"** (full upload seeds the server with the phone's
   collection). → proves phone → server.
3. (desktop peer) `sync_desktop_peer.py` full-downloads the phone's collection
   (**"received 46 cards from the phone; 8 already have review history"** →
   proves phone → desktop), reviews 5 previously-untouched cards, syncs up → 13.
4. `ios_sync_downloaded.png` — phone taps Sync again: **"In sync ✓"** and the
   Memory readout now shows **"13 of 46 cards have review history"** (was 8),
   i.e. it downloaded the desktop's 5 reviews. → proves desktop → phone.

Two-way, end to end, at the app level. Reproduce with `ios/run_sim.sh` (build +
launch), then the two scripts above.
