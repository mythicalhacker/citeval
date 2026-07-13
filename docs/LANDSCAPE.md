# Landscape — scientific citation-verification & claim-checking tools

*Positioning pass, 2026-07-12. Scope: tools and research that touch "does the cited paper support*
*this claim," not general literature search, writing, or reference-management assistants.*

citeval's target is narrow: **one claim, one cited paper**, three grounded axes (retraction,
species/population scope, graded substantive support), each finding stamped with a confidence tier
and provenance label, scored against a corpus rather than asserted. Nothing surveyed below does
that exact combination — most shipped tools work at literature scale on citations that already
exist, and most claim-verification research outputs a flat SUPPORT/REFUTE/NOT-ENOUGH-INFO label
from a single model pass. That gap is real, but it cuts both ways: read this as narrow-and-deep vs.
broad-and-shallow, not simply better-vs-worse.

## Comparison

| Tool / work | Approach | What it verifies | Grounding | Limits, specifically for "does THIS paper support THIS claim" |
|---|---|---|---|---|
| [Scite (Smart Citations)](https://scite.ai/features) | Deep-learning classifier over citation sentences, run at ingestion across the literature ([Nicholson et al. 2021](https://direct.mit.edu/qss/article/2/3/882/102990/scite-A-smart-citation-index-that-displays-the)) | Citation *stance* (supporting/contrasting/mentioning) per paper; flags retracted references on manuscript upload | Retraction flag is metadata (Crossref/PubMed/Retraction Watch); stance comes from a model classifier with a bare confidence % | Classifies citations that already exist, not a new claim you supply; no species/population axis; confidence has no disclosed provenance |
| [Consensus](https://consensus.app/) | Retrieval over ~200M papers + LLM synthesis + a "Consensus Meter" | Whether the literature broadly agrees with a question | Retrieved sources are real; the synthesis and meter are model-generated and unscored | Answers "what does the literature say" in aggregate, not "does this one paper support this one claim"; no retraction/scope axis |
| [Elicit](https://elicit.com/) | LLM extraction from uploaded full text into structured fields, each with a supporting quote | Data-extraction accuracy vs. a schema; a [feasibility study](https://pmc.ncbi.nlm.nih.gov/articles/PMC11921719/) reports 87–99% match to gold answers on tuned fields | Every field is quote-grounded | Extracts fields, doesn't adjudicate a claim against a source; no retraction/scope/graded-overreach axis |
| [SciSpace](https://scispace.com/) / [Scholarcy](https://www.scholarcy.com/) | Extractive, citation-aware summarization; PICO-style extraction; Scholarcy's "Research Quality Indicator" | Paper content, summarized with page-level pointers back to source text | Extractive by design (Scholarcy: does not invent information) | Summarizes the cited paper; doesn't compare it to an external claim or check retraction/scope |
| [Semantic Scholar (S2AG)](https://www.semanticscholar.org/product/api) | Citation graph + classifiers (intent, "highly influential") + SPECTER embeddings + TLDR ([Kinney et al. 2023](https://arxiv.org/pdf/2301.10140)) | Citation function and influence at corpus scale | Supervised classifiers trained on annotated corpora | Classifies a citation's rhetorical role, not the truth of a claim; no stance or scope judgment |
| Citation-intent classification research ([SciCite](https://huggingface.co/datasets/allenai/scicite)) | Supervised classification of citation sentences into Background / Method / Result-comparison | Rhetorical function of a citation | ~11K crowdsourced-labeled instances | Says *why* a paper is cited, not whether the cited finding actually backs the claim |
| SciFact / VeriSci ([Wadden et al. 2020](https://aclanthology.org/2020.emnlp-main.609/)) | Retrieval + sentence-level entailment over abstracts | SUPPORTS / REFUTES / NOT-ENOUGH-INFO vs. gold rationale sentences | 1,409 expert-written claims, gold-annotated | Flat 3-way label, no overreach grading; abstract-only; no retraction/species-scope axis; a benchmark, not a deployed checker |
| MultiVerS / LongChecker ([Wadden et al. 2022](https://aclanthology.org/2022.findings-naacl.6/)) | Longformer joint encoding of claim + full document; weak supervision for domain transfer | Document-level SUPPORTS/REFUTES/NEI + rationale sentences | Same 3-way gold-label tradition, extended to full text | Still flat 3-way; no retraction/scope axis; general-domain, not biomedical-metadata-aware |
| [DeepSciVerify](https://arxiv.org/abs/2605.27710) (May 2026) | Two-stage LLM pipeline: verify at abstract level, escalate to full-text RAG only when needed | Claim–citation alignment, 3-class, 86.7 Micro-F1 | LLM judgment over retrieved text; documents model-specific bias (over-caution vs. overconfidence) | The closest academic analog to citeval's substantive axis — but a single LLM judge, not an adversarial triad; no calibration/abstention mechanism reported; no retraction/scope grounding |
| Reference-hallucination detectors ([GhostCite](https://arxiv.org/pdf/2602.06718); [hallucination detection/correction](https://arxiv.org/html/2604.03173v1)) | Match generated references against bibliographic databases | Whether a *reference itself* exists and is correctly attributed | External DB matching (Crossref/PubMed/DOI) | Checks the citation is real, not whether a real citation supports the claim — an upstream, different problem |
| [Papermill Alarm](https://www.chemistryworld.com/features/ai-tools-tackle-paper-mill-fraud-overwhelming-peer-review/4022253.article) / [Problematic Paper Screener](https://theconversation.com/problematic-paper-screener-trawling-for-fraud-in-the-scientific-literature-246317) | Text-forensics + network analysis (tortured phrases, image duplication, authorship rings) across the literature | Whether a *paper itself* is likely fraudulent, at ~130M-paper scale | Heuristic fingerprints + human review | Finds new, undetected fraud in the literature at large; doesn't check one citing claim against one cited paper |

## Where citeval genuinely leads

- **Metadata overrides the model, structurally.** Scite's retraction flag and citeval's both trace
  to Retraction Watch/Crossref, but Scite's stance label and DeepSciVerify's verdict are single
  model judgments with no hard override. citeval's contracts make retraction/scope facts ones the
  LLM cannot overturn — a conflict is scored as the model being wrong, never adjudicated by it.
- **Species/population scope as its own MeSH-grounded axis.** No surveyed tool or paper couples
  MeSH organism/population check-tags to claim-level scope-mismatch detection this way. The
  components (MeSH taggers, "Humans" classifiers) are established research; the composition —
  catching a claim that silently drops "in mice" — doesn't appear elsewhere in this search.
- **Explicit provenance/tier bookkeeping on every finding**, not just an answer. Scite shows a bare
  confidence percentage; Consensus blends everything into one meter; DeepSciVerify reports
  aggregate F1, not per-verdict epistemic status. citeval's `metadata-grounded | text-grounded |
  model-inferred | stub-not-adjudicated` label on every axis finding is unusually disciplined
  self-disclosure.
- **Measured, anti-circular calibration.** Confidence (self-consistency agreement across resampled
  adjudication rounds) is checked against a reference that is human/decider-corrected and never
  model-generated. citeval's own numbers — a graded axis at **0.90 quadratic-weighted kappa**
  (within one level on every case), confidence that discriminates correctness (AUROC ≈ 0.64), and a
  monotone Platt recalibration to a **leave-one-out ECE ≈ 0.08** (from a raw 0.34), all re-checked on
  a **45-case held-out set** — are a rare instance of a claim-verification system reporting whether
  its confidence is *honest*, not just whether its labels are accurate.
- **A graded ordinal where the field is stuck at three classes.** SciFact, MultiVerS, and
  DeepSciVerify all output SUPPORT/REFUTE/NEI. citeval's 6-level scale (fully-supported through
  contradicted, with `supported-with-overreach` and `technically-true-but-misleading` as named
  intermediate grades) targets exactly the non-binary "spin" that the quotation-accuracy literature
  shows is the dominant real failure mode: a recent [systematic review and meta-analysis](https://researchintegrityjournal.biomedcentral.com/articles/10.1186/s41073-025-00173-z)
  puts the medical-literature quotation-error rate at 16.9%, mostly graded distortion rather than
  binary fabrication.
- **A verbatim guard on the claim itself**, structurally defending against the failure mode that
  2026's citation-hallucination research documents accelerating — even though that literature's
  target (does a *reference* exist and match its metadata) differs from citeval's (does a *real*
  citation actually support the claim). See, e.g., [reports of rising fabricated-reference rates](https://www.forbes.com/sites/michaeltnietzel/2026/05/12/ai-blamed-for-rise-in-fabricated-citations-found-in-recent-research-papers/).
- **LLM-judge hygiene applied where consumer tools disclose none.** Order-randomized,
  identity-blinded transcripts and self-consistency resampling are precisely what the LLM-as-judge
  literature recommends against position and self-preference bias; citeval implements them
  explicitly rather than leaving them undocumented.

## Where citeval currently lags

- **Scale, by orders of magnitude.** Scite has classified 1.4B+ citation statements across 38M+
  papers; Semantic Scholar and Consensus each index ~200M+ papers. citeval's eval set is a 17-case
  demo fixture (per its own docs, explicitly "not the corpus"), with a fuller graded corpus designed
  for low hundreds of cases — a research prototype's corpus, not infrastructure.
- **Coverage bias from the extraction pipeline.** citeval's own pilot measured only ~44% of examined
  PMC citers yielding a usable verbatim claim, and full-text grounding depends on PMC open-access
  availability — paywalled or non-PMC-indexed citing papers are invisible to its deep-text path.
  Scite ingests citation context regardless of OA status.
- **No shipped product.** Scite, Consensus, Elicit, SciSpace, and Scholarcy are polished subscription
  products with browser extensions and manuscript-screening workflows serving millions of users.
  citeval is a CLI pipeline with a JSON scorer — no UI, no reference-list upload.
- **Cost/latency unsuited to bulk screening.** An adversarial triad on Opus for every call, resampled
  for self-consistency, is expensive and slow per verdict next to Scite's precomputed lookups or
  Elicit's single pass. citeval isn't built to screen a whole bibliography in upload time, which is
  exactly Scite's reference-check pitch.
- **Calibration is measured on a small, still-thin reference.** The numbers above come from a small
  corpus whose reference was blind-decider-adjudicated (independent of the grader) and then re-tested
  on a 45-case held-out set — not yet SciFact's scale (1,409 claims, multiply-annotated) or the
  quotation-accuracy meta-analyses (46 studies, ~32K quotations). The calibration claim is real and
  holds out-of-sample, but is not yet broadly externally replicated. Scope recall is the honest weak
  point (0.71 held-out; population 0.40).
- **Doesn't discover new fraud or classify citation function.** Papermill Alarm and the Problematic
  Paper Screener actively mine ~130M papers for undetected fraud signals; citeval only checks
  whether an already-cited paper is a *known*, published retraction — a narrower lookup task. It
  also doesn't classify citation rhetorical intent the way SciCite-trained classifiers do; its
  "N/A — non-substantiating" carve-out is a narrower, model-inferred stand-in for the same idea.
- **Quantitative/dose axes are explicitly punted**, by design (flagged, never fabricated) — while
  adjacent 2025–2026 benchmarks (e.g., [Matter-of-Fact](https://arxiv.org/abs/2506.04410) for
  materials-science magnitude claims) show the field is starting to tackle the exact
  quantitative-verification problem citeval defers.

## Sources

- [Scite: AI for Research — features](https://scite.ai/features)
- [Nicholson et al. 2021, "scite: A smart citation index..." — Quantitative Science Studies](https://direct.mit.edu/qss/article/2/3/882/102990/scite-A-smart-citation-index-that-displays-the)
- [Scite — automated retraction/notice detection](https://scite.ai/blog/2022-10-19_automated-notice-detection)
- [Nature Index — "New bot flags scientific studies that cite retracted papers"](https://www.nature.com/nature-index/news/new-bot-flags-scientific-research-studies-that-cite-retracted-papers)
- [Consensus: AI for Research](https://consensus.app/)
- [Elicit: AI for scientific research](https://elicit.com/)
- [Using Elicit for data extraction in systematic reviews — feasibility study (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC11921719/)
- [SciSpace](https://scispace.com/)
- [Scholarcy — AI Research Paper Reader](https://www.scholarcy.com/features/ai-research-paper)
- [Semantic Scholar Academic Graph API](https://www.semanticscholar.org/product/api)
- [Kinney et al. 2023, "The Semantic Scholar Open Data Platform"](https://arxiv.org/pdf/2301.10140)
- [SciCite dataset (Hugging Face)](https://huggingface.co/datasets/allenai/scicite)
- [Wadden et al. 2020, "Fact or Fiction: Verifying Scientific Claims" (SciFact)](https://aclanthology.org/2020.emnlp-main.609/)
- [SciFact dataset (Hugging Face)](https://huggingface.co/datasets/allenai/scifact)
- [Wadden et al. 2022, "MultiVerS" — ACL Findings](https://aclanthology.org/2022.findings-naacl.6/)
- [MultiVerS code/checkpoints (GitHub)](https://github.com/dwadden/multivers)
- [DeepSciVerify (arXiv:2605.27710, May 2026)](https://arxiv.org/abs/2605.27710)
- [GhostCite: citation validity at scale (arXiv:2602.06718)](https://arxiv.org/pdf/2602.06718)
- [Detecting and Correcting Reference Hallucinations in Commercial LLMs (arXiv:2604.03173)](https://arxiv.org/html/2604.03173v1)
- [Forbes — "AI Blamed For Rise In Fabricated Citations" (May 2026)](https://www.forbes.com/sites/michaeltnietzel/2026/05/12/ai-blamed-for-rise-in-fabricated-citations-found-in-recent-research-papers/)
- [STAT News — fraudulent-citation rise study (May 2026)](https://www.statnews.com/2026/05/07/lancet-study-finds-steep-rise-fraudulent-citations-academic-papers/)
- [Papermill Alarm coverage — Chemistry World](https://www.chemistryworld.com/features/ai-tools-tackle-paper-mill-fraud-overwhelming-peer-review/4022253.article)
- [Problematic Paper Screener — The Conversation](https://theconversation.com/problematic-paper-screener-trawling-for-fraud-in-the-scientific-literature-246317)
- [Retraction Watch data now in the Crossref API](https://www.crossref.org/blog/retraction-watch-retractions-now-in-the-crossref-api-crossref/)
- [Systematic review and meta-analysis of quotation inaccuracy in medicine (2025)](https://researchintegrityjournal.biomedcentral.com/articles/10.1186/s41073-025-00173-z)
- [Mogull, recalculation of quotation error rate (PLOS ONE)](https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0184727)
- [Matter-of-Fact benchmark (arXiv:2506.04410)](https://arxiv.org/abs/2506.04410)
- [Scientific Fact-Checking: A Survey of Resources and Approaches (arXiv:2305.16859)](https://arxiv.org/pdf/2305.16859)
- [Judging the Judges: bias mitigation in LLM-as-Judge pipelines (arXiv:2604.23178)](https://arxiv.org/pdf/2604.23178)
