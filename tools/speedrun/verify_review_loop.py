#!/usr/bin/env python3
# License: GNU AGPL v3 or later.
"""Headless proof that the MCAT deck loads, the review loop runs on the shared
Rust engine, and the new MasteryForDeck RPC returns an honest score.

Run with the built pylib on PYTHONPATH:
  PYTHONPATH=out/pylib out/pyenv/bin/python tools/speedrun/verify_review_loop.py
"""
import os
import tempfile

from anki.collection import Collection
from anki import import_export_pb2 as ie

APKG = os.path.abspath("mcat_starter.apkg")
DECK_NAME = "MCAT::Speedrun Starter"


def main() -> None:
    base = tempfile.mkdtemp(prefix="speedrun_")
    col = Collection(os.path.join(base, "collection.anki2"))

    # 1) Import the MCAT exam deck.
    opts = col._backend.get_import_anki_package_presets()
    col.import_anki_package(
        ie.ImportAnkiPackageRequest(package_path=APKG, options=opts)
    )
    print(f"imported {APKG}")
    print(f"  cards={col.card_count()} notes={col.note_count()}")

    did = col.decks.id(DECK_NAME, create=False)
    assert did, f"deck {DECK_NAME!r} not found after import"
    col.decks.select(did)
    # Raise the new-card daily limit so the loop can churn through the deck.
    conf = col.decks.config_dict_for_deck_id(did)
    conf["new"]["perDay"] = 200
    col.decks.save(conf)

    # 2) Run a real review loop on the exam deck ("Good" = ease 3).
    col.reset()
    reviewed = 0
    while (card := col.sched.getCard()) is not None and reviewed < 60:
        col.sched.answerCard(card, 3)
        reviewed += 1
    print(f"  review loop: answered {reviewed} cards")

    # 3) Honest Memory score via the new Rust RPC.
    m = col._backend.mastery_for_deck(did=did)
    print("MasteryForDeck (honest Memory score):")
    print(f"  cards_total     = {m.cards_total}")
    print(f"  cards_counted   = {m.cards_counted}  (cards with an FSRS memory state)")
    print(f"  mature          = {m.mature}")
    print(f"  sufficient_data = {m.sufficient_data}  (give-up rule)")
    if m.sufficient_data:
        print(
            f"  Memory score    = {m.mean_retrievability*100:.1f}%  "
            f"(95% band {m.lower*100:.1f}%–{m.upper*100:.1f}%)"
        )
    else:
        print("  Memory score    = ABSTAINED — insufficient data; "
              "study more cards first (next best action).")

    col.close()
    print("OK")


if __name__ == "__main__":
    main()
