#!/usr/bin/env python3
# License: GNU AGPL v3 or later.
"""Two-stage card generation + self-refine (the AI card-quality engine).

Pipeline per source chunk (Matuschak two-stage + MCQG-SRefine self-refinement):
  1. TARGET SELECTION  -- pick only the atomic facts worth a card (volume control,
     Wo 'zniak minimum-information principle). Prevents card bloat.
  2. FORMULATION       -- write each card atomically, carrying the source id and a
     VERBATIM span from the chunk that supports the answer (for the entailment gate).
  3. SELF-REFINE       -- critique each card against the rules, then rewrite.

Needs OPENAI_API_KEY. Cards are dicts:
  {front, back, source_id, span, type}
"""
import json
import re

from llm import LLM, GEN_MODEL


def pick_span(source_text: str, answer: str) -> str:
    """Deterministically choose the source sentence that best supports the answer
    (highest content-word overlap). More reliable than asking the LLM to echo a
    verbatim quote, which it tends to abbreviate ('...'). Guarantees the citation
    is a real, auditable sentence from the source."""
    from entailment import _content
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", source_text.strip()) if s.strip()]
    ans = _content(answer)
    if not sents:
        return source_text.strip()
    if not ans:
        return sents[0]
    return max(sents, key=lambda s: len(ans & _content(s)))

WOZNIAK_RULES = (
    "Card rules (Wozniak minimum-information principle):\n"
    "- Atomic: exactly one fact per card. No enumerations, no multi-part answers.\n"
    "- The back is a short, specific answer (a phrase, not a paragraph).\n"
    "- The front is an unambiguous question with a single correct answer.\n"
    "- Test understanding, not verbatim wording. No wall-of-text backs.\n"
    "- Every answer must be directly supported by the provided source text."
)

TARGET_SYS = (
    "You are an expert MCAT tutor selecting which facts in a passage deserve a "
    "flashcard. Favor high-yield, testable, atomic facts. Skip trivia and anything "
    "not stated in the passage. " + WOZNIAK_RULES
)

FORMULATE_SYS = (
    "You are an expert flashcard author. Write ONE atomic MCAT flashcard for the "
    "given target, grounded ONLY in the source text. " + WOZNIAK_RULES
)

REFINE_SYS = (
    "You are a strict flashcard reviewer. Given a card and its source text, find any "
    "rule violation (non-atomic, enumeration, wall-of-text, ambiguous, or unsupported "
    "by the source) and return a corrected card. If already good, return it unchanged. "
    + WOZNIAK_RULES
)


def select_targets(llm: LLM, chunk: dict, max_cards: int = 4) -> list[str]:
    out = llm.json(
        TARGET_SYS,
        f"Source (id={chunk['id']}):\n{chunk['text']}\n\n"
        f"List up to {max_cards} atomic facts worth a card. "
        'Return JSON: {"targets": ["fact 1", "fact 2", ...]}',
        model=GEN_MODEL,
    )
    return out.get("targets", [])[:max_cards]


def formulate(llm: LLM, chunk: dict, target: str) -> dict:
    out = llm.json(
        FORMULATE_SYS,
        f"Source (id={chunk['id']}):\n{chunk['text']}\n\nTarget fact: {target}\n\n"
        'Return JSON: {"front": "...", "back": "...", '
        '"span": "verbatim sentence from the source supporting the answer"}',
        model=GEN_MODEL,
    )
    return {"front": out.get("front", ""), "back": out.get("back", ""),
            "span": out.get("span", ""), "source_id": chunk["id"], "type": "basic"}


def self_refine(llm: LLM, chunk: dict, card: dict) -> dict:
    out = llm.json(
        REFINE_SYS,
        f"Source (id={chunk['id']}):\n{chunk['text']}\n\n"
        f"Card:\nQ: {card['front']}\nA: {card['back']}\n\n"
        'Return the corrected card as JSON: {"front":"...","back":"...","span":"..."}',
        model=GEN_MODEL,
    )
    return {**card, "front": out.get("front", card["front"]),
            "back": out.get("back", card["back"]),
            "span": out.get("span", card.get("span", ""))}


def generate_for_chunk(llm: LLM, chunk: dict, max_cards: int = 4) -> list[dict]:
    cards = []
    for target in select_targets(llm, chunk, max_cards):
        card = formulate(llm, chunk, target)
        card = self_refine(llm, chunk, card)
        if card["front"] and card["back"]:
            # Attach a real, verbatim source sentence as the citation (don't trust
            # the LLM's echoed span, which it abbreviates).
            card["span"] = pick_span(chunk["text"], card["back"])
            cards.append(card)
    return cards


def generate_all(chunks: list[dict], max_cards: int = 3) -> list[dict]:
    llm = LLM(model=GEN_MODEL)
    out = []
    for c in chunks:
        out.extend(generate_for_chunk(llm, c, max_cards))
    return out


if __name__ == "__main__":
    import os
    HERE = os.path.dirname(os.path.abspath(__file__))
    chunks = [json.loads(l) for l in open(os.path.join(HERE, "corpus", "corpus.jsonl"))]
    cards = generate_all(chunks[:3], max_cards=3)
    print(json.dumps(cards, indent=2))
