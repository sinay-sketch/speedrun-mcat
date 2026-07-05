#!/usr/bin/env python3
# License: GNU AGPL v3 or later.
"""Wire the AI harness into the deck (the authoring-time step):
generate -> vet -> import the PASSERS as real cards, tagged `ai::generated`, into
the shared collection, then sync up so BOTH apps show them.

This is run by the deck maintainer, NOT the app and NOT during review — which is
why the app still "runs with AI off". A card only reaches a student after it is
entailed by its named source AND judged usable (tier >= T2).

  PYTHONPATH=out/pylib OPENAI_API_KEY=… out/pyenv/bin/python \
      tools/speedrun/ai/import_approved.py [--gen-chunks N] [--collection PATH]

With no --collection, it full-downloads the shared collection from the sync
server, imports into it, and syncs the new cards back up.
"""
import argparse
import ctypes
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import entailment  # noqa: E402
import generate  # noqa: E402
import judge  # noqa: E402
from llm import LLM, GEN_MODEL, JUDGE_MODEL  # noqa: E402

from anki.collection import Collection  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(HERE, "corpus", "corpus.jsonl")
LIB = os.path.abspath("target/debug/libanki_ffi.dylib")
ENDPOINT = "http://127.0.0.1:8080/"
DECK = "MCAT::Speedrun Starter"


def ffi_sync(path):
    lib = ctypes.CDLL(LIB)
    lib.speedrun_sync.restype = ctypes.c_int32
    lib.speedrun_sync.argtypes = [ctypes.c_char_p] * 4
    return lib.speedrun_sync(path.encode(), ENDPOINT.encode(), b"test", b"test")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gen-chunks", type=int, default=6)
    ap.add_argument("--collection", default=None, help="collection path (default: full-download from server)")
    args = ap.parse_args()

    if args.collection:
        col_path = args.collection
        synced = False
    else:
        col_path = os.path.join(tempfile.mkdtemp(prefix="aiimport_"), "collection.anki2")
        print("full-download shared collection ->", {0: "in-sync", 1: "upload", 2: "download"}.get(ffi_sync(col_path), "err"))
        synced = True

    # 1) generate + 2) vet (entailed by source AND judged usable).
    gen, jdg = LLM(model=GEN_MODEL), LLM(model=JUDGE_MODEL)
    all_chunks = [json.loads(l) for l in open(CORPUS)]
    sources = {c["id"]: c["text"] for c in all_chunks}
    approved, generated = [], 0
    for ch in all_chunks[: args.gen_chunks]:
        for card in generate.generate_for_chunk(gen, ch, max_cards=3):
            generated += 1
            src = sources[card["source_id"]]
            ent = entailment.entailed_llm(jdg, card, src)
            v = judge.judge_card(jdg, card, src)
            if ent and v["usable"]:
                approved.append((card, v["tier"]))
    print(f"generated {generated}, approved {len(approved)} (entailed AND tier ≥ T2)")

    # 3) import the passers as real, tagged cards.
    col = Collection(col_path)
    did = col.decks.id(DECK)
    model = col.models.by_name("Basic")
    before = len(col.find_cards(f'deck:"{DECK}"'))
    for card, tier in approved:
        note = col.new_note(model)
        note.fields[0] = card["front"]
        note.fields[1] = card["back"]
        note.tags = ["ai::generated", f"source::{card['source_id']}", f"tier::T{tier}"]
        col.add_note(note, did)
    after = len(col.find_cards(f'deck:"{DECK}"'))
    ai_now = len(col.find_cards(f'deck:"{DECK}" tag:ai::generated'))
    col.close()
    print(f"deck: {before} -> {after} cards  (+{after-before}; {ai_now} tagged ai::generated)")

    # 4) sync the new cards up so both apps get them.
    if synced:
        print("sync new cards up ->", {0: "in-sync", 1: "upload", 2: "download"}.get(ffi_sync(col_path), "err"))
        print("Now sync the desktop + phone — the AI cards appear in review, tagged ai::generated.")


if __name__ == "__main__":
    main()
