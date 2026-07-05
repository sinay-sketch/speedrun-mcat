# Final demo video — shot list (target 3–5 min)

The rubric wants the video to show: a review session · the Rust change in action ·
a card synced phone→desktop · the three scores with ranges · the AI features · the
test results. Here's a shot-by-shot plan (do the action, say the line). Casual tone.

**0:00 — Intro (both apps on screen)**
- *"This is Speedrun, an MCAT app built by forking Anki. The desktop app and the iPhone app run the same Rust engine — nothing's reimplemented on the phone."*

**0:20 — Review session + the three scores (phone)**
- Open the phone app. Point at the three cards: *"Three honest scores: Memory — predicted recall, Performance — an Elo mastery from how I've actually answered, and Readiness."*
- *"Each shows a range, and if there's not enough data it says so — Readiness stays blank and says 'needs full-length exams,' because a small deck can't tell you your MCAT score. It refuses to make one up."*
- Tap **Study**, answer 2–3 cards. *"That's a real review session on the shared engine."*

**1:15 — The Rust change in action**
- Desktop: **Tools ▸ MCAT Memory Score** → the dialog shows the ranged Memory score.
- *"That score comes from a new function I added inside Anki's Rust core — `MasteryForDeck` — plus Performance and Readiness. It's read-only, so undo and your data are safe. Twelve Rust tests cover it."*
- (Optional) flash the terminal: `cargo test -p anki scheduler::mastery scheduler::performance scheduler::interleave` → 12 passed.

**2:00 — Phone → desktop sync**
- On the phone, answer a card, tap **Sync with desktop**.
- Switch to the desktop, hit **Sync** (or it auto-syncs on the deck list) → *"Same review shows up here — New/Learn/Due match, nothing lost or double-counted. Works both ways, and offline then syncs on reconnect."*

**2:45 — AI features (talk over the terminal / proof files)**
- Show `proof/harness_live_run.txt` or run the harness. *"Every AI card is tied to a named source and checked against it — 100% entailed. There's an eval that runs before you see a card: wrong-answer rate zero, with a cutoff that rejects bad ones, and the judge is calibrated to κ=0.96."*
- *"And it beats plain keyword search by 38%. But the whole app still scores with the AI switched off."*

**3:30 — Test results**
- Run `bash tools/speedrun/run_all_tests.sh` (or show its summary). *"One command runs everything — Rust tests, the 10+10 offline sync + conflict test, leakage check, memory calibration (ECE 0.005), the interleaving ablation (d=0.9), a crash test — 20 hard kills, zero corruption — and a 50k-card speed benchmark that hits every latency target."*

**4:15 — Close**
- *"Two apps, one engine, real two-way sync, three honest scores that know when to shut up, and AI that has to prove itself. Everything's reproducible and on GitHub."*

---
**Must-hit checklist:** ☐ review session ☐ Rust change ☐ phone→desktop sync ☐ three ranged scores + give-up ☐ AI (sourced / eval+cutoff / beats baseline / works off) ☐ test results.
Keep it ~4 min. The Friday clip already nails the sync + three-scores part — you can reuse that footage.
