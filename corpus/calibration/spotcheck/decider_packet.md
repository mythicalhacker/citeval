# Substantive-support grading packet — independent ground-truth adjudication

You are the **decider**: an independent expert reading each cited paper from scratch to establish the
authoritative substantive-support grade. Grade **blind** — you are shown no prior grade of any kind.

## What you are grading
For each case: a **claim** (a sentence from a citing paper) and the **cited paper** it leans on. Decide
how well the cited paper's *actual reported findings* back the claim's asserted **effect, direction,
mechanism, and magnitude/certainty**.

## THE ONE RULE THAT TRIPS PEOPLE UP — hold scope & retraction constant
Grade **substance only**. Do **NOT** lower the grade because the paper is the wrong species/population/
dose, or because it was later retracted — those are scored on separate axes. A mouse-only or retracted
paper can still be **fully-supported** on substance if its finding backs the claim. Judge: *holding
scope constant, does the reported result support this claim?*

## The 6-level scale (best → worst) — apply the FIRST test that fires
1. **fully-supported** — the paper shows exactly what the claim asserts; claim preserves the paper's
   certainty/hedges. (A claim that correctly states a NARROW scope is fully-supported — never penalize
   correct narrowness.)
2. **supported-with-overreach** — the finding is there but the claim over-asserts it: bigger effect,
   hardened certainty (drops a hedge), or a generalized mechanism.
3. **partially-supported** — the claim is multi-part and some conjuncts are supported, others not.
4. **technically-true-but-misleading** — every atomic statement is literally defensible, but the
   framing / selection / causal language misleads.
5. **unsupported-for-the-claim** — the paper contains no finding bearing on this claim's intervention
   and outcome (scope held constant).
6. **contradicted** — the paper's finding is OPPOSITE in direction to the claim.

Two off-scale outcomes:
- **N/A — non-substantiating** — the citation's function is a method, dataset, tool, or background/
  passing pointer, not evidence for this knowledge claim.
- **NOT_ENOUGH_INFO** — the available text is genuinely insufficient to place a grade.

## How to read the paper
Obtain the **fullest version you can**: PubMed Central full text (preferred), else the publisher via
DOI, else the PubMed abstract. Note which you used in `evidence_source`. Quote **verbatim** — every
decisive span must be a real substring of the paper.

## Output — append one JSON object per case to `spotcheck_decider.jsonl`:
{"case_id","grade","confidence","evidence_source","boundary_test_fired","decisive_quotes":["...","..."],"rationale"}
- `confidence`: your probability [0,1] that this grade is correct.
- `decisive_quotes`: 2–4 verbatim spans from the paper that drove the grade.
- Grade independently; do not infer or guess what any automated system concluded.

---

## Cases to grade
### Ch10
- **Claim (verbatim):** Recent preclinical development of clinical-grade iPSC lines from Parkinson’s patients revealed ongoing concerns related to genomic stability and cell line quality control (Jeon et al., 2025).
- **Cited paper:** Pre-clinical safety and efficacy of human induced pluripotent stem cell-derived products for autologous cell therapy in Parkinson's disease.
- **Journal:** Cell stem cell
- **PMID:** 39952239  |  **DOI:** 10.1016/j.stem.2025.01.006

### Ce11
- **Claim (verbatim):** Remarkably, recent epidemiological data exhibit an increased association of obesity and allergy [200,201,202,203].
- **Cited paper:** Relationship between infant weight gain and later asthma.
- **Journal:** Pediatric allergy and immunology : official publication of the European Society of Pediatric Allergy and Immunology
- **PMID:** 19725894  |  **DOI:** 10.1111/j.1399-3038.2009.00926.x

### Ch03
- **Claim (verbatim):** Studies in children showed high rate of viral/viral co-infections (18−34%) [7,8,9,19], although it should be taken into account that children included in these studies were hospitalized for respiratory infections, which could explain the high percentage of co-infections.
- **Cited paper:** High Frequency of Viral Co-Detections in Acute Bronchiolitis.
- **Journal:** Viruses
- **PMID:** 34073414  |  **DOI:** 10.3390/v13060990

### A27
- **Claim (verbatim):** Similarly, a previous study provided strong evidence that miR-214 could promote fibroblast differentiation of adipose-derived MSCs by restoring elastin expression to improve PFD in rats with birth trauma [31].
- **Cited paper:** MicroRNA-214 Affects Fibroblast Differentiation of Adipose-Derived Mesenchymal Stem Cells by Targeting Mitofusin-2 during Pelvic Floor Dysfunction in SD Rats with Birth Trauma.
- **Journal:** Cellular physiology and biochemistry : international journal of experimental cellular physiology, biochemistry, and pharmacology
- **PMID:** 28772265  |  **DOI:** 10.1159/000479570

### A17
- **Claim (verbatim):** Case series by Sys et al28 and Iwamoto et al8 each found a high percentage of return to sport (89.3% and 87.5%, respectively) with nonoperative treatment and bracing.
- **Cited paper:** Return to sports activity by athletes after treatment of spondylolysis.
- **Journal:** World journal of orthopedics
- **PMID:** 22474624  |  **DOI:** 10.5312/wjo.v1.i1.26

### A13
- **Claim (verbatim):** In 2008, the main left bronchus in a young man was replaced with a decellularized cadaveric trachea seeded with the patient's own cells [515].
- **Cited paper:** Clinical transplantation of a tissue-engineered airway.
- **Journal:** Lancet (London, England)
- **PMID:** 19022496  |  **DOI:** 10.1016/S0140-6736(08)61598-6

### Ch13
- **Claim (verbatim):** In particular, increased mitochondrial oxidative stress in fibroblast-derived induced pluripotent stem cells, differentiated into human nigral DA neurons, triggers a DA-dependent toxic cascade, leading to oxidized DA accumulation and reduction in glucocerebrosidase enzymatic activity, lysosomal dysfunctions, and α-syn accumulation [49].
- **Cited paper:** Dopamine oxidation mediates mitochondrial and lysosomal dysfunction in Parkinson's disease.
- **Journal:** Science (New York, N.Y.)
- **PMID:** 28882997  |  **DOI:** 10.1126/science.aam9080

### A25
- **Claim (verbatim):** Chen Guanghui found that Mfn2 can significantly inhibit VSMC proliferation in vitro and in vivo, and this action has nothing to do with mitochondrial fusion; Furthermore rats and humans have 95.2% Mfn2 homology 35.
- **Cited paper:** MicroRNA-214 Affects Fibroblast Differentiation of Adipose-Derived Mesenchymal Stem Cells by Targeting Mitofusin-2 during Pelvic Floor Dysfunction in SD Rats with Birth Trauma.
- **Journal:** Cellular physiology and biochemistry : international journal of experimental cellular physiology, biochemistry, and pharmacology
- **PMID:** 28772265  |  **DOI:** 10.1159/000479570

