# MANAGER ANSWER KEY — do NOT give to the decider

Join `spotcheck_decider.jsonl` back to this. For each contested case, does the decider match the
REFERENCE (reference validated), match C4 (C4 was right, reference wrong), or neither (both off)?
The 2 controls (Ch13, A25) are exact C4=reference agreements — the decider should agree there too;
if it doesn't, the decider is on a different scale and the whole check is suspect.

## Ch10 — CONTESTED (dist 3)
- C4: **technically-true-but-misleading** (conf 0.71)
- reference: **fully-supported** (grader_conf high)
- reference rationale: The paper is precisely a preclinical development of clinical-grade iPSC lines from Parkinson's patients that raises genomic-stability and QC concerns—e.g., a Coriell-fibroblast-derived line showed compromised genomic integrity and tumorigenicity, and the authors explicitly advocate stricter genomic-integrity QC criteria amid escalating reports of genomic aberrations.

## Ce11 — CONTESTED (dist 3)
- C4: **contradicted** (conf 0.86)
- reference: **partially-supported** (grader_conf medium)
- reference rationale: The claim concerns an association of obesity and allergy; this paper studies infant weight-gain pattern and asthma outcomes (not obesity per se and not allergy broadly), and it found weight-gain pattern associated with asthma exacerbations but notably higher atopy (IgE, skin-test positivity) in the slow/decelerated group — an inverse rather than positive obesity–allergy link. It supports an obesity/weight–asthma connection but not cleanly an "obesity and allergy" positive association.

## Ch03 — CONTESTED (dist 2)
- C4: **technically-true-but-misleading** (conf 1.0)
- reference: **supported-with-overreach** (grader_conf high)
- reference rationale: The claim cites this paper for a viral/viral co-infection rate of 18−34%, but the paper reports a co-detection rate of 55% in its own cohort (citing 34% and 61% from other studies as comparison range). The paper does confirm the "hospitalized for respiratory infections" caveat, but its headline co-detection figure (55%) exceeds the 18−34% range attributed to it.

## A27 — CONTESTED (dist 2)
- C4: **technically-true-but-misleading** (conf 1.0)
- reference: **supported-with-overreach** (grader_conf low)
- reference rationale: The abstract confirms miR-214 promotes fibroblast differentiation of ADMSCs and improves PFD in birth-trauma rats, but the mechanism is stated as down-regulating Mfn2 (its target gene), not "restoring elastin expression"; elastin was one of several upregulated markers, so the claim mischaracterizes the mechanism.

## A17 — CONTESTED (dist 2)
- C4: **partially-supported** (conf 0.43)
- reference: **unsupported-for-the-claim** (grader_conf low)
- reference rationale: The claim attributes an 87.5% return-to-sport rate to Iwamoto et al with nonoperative treatment, but this abstract is a review reporting conservative-treatment return rates ranging 80.0%–89.3%; the specific 87.5% figure does not appear, and the paper is a meta-review rather than a single case series with that value.

## A13 — CONTESTED (dist 2)
- C4: **partially-supported** (conf 0.57)
- reference: **fully-supported** (grader_conf low)
- reference rationale: Holding population scope constant per rubric, the paper fully backs the substantive claim: a decellularized cadaveric (donor) trachea seeded with the recipient's own epithelial and MSC-derived chondrocyte cells replaced the left main bronchus. The 'young man' vs paper's 'woman' discrepancy is a population/demographic attribute scored on the separate scope axis, not substance (abstract only; confidence low).

## Ch13 — CONTROL (agree)
- C4: **fully-supported** (conf 1.0)
- reference: **fully-supported** (grader_conf high)
- reference rationale: The paper's own discussion states verbatim that elevated mitochondrial oxidant stress in human iPSC-derived nigral DA neurons triggers a dopamine-dependent toxic cascade leading to oxidized dopamine accumulation, reduced GCase activity, lysosomal dysfunction, and α-synuclein accumulation — matching every element of the claim.

## A25 — CONTROL (agree)
- C4: **unsupported-for-the-claim** (conf 1.0)
- reference: **unsupported-for-the-claim** (grader_conf low)
- reference rationale: The abstract concerns miR-214 targeting Mfn2 in fibroblast differentiation of ADMSCs during pelvic floor dysfunction; it says nothing about Mfn2 inhibiting VSMC proliferation, its independence from mitochondrial fusion, or rat/human Mfn2 homology (95.2%). Abstract only, so confidence is low.
