# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Speedrun (MCAT): a Tools-menu action that shows the honest, aggregated
Memory score for the current deck, computed by the new MasteryForDeck Rust RPC.

Demonstrates the "memory model running, with an honest score: a range plus the
give-up rule" requirement inside the desktop app."""

from __future__ import annotations

import aqt
from aqt import gui_hooks
from aqt.qt import QAction, qconnect
from aqt.utils import showInfo


def add_autosync_on_deckbrowser(mw: aqt.main.AnkiQt) -> None:
    """Auto-sync when the user returns to the deck list after studying, mirroring
    the phone app's sync-on-return-to-Home. Fires the same path as the Sync button
    only when already authenticated (never pops a login dialog) and never overlaps
    an in-progress sync."""

    def on_state_did_change(new_state: str, old_state: str) -> None:
        if new_state != "deckBrowser" or old_state not in ("review", "overview"):
            return
        if not mw.col:
            return
        try:
            if mw.pm.sync_auth() is None:
                return
        except Exception:
            return
        if mw.progress.busy():
            return
        try:
            if mw.media_syncer.is_syncing():
                return
        except Exception:
            pass
        mw.on_sync_button_clicked()

    gui_hooks.state_did_change.append(on_state_did_change)


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
