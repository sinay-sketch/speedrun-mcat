#!/usr/bin/env python3
# License: GNU AGPL v3 or later.
"""Automated leakage assertion for the Speedrun AI harness.

The rubric zeroes a score if test data leaks into training. This script makes
the guarantees explicit and machine-checked (exit non-zero on any failure):

  L1  Held-out retrieval queries are NOT verbatim copies of the corpus chunks
      they retrieve — the retriever can't win by memorization.
  L2  The judge's calibration sets are disjoint: the 50 gold ("usable") cards
      and the 15 deliberately-bad cards share no front.
  L3  The held-out query set is disjoint from the gold-card set (we don't test
      retrieval on the same strings we judge cards with).
  L4  qrels integrity: every query's relevant chunk exists in the corpus.
  L5  (optional) If a generated-cards file is passed, none of the generated
      cards judged by the LLM are near-duplicates of the gold cards that
      CALIBRATED the judge — so the judge isn't graded on its own answer key.

Deterministic; needs no API key.
  python tools/speedrun/ai/leakage.py [generated_cards.jsonl]
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(HERE, "corpus", "corpus.jsonl")
QUERIES = os.path.join(HERE, "gold", "queries.jsonl")
GOLD = os.path.join(HERE, "gold", "gold_cards.jsonl")
CALIB = os.path.join(HERE, "gold", "calib_bad.jsonl")

_STOP = set("a an the of to in on for and or is are was were be as by with at from that this "
            "which what who whom whose when where why how it its into their than then".split())
_WORD = re.compile(r"[a-z0-9]+")


def content(s):
    return {w for w in _WORD.findall(s.lower()) if w not in _STOP and len(w) > 1}


def rows(path):
    return [json.loads(l) for l in open(path)]


def containment(a, b):
    """|a ∩ b| / |a| — how much of a is covered by b (1.0 => a is a subset copy)."""
    return len(a & b) / len(a) if a else 0.0


def main():
    corpus = rows(CORPUS)
    queries = rows(QUERIES)
    gold = rows(GOLD)
    calib = rows(CALIB)
    chunks = {c["id"]: content(c["text"]) for c in corpus}
    chunk_text = {c["id"]: c["text"].lower() for c in corpus}
    fails = []

    # L1: no query is a verbatim / near-copy of a corpus chunk.
    QUERY_COPY_MAX = 0.80
    worst_q, worst_v = None, 0.0
    for q in queries:
        qc = content(q["query"])
        for cid, cwords in chunks.items():
            v = containment(qc, cwords)  # fraction of the query's words that appear in the chunk
            if v > worst_v:
                worst_v, worst_q = v, (q["qid"], cid)
        # also flag exact-substring copies
        if any(q["query"].lower().strip(" ?.") in t for t in chunk_text.values()):
            fails.append(f"L1: query {q['qid']} is a verbatim substring of a corpus chunk")
    print(f"L1 retrieval queries not copied from corpus: max word-containment {worst_v:.2f} "
          f"(query {worst_q[0]} vs {worst_q[1]}), threshold {QUERY_COPY_MAX}")
    if worst_v >= QUERY_COPY_MAX:
        fails.append(f"L1: query {worst_q[0]} overlaps chunk {worst_q[1]} at {worst_v:.2f} ≥ {QUERY_COPY_MAX}")

    # L2: gold (usable) and bad calibration cards are disjoint by front.
    gold_fronts = {g["front"].strip().lower() for g in gold}
    bad_fronts = {b["front"].strip().lower() for b in calib}
    overlap = gold_fronts & bad_fronts
    print(f"L2 gold({len(gold_fronts)}) vs bad({len(bad_fronts)}) calibration fronts disjoint: "
          f"{'yes' if not overlap else 'NO — ' + str(overlap)}")
    if overlap:
        fails.append(f"L2: gold/bad share fronts: {overlap}")

    # L3: held-out queries are disjoint from gold-card fronts.
    q_texts = {q["query"].strip().lower() for q in queries}
    qg = q_texts & gold_fronts
    print(f"L3 query set disjoint from gold-card fronts: {'yes' if not qg else 'NO — ' + str(qg)}")
    if qg:
        fails.append(f"L3: queries overlap gold fronts: {qg}")

    # L4: qrels integrity.
    ids = set(chunks)
    missing = [(q["qid"], r) for q in queries for r in q["relevant"] if r not in ids]
    print(f"L4 qrels reference only real chunks: {'yes' if not missing else 'NO — ' + str(missing)}")
    if missing:
        fails.append(f"L4: dangling qrels: {missing}")

    # L5 (optional): generated cards judged must not be near-copies of gold cards.
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        gen = rows(sys.argv[1])
        gold_content = [content(g["front"] + " " + g["back"]) for g in gold]
        DUP_MAX = 0.85
        worst = 0.0
        for c in gen:
            gc = content(c.get("front", "") + " " + c.get("back", ""))
            for goldc in gold_content:
                worst = max(worst, containment(gc, goldc))
        print(f"L5 generated cards not near-duplicates of gold: max containment {worst:.2f} (< {DUP_MAX})")
        if worst >= DUP_MAX:
            fails.append(f"L5: a generated card is a near-duplicate of a gold card ({worst:.2f})")
    else:
        print("L5 (generated-vs-gold) skipped: pass a generated_cards.jsonl to enable.")

    print()
    if fails:
        print("LEAKAGE CHECK FAILED:")
        for f in fails:
            print("  -", f)
        sys.exit(1)
    print("LEAKAGE CHECK PASSED: no test data leaks into training/eval inputs.")


if __name__ == "__main__":
    main()
