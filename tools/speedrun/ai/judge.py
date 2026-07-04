#!/usr/bin/env python3
# License: GNU AGPL v3 or later.
"""LLM-as-judge card-quality evaluation (NOT ROUGE/BLEU).

Rubric = Memory-Machines 4-tier quality with explicit failure dimensions and
Wozniak/Haladyna item-writing rules:
  T3  correct AND well-formed (atomic, minimum-information, tests understanding) -> use as-is
  T2  correct, minor issues (small edit needed)                                  -> usable
  T1  correct but poorly formed (wall-of-text, enumeration, ambiguous)           -> rework
  T0  incorrect, misleading, or unsupported by the source                        -> reject
"Usable" = T2 or T3.

Calibration: the judge scores a labeled mix (50 gold = usable, 15 calib_bad =
not-usable) and we report Cohen's kappa between judge and human labels. A high
kappa means the judge can be trusted to grade generated cards.

Needs OPENAI_API_KEY.
"""
import json
import os

from llm import LLM, JUDGE_MODEL

HERE = os.path.dirname(os.path.abspath(__file__))

JUDGE_SYS = (
    "You are a strict MCAT flashcard quality judge. Grade one card on this rubric:\n"
    "T3 = correct AND well-formed (atomic: one fact; short specific answer; unambiguous; "
    "tests understanding).\n"
    "T2 = correct with only minor issues (usable after a small edit).\n"
    "T1 = correct but poorly formed (wall-of-text back, multi-part/enumeration, ambiguous).\n"
    "T0 = incorrect, misleading, or not supported by the source.\n"
    "Judge correctness against the provided source text. Be harsh on non-atomic cards "
    "and wall-of-text/enumeration backs."
)


def judge_card(llm: LLM, card: dict, source_text: str) -> dict:
    out = llm.json(
        JUDGE_SYS,
        f"Source text:\n{source_text}\n\n"
        f"Card:\nQ: {card['front']}\nA: {card['back']}\n\n"
        'Return JSON: {"tier": 0|1|2|3, "reason": "one short sentence"}',
        model=JUDGE_MODEL,
    )
    tier = int(out.get("tier", 0))
    return {"tier": tier, "usable": tier >= 2, "reason": out.get("reason", "")}


def cohens_kappa(a: list[bool], b: list[bool]) -> float:
    n = len(a)
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    pa1 = sum(a) / n; pb1 = sum(b) / n
    pe = pa1 * pb1 + (1 - pa1) * (1 - pb1)
    return (po - pe) / (1 - pe) if pe != 1 else 1.0


def load_sources() -> dict:
    return {c["id"]: c["text"] for c in
            (json.loads(l) for l in open(os.path.join(HERE, "corpus", "corpus.jsonl")))}


def tier_distribution(cards: list[dict], sources: dict, llm: LLM | None = None) -> dict:
    llm = llm or LLM(model=JUDGE_MODEL)
    tiers = {0: 0, 1: 0, 2: 0, 3: 0}
    judged = []
    for c in cards:
        v = judge_card(llm, c, sources.get(c["source_id"], ""))
        tiers[v["tier"]] += 1
        judged.append({**c, **v})
    n = len(cards)
    usable = tiers[2] + tiers[3]
    return {"n": n, "tiers": tiers, "usable_rate": usable / n if n else 0.0, "judged": judged}


def calibrate(llm: LLM | None = None) -> dict:
    """Judge the labeled set; report Cohen's kappa vs human labels."""
    llm = llm or LLM(model=JUDGE_MODEL)
    sources = load_sources()
    gold = [json.loads(l) for l in open(os.path.join(HERE, "gold", "gold_cards.jsonl"))]
    bad = [json.loads(l) for l in open(os.path.join(HERE, "gold", "calib_bad.jsonl"))]
    human, judge = [], []
    for c in gold:
        human.append(True)
        judge.append(judge_card(llm, c, sources.get(c["source_id"], ""))["usable"])
    for c in bad:
        human.append(False)
        judge.append(judge_card(llm, c, sources.get(c["source_id"], ""))["usable"])
    k = cohens_kappa(human, judge)
    agree = sum(1 for x, y in zip(human, judge) if x == y) / len(human)
    # Where the judge disagreed with humans.
    tp = sum(1 for h, j in zip(human, judge) if h and j)
    fn = sum(1 for h, j in zip(human, judge) if h and not j)   # gold called unusable
    fp = sum(1 for h, j in zip(human, judge) if not h and j)   # bad called usable
    tn = sum(1 for h, j in zip(human, judge) if not h and not j)
    return {"n": len(human), "kappa": k, "agreement": agree,
            "gold_kept": tp, "gold_rejected": fn, "bad_passed": fp, "bad_caught": tn}


if __name__ == "__main__":
    c = calibrate()
    print(f"Judge calibration on {c['n']} labeled cards: "
          f"kappa={c['kappa']:.3f}, agreement={c['agreement']:.1%}")
    print(f"  gold kept usable {c['gold_kept']}/50, wrongly rejected {c['gold_rejected']}; "
          f"bad caught {c['bad_caught']}/15, wrongly passed {c['bad_passed']}")
