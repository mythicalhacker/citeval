# Citation-grounding demo — worked records

_All fields below are pulled from record metadata via NCBI E-utilities `efetch` (db=pubmed)
and NLM MeSH linked-data tree numbers (id.nlm.nih.gov). MeSH organism vs. population split
is keyed on the authoritative MeSH tree, not text inference._

## Record 1 — PMID 9500320 (retracted)
**Title:** Ileal-lymphoid-nodular hyperplasia, non-specific colitis, and pervasive developmental disorder in children.
**Abstract (first 400 chars):** BACKGROUND: We investigated a consecutive series of children with chronic enterocolitis and regressive developmental disorder.
METHODS: 12 children (mean age 6 years [range 3-10], 11 boys) were referred to a paediatric gastroenterology unit with a history of normal development followed by loss of acquired skills, including language, together with diarrhoea and abdominal pain. Children underwent ga…

| Axis | Value | Source field |
|---|---|---|
| Organism | Humans | MeSH tree `B` (organisms) |
| Age group | Child, Child, Preschool | MeSH tree `M01.060` |
| Sex | Female, Male | MeSH sex check-tags |
| **Retraction status** | **RETRACTED** | `PublicationType` + `CommentsCorrections` |

Retraction / EoC notices (structured linkages):
  - `RetractionIn` → notice PMID 15016483: Lancet. 2004 Mar 6;363(9411):750. doi: 10.1016/S0140-6736(04)15715-2.
  - `RetractionIn` → notice PMID 20137807: Lancet. 2010 Feb 6;375(9713):445. doi: 10.1016/S0140-6736(10)60175-4.
  - `ExpressionOfConcernIn` → notice PMID 21971344: Eur J Gastroenterol Hepatol. 2011 Nov;23(11):1082. doi: 10.1097/MEG.0b013e328349d184.

## Record 2 — PMID 27189859 (mouse-only compound/tumor study)
**Title:** Penfluridol suppresses pancreatic tumor growth by autophagy-mediated apoptosis.
**Abstract (first 400 chars):** Pancreatic tumors exhibit enhanced autophagy as compared to any other cancer, making it resistant to chemotherapy. We evaluated the effect of penfluridol against pancreatic cancer. Penfluridol treatment induced apoptosis and inhibited the growth of Panc-1, BxPC-3 and AsPC-1, pancreatic cancer cells with IC50 ranging between 6-7 μM after 24 h of treatment. Significant autophagy was induced by penfl…

| Axis | Value | Source field |
|---|---|---|
| Organism | Animals, Mice | MeSH tree `B` (organisms) |
| Age group | (none) | MeSH tree `M01.060` |
| **Retraction status** | **NONE_FOUND** | `PublicationType` + `CommentsCorrections` |

---

# Sample citation-check verdict

**Claim:** "Compound X reduces tumor growth in humans"
**Cited paper:** PMID 27189859 — Penfluridol suppresses pancreatic tumor growth by autophagy-mediated apoptosis.

**Overall: CITATION DOES NOT SUPPORT CLAIM (species scope mismatch)**

### Layer A — claim parse (MODEL-INFERRED, medium confidence)
Asserted organism: **Humans** (parsed from the phrase "in humans").

### Layer B — paper scope (METADATA-GROUNDED)
Paper MeSH organism tags: **Animals, Mice**
Source: efetch <MeshHeading><DescriptorName> + NLM MeSH tree numbers (id.nlm.nih.gov)

### Grade — species axis
**SCOPE_MISMATCH** · tier=`high` · provenance=`metadata-grounded`
Claim asserts 'Humans'. Paper MeSH organism tags = ['Animals', 'Mice'] (animal model, no Humans tag). Human effect not supported by cited paper.

### Axes flagged UNVERIFIABLE (not fabricated)
- **dose**: No structured dose field in PubMed metadata; would require full-text extraction (model-inferred, flagged).
- **population_subgroup**: Paper has no human population/age tags (animal study); N/A.
- **effect_direction**: Whether 'reduces' matches the paper's reported direction requires reading Results text (model-inferred, out of metadata scope).

_Citation: metadata from PubMed (NCBI). Record 1 DOI 10.1016/s0140-6736(97)11096-0; Record 2 via PubMed PMID 27189859._
