# Three honest, ranged scores on the phone (Memory / Performance / Readiness)

`phone_three_scores.png` — the phone home screen now shows all three scores, each
with a 95% range and a give-up rule, all computed in the **shared Rust engine**.

| Score | Value (example) | What it is | Where it's computed | Give-up rule |
|---|---|---|---|---|
| **Memory** | 99% (95–100%) | Mean FSRS predicted recall of **studied** cards + Poisson-binomial band | `rslib` `mastery_for_deck` | abstains < 20 cards with a memory state |
| **Performance** | 90% (85–94%) | Online **Elo** mastery of **this deck** (Again=loss, Hard/Good/Easy=win) → P(correct vs avg card); band narrows with #reviews | `rslib` `performance_for_deck` | abstains < 30 graded reviews |
| **Readiness** | **ABSTAINS** (blank) | Transparent link of Memory+Performance → MCAT 472–528 (kept only as a *transparency* estimate, e.g. ~525) | `rslib` `readiness_for_deck` | **abstains until ≥ 5 scored full-length exams** — the app ingests none yet, so it shows blank rather than an inflated number off a small deck |

## How the numbers are honest
- All three are **read-only** aggregates in the Rust core (no mutation, no undo/corruption risk).
- Each carries a **range**, not just a point, and follows the **give-up rule** (shows "—" + what's needed when data is thin).
- **Memory and Performance are scoped to the cards you've studied** — they don't claim to cover the whole deck or the whole exam.
- **Readiness abstains** rather than report a number: a small, freshly-studied flashcard deck implies a misleadingly high MCAT scaled score (~525), which is not real readiness. It stays blank until there are ≥ 5 scored full-length exams (the BrainLift's hard gate against fake readiness). The provisional estimate is still returned in the JSON (`sufficient_data:false, full_lengths:0`) purely for transparency.

## Verification (Rust unit tests, all pass)
`rslib/src/scheduler/performance.rs`:
- `expected_is_symmetric_and_monotonic` — Elo win-probability is 0.5 at equal rating, monotonic in rating.
- `elo_rewards_wins_and_punishes_losses` — a win streak raises the rating, a loss streak lowers it.
- `empty_deck_gives_up` — no reviews → Performance abstains.
- `readiness_abstains_without_enough_data` — no data → Readiness abstains and is never confident.
- `readiness_gates_on_full_lengths` — Readiness stays blank until ≥ 5 scored full-lengths (0 today).

Run: `cargo test -p anki scheduler::performance`. (This is in addition to the 4 tests on `mastery_for_deck`.)

FFI: `speedrun_performance`, `speedrun_readiness` (JSON) over the same C ABI as Memory. Phone UI: `ScoreCard` row in `SpeedrunMCATApp.swift`.
