# Pilot Yield Report — Citing-Claim Extraction

## Pipeline tested
For each cited source, the full extraction pipeline was run end-to-end:
1. **OpenAlex `openalex_citations`** → list of papers that cite the source (with `is_oa`, PMID).
2. **PubMed `convert_article_ids`** → filter to citers that have a **PMCID** (PMC open-access full text).
3. **NCBI EFetch (PMC JATS XML)** → fetch the citer's structured full text. *(Note: the PubMed MCP `get_full_text_article` strips inline citation markers, so raw JATS XML from EFetch is used instead — it preserves `<xref ref-type="bibr" rid="...">` markers and the structured `<ref-list>`.)*
4. **Reference matching** → find the `<ref>` entry in the citer whose `<pub-id pub-id-type="pmid|doi">` matches the cited source, giving its reference id (`rid`).
5. **Sentence extraction** → find every sentence containing an `<xref>` pointing to that `rid`, extract it verbatim.
6. **Fabrication guard** → each extracted sentence is confirmed as a verbatim substring of the citer's whitespace-normalized full text (100% pass by construction; independently re-verified on a sample).

**Key consequence:** claim→cited-source linkage is now **metadata-grounded** (via the JATS `rid`/`pub-id` match), not inferred from proximity. This directly serves the project rule to prefer structured record data over free-text inference.

## Yield (3 pilot sources, one per category)

| Source | Category | PMC citers examined | Ref matched | Verbatim claim extracted |
|---|---|---|---|---|
| Wakefield MMR/autism (PMID 9500320) | A retracted | 13 | 5 (38%) | 3 |
| Resveratrol in mice (PMID 17086191) | B species | 15 | 12 (80%) | 8 |
| Pembrolizumab melanoma trial (PMID 25891173) | C control | 15 | 14 (93%) | 8 |
| **TOTAL** | | **43** | **31 (72%)** | **19 (44%)** |

**Bottom line: 44% of examined PMC citers yield a usable verbatim claim.** With 13–46 PMC-indexed citers available per source (before examination) and 5 candidate sources staged per category, hitting 5–7 verified cases per category is comfortable. **Yield is NOT a constraint.**

## Two qualitative findings that shape case selection (need your awareness)

**1. Category A — many citers explicitly flag the retraction.** For the Wakefield paper, several citing sentences already say "fraudulent research," "now retracted study," "debunked claim." Ground truth ("the cited paper is retracted") holds regardless, but the *useful* stress-test for a verification tool is an **uncritical citation** that treats the retracted finding as valid. Both exist in the citer pool. **Plan: prefer neutral/uncritical citing claims where available, and label each A case with whether the citer acknowledged the retraction** (an extra `citer_acknowledges_retraction` field) — this is itself useful eval metadata. Wakefield may be a poor choice precisely because it's so infamous; lower-profile retractions give cleaner uncritical citations.

**2. Category B — asserting the mismatch is the part that needs a claim-side judgment.** The cited paper's animal-only scope is fully metadata-grounded (MeSH `Animals`/`Mice`, no `Humans`). But whether a *citing claim* over-generalizes to humans depends on the claim's wording. Some citers correctly restrict to "in mice"; those are NOT mismatches. Only citers that drop the species qualifier or assert human/clinical relevance are true Category B cases. **Plan: extract the claim verbatim, then classify its asserted scope by explicit lexical markers ("in humans", "patients", "clinical") = text-grounded; anything requiring interpretation = model-inferred and flagged separately** — exactly the metadata-grounded vs model-inferred split the project requires. This means Category B will carry more `model-inferred` flags than A or C, honestly marked.

## Recommendation
Proceed to full build with the staged candidates. No scope reduction needed. I'll (a) add the `citer_acknowledges_retraction` field to Category A, and (b) route Category B claim-scope classification through the explicit-marker vs inferred split. Awaiting your go-ahead.
