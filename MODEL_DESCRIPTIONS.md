# Speedrun — Model Descriptions (Memory · Performance · Readiness)

Three scores, three *different* things. Each is a **read-only** aggregate computed in the
shared Rust core (`rslib/src/scheduler/{mastery,performance}.rs`), each carries a **range**,
and each has an explicit **give-up rule** — it shows *no number* when it lacks data. The
honesty rule follows the spec: we grade the steps of the bridge, not a made-up final number.

---

## 1. Memory — "how much of what I've studied would I recall right now?"
- **Input:** each studied card's FSRS memory state (stability, difficulty) + time since last review.
- **Method:** FSRS-5 forgetting curve `R(t) = (1 + (19/81)·t/S)^(−0.5)` per card (the same curve
  the browser uses), averaged over the deck. Point estimate = mean predicted recall. Band =
  95% normal approximation of a **Poisson-binomial** (variance `Σ pᵢ(1−pᵢ)/n²`).
- **Range:** e.g. *99% (95–100%)*.
- **Give-up rule:** abstains (`sufficient_data = false`) when **< 20 cards** have an FSRS memory
  state. Below that the estimate is too noisy to be honest.
- **Calibration:** FSRS-5 uses published default parameters (nothing fit to our data ⇒ every
  review is out-of-sample). Validated: **ECE = 0.0048**, Brier 0.133, full reliability diagram
  on a time split (`proof/calibration_output.txt`; `tools/speedrun/scoring/calibration.py`).
- **Code:** `rslib/src/scheduler/mastery.rs` (4 tests) · FFI `speedrun_mastery`.

## 2. Performance — "how well am I actually answering this deck?"
- **Input:** the review log (`revlog`) outcomes — `Again` = miss, `Hard/Good/Easy` = hit.
- **Method:** an **online Elo** replay (student vs. card). Per review:
  `E = 1/(1+10^((D−S)/400))`, `S += K(outcome−E)`, `D −= K(outcome−E)` (K = 24). The score =
  the student's predicted probability of answering an *average-difficulty* card, `P = E(S, D̄)`.
- **Range:** a band from rating uncertainty that **narrows with the number of reviews**
  (`σ = 400/√n`), e.g. *90% (85–94%)*.
- **Give-up rule:** abstains when **< 30 graded reviews**.
- **Scope (honesty):** this is mastery *of this deck*, from real answer outcomes — not an MCAT
  claim. Baseline to beat (future): a logistic/PFA model over {Elo, difficulty, timing}.
- **Code:** `rslib/src/scheduler/performance.rs` (`performance_for_deck`; 5 tests) · FFI `speedrun_performance`.

## 3. Readiness — "am I ready for the MCAT?" (and why it usually says *not yet*)
- **Input:** Memory + Performance, plus a count of **scored full-length exams**.
- **Method:** a **transparent monotone link** of the Memory+Performance blend onto the public
  MCAT scaled range (472–528), with a **widened band** (deliberately wider than AAMC's ±2). This
  is a linking, *not* a claim of equating.
- **Give-up rule (the important one):** Readiness **abstains** until there are **≥ 5 scored
  full-length exams**. Flashcard recall cannot substitute for a full-length, and a small,
  freshly-studied deck implies a misleadingly high score (~525 ≈ 100th percentile) that is not
  real readiness. The app ingests no full-lengths yet, so it shows **"needs full-length exams"**
  rather than a number. The provisional estimate stays in the JSON (`sufficient_data:false,
  full_lengths:0`) for transparency only. It is **never** labeled "confident."
- **Why this matters:** a confident readiness with no scored full-lengths is an auto-fail in the
  spec. A good system knows when it does not know.
- **Code:** `rslib/src/scheduler/performance.rs` (`readiness_for_deck`) · FFI `speedrun_readiness`.

---

### The give-up rule, stated plainly (per the spec's request to "write yours down")
> **No score is shown unless:** Memory has ≥ 20 cards with a memory state; Performance has ≥ 30
> graded reviews; Readiness has ≥ 5 scored full-length exams **and** sufficient topic coverage.
> When a score abstains, the app shows *why* and what to do next instead of a number.

All three are surfaced on the iOS home screen (`proof/three_scores_output.txt` shows live values)
and Memory is also in the desktop **Tools ▸ MCAT Memory Score** dialog.
