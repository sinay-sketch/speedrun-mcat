#!/usr/bin/env python3
# License: GNU AGPL v3 or later.
"""Source-entailment gate: every generated card must be supported by its cited
source, or it is rejected. This is the anti-hallucination guardrail.

Each card carries (source_id, span). The gate checks two things:
  1. GROUNDING   -- the cited span is actually verbatim in the source chunk.
  2. ENTAILMENT  -- the card's answer is entailed by the source (not invented).

Entailment uses an LLM NLI check when OPENAI_API_KEY is set; otherwise a
lexical-overlap proxy runs offline (weaker, but keeps the gate reproducible
and functional with AI OFF). Target: >= 95% of kept cards entailed.
"""
import os
import re

_WORD = re.compile(r"[a-z0-9]+")
STOP = set("the a an of to in on and or is are was were be been being for with as by at "
           "that this it its from into than then which who whom whose what when where how "
           "not no do does can could may might will would should more most less least".split())


def _content(s: str) -> set:
    return {w for w in _WORD.findall(s.lower()) if w not in STOP and len(w) > 2}


def grounded(card: dict, source_text: str) -> bool:
    """The cited span must be (nearly) verbatim in the source."""
    span = (card.get("span") or "").strip().lower()
    if not span:
        return False
    src = source_text.lower()
    if span in src:
        return True
    # tolerate minor whitespace/punctuation drift: >=85% of span content words present
    sw = _content(span)
    return bool(sw) and len(sw & _content(src)) / len(sw) >= 0.85


def entailed_lexical(card: dict, source_text: str, thresh: float = 0.6) -> bool:
    """Offline proxy: the answer's content words are largely present in the source."""
    back = _content(card.get("back", ""))
    if not back:
        return False
    return len(back & _content(source_text)) / len(back) >= thresh


def entailed_llm(llm, card: dict, source_text: str) -> bool:
    out = llm.json(
        "You are a strict fact-checker. Decide whether the ANSWER is fully supported "
        "(entailed) by the SOURCE. Answer only about support, not general truth.",
        f"SOURCE:\n{source_text}\n\nQUESTION: {card['front']}\nANSWER: {card['back']}\n\n"
        'Is the answer entailed by the source? Return JSON: {"entailed": true|false}',
    )
    return bool(out.get("entailed", False))


def gate(cards: list[dict], sources: dict, llm=None) -> dict:
    """Run the entailment gate over cards. Returns kept/rejected + entailed rate."""
    kept, rejected = [], []
    for c in cards:
        src = sources.get(c["source_id"], "")
        is_grounded = grounded(c, src)
        if llm is not None:
            is_entailed = entailed_llm(llm, c, src)
        else:
            is_entailed = entailed_lexical(c, src)
        if is_grounded and is_entailed:
            kept.append(c)
        else:
            rejected.append({**c, "grounded": is_grounded, "entailed": is_entailed})
    n = len(cards)
    return {"n": n, "kept": len(kept), "rejected": len(rejected),
            "entailed_rate": len(kept) / n if n else 0.0,
            "kept_cards": kept, "rejected_cards": rejected}


if __name__ == "__main__":
    import json
    HERE = os.path.dirname(os.path.abspath(__file__))
    sources = {c["id"]: c["text"] for c in
               (json.loads(l) for l in open(os.path.join(HERE, "corpus", "corpus.jsonl")))}
    # Sanity: gold cards (with a synthetic span = their source) should pass the offline proxy.
    gold = [json.loads(l) for l in open(os.path.join(HERE, "gold", "gold_cards.jsonl"))]
    for g in gold:
        g["span"] = sources[g["source_id"]]  # gold is authored from the whole chunk
    r = gate(gold, sources, llm=None)
    print(f"offline entailment proxy on 50 gold cards: {r['kept']}/{r['n']} entailed "
          f"({r['entailed_rate']:.1%})")
