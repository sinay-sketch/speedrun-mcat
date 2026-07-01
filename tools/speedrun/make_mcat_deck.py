#!/usr/bin/env python3
# Copyright: Speedrun (MCAT) project. License: GNU AGPL v3 or later.
"""Generate a small, reproducible MCAT starter deck as an .apkg.

Every note is tagged with its AAMC section + discipline so the deck doubles as
seed data for the coverage map. This is a *starter* deck for the review loop and
demos; full community decks (MileDown ~2,900 cloze; JackSparrow ~6,300 basic)
import through the exact same path.

Run:  python tools/speedrun/make_mcat_deck.py  ->  writes mcat_starter.apkg
"""
import genanki

# Stable IDs so regenerating produces the same deck/model (reproducible).
DECK_ID = 1607392319
MODEL_ID = 1607392320

MODEL = genanki.Model(
    MODEL_ID,
    "Speedrun MCAT Basic",
    fields=[{"name": "Front"}, {"name": "Back"}, {"name": "Discipline"}],
    templates=[
        {
            "name": "Card 1",
            "qfmt": "{{Front}}",
            "afmt": '{{FrontSide}}<hr id="answer">{{Back}}'
            '<br><br><span style="color:#888;font-size:12px">{{Discipline}}</span>',
        }
    ],
)

# (front, back, section, discipline) — real MCAT content across the weighted
# disciplines: B/B (bio 65 / biochem 25), C/P (gchem / physics / orgo / biochem),
# P/S (psych 65 / soc 30). Biochem is intentionally double-represented (B/B + C/P).
CARDS = [
    # ---- Biology / Biochemistry (B/B) ----
    ("Which glycolytic enzyme catalyzes the first committed, rate-limiting step?",
     "Phosphofructokinase-1 (PFK-1), converting fructose-6-phosphate to fructose-1,6-bisphosphate.", "B/B", "Biochemistry"),
    ("Net ATP yield of glycolysis (glucose to 2 pyruvate)?", "2 ATP (4 produced − 2 invested) and 2 NADH.", "B/B", "Biochemistry"),
    ("Where does the citric acid cycle occur in eukaryotes?", "The mitochondrial matrix.", "B/B", "Biochemistry"),
    ("What bond links amino acids in a protein?", "The peptide (amide) bond, formed by dehydration synthesis.", "B/B", "Biochemistry"),
    ("Michaelis constant (Km) physically represents what?", "The substrate concentration at which reaction velocity is half of Vmax; a proxy for enzyme–substrate affinity (lower Km = higher affinity).", "B/B", "Biochemistry"),
    ("Competitive inhibition affects Km and Vmax how?", "Increases apparent Km; Vmax unchanged.", "B/B", "Biochemistry"),
    ("Which nitrogenous bases are purines?", "Adenine and guanine (double-ring).", "B/B", "Biology"),
    ("Enzyme that unwinds the DNA double helix at the replication fork?", "Helicase.", "B/B", "Biology"),
    ("Which enzyme synthesizes RNA from a DNA template?", "RNA polymerase.", "B/B", "Biology"),
    ("Stop codons (three)?", "UAA, UAG, UGA.", "B/B", "Biology"),
    ("Hormone from pancreatic beta cells that lowers blood glucose?", "Insulin.", "B/B", "Biology"),
    ("Functional unit of the kidney?", "The nephron.", "B/B", "Biology"),
    ("Which part of the nephron is impermeable to water but reabsorbs Na+/K+/Cl-?", "The thick ascending limb of the loop of Henle.", "B/B", "Biology"),
    ("Type of feedback that dominates homeostasis (e.g., thermoregulation)?", "Negative feedback.", "B/B", "Biology"),
    ("Phase of the cell cycle where DNA is replicated?", "S phase (synthesis).", "B/B", "Biology"),
    ("Michaelis–Menten: what does a Lineweaver–Burk plot linearize?", "The MM equation; y-intercept = 1/Vmax, x-intercept = -1/Km.", "B/B", "Biochemistry"),
    ("Which macromolecule stores energy long-term in animals via glucose polymers?", "Glycogen.", "B/B", "Biochemistry"),
    ("Primary structure of a protein refers to what?", "The linear sequence of amino acids.", "B/B", "Biochemistry"),

    # ---- Chemical & Physical Foundations (C/P) ----
    ("Ideal gas law equation?", "PV = nRT.", "C/P", "General Chemistry"),
    ("Definition of pH?", "pH = -log10[H+].", "C/P", "General Chemistry"),
    ("Henderson–Hasselbalch equation?", "pH = pKa + log([A-]/[HA]).", "C/P", "General Chemistry"),
    ("A strong acid has a pKa that is...?", "Very low (large Ka); it dissociates essentially completely.", "C/P", "General Chemistry"),
    ("Le Chatelier: adding product to an equilibrium shifts it which way?", "Toward reactants (to the left).", "C/P", "General Chemistry"),
    ("First law of thermodynamics?", "Energy is conserved: ΔU = q - w (internal energy change = heat added minus work done by system).", "C/P", "Physics"),
    ("Ohm's law?", "V = IR.", "C/P", "Physics"),
    ("Equation for kinetic energy?", "KE = ½mv².", "C/P", "Physics"),
    ("Snell's law?", "n1 sin(θ1) = n2 sin(θ2).", "C/P", "Physics"),
    ("Bernoulli's principle (qualitative)?", "In flowing fluid, higher velocity corresponds to lower pressure.", "C/P", "Physics"),
    ("Which functional group defines a carboxylic acid?", "-COOH (carboxyl).", "C/P", "Organic Chemistry"),
    ("SN1 reaction rate depends on the concentration of...?", "Only the substrate (rate = k[substrate]); unimolecular rate-determining step.", "C/P", "Organic Chemistry"),
    ("What technique separates compounds by boiling point?", "Distillation.", "C/P", "Organic Chemistry"),
    ("Chirality: a carbon bonded to four different groups is called?", "A stereocenter (chiral center).", "C/P", "Organic Chemistry"),
    ("Which spectroscopy identifies functional groups via bond vibrations?", "Infrared (IR) spectroscopy.", "C/P", "Organic Chemistry"),
    ("pKa relationship to buffer capacity: a buffer is most effective when...?", "pH is within ~1 unit of the pKa.", "C/P", "Biochemistry"),

    # ---- Psychological, Social, and Biological Foundations of Behavior (P/S) ----
    ("Which brain structure consolidates new long-term memories?", "The hippocampus.", "P/S", "Psychology"),
    ("Classical conditioning: term for the previously neutral stimulus after learning?", "Conditioned stimulus (CS).", "P/S", "Psychology"),
    ("Operant conditioning: negative reinforcement does what?", "Increases a behavior by removing an aversive stimulus.", "P/S", "Psychology"),
    ("Piaget's stage (roughly 2–7 yrs) marked by egocentrism and lack of conservation?", "Preoperational stage.", "P/S", "Psychology"),
    ("Which neurotransmitter is most associated with reward and is low in Parkinson's?", "Dopamine.", "P/S", "Psychology"),
    ("Weber's law states that the just-noticeable difference is...?", "A constant proportion of the original stimulus intensity.", "P/S", "Psychology"),
    ("Sociology: the theory that society is a system of interdependent parts?", "Functionalism (structural functionalism).", "P/S", "Sociology"),
    ("Term for a self-fulfilling expectation based on group membership?", "Stereotype threat / self-fulfilling prophecy (labeling).", "P/S", "Sociology"),
    ("Difference between prejudice and discrimination?", "Prejudice is an attitude/belief; discrimination is the behavior/action.", "P/S", "Sociology"),
    ("Which type of social mobility is movement between generations?", "Intergenerational mobility.", "P/S", "Sociology"),
    ("Maslow's hierarchy: what sits at the base?", "Physiological needs.", "P/S", "Psychology"),
    ("Fundamental attribution error is the tendency to...?", "Overattribute others' behavior to disposition and underweight situational factors.", "P/S", "Psychology"),
]


def main() -> None:
    deck = genanki.Deck(DECK_ID, "MCAT::Speedrun Starter")
    for front, back, section, discipline in CARDS:
        note = genanki.Note(
            model=MODEL,
            fields=[front, back, f"{section} · {discipline}"],
            tags=[f"MCAT::{section}", f"discipline::{discipline.replace(' ', '_')}"],
        )
        deck.add_note(note)
    out = "mcat_starter.apkg"
    genanki.Package(deck).write_to_file(out)
    print(f"wrote {out} with {len(CARDS)} notes across B/B, C/P, P/S")


if __name__ == "__main__":
    main()
