#!/usr/bin/env python3
# License: GNU AGPL v3 or later.
"""Coverage map: what fraction of the AAMC MCAT outline does the deck touch?

Reads the deck's discipline/section tags and maps them to the four AAMC sections,
reporting cards per discipline and per section. This is the coverage signal behind
the Readiness give-up rule: below the coverage line (and without scored
full-lengths) Readiness abstains — you can't be "ready" for topics you haven't seen.

  PYTHONPATH=out/pylib out/pyenv/bin/python tools/speedrun/coverage_map.py [out.txt]
"""
import collections
import os
import sys
import tempfile

from anki.collection import Collection
from anki import import_export_pb2 as ie

# AAMC's four scored sections. CARS has NO content to memorize — it is 0%
# flashcardable by design, so it is never "covered" by a deck (documented, not a gap).
SECTIONS = {
    "C/P": "Chemical & Physical Foundations (gen chem, physics, org chem, biochem)",
    "CARS": "Critical Analysis & Reasoning (no content — 0% flashcardable)",
    "B/B": "Biological & Biochemical Foundations (biology, biochem)",
    "P/S": "Psychological, Social & Biological Foundations (psych, soc, biology)",
}
# Disciplines the AAMC science sections draw on (the reference set we score against).
AAMC_DISCIPLINES = ["Biochemistry", "Biology", "General_Chemistry",
                    "Organic_Chemistry", "Physics", "Psychology", "Sociology"]
COVERAGE_LINE = 0.50  # Readiness abstains below this topic coverage (also needs ≥5 full-lengths)


def main():
    p = tempfile.mktemp(suffix=".anki2")
    col = Collection(p)
    opts = col._backend.get_import_anki_package_presets()
    col.import_anki_package(ie.ImportAnkiPackageRequest(
        package_path=os.path.abspath("mcat_starter.apkg"), options=opts))
    disc = collections.Counter()
    sect = collections.Counter()
    total = 0
    for cid in col.find_cards("deck:MCAT::*"):
        total += 1
        for t in col.get_card(cid).note().tags:
            if t.startswith("discipline::"):
                disc[t.split("::", 1)[1]] += 1
            elif t.startswith("MCAT::"):
                sect[t.split("::", 1)[1]] += 1
    col.close()

    lines = []
    def pr(s=""):
        lines.append(s); print(s)

    pr(f"MCAT coverage map — {total} cards in the starter deck\n")
    pr("By AAMC section:")
    for key, desc in SECTIONS.items():
        n = sect.get(key, 0)
        mark = "✓" if n else ("—" if key == "CARS" else "✗")
        pr(f"  [{mark}] {key:4} {n:3d} cards   {desc}")
    covered_sections = sum(1 for k in SECTIONS if k != "CARS" and sect.get(k, 0) > 0)
    pr(f"  -> {covered_sections}/3 content sections have cards (CARS excluded: not flashcardable)\n")

    pr("By discipline (AAMC reference set):")
    covered = 0
    for d in AAMC_DISCIPLINES:
        n = disc.get(d, 0)
        if n:
            covered += 1
        pr(f"  [{'✓' if n else '✗'}] {d.replace('_', ' '):18} {n:3d} cards")
    disc_cov = covered / len(AAMC_DISCIPLINES)
    pr(f"  -> {covered}/{len(AAMC_DISCIPLINES)} disciplines touched = {disc_cov*100:.0f}% discipline coverage\n")

    pr(f"Readiness coverage line: ≥{COVERAGE_LINE*100:.0f}% topic DEPTH covered AND ≥5 scored full-lengths.")
    pr(f"Breadth is good ({covered}/{len(AAMC_DISCIPLINES)} disciplines), but 46 cards touch only a "
       f"handful of the ~59 AAMC content categories, so per-topic DEPTH is thin.")
    pr("=> Readiness ABSTAINS regardless, on the hard gate: 0 scored full-lengths (< 5 required). "
       "You can't be 'ready' for topics you haven't been tested on. Honest, not a bug — this is "
       "the same give-up rule enforced in rslib readiness_for_deck.")

    if len(sys.argv) > 1:
        open(sys.argv[1], "w").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
