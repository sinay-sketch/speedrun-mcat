#!/usr/bin/env python3
# License: GNU AGPL v3 or later.
"""Build the collection that the iOS app bundles: a fresh collection.anki2 with
the MCAT starter deck imported. Prints the deck id for the FFI/Swift layer.

  PYTHONPATH=out/pylib out/pyenv/bin/python tools/speedrun/prepare_ios_collection.py
"""
import os
import shutil

from anki.collection import Collection
from anki import import_export_pb2 as ie
from anki import deck_config_pb2 as dcpb

APKG = os.path.abspath("mcat_starter.apkg")
OUT_DIR = os.path.abspath("ios/SpeedrunMCAT/Resources")
COL_PATH = os.path.join(OUT_DIR, "collection.anki2")
DECK_NAME = "MCAT::Speedrun Starter"


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    for suffix in ("", "-wal", "-shm"):
        p = COL_PATH + suffix
        if os.path.exists(p):
            os.remove(p)

    col = Collection(COL_PATH)
    opts = col._backend.get_import_anki_package_presets()
    col.import_anki_package(
        ie.ImportAnkiPackageRequest(package_path=APKG, options=opts)
    )
    did = col.decks.id(DECK_NAME, create=False)
    col.decks.select(did)
    # Raise the new-card daily limit so the companion has plenty to review.
    conf = col.decks.config_dict_for_deck_id(did)
    conf["new"]["perDay"] = 200
    conf["rev"]["perDay"] = 500
    col.decks.save(conf)
    # Enable FSRS — it is the memory engine the Memory score is built on. Without
    # it, cards never get an FSRS memory state and the score can only ever abstain.
    gather = col.decks.get_deck_configs_for_update(did)
    col.decks.update_deck_configs(
        dcpb.UpdateDeckConfigsRequest(
            target_deck_id=did,
            configs=[cwe.config for cwe in gather.all_config],
            removed_config_ids=[],
            mode=dcpb.UpdateDeckConfigsMode.UPDATE_DECK_CONFIGS_MODE_NORMAL,
            fsrs=True,
            fsrs_reschedule=True,
        )
    )
    col.close()

    with open(os.path.join(OUT_DIR, "deck_id.txt"), "w") as f:
        f.write(str(did))
    print(f"collection={COL_PATH}")
    print(f"deck_id={did}")
    print("cards imported OK")


if __name__ == "__main__":
    main()
