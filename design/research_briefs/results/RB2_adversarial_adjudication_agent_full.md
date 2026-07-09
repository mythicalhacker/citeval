# RB2 — Adversarial Claim-Verification Adjudication Agent (C4 Substantive-Support Engine)

**Engineering specification. Target: ~70% buildable detail, ~30% literature justification. All LLM calls use a single frozen model, "Opus 4.8."**

## TL;DR
- RB2 is a three-agent (SUPPORTER → REFUTER → CRITIC) adversarial pipeline that grades ONLY the `substantive_support` axis of the C4 Verdict; the three objective axes (retraction, species_scope, population_scope) are decided upstream by C2 metadata and injected as immutable fixed facts the agents may not overturn.
- The critic maps a span-grounded supporter/refuter exchange onto the swappable RB1 ordinal scale, emits NOT_ENOUGH_INFO when evidence is insufficient, and hands off to a swappable overall-rollup that gates retraction/scope-mismatch cases to "not supported as stated."
- Determinism comes from a low-temperature critic with multi-sample self-consistency voting on the graded axis; bias mitigations (position-swap, evidence-first ordering, tuple-normalized points, identity-blinding) are baked into the prompts and aggregation.

## Key Findings (design commitments)
1. **A 3-way SUPPORT/REFUTE/NEI label is insufficient.** SciFact/VeriSci (Wadden et al., EMNLP 2020) and MultiVerS/LongChecker (Wadden et al., Findings-NAACL 2022) classify each abstract as SUPPORTS/REFUTES/NEI with rationale sentences. That coarse label cannot express the graded overreach RB1 needs — e.g. a mouse-only finding presented as a clinical benefit is neither a clean SUPPORT nor a clean REFUTE. RB1's six-point ordinal captures the "technically-true-but-misleading" and "supported-with-overreach" middle that the entailment framing collapses; the exaggeration/distortion literature (Wright & Augenstein; Wührl et al., Findings-ACL 2024, on causality/certainty/generality/sensationalism) confirms distortions are graded, not binary.
2. **Adversarial role separation reduces one-sided confirmation bias** relative to a single pass (Du et al., ICML 2024, multi-agent debate; Madaan et al., Self-Refine, NeurIPS 2023; Bai et al., Constitutional AI critique-revise, 2022).
3. **Every support/refute point must quote a verbatim span or be discarded** — the single strongest lever against invented support (FActScore atomic grounding; "Correctness is not Faithfulness," 2024, on post-rationalization; the debate "quote tool" of Khan et al.).
4. **The metadata-override boundary is a hard constraint** in every prompt: a model judgment never overturns a structured record; a conflict is scored as the model being wrong.
5. **Scope never depresses the graded number** — orthogonal axis semantics resolve the B05 hard case: implicit scope is inferred upstream in C3 and flagged deterministically in C4's species_scope, never inside the substantive grade.

---

## SECTION 1 — Pipeline diagram + I/O

### 1.1 Data flow

```
        ┌────────────────────────────────────────────────────────────────┐
        │  C2 GroundedRecord (cited paper, metadata-grounded)              │
        │  C3 ScopeFrame     (claim assertion, may be model-inferred)      │
        └────────────────────────────────────────────────────────────────┘
                    │
                    ▼
        ┌──────────────────────────────────────────────┐
        │  C4 PRE-ADJUDICATION (deterministic, no LLM)   │
        │  • Compute objective axes:                     │
        │      retraction     ← RetractionInfo           │
        │      species_scope  ← organism_tags vs C3      │
        │      population_scope ← population_tags vs C3   │
        │  • Assemble FIXED_FACTS block                  │
        │  • Extract EVIDENCE_POOL = abstract sentences  │
        │    (+ full-text spans if available), indexed   │
        └──────────────────────────────────────────────┘
                    │  FIXED_FACTS + EVIDENCE_POOL + claim + scope frame
                    ▼
      ┌───────────────┐     ┌───────────────┐     ┌────────────────┐
      │  SUPPORTER    │────▶│   REFUTER     │────▶│    CRITIC      │
      │  (Opus 4.8)   │     │  (Opus 4.8)   │     │  (Opus 4.8)    │
      │ strongest     │     │ distortion    │     │ adjudicates →  │
      │ grounded case │     │ hunt +        │     │ RB1 grade +    │
      │ FOR support   │     │ disconfirming │     │ confidence +   │
      │               │     │ evidence      │     │ spans          │
      └───────────────┘     └───────────────┘     └────────────────┘
                    │                 │                    │
                    └─────────────────┴────────────────────┘
                                      ▼
                    ┌──────────────────────────────────────┐
                    │  SWAPPABLE OVERALL-ROLLUP (no LLM)     │
                    │  gate(objective axes, substantive) →  │
                    │  overall                              │
                    └──────────────────────────────────────┘
                                      ▼
                    ┌──────────────────────────────────────┐
                    │  Verdict (C4 output → C5/C6)          │
                    │  overall; axis_findings[4];           │
                    │  unverifiable_axes; stub; notes[]     │
                    └──────────────────────────────────────┘
```

### 1.2 What each agent receives and emits

**Shared inputs (all three agents):**
- `claim` (verbatim text).
- `scope_frame` (C3 ScopeFrame): organism/population/effect/direction + evidence lists + provenance/tier. Presented for context only; agents are told **effect + direction are the substantive fields** they may reason about, and organism/population are scope fields they may not use to move the grade.
- `FIXED_FACTS` block: the three objective-axis verdicts already decided by C2 metadata, presented as immutable. Example lines:
  `RETRACTION = RETRACTED (metadata-grounded, high)`
  `SPECIES_SCOPE = MISMATCH: cited organism_tags=[Rats, Animals, Rats Sprague-Dawley], Humans absent; claim asserts human/therapeutic relevance (metadata-grounded (cited) + model-inferred (claim), medium)`
  `POPULATION_SCOPE = OK`
- `EVIDENCE_POOL`: list of `{span_id, text, source}` where source ∈ {abstract, full_text, title}. Each span carries a stable integer id so agents cite `span_id` and the critic can re-verify verbatim membership before a point is allowed to move the grade.

**SUPPORTER** — receives shared inputs. Emits an ordered list of `support_points`, each with a `claim_component` (which part of effect/direction/magnitude/mechanism/certainty it addresses), a verbatim `quoted_span`, its `span_id`, and `reasoning`; plus a `best_case_summary` and a self-reported `strongest_grade` on the RB1 scale. This is the "strongest case FOR" role, analogous to a debate expert arguing one side (Khan et al.).

**REFUTER** — receives shared inputs PLUS the supporter transcript. Emits `refutation_points`, each tagged with a `distortion_type` ∈ {direction_reversal, magnitude_inflation, cherry_picking, mechanism_mismatch, over_certainty, over_generalization, no_evidence_for_support}, a `targets_support_point` index (or null), a verbatim `quoted_span`+`span_id` (or explicit `no_disconfirming_span`), and `reasoning`. Scope-framing overreach is emitted under `over_generalization` but flagged `routes_to = "rollup_not_grade"` so it can never depress the substantive number.

**CRITIC** — receives shared inputs PLUS both transcripts (order-randomized, identity-blinded). Emits the `substantive_support` AxisFinding: `verdict` (RB1 value or NOT_ENOUGH_INFO), `confidence` (interface only; RB3 owns calibration), `detail`, and an `evidence` object holding the ≥1 decisive `quoted_span`(s). The critic never issues verdicts on the three objective axes.

The deterministic rollup then composes all four AxisFindings into `Verdict.overall`.

---

## SECTION 2 — Prompt skeletons

### 2.1 SUPPORTER

**System:**
```
You are the SUPPORTER in an adversarial scientific citation-verification panel.
Your sole job: build the STRONGEST evidence-grounded case that the CITED PAPER
supports the CLAIM's SUBSTANTIVE assertion — its effect, direction, magnitude,
mechanism, and certainty.

HARD CONSTRAINTS (never violate):
1. FIXED FACTS are decided by structured metadata and are IMMUTABLE. You may not
   argue about retraction, species scope, or population scope. If you assert
   anything contradicting a FIXED FACT, you are wrong by construction.
2. You reason ONLY about substantive support (does the paper's actual finding
   back the claim's substance?). You NEVER argue that species/population/dose
   makes the claim more or less supported.
3. EVERY support point MUST quote a verbatim span from EVIDENCE_POOL (copy the
   text exactly and cite its span_id). A point with no verbatim span is discarded.
   Do not paraphrase a span and present it as a quote. Do not invent findings.
4. If no span supports a claim component, list it under unsupported_components
   rather than inventing support.
```
**Task:** Given `claim`, `scope_frame`, `FIXED_FACTS`, `EVIDENCE_POOL`, enumerate the best-supported components; for each attach the single best verbatim span. Conclude with the highest RB1 grade the evidence honestly permits.

**Output schema:**
```json
{
  "support_points": [
    {"claim_component": "string",
     "span_id": 0,
     "quoted_span": "verbatim substring",
     "reasoning": "why this span supports this component"}
  ],
  "unsupported_components": ["components with no supporting span"],
  "best_case_summary": "string",
  "strongest_grade": "fully-supported | supported-with-overreach | partially-supported | technically-true-but-misleading | unsupported | contradicted | NOT_ENOUGH_INFO"
}
```

### 2.2 REFUTER

**System:**
```
You are the REFUTER in an adversarial scientific citation-verification panel.
Your job: hunt for SUBSTANTIVE DISTORTION and disconfirming evidence in how the
CLAIM represents the CITED PAPER's finding.

Probe specifically for:
  • direction_reversal   — claim flips the sign of the effect
  • magnitude_inflation  — claim overstates effect size/strength
  • cherry_picking       — claim leans on a secondary/qualified result, ignoring
                           the paper's primary or null finding
  • mechanism_mismatch   — claim asserts a mechanism the paper did not establish
  • over_certainty       — claim states as settled what the paper framed as
                           preliminary/associational
  • over_generalization  — claim generalizes the finding's STRENGTH beyond shown

HARD CONSTRAINTS:
1. FIXED FACTS (retraction, species_scope, population_scope) are IMMUTABLE. You
   may NOTE scope-framing overreach, but you MUST tag it
   routes_to="rollup_not_grade". You may NOT use species/population/dose to
   depress the substantive grade.
2. EVERY refutation point MUST quote a verbatim span from EVIDENCE_POOL, OR be an
   explicit "no supporting span found" objection against a supporter point that
   lacked a span. Discard any point that does neither.
3. You reason ONLY about substantive support. Scope mismatch is handled upstream.
```
**Task:** Given the shared inputs and the SUPPORTER transcript, attack each support point and independently surface disconfirming spans; classify each objection by distortion_type.

**Output schema:**
```json
{
  "refutation_points": [
    {"distortion_type": "direction_reversal | magnitude_inflation | cherry_picking | mechanism_mismatch | over_certainty | over_generalization | no_evidence_for_support",
     "targets_support_point": 0,
     "span_id": 0,
     "quoted_span": "verbatim substring OR ''",
     "no_disconfirming_span": false,
     "routes_to": "grade | rollup_not_grade",
     "reasoning": "string"}
  ],
  "most_severe_distortion": "string",
  "refuter_grade_pressure": "none | mild | strong"
}
```

### 2.3 CRITIC

**System:**
```
You are the CRITIC, the adjudicator in an adversarial scientific
citation-verification panel. You issue the FINAL verdict on ONE axis only:
substantive_support.

WHAT YOU GRADE: does the CITED PAPER's actual finding back the CLAIM's substance
— effect, direction, magnitude, mechanism, certainty? Hold scope CONSTANT.

HARD CONSTRAINTS:
1. FIXED FACTS are immutable. You do NOT issue verdicts on retraction, species,
   or population scope. Do not let a scope mismatch or a retraction change your
   substantive grade — those are handled by the rollup after you.
2. Discard any supporter/refuter point not tied to a verbatim EVIDENCE_POOL span.
   Reward span-grounded reasoning; penalize unsupported assertions of support.
3. Weigh arguments by evidential quality, NOT by length, order, or which agent
   sounds more fluent. The two transcripts are given in randomized order and with
   agent identities blinded.
4. If the span-grounded evidence is insufficient to distinguish two adjacent
   grades, or the abstract does not address the claim's substantive component,
   output NOT_ENOUGH_INFO rather than forcing a grade.
5. Produce your reasoning and cite decisive spans FIRST, then the grade LAST.
```
**Task:** Read both transcripts; identify decisive spans; assign one RB1 grade or NOT_ENOUGH_INFO; give a confidence value (RB3 calibrates downstream); cite ≥1 decisive verbatim span or record "no supporting span found."

**Output schema:**
```json
{
  "reasoning": "evidence-first adjudication narrative",
  "decisive_spans": [{"span_id": 0, "quoted_span": "verbatim substring", "role": "supports | refutes"}],
  "substantive_grade": "fully-supported | supported-with-overreach | partially-supported | technically-true-but-misleading | unsupported | contradicted | NOT_ENOUGH_INFO",
  "confidence": 0.0,
  "grade_rationale_last": "one-line justification of the final grade",
  "no_span_found": false
}
```

The evidence-first / grade-last ordering follows the Multiple-Evidence-Calibration finding of Wang et al. ("Large Language Models are not Fair Evaluators," ACL 2024): because autoregressive judges do not retro-justify a conclusion generated first, forcing the evidence before the score reduces snap-judgment rationalization.

---

## SECTION 3 — Adjudication logic (pseudocode)

```python
# ---- Swappable grade scale (RB1 provisional; boundaries swappable) ----
RB1_SCALE = ["contradicted", "unsupported", "technically-true-but-misleading",
             "partially-supported", "supported-with-overreach", "fully-supported"]
ABSTAIN = "NOT_ENOUGH_INFO"

# ---- Objective axes come from C2; agents NEVER touch these ----
def pre_adjudicate(grounded_record, scope_frame):
    retraction = axis_from_retraction(grounded_record.retraction)                 # metadata-grounded
    species    = axis_species_scope(grounded_record.organism_tags, scope_frame)   # composite prov
    population = axis_population_scope(grounded_record.population_tags, scope_frame)
    fixed_facts = render_fixed_facts(retraction, species, population)
    evidence_pool = index_spans(grounded_record.abstract,
                                grounded_record.full_text,
                                grounded_record.title)
    return fixed_facts, evidence_pool, {"retraction":retraction,
                                        "species_scope":species,
                                        "population_scope":population}

# ---- Span discipline: enforce verbatim membership ----
def keep_grounded(points, evidence_pool):
    kept = []
    for p in points:
        if p.get("no_disconfirming_span") or p.get("no_span_found"):
            kept.append(p)                                  # explicit null is allowed
        elif is_verbatim_substring(p["quoted_span"], evidence_pool):
            kept.append(p)
        # else: silently discarded (invented/paraphrased support penalized)
    return kept

# ---- Critic maps exchange -> grade via self-consistency voting ----
def adjudicate_substantive(claim, scope_frame, fixed_facts, evidence_pool):
    grades, confs, spans = [], [], []
    order_flip = False
    for i in range(N_SAMPLES):                              # self-consistency
        sup = run(SUPPORTER, claim, scope_frame, fixed_facts, evidence_pool,
                  temperature=T_AGENT, seed=i)
        sup.points = keep_grounded(sup.support_points, evidence_pool)
        ref = run(REFUTER, claim, scope_frame, fixed_facts, evidence_pool, sup,
                  temperature=T_AGENT, seed=i)
        ref.points = keep_grounded(ref.refutation_points, evidence_pool)
        ref.points = [r for r in ref.points if r["routes_to"] == "grade"]  # drop scope objections
        order_flip = not order_flip                         # alternate transcript order
        crit = run(CRITIC, claim, fixed_facts, evidence_pool,
                   transcripts=blind_and_order([sup, ref], flip=order_flip),
                   temperature=T_CRITIC, seed=i)
        grades.append(crit.substantive_grade)
        confs.append(crit.confidence)
        spans.append(crit.decisive_spans)

    # ---- Abstention gate BEFORE voting ----
    if grades.count(ABSTAIN) >= ceil(N_SAMPLES/2):
        return AxisFinding("substantive_support", ABSTAIN,
                           tier=tier_from_dispersion(grades),
                           provenance=prov_composite(scope_frame),
                           detail="insufficient span-grounded evidence",
                           evidence=first_nonempty(spans) or {"no_span":True},
                           confidence=mean(confs))

    non_abstain = [g for g in grades if g != ABSTAIN]
    winner, agree = ordinal_majority(non_abstain, RB1_SCALE)   # median-of-ordinal tie-break
    if agree < AGREEMENT_FLOOR and ordinal_spread(non_abstain, RB1_SCALE) > 2:
        winner = ABSTAIN                                       # too dispersed -> abstain
    return AxisFinding("substantive_support", winner,
                       tier=tier_from_agreement(agree),
                       provenance=prov_composite(scope_frame),
                       detail=summarize(spans, winner),
                       evidence=representative_spans(spans, winner),
                       confidence=aggregate_conf(confs, agree))  # RB3 recalibrates

# ---- SWAPPABLE overall rollup: DEFAULT gating policy ----
def rollup_default(axes):                                      # axes = dict of 4 AxisFindings
    substantive = axes["substantive_support"].verdict
    if axes["retraction"].verdict == "RETRACTED":
        return "not supported as stated (retracted source)"
    if axes["species_scope"].verdict == "MISMATCH" or \
       axes["population_scope"].verdict == "MISMATCH":
        return "not supported as stated (scope mismatch)"
    if substantive == ABSTAIN:
        return "insufficient information"
    return map_substantive_to_overall(substantive)             # otherwise overall tracks substance

ROLLUP_POLICY = rollup_default    # swap here without touching the pipeline

def build_verdict(claim, cid, axes, stub=False):
    return Verdict(claim=claim, cited_identifier=cid,
                   overall=ROLLUP_POLICY(axes),
                   axis_findings=list(axes.values()),
                   unverifiable_axes=collect_abstain(axes),
                   stub=stub,
                   notes=provenance_notes(axes))
```

**When the critic must abstain (NOT_ENOUGH_INFO):** (a) the abstract/full text does not address the claim's substantive component at all; (b) span-grounded evidence cannot distinguish two adjacent RB1 ranks and inter-sample spread exceeds two ranks with no majority; (c) all supporter/refuter points were discarded for lacking verbatim spans. Abstention is surfaced through the `confidence`/NOT_ENOUGH_INFO interface that RB3 owns — RB2 only exposes the plug points, it does not calibrate them. This mirrors the NEI class of SciFact/MultiVerS but is applied only on the graded axis, not as the whole verdict.

---

## SECTION 4 — Determinism / repeatability

- **Critic temperature low; agents warmer.** The critic runs at low (near-greedy) temperature for a stable verdict; supporter and refuter run warmer to diversify arguments and candidate spans. Adversarial diversity is valuable on the generation side, stability on the judgment side.
- **Self-consistency voting on the graded axis.** Run the full triad several times and take an ordinal majority over the critic's grade. Self-consistency — sampling multiple reasoning paths and majority-voting — gives large, hyperparameter-robust gains over a single greedy pass: per Wang et al., "Self-Consistency Improves Chain of Thought Reasoning in Language Models" (ICLR 2023, arXiv:2203.11171), it "boosts the performance of chain-of-thought prompting with a striking margin," reporting GSM8K +17.9%, SVAMP +11.0%, AQuA +12.2%, StrategyQA +6.4%, and ARC-challenge +3.9%. Because RB1 is ordinal, use an ordinal/median-aware vote rather than plain plurality so adjacent-grade disagreement collapses toward the center rather than splitting the vote.
- **Sample budget.** Default `N_SAMPLES` in the small-odd range (e.g. 5) for the triad with an `AGREEMENT_FLOOR` on the vote. Adaptive early stopping (Aggarwal et al., Adaptive-Consistency, EMNLP 2023; Li et al., Early-Stopping Self-Consistency) halts sampling once a dominant grade's Beta/Dirichlet posterior exceeds a confidence threshold, cutting sample cost substantially — Adaptive-Consistency reports up to a 3.2–6.0× reduction in sample budget with an average accuracy drop under 0.1% — with negligible accuracy loss on easy cases (A01/C01) while spending the full budget only on contested ones (B05).
- **Fixed decode seeds + pinned model version** ("Opus 4.8") for replayability; the deterministic pre-adjudicator and rollup add zero variance.
- **Scoring stability.** Report both the winning grade and inter-sample agreement so eval harnesses can distinguish a confident verdict from a coin-flip — single-sample LLM-judge verdicts are documented to be noisy run-to-run, so the agreement statistic is a first-class output, not a diagnostic afterthought.

---

## SECTION 5 — Failure-mode mitigations (LLM-as-judge)

All four are drawn from Zheng et al., "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena" (NeurIPS 2023, arXiv:2306.05685), which examines "position bias, verbosity bias, self-enhancement bias" and finds strong GPT-4 judges "match human evaluations at an agreement rate exceeding 80%" — establishing both the promise and the failure modes of the LLM-as-judge design RB2 adopts.

- **Position bias** (judges favor answers by presentation order; Zheng et al., arXiv:2306.05685). Mitigation: the critic receives the supporter/refuter transcripts in **randomized/alternating order** across self-consistency samples and aggregates across orderings — the Balanced Position Calibration of Wang et al. (ACL 2024) — and the roles are **identity-blinded**.
- **Verbosity bias** (longer answers win; Zheng et al. show "all LLMs may be prone to verbosity bias though GPT-4 defends significantly better than others," demonstrated with a "repetitive list" attack that doubles length without adding information). Mitigation: the critic rubric explicitly weighs evidential quality, not length; every point is reduced to a `(distortion_type, span_id, quoted_span)` tuple so a long supporter narrative and a one-line refutation compete on span quality, not word count; the discard-if-no-span rule removes padding.
- **Sycophancy** (agreeing with whatever is asserted). Mitigation: the adversarial structure forces the refuter to attack, and the **evidence-first / conclusion-last** critic ordering (Wang et al., ACL 2024) prevents post-hoc rationalization of a snap judgment.
- **Self-preference / self-enhancement bias** (judge favors its own text). Zheng et al. adopt the term from social-cognition literature and find statistically that "GPT-4 seems to prefer responses from its own model." This is acute here because all three roles are the same model (Opus 4.8). Mitigations: (a) role/agent-identity blinding so the critic cannot tell which text is "its own"; (b) the critic scores against the fixed EVIDENCE_POOL rather than the debaters' prose; (c) the discard rule means only verbatim-span-anchored claims can move the grade, capping how much fluent self-generated rhetoric can sway the verdict. A separate-judge design is supported by Khan et al., "Debating with More Persuasive LLMs Leads to More Truthful Answers" (ICML 2024, arXiv:2402.06782): "debate consistently helps both non-expert models and humans answer questions, achieving 76% and 88% accuracy respectively (naive baselines obtain 48% and 60%)," and debaters were equipped with a verified-quote tool — directly motivating RB2's span-quote discipline.

---

## Acceptance tests (mapped to A01/B01/B05/C01)

MeSH facts below were verbatim-verified from MEDLINE XML for three of four PMIDs (see Caveats).

**A01 — Retracted (PMID 22088800, SCIPIO trial).** C2 metadata: publication types include **"Retracted Publication"** and "Randomized Controlled Trial, Clinical Trial Phase I"; MeSH "Humans" present, "Middle Aged" present, no animal terms. FIXED_FACTS carries `RETRACTION = RETRACTED (metadata-grounded, high)`. The PubMed abstract states the trial was of "autologous CSCs for the treatment of heart failure resulting from ischaemic heart disease" and the Lancet retraction states "the laboratory work undertaken by Piero Anversa and colleagues at Harvard cannot be held to be reliable." Test asserts: (1) neither supporter, refuter, nor critic overturns retraction; (2) the substantive axis still reasons about whether the claim of "small significant functional improvements" leans on the discredited finding, citing a verbatim abstract span; (3) rollup gates `overall = "not supported as stated (retracted source)"` regardless of the substantive grade. **PASS** = retraction axis metadata-grounded/high + overall gated + ≥1 span.

**B01 — Species mismatch (PMID 17086191, resveratrol mouse study).** C2 metadata: mouse-only study; claim asserts CLINICAL (human) benefit. FIXED_FACTS carries `SPECIES_SCOPE = MISMATCH`. The abstract states "resveratrol shifts the physiology of middle-aged mice on a high-calorie diet towards that of mice on a standard diet and significantly increases their survival." Test asserts: (1) the refuter surfaces the mouse→human generalization but tags it `routes_to="rollup_not_grade"`; (2) the substantive grade is computed holding scope constant — the mouse data genuinely show the physiological effects, so on substance the grade may be supported/partially-supported; (3) rollup gates `overall = "not supported as stated (scope mismatch)"`. **PASS** = species_scope MISMATCH + substantive grade NOT depressed by species + overall gated.

**B05 — Implicit scope over-generalization (PMID 37781508, tofacitinib rat study). THE HARD CASE.** C2 metadata (verbatim MeSH): `organism_tags = [Rats; Animals; Rats, Sprague-Dawley]`, **"Humans" absent**, no age terms, publication type "Journal Article" only. The claim asserts therapeutic/motor-recovery relevance with NO lexical human marker ("humans"/"patients" absent). Handling: **C3 (UPSTREAM)** infers the implicit therapeutic/human scope of "promote recovery of motor function," emitting it with `model-inferred` provenance + a confidence tier; **C4's deterministic comparison** against the rat organism_tags then flags `SPECIES_SCOPE = MISMATCH` with composite provenance `metadata-grounded (cited) + model-inferred (claim)`. A purely lexical scope stub would miss this because no human keyword appears — the implicit-scope inference is what catches it. The refuter may note the over-generalization but tags it `routes_to="rollup_not_grade"`. The substantive grade is HIGH/supported because the paper's own abstract states verbatim: "TOF could regulate microglial activation via JAK / STAT pathway and promote the recovery of motor function after SCI," which backs the claim's effect/direction/mechanism exactly. Test asserts: (1) species_scope flags via implicit-scope inference, NOT a lexical stub; (2) the substantive grade is NOT depressed by the rat scope; (3) overall gated to scope mismatch. **PASS** = the flag lands on species_scope + overall, while the graded number stays high — demonstrating orthogonal axis semantics.

**C01 — Supported control (PMID 25891173, pembrolizumab vs ipilimumab, KEYNOTE-006).** C2 metadata (verbatim MeSH): "Humans" present; age terms Adolescent, Adult, Aged, Aged 80-and-over, Middle Aged, Young Adult; publication types "Randomized Controlled Trial, Clinical Trial Phase III, Comparative Study, Multicenter Study." No retraction, no scope mismatch. Per Robert et al., NEJM 2015;372:2521–2532, the abstract states "The estimated 6-month progression-free-survival rates were 47.3% for pembrolizumab every 2 weeks, 46.4% for pembrolizumab every 3 weeks, and 26.5% for ipilimumab (hazard ratio for disease progression, 0.58; P<0.001)... The response rate was improved with pembrolizumab... (33.7%) and every 3 weeks (32.9%), as compared with ipilimumab (11.9%)," and concludes pembrolizumab "prolonged progression-free survival and overall survival." Test asserts: (1) no axis is flagged; (2) the critic grades `fully-supported` (or at most `supported-with-overreach`) WITHOUT a forced objection — refuter returns `refuter_grade_pressure="none"`; (3) rollup returns a supported overall. **PASS** = unflagged + supported grade + ≥1 span, no fabricated objection.

**Global acceptance invariants:** every Verdict carries ≥1 quoted evidence span per graded axis OR an explicit "no supporting span found"; output conforms to the Verdict contract (four AxisFindings + confidence + provenance atoms) so it drops into C5/C6 unchanged; grade boundaries and rollup policy are swappable module-level constants (`RB1_SCALE`, `ROLLUP_POLICY`).

## Recommendations (build order)
1. **Deterministic core first.** Build the pre-adjudicator and rollup (no LLM) and lock the Verdict-contract serializer; these carry zero model variance and encode the hard constraints. Wire A01/B01/B05/C01 as fixtures with their frozen FIXED_FACTS so the metadata-override boundary is testable before any prompt exists.
2. **Span enforcement second.** Implement span indexing + `is_verbatim_substring` before agent prompt work — the highest-leverage correctness lever against invented support. Unit-test that paraphrased-but-not-verbatim quotes are discarded.
3. **Prompts + aggregation third.** Land the three prompts, then wire self-consistency + position-swap + identity-blinding aggregation. Run A01/B01/B05/C01 as regression tests on every prompt edit; B05 is the canary — if the substantive grade drops when the rat scope is present, the orthogonality constraint has leaked.
4. **Expose, don't build, the RB3 interface** (`confidence`, NOT_ENOUGH_INFO plug points).
5. **Thresholds that change course:** if inter-sample agreement on the four eval cases falls below `AGREEMENT_FLOOR`, raise `N_SAMPLES` or lower critic temperature before touching prompts; if the refuter fabricates objections on C01 (`refuter_grade_pressure != "none"`), tighten the discard rule and re-blind before re-prompting; if abstention rate on abstract-only inputs exceeds tolerance, the fix is upstream (supply full-text spans from C2), not loosening the critic.

## Caveats
- MeSH facts for PMIDs 22088800, 37781508, and 25891173 were verbatim-verified from MEDLINE XML (NCBI E-utilities). The resveratrol record (17086191) could not be machine-fetched this session (E-utilities returned a stale cached record and PubMed/PMC were CAPTCHA-blocked); its mouse-only scope is confirmed from the Nature abstract (doi:10.1038/nature05354) but its exact MeSH descriptor list is inferred, not verbatim-confirmed. Re-verify before locking the B01 fixture.
- Confidence calibration is explicitly out of scope (RB3); the numbers RB2 emits are uncalibrated proxies. Self-consistency agreement is a usable interim signal but is not a calibrated probability.
- Full-text spans are available only when C2 supplies them; abstract-only cases will abstain more often, which is the intended conservative behavior, not a bug.
- The literature on multi-agent debate is not unanimous: Huang et al. ("Large Language Models Cannot Self-Correct Reasoning Yet," 2023) found debate did not outperform plain self-consistency on some reasoning tasks. RB2 therefore treats self-consistency voting — not the debate exchange alone — as the primary reliability mechanism, and uses the adversarial roles chiefly to diversify span discovery and surface distortions, a use case closer to the truthful-debate results of Khan et al. than to open-ended reasoning.