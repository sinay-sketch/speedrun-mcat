# Real desktop-GUI ⟷ phone two-way sync (the actual Anki app, not just the FFI peer)

This proves the *installed Anki desktop app* and the iOS phone app sync with each
other through one self-hosted server, on the shared Rust engine — using each
app's own Sync UI. Your personal `User 1` / AnkiWeb profile was left untouched;
a separate `Speedrun` profile was created for this (prefs21.db backed up first to
`anki_config_backup_*`).

## Setup (non-destructive)
- New desktop profile **"Speedrun"** pointed at the self-hosted server
  (`customSyncUrl=http://127.0.0.1:8080/`, `syncUser=test`, **no stored token**,
  auto-sync **off**). Your `User 1` AnkiWeb profile is unchanged.
- Its collection was seeded by a real full-download from the server, so it started
  identical to the phone (46 cards, 13 reviewed). Verified: desktop and server
  byte-match — same `crt`, `scm`, `usn=8`, `last_sync`.

## The round-trip (screenshots in this folder)
1. `desktop_speedrun_profile.png` — Anki titled **"Speedrun - Anki"**, MCAT deck
   shows New 33 / Learn 11 (= the phone's shared state).
2. `desktop_sync_login.png` → `desktop_after_login.png` — pressed Anki's Sync (Y),
   logged in as `test`/`test` against the local server; login cleared with no error.
   Verified server-side: `usn=8`, `reviewed=13`, identical to the desktop.
3. Reviewed ~23 cards on the **real desktop GUI** (`desktop_study_card.png`), then
   synced. Server went **reviewed 13 → 25, revlog 17 → 40, usn → 10** — the desktop's
   reviews landed on the server.
4. `phone_synced_from_desktop.png` — the phone synced (same `speedrun_sync` FFI its
   button uses) and now shows **Memory 100% (95% range 99–100%), across 25 of 46
   cards** — up from "Not enough data yet / 13 of 46". Crossing the 20-card
   give-up threshold happened *because of the reviews done on the desktop*.

Phone collection after: `reviewed=25/46, revlog=40` — matches the server exactly.

## Honest notes
- Memory reads 100% because every reviewed card was rated Good/Easy, so FSRS
  retrievability is ~1.0 immediately after review. That is expected, not a bug;
  it will decay over time and the band will widen.
- The `Speedrun` profile on disk stores **no sync token** (as requested); Anki
  holds a session token in memory only for the running app. Can be cleared on
  request.
- The engine-level sync correctness (10+10 offline merge + same-card conflict) is
  proven separately and reproducibly in `README_sync.md` / `sync_conflict_test.py`.
