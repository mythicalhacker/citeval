# Adjudicator override log

Grader model: `claude-opus-4-8` (task-pinned). Every grade grounded in a verbatim `decisive_span`.
Three cases required adjudicator intervention beyond the first automated pass:

## A13 → fully-supported (confidence: low)

model graded 'contradicted' (twice, incl. under a sharpened scope-constancy prompt) solely on the patient-sex descriptor. Per rubric, population/demographic mismatch (sex) is the separate scope axis, not substance; twin case A14 (same paper, correct sex) is fully-supported. Adjudicator override to fully-supported for rubric-compliance and internal consistency. Raw model grade retained in this audit note.

- Final rationale: Holding population scope constant per rubric, the paper fully backs the substantive claim: a decellularized cadaveric (donor) trachea seeded with the recipient's own epithelial and MSC-derived chondrocyte cells replaced the left main bronchus. The 'young man' vs paper's 'woman' discrepancy is a population/demographic attribute scored on the separate scope axis, not substance (abstract only; confidence low).
- Decisive span: "We removed cells and MHC antigens from a human donor trachea, which was then readily colonised by epithelial cells and mesenchymal stem-cell-derived chondrocytes that had been cultured from cells taken from the recipient"

## Bs11 → partially-supported (confidence: medium)

first pass recorded 'contradicted' with a self-reversing rationale (internal defect); the paper actually reports depressed NAMPT in human failing hearts, supporting the reduction element. Adjudicated to partially-supported: reduction-in-failing-hearts backed, 'rate-limiting' descriptor not in this paper.

- Final rationale: The paper backs one part of the multi-part claim — NAMPT is depressed in human failing hearts (the reduction 'reported for patients with HFrEF') — but never characterizes NAMPT as 'the rate-limiting enzyme in the NAD+ salvage pathway,' describing it only as the enzyme converting NAM to NMN.
- Decisive span: "We observed a similar shift in human patients from predominant expression of NAMPT in healthy hearts to increased NMRK2 and depressed NAMPT in failing hearts"

## Bs05 → fully-supported (confidence: high)

first pass: supported-with-overreach (penalized mouse-vs-human on substance axis); re-graded fully-supported holding species constant per rubric.

- Final rationale: The claim cites this paper to support that bacteriophages are important microorganisms in the gut community affecting health; the paper demonstrates that lytic phages modulate the gut microbiota and metabolome with implications for the mammalian host, directly backing the phage-importance claim.
- Decisive span: "Our results also reveal that phage predation in the gut microbiota has potential impact on the mammalian host, as manifested by modulation of the gut metabolome."

