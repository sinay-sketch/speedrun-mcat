# Speedrun (MCAT) — Build Notes: from thesis to working app

Plain-language map from the project's thesis to what's actually in this repo: what
was built, how the thesis guided each decision, and how the pre-registered
predictions turned out. *(The full BrainLift — the thesis and the interrogated
learning science behind it — is submitted separately.)*

## The thesis, in two lines
Spaced repetition (FSRS) already schedules *when* you review near-perfectly. It
says nothing about **whether a card is worth seeing** or **whether it transfers to
reasoning** — and the MCAT is ~65% reasoning. So we don't touch the scheduler; we
build the missing middle: better cards, discrimination-aware interleaving, honest
scores, and a recall→reasoning bridge.

## The one big design choice: keep the engine, build the missing middle
The thesis says a better scheduler is a dead end — FSRS already gets the *timing*
right. So I did **not** rebuild the scheduler. I forked Anki and left its Rust FSRS
engine alone. Everything I added is a **read-only** add-on: my code only *reads* the
data to compute scores; it never changes cards or the schedule. So it can't break
what works, and Undo stays safe. That single choice is the thesis in action — don't
fight the scheduler, build what it ignores.

## Two apps, one engine (desk *and* phone)
A **desktop app** and an **iPhone app** run the *exact same* Rust engine. The phone
reaches it through a thin C bridge (FFI) — the study logic is never rewritten in
Swift (which would defeat "one shared engine"). They **sync both ways** through a
self-hosted server: study on one, it shows on the other; nothing lost or
double-counted; works offline then catches up. A crash test (20 kills mid-review)
left the data intact every time.

## Pillar 1 — better cards (an AI card factory with a safety gate)
The "is the card worth seeing?" half of the thesis:
1. **Generate** a card from the student's own source text.
2. **Tie it to a named source** and check the answer is entailed by that source (no made-up facts).
3. **Judge** its quality against a rubric; only good-enough cards survive.
4. **Import** the survivors into the deck, tagged `ai::generated` so they're distinguishable.

Live-run results: 0% wrong-card rate, every kept card source-backed, judge agreement
with humans κ ≈ 0.96, and meaning-based search **+38% over keyword (BM25)**. It also
blocks prompt-injection, and the app runs fully **with AI off**. The AI is never
trusted blindly — every card earns its place before a student sees it.
*(Code: `tools/speedrun/ai/`; run: `tools/speedrun/ai/run_harness.py`, `import_approved.py`.)*

## Pillar 2 — interleaving that adds discrimination, not just spacing
The research worry (Foster 2019) is interleaving might just be spacing — which FSRS
already does. So the interleaving feature lives in the Rust engine, and the ablation
**holds spacing constant** across groups. With spacing equalized, interleaving still
improved "tell similar things apart" by **d ≈ 0.90 [0.75, 1.04]**, while blocked ≈
plain on pure recall. That's the benefit *beyond* spacing the thesis needed.
*(Code: `rslib/src/scheduler/interleave.rs`; ablation: `tools/speedrun/ablation/`.)*

## Pillar 3 — recall→reasoning bridge (honest status)
The hardest pillar: turning recall cards into AAMC passage-style reasoning. I built
the **measuring** side (the paraphrase idea is what the ablation measures), but the
full "generate real passage/application items" engine is **not** finished. Stated
plainly — it's the clearest piece of future work.

## Pillar 4 — three honest scores that know when to shut up
All three live in the Rust engine, each ranged, each with a give-up rule:
- **Memory** — predicted recall of studied cards (FSRS) + range; blank under 20 cards.
- **Performance** — Elo mastery over real review outcomes; blank under 30 reviews.
- **Readiness** — a provisional MCAT-scale number that **refuses to show** until there are ≥5 scored full-length exams.

Readiness is the honesty rule as code: when it first flashed a "525" off a tiny deck,
I caught it and made it **abstain**. The Memory model is calibrated too — when it says
80%, it really is ~80% (**ECE 0.0048**).
*(Code: `rslib/src/scheduler/{mastery,performance}.rs`; details in `MODEL_DESCRIPTIONS.md`.)*

## How the BrainLift guided the build
- **It became the plan.** Every task pointed back to a pillar and a prediction; if it didn't serve a pillar, I didn't build it.
- **The Spiky POV set priorities.** "A better scheduler is a dead end" → I spent zero time on scheduling and all of it on cards, discrimination, and honest scores.
- **Kill-thresholds kept me honest.** Each pre-registered number got a test; I reported the real result.
- **Honesty rules drove real decisions** — e.g., making Readiness abstain instead of showing a confident fake number.

## Did the predictions hold? (scoreboard)
| Pre-registered prediction | Threshold | Measured | Verdict |
|---|---|---|---|
| Interleaving beats spacing-matched blocked on discrimination | ≥ d ~0.3 | **d = 0.90** [0.75, 1.04], spacing held constant | ✅ held |
| AI card usable rate | ≥ 80% (beat ~64% raw-GPT) | **100%** usable | ✅ held |
| Source faithfulness | ≥ 95% entailed | **100%** (24/24) | ✅ held |
| Calibration | ECE ≤ 0.05 | **ECE 0.0048** | ✅ held |
| Retrieval beats a simpler baseline | beat BM25 | dense **+38%** over BM25 | ✅ held (dense arm; reported honestly) |
| Give-up gate | abstain without ≥5 full-lengths | Readiness **abstains** | ✅ implemented |
| Paraphrase test (recall vs reworded) | positive, not huge, with elaboration | measured in the ablation; full reworded-item test on real cards **not built** | ◐ partial (honest) |

## How this achieved the goal
The goal was to **own the middle** — between "great scheduling on bloated cards" and
"great reasoning with weak scheduling." I stacked four things on one engine: keep FSRS
(scheduling) + a card-quality factory (better cards) + spacing-controlled interleaving
(discrimination) + three honest scores (know where you stand). The real differentiator
is **honesty**: ranges instead of fake certainty, and scores that go blank when data is
thin — the direct rebuttal to tools that show a confident number they can't back up.
Proven with code + tests: the engine change, both apps, sync, the three scores, the
AI-safety numbers, calibration. Shown by simulation (a weekend can't run a multi-week
human study, exactly as the BrainLift warned): the interleaving benefit and the
calibration curve — both labeled as simulated.

## Honest limits
- The **reasoning-bridge** pillar (real AAMC passage items) is the least-finished — top future work.
- The **ablation and calibration** are literature-grounded simulations, not human trials — labeled as such.
- The **iPhone build** runs on the Simulator (no cable for a device install); a sideload path is included but optional.
- **AI cards enter the deck via a maintainer-run script**, not an in-app button — the safety gate is the graded part; the button is future polish.

## Where to see it in the repo
- **Engine change:** `rslib/src/scheduler/{mastery,performance,interleave}.rs`, `rslib/ffi/`, `proto/anki/scheduler.proto`
- **Apps:** `ios/SpeedrunMCAT/`, `qt/aqt/speedrun.py`
- **Tests + numbers:** `proof/` (see `proof/README.md`, a requirement→file index); run all: `bash tools/speedrun/run_all_tests.sh`
- **Docs:** `SPEEDRUN.md` (README), `MODEL_DESCRIPTIONS.md`
- **Installer:** Releases ▸ [v1.0-speedrun](https://github.com/sinay-sketch/speedrun-mcat/releases/tag/v1.0-speedrun)
