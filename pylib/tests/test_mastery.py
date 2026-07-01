# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Speedrun (MCAT): exercises the new MasteryForDeck Rust RPC from Python."""

from tests.shared import getEmptyCol

DEFAULT_DECK_ID = 1


def test_mastery_for_deck_round_trips_and_gives_up_without_data():
    col = getEmptyCol()

    # Empty deck: the give-up rule fires and no score is asserted.
    resp = col._backend.mastery_for_deck(did=DEFAULT_DECK_ID)
    assert resp.cards_total == 0
    assert resp.cards_counted == 0
    assert resp.sufficient_data is False

    # Add a single brand-new card. It has no FSRS memory state yet, so it is
    # counted in the total but not in the estimate, and we still abstain.
    note = col.newNote()
    note["Front"] = "The powerhouse of the cell is the ___"
    note["Back"] = "mitochondrion"
    col.addNote(note)

    resp = col._backend.mastery_for_deck(did=DEFAULT_DECK_ID)
    assert resp.cards_total >= 1
    assert resp.cards_counted == 0
    assert resp.sufficient_data is False

    # The reported range is always well-formed and within [0, 1].
    assert 0.0 <= resp.lower <= resp.upper <= 1.0
