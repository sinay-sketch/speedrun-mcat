#!/usr/bin/env python3
# License: GNU AGPL v3 or later.
"""Build the reproducible datasets for the Speedrun AI harness:

  corpus.jsonl       named MCAT source chunks (what cards must be traced to)
  queries.jsonl      held-out MCAT queries + relevance judgments (qrels) over the corpus
  gold_cards.jsonl   50 human-authored gold cards (judge calibration + AI-OFF deck)

All content is compact, real MCAT material authored for this project. Biochem
is intentionally over-represented (it is double-weighted on the real MCAT).
Deterministic: no randomness, so a grader re-running gets identical files.

  python tools/speedrun/ai/build_datasets.py
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(HERE, "corpus", "corpus.jsonl")
QUERIES = os.path.join(HERE, "gold", "queries.jsonl")
GOLD = os.path.join(HERE, "gold", "gold_cards.jsonl")
CALIB = os.path.join(HERE, "gold", "calib_bad.jsonl")

# --- Named source chunks -------------------------------------------------
# (id, discipline, source, text). `source` is the citable document name.
CHUNKS = [
    # Biochemistry (double-weighted on the MCAT)
    ("bc01", "biochem", "Lehninger ch14",
     "Glycolysis converts one molecule of glucose into two molecules of pyruvate. "
     "The pathway has a net yield of 2 ATP and 2 NADH per glucose. The committed, "
     "rate-limiting step is catalyzed by phosphofructokinase-1 (PFK-1), which is "
     "allosterically inhibited by ATP and citrate and activated by AMP and fructose-2,6-bisphosphate."),
    ("bc02", "biochem", "Lehninger ch14",
     "Hexokinase catalyzes the first step of glycolysis, phosphorylating glucose to "
     "glucose-6-phosphate using one ATP. Hexokinase is inhibited by its product, "
     "glucose-6-phosphate. In the liver, the isozyme glucokinase has a high Km and is not "
     "inhibited by glucose-6-phosphate, letting the liver buffer blood glucose."),
    ("bc03", "biochem", "Lehninger ch16",
     "The citric acid cycle (Krebs cycle) oxidizes acetyl-CoA to two CO2. Per acetyl-CoA it "
     "yields 3 NADH, 1 FADH2, and 1 GTP. Isocitrate dehydrogenase is the rate-limiting enzyme "
     "and is activated by ADP and inhibited by ATP and NADH."),
    ("bc04", "biochem", "Lehninger ch19",
     "Oxidative phosphorylation couples electron transport to ATP synthesis. Electrons from "
     "NADH and FADH2 pass through complexes I-IV, pumping protons into the intermembrane space. "
     "ATP synthase uses the proton-motive force to make ATP. Complete oxidation of glucose "
     "yields about 30-32 ATP."),
    ("bc05", "biochem", "Lehninger ch6",
     "Enzymes lower the activation energy of a reaction without changing the equilibrium. "
     "The Michaelis-Menten model gives v = Vmax[S]/(Km+[S]). Km is the substrate concentration "
     "at half Vmax and reflects affinity; a lower Km means higher affinity."),
    ("bc06", "biochem", "Lehninger ch6",
     "Competitive inhibitors bind the active site and raise the apparent Km while Vmax is "
     "unchanged. Noncompetitive inhibitors bind elsewhere and lower Vmax while Km is unchanged. "
     "On a Lineweaver-Burk plot, competitive inhibition changes the x-intercept but not the y-intercept."),
    ("bc07", "biochem", "Lehninger ch3",
     "The 20 standard amino acids share an amino group, a carboxyl group, and a side chain (R group) "
     "on a central alpha carbon. Side chains determine polarity and charge. At physiological pH, "
     "acidic side chains (Asp, Glu) are negatively charged and basic side chains (Lys, Arg, His) can be positive."),
    ("bc08", "biochem", "Lehninger ch4",
     "Protein secondary structure includes alpha helices and beta sheets, stabilized by backbone "
     "hydrogen bonds. Tertiary structure is the overall 3D fold, driven largely by the hydrophobic "
     "effect. Quaternary structure describes the assembly of multiple polypeptide subunits."),
    ("bc09", "biochem", "Lehninger ch5",
     "Hemoglobin binds oxygen cooperatively, giving a sigmoidal binding curve; myoglobin is "
     "hyperbolic. The Bohr effect: increased CO2 and H+ (lower pH) lower hemoglobin's oxygen "
     "affinity, promoting oxygen release in metabolically active tissue."),
    ("bc10", "biochem", "Stryer ch12",
     "The fluid mosaic model describes membranes as a phospholipid bilayer with embedded proteins. "
     "Cholesterol modulates fluidity, buffering against temperature changes. Membranes are "
     "selectively permeable; small nonpolar molecules cross freely while ions require transporters."),
    # General chemistry
    ("gc01", "genchem", "Zumdahl ch13",
     "For a reaction at equilibrium, Le Chatelier's principle states that a system responds to a "
     "stress by shifting to counteract it. Adding reactant shifts the reaction toward products; "
     "increasing pressure shifts toward the side with fewer moles of gas."),
    ("gc02", "genchem", "Zumdahl ch14",
     "A buffer resists pH change and consists of a weak acid and its conjugate base. The "
     "Henderson-Hasselbalch equation is pH = pKa + log([A-]/[HA]). Buffering capacity is maximal "
     "when pH equals pKa, where [A-] = [HA]."),
    ("gc03", "genchem", "Zumdahl ch16",
     "Gibbs free energy determines spontaneity: dG = dH - T dS. A negative dG means a spontaneous "
     "(exergonic) process. dG = dG0 + RT ln Q, and at equilibrium dG = 0 so dG0 = -RT ln K."),
    ("gc04", "genchem", "Zumdahl ch17",
     "In electrochemistry, oxidation occurs at the anode and reduction at the cathode. A galvanic "
     "cell has a positive cell potential and is spontaneous; dG0 = -nFE0. Electrons flow from anode to cathode."),
    ("gc05", "genchem", "Zumdahl ch5",
     "The ideal gas law is PV = nRT. Real gases deviate at high pressure and low temperature, where "
     "molecular volume and intermolecular attractions matter. At STP, one mole of an ideal gas occupies 22.4 L."),
    ("gc06", "genchem", "Zumdahl ch12",
     "Reaction rate depends on the rate-determining (slowest) step. The rate law is determined "
     "experimentally, not from stoichiometry. A catalyst speeds a reaction by lowering activation "
     "energy and is not consumed."),
    # Physics
    ("ph01", "physics", "Halliday ch7",
     "The work-energy theorem states that the net work done on an object equals its change in "
     "kinetic energy: W_net = dKE. Kinetic energy is (1/2)mv^2. Work by a constant force is "
     "W = Fd cos(theta)."),
    ("ph02", "physics", "Halliday ch8",
     "Mechanical energy is conserved when only conservative forces act. Gravitational potential "
     "energy near Earth's surface is mgh. In the presence of friction, mechanical energy is not "
     "conserved and energy is dissipated as heat."),
    ("ph03", "physics", "Halliday ch14",
     "For an incompressible fluid, the continuity equation A1v1 = A2v2 conserves volume flow rate. "
     "Bernoulli's equation relates pressure, height, and speed: P + (1/2)rho v^2 + rho g h = constant. "
     "Faster flow corresponds to lower pressure."),
    ("ph04", "physics", "Halliday ch21",
     "Coulomb's law gives the force between charges as F = k q1 q2 / r^2. Like charges repel and "
     "opposite charges attract. The electric field of a point charge is E = kq/r^2, pointing away "
     "from positive charge."),
    ("ph05", "physics", "Halliday ch16",
     "Sound intensity level in decibels is beta = 10 log(I/I0), with I0 = 10^-12 W/m^2. Because it "
     "is logarithmic, every 10 dB corresponds to a tenfold change in intensity. The Doppler effect "
     "shifts observed frequency when source and observer move relative to each other."),
    ("ph06", "physics", "Halliday ch33",
     "For a thin lens, 1/f = 1/do + 1/di, and magnification m = -di/do. A converging lens has "
     "positive focal length; a real image forms when the object is beyond the focal point. Diverging "
     "lenses always form virtual, upright, reduced images."),
    # Biology
    ("bi01", "biology", "Campbell ch7",
     "The plasma membrane controls what enters and exits the cell. Passive transport (diffusion, "
     "osmosis, facilitated diffusion) requires no energy and moves down a gradient. Active transport "
     "uses ATP to move substances against their gradient, as with the sodium-potassium pump."),
    ("bi02", "biology", "Campbell ch12",
     "The cell cycle consists of interphase (G1, S, G2) and the mitotic phase. DNA replicates during "
     "S phase. Checkpoints (notably G1/S and G2/M) ensure fidelity; the G1 checkpoint is the primary "
     "restriction point regulated by cyclins and cyclin-dependent kinases."),
    ("bi03", "biology", "Campbell ch17",
     "In transcription, RNA polymerase synthesizes mRNA from a DNA template 5' to 3'. In eukaryotes, "
     "pre-mRNA is processed with a 5' cap, a poly-A tail, and splicing to remove introns. Translation "
     "then occurs at the ribosome, reading codons to assemble a polypeptide."),
    ("bi04", "biology", "Campbell ch48",
     "A neuron maintains a resting membrane potential near -70 mV, set largely by potassium leak "
     "channels and the sodium-potassium pump. An action potential is triggered when depolarization "
     "reaches threshold, opening voltage-gated sodium channels for a rapid, all-or-none spike."),
    ("bi05", "biology", "Campbell ch45",
     "The endocrine system uses hormones for slow, widespread signaling. Steroid hormones are "
     "lipid-soluble and bind intracellular receptors to alter transcription; peptide hormones bind "
     "cell-surface receptors and act through second messengers like cAMP."),
    ("bi06", "biology", "Campbell ch44",
     "The nephron is the functional unit of the kidney. Filtration occurs at the glomerulus; the "
     "proximal tubule reabsorbs most solutes; the loop of Henle establishes a medullary osmotic "
     "gradient; ADH increases water reabsorption in the collecting duct."),
    # Psych/Soc (behavioral sciences)
    ("ps01", "psychsoc", "Kaplan Behavioral ch4",
     "Classical conditioning pairs a neutral stimulus with an unconditioned stimulus until it elicits "
     "a conditioned response. Operant conditioning changes behavior through reinforcement and "
     "punishment; variable-ratio schedules produce the highest, most persistent response rates."),
    ("ps02", "psychsoc", "Kaplan Behavioral ch7",
     "Weber's law states that the just-noticeable difference between two stimuli is proportional to "
     "the magnitude of the stimuli. Signal detection theory separates sensitivity from response bias "
     "in how observers detect stimuli against noise."),
]

# --- Held-out queries with relevance judgments (qrels) -------------------
# (qid, query text, [relevant chunk ids])
# Queries are deliberately PARAPHRASED with low lexical overlap to their source
# chunk (synonyms, lay phrasing) -- the realistic case where a student asks in
# their own words. This is where a pure keyword baseline (BM25) is challenged
# and semantic / hybrid retrieval earns its keep.
QUERIES_DATA = [
    ("q01", "In sugar breakdown, which protein governs the committed, slowest control point, and what switches it on or off?", ["bc01"]),
    ("q02", "Per molecule of blood sugar, what net energy currency and electron carriers does the initial cytoplasmic breakdown to pyruvate produce?", ["bc01"]),
    ("q03", "Why can the liver keep soaking up sugar when other tissues stop, thanks to its distinctive phosphorylating enzyme?", ["bc02"]),
    ("q04", "In the cycle that fully oxidizes acetyl groups to carbon dioxide, which enzyme is the bottleneck?", ["bc03"]),
    ("q05", "What harnesses the proton gradient across the inner mitochondrial membrane to assemble the cell's energy currency?", ["bc04"]),
    ("q06", "In enzyme kinetics, what does the constant equal to the substrate level at half-maximal speed tell you about binding?", ["bc05"]),
    ("q07", "A molecule fights for the active site. How does it change the apparent binding constant versus the top speed?", ["bc06"]),
    ("q08", "What mainly drives a chain of amino acids to collapse into its compact folded shape?", ["bc08"]),
    ("q09", "How does the body coax the oxygen carrier to let go of more oxygen in hard-working, acidic tissue?", ["bc09"]),
    ("q10", "Which membrane ingredient keeps the bilayer from getting too rigid in the cold or too runny in the heat?", ["bc10"]),
    ("q11", "If you compress a gas-phase reaction, which way does the balance shift?", ["gc01"]),
    ("q12", "At what acidity is a weak-acid mixture most resistant to changes when acid or base is added?", ["gc02"]),
    ("q13", "How is the standard spontaneity measure tied to where a reaction settles at balance?", ["gc03"]),
    ("q14", "In a battery that runs on its own, at which terminal do electrons depart?", ["gc04"]),
    ("q15", "Can you read how fast a reaction goes straight off the balanced equation, or must you measure it?", ["gc06"]),
    ("q16", "What links the total push-times-distance on an object to its energy of motion?", ["ph01"]),
    ("q17", "Under what condition does an object's total useful energy stay constant during motion?", ["ph02"]),
    ("q18", "In flowing liquid, what happens to the push on the walls where the stream speeds up?", ["ph03"]),
    ("q19", "How does the influence field around a single charged particle weaken as you move away?", ["ph04"]),
    ("q20", "Why does adding ten to the loudness number correspond to ten times the power?", ["ph05"]),
    ("q21", "What separates moving a dissolved substance uphill using cellular fuel from letting it drift down its gradient?", ["bi01"]),
    ("q22", "During which stretch of a dividing cell's life is its full genome duplicated?", ["bi02"]),
    ("q23", "Why can some chemical messengers slip inside a cell and tune gene activity while others only knock from outside?", ["bi05"]),
    ("q24", "What holds a resting nerve cell's interior negative compared with the outside?", ["bi04"]),
    ("q25", "Which reward pattern makes a learned behavior the hardest to stamp out?", ["ps01"]),
]

# --- 50 human-authored GOLD cards ---------------------------------------
# (id, source chunk, type, front, back). Atomic, Wozniak-compliant.
GOLD_DATA = [
    ("g01", "bc01", "basic", "What is the rate-limiting enzyme of glycolysis?", "Phosphofructokinase-1 (PFK-1)."),
    ("g02", "bc01", "basic", "PFK-1 is allosterically inhibited by which two molecules?", "ATP and citrate."),
    ("g03", "bc01", "basic", "PFK-1 is allosterically activated by which two molecules?", "AMP and fructose-2,6-bisphosphate."),
    ("g04", "bc01", "basic", "Net ATP yield of glycolysis per glucose?", "2 ATP."),
    ("g05", "bc01", "basic", "Net NADH yield of glycolysis per glucose?", "2 NADH."),
    ("g06", "bc01", "basic", "Glycolysis converts glucose into two molecules of what?", "Pyruvate."),
    ("g07", "bc02", "basic", "Which enzyme catalyzes the first step of glycolysis?", "Hexokinase."),
    ("g08", "bc02", "basic", "Hexokinase is inhibited by which product?", "Glucose-6-phosphate."),
    ("g09", "bc02", "basic", "Why is liver glucokinase not inhibited by glucose-6-phosphate?", "It has a high Km, letting the liver buffer blood glucose."),
    ("g10", "bc03", "basic", "How many CO2 are released per acetyl-CoA in the citric acid cycle?", "Two CO2."),
    ("g11", "bc03", "basic", "Rate-limiting enzyme of the citric acid cycle?", "Isocitrate dehydrogenase."),
    ("g12", "bc03", "basic", "Per acetyl-CoA, the citric acid cycle yields how many NADH?", "3 NADH."),
    ("g13", "bc04", "basic", "What drives ATP synthase during oxidative phosphorylation?", "The proton-motive force (proton gradient)."),
    ("g14", "bc04", "basic", "Approximate ATP yield from complete oxidation of one glucose?", "About 30-32 ATP."),
    ("g15", "bc05", "basic", "What does Km equal in terms of substrate concentration?", "The substrate concentration at half Vmax."),
    ("g16", "bc05", "basic", "A lower Km indicates what about enzyme-substrate affinity?", "Higher affinity."),
    ("g17", "bc06", "basic", "How does a competitive inhibitor affect apparent Km?", "It raises the apparent Km."),
    ("g18", "bc06", "basic", "How does a noncompetitive inhibitor affect Vmax?", "It lowers Vmax."),
    ("g19", "bc07", "basic", "At physiological pH, which amino acid side chains are negatively charged?", "Acidic side chains: aspartate and glutamate."),
    ("g20", "bc08", "basic", "Which effect primarily drives protein tertiary folding?", "The hydrophobic effect."),
    ("g21", "bc08", "basic", "What stabilizes alpha helices and beta sheets?", "Backbone hydrogen bonds."),
    ("g22", "bc09", "basic", "In the Bohr effect, how does lower pH change hemoglobin's O2 affinity?", "It lowers oxygen affinity, promoting O2 release."),
    ("g23", "bc09", "basic", "Which oxygen-binding curve is sigmoidal, hemoglobin or myoglobin?", "Hemoglobin (cooperative binding)."),
    ("g24", "bc10", "basic", "What does cholesterol do to membrane fluidity?", "It buffers fluidity against temperature changes."),
    ("g25", "gc01", "basic", "Increasing pressure shifts a gas equilibrium toward which side?", "The side with fewer moles of gas."),
    ("g26", "gc02", "basic", "State the Henderson-Hasselbalch equation.", "pH = pKa + log([A-]/[HA])."),
    ("g27", "gc02", "basic", "A buffer's capacity is greatest when pH equals what?", "The pKa (where [A-] = [HA])."),
    ("g28", "gc03", "basic", "Write the Gibbs free energy equation.", "dG = dH - T*dS."),
    ("g29", "gc03", "basic", "A negative dG indicates what kind of process?", "Spontaneous (exergonic)."),
    ("g30", "gc03", "basic", "Relate dG0 to the equilibrium constant K.", "dG0 = -RT ln K."),
    ("g31", "gc04", "basic", "At which electrode does oxidation occur?", "The anode."),
    ("g32", "gc04", "basic", "Is a galvanic cell with positive cell potential spontaneous?", "Yes."),
    ("g33", "gc05", "basic", "State the ideal gas law.", "PV = nRT."),
    ("g34", "gc05", "basic", "Volume of one mole of ideal gas at STP?", "22.4 L."),
    ("g35", "gc06", "basic", "The overall reaction rate is limited by which step?", "The rate-determining (slowest) step."),
    ("g36", "gc06", "basic", "How does a catalyst speed a reaction?", "By lowering the activation energy; it is not consumed."),
    ("g37", "ph01", "basic", "State the work-energy theorem.", "Net work equals the change in kinetic energy."),
    ("g38", "ph01", "basic", "Formula for kinetic energy?", "(1/2)mv^2."),
    ("g39", "ph02", "basic", "Gravitational potential energy near Earth's surface?", "mgh."),
    ("g40", "ph02", "basic", "When is mechanical energy conserved?", "When only conservative forces act."),
    ("g41", "ph03", "basic", "According to Bernoulli, faster fluid flow corresponds to what pressure?", "Lower pressure."),
    ("g42", "ph03", "basic", "State the continuity equation for an incompressible fluid.", "A1v1 = A2v2."),
    ("g43", "ph04", "basic", "State Coulomb's law.", "F = k*q1*q2 / r^2."),
    ("g44", "ph05", "basic", "A 10 dB increase corresponds to what change in intensity?", "A tenfold increase."),
    ("g45", "ph06", "basic", "Thin-lens equation?", "1/f = 1/do + 1/di."),
    ("g46", "bi01", "basic", "What powers active transport?", "ATP (energy), to move against the gradient."),
    ("g47", "bi02", "basic", "In which phase of the cell cycle does DNA replicate?", "S phase."),
    ("g48", "bi04", "basic", "Typical resting membrane potential of a neuron?", "About -70 mV."),
    ("g49", "bi05", "basic", "How do steroid hormones alter cell behavior?", "They are lipid-soluble and bind intracellular receptors to alter transcription."),
    ("g50", "ps01", "basic", "Which reinforcement schedule yields the highest, most persistent response rate?", "Variable-ratio."),
]


# --- Calibration BAD cards (labeled not-usable) --------------------------
# Deliberately violate the rules so we can measure the judge's agreement
# (Cohen's kappa) against human labels: gold=usable, these=not-usable.
# (id, source, type, front, back, why) -- targets the real deck failure modes.
CALIB_BAD = [
    ("b01", "bc01", "basic", "Tell me everything about glycolysis.",
     "Glycolysis is a ten-step cytoplasmic pathway that converts glucose into two pyruvate, "
     "generating a net of 2 ATP and 2 NADH; it begins with hexokinase phosphorylating glucose, "
     "proceeds through the committed PFK-1 step which is inhibited by ATP and citrate and "
     "activated by AMP and fructose-2,6-bisphosphate, and ends with pyruvate kinase; the pathway "
     "feeds pyruvate into the citric acid cycle under aerobic conditions.", "wall-of-text back"),
    ("b02", "bc01", "cloze", "Glycolysis yields {{c1::2 ATP}}, {{c2::2 NADH}}, and {{c3::2 pyruvate}} from {{c4::1 glucose}}.",
     "multi-blank enumeration", "multi-blank cloze enumeration"),
    ("b03", "bc03", "basic", "What is the rate-limiting enzyme of the citric acid cycle?",
     "Phosphofructokinase-1.", "factually wrong (it is isocitrate dehydrogenase)"),
    ("b04", "bc05", "basic", "What is Km?",
     "It depends; kinetics is complicated and there are many factors to consider.", "non-answer / ambiguous"),
    ("b05", "gc02", "basic", "List everything about buffers.",
     "A buffer is a weak acid and its conjugate base; it resists pH change; the Henderson-Hasselbalch "
     "equation is pH = pKa + log([A-]/[HA]); capacity is maximal at pH = pKa; buffers are used in blood "
     "(bicarbonate) and in the lab.", "wall-of-text enumeration back"),
    ("b06", "ph01", "basic", "Work-energy theorem?",
     "Energy is always conserved in the universe.", "wrong/irrelevant answer"),
    ("b07", "bi02", "basic", "What are all the phases of the cell cycle and what happens in each?",
     "G1 (growth), S (DNA replication), G2 (growth and preparation), and M (mitosis: prophase, "
     "metaphase, anaphase, telophase, then cytokinesis).", "non-atomic, multi-part"),
    ("b08", "gc03", "basic", "Gibbs free energy?",
     "dG = dH + T*dS.", "factually wrong sign (should be minus T*dS)"),
    ("b09", "bc09", "basic", "Describe hemoglobin.",
     "Hemoglobin is a tetrameric protein with four heme groups that binds oxygen cooperatively giving "
     "a sigmoidal curve, exhibits the Bohr effect, and is found in red blood cells.", "wall-of-text, non-atomic"),
    ("b10", "ph04", "basic", "Coulomb's law says the force is proportional to what?",
     "The force is inversely proportional to distance.", "wrong (inverse-square, not inverse)"),
    ("b11", "bi04", "basic", "Resting potential?", "Positive 70 mV.", "wrong sign (should be about -70 mV)"),
    ("b12", "gc05", "basic", "Volume of a mole of gas at STP?", "24.5 liters.", "wrong value (22.4 L)"),
    ("b13", "bc06", "basic", "How do inhibitors work in general and what are all the types?",
     "There are competitive, noncompetitive, uncompetitive, and mixed inhibitors, each affecting Km "
     "and Vmax differently in ways shown on Lineweaver-Burk plots.", "non-atomic, enumeration"),
    ("b14", "ps01", "basic", "Explain conditioning.",
     "Classical conditioning pairs stimuli while operant conditioning uses reinforcement and punishment, "
     "and there are fixed and variable ratio and interval schedules.", "wall-of-text, multi-topic"),
    ("b15", "bc04", "basic", "ATP from glucose?", "Exactly 38 ATP, always.", "overspecified/outdated (about 30-32)"),
]


def _write(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def main():
    _write(CORPUS, [{"id": i, "discipline": d, "source": s, "text": t} for i, d, s, t in CHUNKS])
    _write(QUERIES, [{"qid": q, "query": text, "relevant": rel} for q, text, rel in QUERIES_DATA])
    _write(GOLD, [{"id": i, "source_id": s, "type": ty, "front": fr, "back": bk}
                  for i, s, ty, fr, bk in GOLD_DATA])
    _write(CALIB, [{"id": i, "source_id": s, "type": ty, "front": fr, "back": bk,
                    "why_bad": why, "usable": False} for i, s, ty, fr, bk, why in CALIB_BAD])
    print(f"corpus:     {len(CHUNKS)} chunks   -> {CORPUS}")
    print(f"queries:    {len(QUERIES_DATA)} queries  -> {QUERIES}")
    print(f"gold cards: {len(GOLD_DATA)} cards    -> {GOLD}")
    print(f"calib bad:  {len(CALIB_BAD)} cards    -> {CALIB}")
    assert len(GOLD_DATA) == 50, "gold set must be 50 cards"
    # Every query's relevant chunks must exist in the corpus.
    ids = {c[0] for c in CHUNKS}
    for q, _, rel in QUERIES_DATA:
        for r in rel:
            assert r in ids, f"{q} references missing chunk {r}"
    for g in GOLD_DATA:
        assert g[1] in ids, f"gold {g[0]} references missing chunk {g[1]}"
    print("validated: all references resolve.")


if __name__ == "__main__":
    main()
