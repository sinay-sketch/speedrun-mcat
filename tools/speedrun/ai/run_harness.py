#!/usr/bin/env python3
# License: GNU AGPL v3 or later.
"""One-command AI card-quality harness. Reproducible.

  python tools/speedrun/ai/run_harness.py            # runs everything possible
  python tools/speedrun/ai/run_harness.py --gen-chunks 8

Without OPENAI_API_KEY it runs the fully offline, reproducible parts:
  - retrieval "beat a baseline" (BM25 vs TF-IDF vs hybrid RRF)
  - injection-defense datamarking (structural)
  - offline entailment proxy on the gold set
  - AI-OFF path (the 50 pre-authored gold cards load as a usable deck)

With OPENAI_API_KEY it ALSO runs the live pipeline and reports real numbers:
  - retrieval gains a dense OpenAI-embeddings arm + BM25+dense hybrid
  - two-stage generation + self-refine over N source chunks
  - LLM-as-judge tier distribution + Cohen's kappa calibration vs the labeled set
  - LLM source-entailment gate (target >= 95%)
  - injection red-team (attacks embedded in sources must be blocked)

Writes a machine-readable report to ai_report.json.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import retrieval  # noqa: E402
import injection  # noqa: E402
import entailment  # noqa: E402
from llm import have_key, GEN_MODEL, JUDGE_MODEL  # noqa: E402


def load_jsonl(name):
    return [json.loads(l) for l in open(os.path.join(HERE, name))]


def hr(title):
    print("\n" + "=" * 72 + f"\n{title}\n" + "=" * 72)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gen-chunks", type=int, default=8,
                    help="how many source chunks to generate from (needs a key)")
    args = ap.parse_args()

    report = {"has_key": have_key(), "gen_model": GEN_MODEL, "judge_model": JUDGE_MODEL}
    sources = {c["id"]: c["text"] for c in load_jsonl("corpus/corpus.jsonl")}
    gold = load_jsonl("gold/gold_cards.jsonl")

    # 1) RETRIEVAL -- beat a simpler baseline (offline; dense arm added if key).
    hr("1. Retrieval: beat a simpler baseline")
    ret = retrieval.run()
    report["retrieval"] = ret

    # 2) INJECTION DEFENSE (structural, offline).
    hr("2. Prompt-injection defense (spotlighting / datamarking)")
    demo = injection.datamark("Glycolysis nets 2 ATP per glucose. " + injection.ATTACKS[0][1])
    print("datamarking wrapper applied:", injection.has_datamarking(demo))
    print(f"{len(injection.ATTACKS)} attack templates staged for the red-team.")
    report["injection_structural_ok"] = injection.has_datamarking(demo)

    # 3) OFFLINE ENTAILMENT PROXY on gold (reproducible smoke test of the gate).
    hr("3. Source-entailment gate (offline lexical proxy on gold)")
    for g in gold:
        g["span"] = sources[g["source_id"]]
    off = entailment.gate(gold, sources, llm=None)
    print(f"offline proxy: {off['kept']}/{off['n']} gold cards pass "
          f"({off['entailed_rate']:.1%}); coarse fallback -- real gate is the LLM NLI below.")
    report["entailment_offline"] = {"kept": off["kept"], "n": off["n"], "rate": off["entailed_rate"]}

    # 4) AI-OFF path: the app still works with AI disabled.
    hr("4. AI-OFF path")
    print(f"AI disabled -> deck = {len(gold)} pre-authored gold cards + BM25 retrieval. "
          f"No generation, no network. The app studies and scores normally.")
    report["ai_off_deck_cards"] = len(gold)

    # ----- Live LLM pipeline (only with a key) -----
    if not have_key():
        hr("LIVE LLM PIPELINE -- SKIPPED (no OPENAI_API_KEY)")
        print("Set OPENAI_API_KEY to run generation + judge (kappa) + LLM entailment + red-team.")
    else:
        import generate
        import judge
        from llm import LLM
        gen_llm = LLM(model=GEN_MODEL)
        judge_llm = LLM(model=JUDGE_MODEL)
        chunks = load_jsonl("corpus/corpus.jsonl")[: args.gen_chunks]

        hr("5. Two-stage generation + self-refine")
        cards = []
        for c in chunks:
            cards.extend(generate.generate_for_chunk(gen_llm, c, max_cards=3))
        print(f"generated {len(cards)} cards from {len(chunks)} source chunks.")

        hr("6. Source-entailment gate (LLM NLI)")
        egate = entailment.gate(cards, sources, llm=judge_llm)
        print(f"entailed: {egate['kept']}/{egate['n']} ({egate['entailed_rate']:.1%}); "
              f"rejected {egate['rejected']} (target >= 95%).")
        kept = egate["kept_cards"]
        report["entailment_llm"] = {"kept": egate["kept"], "n": egate["n"], "rate": egate["entailed_rate"]}

        hr("7. LLM-as-judge: quality tiers on kept cards")
        dist = judge.tier_distribution(kept, sources, llm=judge_llm)
        print(f"tiers T0/T1/T2/T3 = {dist['tiers'][0]}/{dist['tiers'][1]}/"
              f"{dist['tiers'][2]}/{dist['tiers'][3]}; usable (T2+T3) = {dist['usable_rate']:.1%} "
              f"(target >= 80%, vs raw-LLM ~64% baseline).")
        report["generation"] = {"n": len(cards), "tiers": dist["tiers"], "usable_rate": dist["usable_rate"]}

        hr("8. Judge calibration (Cohen's kappa vs human labels)")
        cal = judge.calibrate(llm=judge_llm)
        print(f"kappa={cal['kappa']:.3f}, agreement={cal['agreement']:.1%} on {cal['n']} labeled cards; "
              f"gold kept {cal['gold_kept']}/50, bad caught {cal['bad_caught']}/15.")
        report["judge_calibration"] = cal

        hr("9. Injection red-team (attacks embedded in a source)")
        rt = injection.run_red_team(judge_llm, chunks[0])
        print(f"blocked {rt['blocked']}/{rt['attacks']} attacks ({rt['block_rate']:.0%}).")
        for d in rt["detail"]:
            print(f"  [{'BLOCKED' if d['blocked'] else 'LEAKED '}] {d['attack'][:60]}...")
        report["injection_red_team"] = {"blocked": rt["blocked"], "attacks": rt["attacks"],
                                         "block_rate": rt["block_rate"]}

    out = os.path.join(HERE, "ai_report.json")
    json.dump(report, open(out, "w"), indent=2, default=lambda o: getattr(o, "__dict__", str(o)))
    hr("REPORT")
    print(f"written -> {out}")


if __name__ == "__main__":
    main()
