# Speedrun (MCAT) — Friday proof bundle

Each Friday requirement mapped to the file(s) here that prove it. All numbers are
reproducible from the code in this repo. Screenshots and the demo video live
outside the repo; the phone→desktop sync **recording** is submitted separately.

## AI
| Requirement | Proof file(s) |
|---|---|
| 1. Short note: what AI I built, why, what I skipped | `AI Note.docx` |
| 2. Every AI output traces to a named source | `harness_live_run.txt` §6 (entailment **24/24 = 100%**); code `tools/speedrun/ai/{generate,entailment}.py`, sources in `tools/speedrun/ai/corpus/corpus.jsonl` |
| 3. Eval before students see it: accuracy + wrong-answer rate on held-out, with a cutoff | `harness_live_run.txt` §6–8 (**wrong-answer rate 0%**, usable **100%**, judge **κ=0.958** on a held-out gold+bad set); `ai_report_live.json`; cutoff = *entailed AND tier ≥ T2* |
| 4. Beats a simpler method (keyword/vector) | `harness_live_run.txt` §1 (**BM25 0.723 vs dense 1.000, +38%**); `ai_report_live.json` retrieval block |
| 5. App still scores with AI off | `harness_live_run.txt` §4 (AI-OFF path); the three scores are computed in Rust with no AI |

## Mobile
| Requirement | Proof file(s) |
|---|---|
| 6. Two-way sync, no lost/double-counted | `sync_conflict_test_results.txt` (**PASS #1: 20/20 both, revlog 20/20**); `README_sync.md` (engine-level) + `README_desktop_gui_sync.md` (real desktop GUI ↔ phone); script `sync_conflict_test.py` |
| 7. Offline review, then syncs on reconnect | same `sync_conflict_test.py` / `sync_conflict_test_results.txt` (reviews made offline, then synced) |
| 8. Phone shows the three scores, ranged, give-up rule | `three_scores_output.txt` (live values with ranges) + `README_three_scores.md`; code `rslib/src/scheduler/{mastery,performance}.rs` (8 Rust tests) |

## Proof
| Requirement | Proof file(s) |
|---|---|
| 9a. Eval numbers + baseline comparison | `harness_live_run.txt`, `ai_report_live.json` |
| 9b. Recording: phone review → appears on desktop after sync | *submitted separately (screen recording)* |

## Reproduce
- AI harness: `OPENAI_API_KEY=… tools/speedrun/ai/.venv/bin/python tools/speedrun/ai/run_harness.py --gen-chunks 8` (offline parts need no key).
- Sync test: start a fresh `anki-sync-server`, then `PYTHONPATH=out/pylib out/pyenv/bin/python tools/speedrun/sync_conflict_test.py`.
- Rust score tests: `cargo test -p anki scheduler::mastery scheduler::performance`.
