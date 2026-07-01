# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Speedrun (MCAT): a Tools-menu action that shows the honest, aggregated
Memory score for the current deck, computed by the new MasteryForDeck Rust RPC.

Demonstrates the "memory model running, with an honest score: a range plus the
give-up rule" requirement inside the desktop app."""

from __future__ import annotations

import aqt
from aqt.qt import QAction, qconnect
from aqt.utils import showInfo


def add_memory_score_action(mw: aqt.main.AnkiQt) -> None:
    """Add the 'MCAT Memory Score…' action to the Tools menu."""
    action = QAction("MCAT Memory Score…", mw)
    qconnect(action.triggered, lambda: show_memory_score(mw))
    mw.form.menuTools.addAction(action)


def show_memory_score(mw: aqt.main.AnkiQt) -> None:
    if not mw.col:
        showInfo("No collection is open.")
        return
    did = mw.col.decks.selected()
    name = mw.col.decks.name(did)
    m = mw.col._backend.mastery_for_deck(did=did)

    if m.sufficient_data:
        body = (
            f"<b>Memory score — “{name}”</b><br><br>"
            f"Predicted recall: <b>{m.mean_retrievability * 100:.0f}%</b><br>"
            f"95% range: {m.lower * 100:.0f}%–{m.upper * 100:.0f}%<br><br>"
            f"Based on {m.cards_counted} of {m.cards_total} cards with a memory "
            f"state ({m.mature} mature)."
        )
    else:
        body = (
            f"<b>Memory score — “{name}”</b><br><br>"
            f"<b>Not enough data to show a score.</b><br>"
            f"Only {m.cards_counted} of {m.cards_total} cards have an FSRS memory "
            f"state (need ≥ 20).<br><br>"
            f"<i>Next best action:</i> study more cards in this deck so they graduate "
            f"to review, then check again. A good system knows when it doesn't know."
        )
    showInfo(body, title="Speedrun — MCAT", textFormat="rich")
