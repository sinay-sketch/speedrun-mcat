# Speedrun — an MCAT study app built on Anki

**Exam: MCAT** (scored 472–528; four sections each 118–132).

Speedrun is a fork of [Anki](https://apps.ankiweb.net) (© Ankitects Pty Ltd and contributors)
that turns it into an MCAT study system: a **desktop app** and an **iOS companion** that share
**one Rust engine** and sync both ways, a **three-score dashboard** (Memory / Performance /
Readiness) with honest ranges and a give-up rule, a **discrimination-aware interleaving**
feature, and an **AI card-quality harness** with source-tracing, held-out evals, and safety
checks. The thesis is in `../BrainLift_v2_Enhanced.md` (summary: `../BrainLift_v2_Summary.pdf`).
**See [`BUILD_NOTES.md`](BUILD_NOTES.md)** for a plain-language map from the thesis to what's built here + the pre-registered predictions scoreboard.

## License & credit
Licensed under the **GNU AGPL, v3 or later** (same as upstream Anki), portions BSD-3 (see
`CONTRIBUTORS`). All original Anki code and trademarks belong to **Ankitects Pty Ltd and
contributors**. Independent, unaffiliated fork for the Alpha AI Engineering "Speedrun" project.
Upstream: https://github.com/ankitects/anki · Base: Anki **v26.05**.

---

## Architecture (two apps, one engine)
```
              ┌───────────────────────── shared Rust core (rslib) ─────────────────────────┐
              │  scheduling · FSRS · storage · sync · NEW: mastery / performance /          │
              │  readiness / interleave  (all read-only aggregates, unit-tested)            │
              └───────▲───────────────────────────────▲──────────────────────────▲─────────┘
       protobuf/PyO3   │                    C ABI (rslib/ffi)                      │ HTTP sync
              ┌────────┴────────┐               ┌───────┴────────┐        ┌────────┴─────────┐
              │ Desktop (Qt)    │               │ iOS (SwiftUI)  │        │ anki-sync-server │
              │ qt/aqt/…        │◀── two-way sync ──▶ AnkiRust.xcframework │ (self-hosted)    │
              └─────────────────┘               └────────────────┘        └──────────────────┘
```
The Rust change ships to **both** apps because they share `rslib`. The mobile side reimplements
**no** scheduling logic (it calls the engine over a thin C FFI) — per the spec, rewriting the
scheduler in Swift/JS would not count.

## The Rust-core change (all read-only ⇒ undo-safe, no corruption risk)
| Module | What it adds | Tests |
|---|---|---|
| `rslib/src/scheduler/mastery.rs` | `MasteryForDeck` — mean FSRS retrievability + Poisson-binomial 95% band + give-up (<20 cards). Wired as an RPC in `proto/anki/scheduler.proto` + `service/mod.rs`. | 4 |
| `rslib/src/scheduler/performance.rs` | `performance_for_deck` (online **Elo** over the revlog) + `readiness_for_deck` (transparent link → MCAT 472–528; **abstains** without full-lengths). | 5 |
| `rslib/src/scheduler/interleave.rs` | `interleave_by_topic` — discrimination-aware session composition (round-robin across confusable topics). | 3 |
| `rslib/ffi/` | C ABI (`speedrun_open/answer/next_card/sync/deck_counts/mastery/performance/readiness/…`) → `AnkiRust.xcframework`. | via Python + Swift |

Python test calling the engine: `pylib/tests/test_mastery.py`. **12 Rust unit tests + 1 Python test.**

---

## Build & run

### Desktop
**Prebuilt installer:** [Releases ▸ v1.0-speedrun](https://github.com/sinay-sketch/speedrun-mcat/releases/tag/v1.0-speedrun) → the macOS `.dmg` (macOS 13+, Apple Silicon; ad-hoc signed, so right-click ▸ Open on first launch). Or build it yourself:
```bash
just run                 # dev run
just check               # fmt + lint + all tests (before submitting)
tools/build-installer    # -> .dmg in out/installer/dist/ (macOS 13+)
```

### iOS companion (Simulator)
```bash
bash ios/build_xcframework.sh   # cross-compile rslib/ffi → AnkiRust.xcframework (device + sim)
bash ios/run_sim.sh             # build + launch in the iOS Simulator
# real-device sideload (optional, free Apple ID): bash ios/run_device.sh
```

### Self-hosted sync server
```bash
SYNC_USER1=test:test SYNC_BASE=/tmp/speedrun_syncbase SYNC_HOST=127.0.0.1 SYNC_PORT=8080 \
  cargo run -p anki-sync-server
```

### AI harness (needs an OpenAI key only for live generation/judging)
```bash
python3 -m venv tools/speedrun/ai/.venv
tools/speedrun/ai/.venv/bin/pip install -r tools/speedrun/ai/requirements.txt
OPENAI_API_KEY=… tools/speedrun/ai/.venv/bin/python tools/speedrun/ai/run_harness.py --gen-chunks 8
```
The app runs fully **with AI off** — scores are pure-Rust/FSRS; the AI-off card path is the
50 pre-authored gold cards + BM25 retrieval.

To actually put vetted AI cards into the deck (authoring-time; run by the maintainer, never
by the app during review):
```bash
OPENAI_API_KEY=… PYTHONPATH=out/pylib out/pyenv/bin/python tools/speedrun/ai/import_approved.py --gen-chunks 6
```
It generates → keeps only cards **entailed by their named source AND judged ≥ T2** → adds them
via `col.add_note` tagged `ai::generated` / `source::…` / `tier::…` → syncs up, so both apps
show them as normal review cards you can tell apart. Every AI card a student sees passed the
gate first.

---

## The three scores (each ranged, each with a give-up rule)
- **Memory** = mean FSRS predicted recall of studied cards + 95% band. Abstains < 20 cards.
- **Performance** = online Elo mastery of the deck from review outcomes; band narrows with #reviews. Abstains < 30 reviews.
- **Readiness** = transparent link of Memory + Performance → MCAT 472–528. **Abstains** (shows "needs full-length exams") until ≥ 5 scored full-lengths — it never reports a confident number off a small deck.

## Reproducible tests (one command each; deterministic)
```bash
cargo test -p anki scheduler::mastery scheduler::performance scheduler::interleave   # 12 Rust tests
PYTHONPATH=out/pylib out/pyenv/bin/python tools/speedrun/sync_conflict_test.py        # 10+10 offline merge + conflict
tools/speedrun/ai/.venv/bin/python tools/speedrun/ai/leakage.py                       # leakage assertion
tools/speedrun/ai/.venv/bin/python tools/speedrun/scoring/calibration.py              # ECE + reliability diagram
tools/speedrun/ai/.venv/bin/python tools/speedrun/ablation/interleaving_ablation.py   # pre-registered ablation
```
Evidence + numbers: **`proof/`** (see `proof/README.md`, which maps every requirement to a file).

## Touched files (Speedrun additions vs. upstream)
Full list: `git diff --name-status 8127fd248..HEAD`. Highlights:
- **Rust:** `rslib/src/scheduler/{mastery,performance,interleave}.rs`, `rslib/src/scheduler/{mod,service/mod}.rs`, `rslib/ffi/`, `proto/anki/scheduler.proto`
- **Desktop:** `qt/aqt/speedrun.py` (Tools ▸ Memory Score + auto-sync-on-deck-list), `qt/aqt/main.py`
- **iOS:** `ios/SpeedrunMCAT/` (SwiftUI app, `anki_ffi.h`, `project.yml`), `ios/build_xcframework.sh`, `ios/run_sim.sh`
- **Tooling/tests:** `tools/speedrun/` (deck builder, sync tests, AI harness, calibration, ablation), `pylib/tests/test_mastery.py`
- **Docs/proof:** `SPEEDRUN.md`, `proof/`, `mcat_starter.apkg`
