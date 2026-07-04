# Speedrun AI card-quality harness

Pillar 1 of the BrainLift: **fix the card, not the scheduler.** This harness
generates atomic, source-traced MCAT flashcards and, crucially, *checks* them —
every AI claim is tied to a named source, evaluated on a held-out set, and made
to beat a simpler baseline. The study app runs fine with the whole harness OFF.

## Run

```bash
# one-time
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python build_datasets.py          # builds corpus + queries + gold (deterministic)

# reproducible, no API key needed:
.venv/bin/python run_harness.py

# full live pipeline (generation + judge + entailment + red-team):
OPENAI_API_KEY=sk-... .venv/bin/python run_harness.py --gen-chunks 8
```

## What it checks (maps to the rubric's "AI checking / safety" 15%)

| Stage | File | Needs key? | What it proves |
|---|---|---|---|
| 1. Retrieval: beat a baseline | `retrieval.py` | no (dense arm: yes) | BM25 vs TF-IDF vs hybrid RRF on 25 held-out queries, real nDCG@10 / Recall@k / MRR |
| 2. Injection defense | `injection.py` | no (red-team: yes) | spotlighting + datamarking wrap untrusted source; embedded attacks are blocked |
| 3. Entailment gate | `entailment.py` | proxy no / NLI yes | every card must be entailed by its cited source; target ≥ 95% |
| 4. AI-OFF path | `run_harness.py` | no | 50 pre-authored gold cards + BM25 keep the app fully working |
| 5. Two-stage generation | `generate.py` | yes | target-selection → Woźniak-rule formulation → self-refine |
| 6. LLM-as-judge (T0–T3) | `judge.py` | yes | quality tiers; usable (T2+T3) rate; **Cohen's κ** vs human labels |

## Datasets (all in-repo, deterministic)

- `corpus/corpus.jsonl` — 30 named MCAT source chunks (biochem over-weighted, as on the real exam).
- `gold/queries.jsonl` — 25 held-out queries with relevance judgments (qrels), deliberately *paraphrased* (low lexical overlap) so keyword search is genuinely challenged.
- `gold/gold_cards.jsonl` — **50 human-authored gold cards** (judge calibration + the AI-OFF deck).
- `gold/calib_bad.jsonl` — 15 deliberately-bad cards (wall-of-text backs, multi-blank enumerations, factual errors) labeled *not usable*, so the judge's κ is measured against a real mix.

## Honest baseline numbers (offline, no key — reproduce exactly)

```
method                           nDCG@10  Recall@1  Recall@3  Recall@5     MRR
BM25 (lexical baseline)            0.723     0.560     0.720     0.760   0.666
Vector (TF-IDF cosine)             0.731     0.560     0.720     0.800   0.676
Hybrid RRF (BM25+TF-IDF)           0.723     0.560     0.720     0.760   0.666
```

On paraphrased queries BM25 already misses ~44% at rank 1 (Recall@1 = 0.56). Two
*lexical* methods (BM25, TF-IDF) barely differ, so fusing them adds little — this
is the honest result. The real gain comes from the **dense OpenAI-embeddings
arm** (semantic match to paraphrases), which the harness adds and reports when a
key is present. Per the BrainLift's own rule: if BM25 were to win on this corpus,
we would ship BM25 and say so.

The offline entailment proxy passes 40/50 gold cards (80%) — it is a coarse
lexical fallback (short answers like "the anode" share few words with a full
paragraph); the graded ≥95% number is the **LLM NLI gate**.

## Provider

Live calls use **OpenAI** (`llm.py`; `SPEEDRUN_GEN_MODEL` default `gpt-4o-mini`,
`SPEEDRUN_JUDGE_MODEL` default `gpt-4o`). The client is isolated to one file so
the backend can be swapped.
