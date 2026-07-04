# Three honest, ranged scores on the phone (Memory / Performance / Readiness)

`phone_three_scores.png` — the phone home screen now shows all three scores, each
with a 95% range and a give-up rule, all computed in the **shared Rust engine**.

| Score | Value (example) | What it is | Where it's computed | Give-up rule |
|---|---|---|---|---|
| **Memory** | 99% (95–100%) | Mean FSRS predicted recall + Poisson-binomial band | `rslib` `mastery_for_deck` | abstains < 20 cards with a memory state |
| **Performance** | 89% (83–93%) | Online **Elo** over review history (Again=loss, Hard/Good/Easy=win) → P(correct vs avg card); band narrows with #reviews | `rslib` `performance_for_deck` | abstains < 30 graded reviews |
| **Readiness** | 525 (521–527) | Transparent monotone link of Memory+Performance → MCAT 472–528, widened band | `rslib` `readiness_for_deck` | **provisional always** (a confident score needs scored full-length exams); abstains if Memory or Performance is insufficient |

## How the numbers are honest
- All three are **read-only** aggregates in the Rust core (no mutation, no undo/corruption risk).
- Each carries a **range**, not just a point.
- Each follows the **give-up rule** (shows "—" + what's needed when data is thin).
- Readiness is deliberately **never labeled confident** — the app states it needs full-length exams, matching the BrainLift's hard gate against fake readiness.

## Verification (Rust unit tests, all pass)
`rslib/src/scheduler/performance.rs`:
- `expected_is_symmetric_and_monotonic` — Elo win-probability is 0.5 at equal rating, monotonic in rating.
- `elo_rewards_wins_and_punishes_losses` — a win streak raises the rating, a loss streak lowers it.
- `empty_deck_gives_up` — no reviews → Performance abstains.
- `readiness_abstains_without_enough_data` — no data → Readiness abstains and is never confident.

Run: `cargo test -p anki scheduler::performance`. (This is in addition to the 4 tests on `mastery_for_deck`.)

FFI: `speedrun_performance`, `speedrun_readiness` (JSON) over the same C ABI as Memory. Phone UI: `ScoreCard` row in `SpeedrunMCATApp.swift`.
