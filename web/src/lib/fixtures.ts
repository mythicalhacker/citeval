/**
 * Four fully-populated RunResult fixtures (W0-CONTRACTS) — retraction catch, species
 * scope mismatch, graded over-reach, and abstention. The verdict LOGIC (objective axes,
 * gating, grades, confidence, render_json/render_html shape) is produced by the REAL
 * citeval pipeline contracts via scratchpad/gen_fixtures.py, and the OBJECTIVE facts
 * (retraction status/record, organism class, publication types, MeSH) reflect the real
 * cited record. These render in the verdict/showcase views and drive the mock with NO
 * backend and NO API key.
 *
 * INTEGRITY NOTE: each cited-paper ABSTRACT / FULL-TEXT prose here is a CONDENSED,
 * ILLUSTRATIVE stand-in for offline rendering — NOT a verbatim NCBI/PMC record (each
 * result says so in verdict.notes[0] and its grounded.provenance). The verbatim guard is
 * demonstrated against this illustrative text; the mechanism is real, the source text is
 * a stand-in. DO NOT hand-edit the RunResult blobs — regenerate them; only the curated
 * FIXTURES metadata below is authored by hand.
 *
 * Cases: A01 SCIPIO (PMID 22088800), B01 resveratrol/mice (17086191), Ce11 obesity–
 * allergy (19725894, real committed debate transcript), Ch05 VZV review (2832088).
 */
import type { RunResult, RunMode } from './types';

export const FIXTURE_RETRACTION: RunResult = {
  "run_id": "run_a01_retraction",
  "verdict": {
    "claim_unit": {
      "atomic_claim": "Exogenous c-kit+ cells are currently being used to treat post-MI heart failure patients, and early results have shown small, albeit significant functional improvements in the heart 24.",
      "cited_identifier": {
        "type": "pmid",
        "value": "22088800"
      },
      "citing_source": {
        "pmid": "24805242",
        "pmcid": "PMC4127035",
        "note": "citing review, cited as ref [24]"
      }
    },
    "grounded": {
      "identifier": {
        "type": "pmid",
        "value": "22088800"
      },
      "title": "Cardiac stem cells in patients with ischaemic cardiomyopathy (SCIPIO): initial results of a randomised phase 1 trial",
      "abstract": "BACKGROUND: c-kit-positive, lineage-negative cardiac stem cells (CSCs) improve post-infarction left ventricular dysfunction in animal models. We report the initial results of a phase 1 randomised trial of autologous CSCs in patients with heart failure of ischaemic origin. METHODS: Patients with a left ventricular ejection fraction (LVEF) of 40% or less after coronary artery bypass grafting received intracoronary infusion of autologous CSCs. FINDINGS: In treated patients, intracoronary infusion of autologous c-kit+ cardiac stem cells produced a small but significant improvement in left ventricular ejection fraction in patients with post-infarction heart failure over four months, with a concordant reduction in infarct size. INTERPRETATION: These initial results are promising and warrant a larger phase 2 study.",
      "mesh_all": [
        "Aged",
        "Coronary Artery Bypass",
        "Female",
        "Heart Failure",
        "Humans",
        "Male",
        "Middle Aged",
        "Myocardial Infarction",
        "Myocardial Ischemia",
        "Stem Cell Transplantation",
        "Stem Cells",
        "Stroke Volume",
        "Treatment Outcome",
        "Ventricular Function, Left"
      ],
      "organism_tags": [
        {
          "descriptor": "Humans",
          "ui": "D006801",
          "tree_numbers": [
            "B01.050.150.900.649.313.988.400.112.400.400"
          ],
          "major_topic": false
        }
      ],
      "population_tags": [
        {
          "descriptor": "Aged",
          "ui": "D000368",
          "tree_numbers": [
            "M01.060.116.100"
          ],
          "major_topic": false
        },
        {
          "descriptor": "Middle Aged",
          "ui": "D008875",
          "tree_numbers": [
            "M01.060.116.630"
          ],
          "major_topic": false
        }
      ],
      "sex_tags": [
        {
          "descriptor": "Female",
          "ui": "D005260",
          "tree_numbers": [],
          "major_topic": false
        },
        {
          "descriptor": "Male",
          "ui": "D008297",
          "tree_numbers": [],
          "major_topic": false
        }
      ],
      "publication_types": [
        "Journal Article",
        "Randomized Controlled Trial",
        "Research Support, N.I.H., Extramural",
        "Retracted Publication"
      ],
      "retraction": {
        "status": "RETRACTED",
        "retraction_watch": {
          "present": true,
          "rw_record_id": "20119",
          "reason": "Investigation by Company/Institution; Unreliable Data; Unreliable Results and/or Conclusions; Upgrade/Update of Prior Notice(s)",
          "date": "2019-03-14"
        },
        "ncbi_publication_type_flag": true,
        "comments_corrections": [
          {
            "ref_type": "RetractionIn",
            "pmid": "30971817",
            "source": "Lancet. 2019 Mar 23;393(10177):1084. doi: 10.1016/S0140-6736(19)30542-2."
          }
        ],
        "source_agreement": "agree",
        "provenance": "metadata-grounded"
      },
      "has_humans": true,
      "provenance": {
        "abstract": "ILLUSTRATIVE fixture text — condensed from the cited paper for offline rendering; NOT a verbatim NCBI EFetch <AbstractText> record (W0 demo fixture).",
        "mesh": "EFetch <MeshHeading> + NLM MeSH tree numbers",
        "retraction": "Retraction Watch RW record 20119 + EFetch <PublicationType>",
        "_fixture": "W0 demo fixture — grounding text is illustrative; see verdict.notes[0]."
      },
      "grounding_errors": [],
      "full_text": "",
      "full_text_provenance": ""
    },
    "claim_scope": {
      "organism": "Humans",
      "organism_evidence": [
        "post-MI heart failure patients",
        "patients"
      ],
      "population": null,
      "population_evidence": [],
      "effect": "functional improvement",
      "direction": "increase",
      "direction_evidence": [
        "improvements"
      ],
      "dose_stated": false,
      "provenance": "text-grounded (claim) + metadata-grounded (cited)",
      "tier": "high"
    },
    "verdict": {
      "claim": "Exogenous c-kit+ cells are currently being used to treat post-MI heart failure patients, and early results have shown small, albeit significant functional improvements in the heart 24.",
      "cited_identifier": {
        "type": "pmid",
        "value": "22088800"
      },
      "overall": "NOT SUPPORTED AS STATED (CITATION RELIES ON A RETRACTED PAPER) — substantive grade: supported-with-overreach (held separately)",
      "axis_findings": [
        {
          "axis": "retraction",
          "verdict": "RELIES_ON_RETRACTED",
          "tier": "high",
          "provenance": "metadata-grounded",
          "detail": "Cited paper is retracted per structured records; a claim resting on it inherits the retraction.",
          "evidence": {
            "retraction_watch": {
              "present": true,
              "record_id": "20119",
              "reason": "Investigation by Company/Institution; Unreliable Data; Unreliable Results and/or Conclusions; Upgrade/Update of Prior Notice(s)",
              "date": "2019-03-14"
            },
            "ncbi_publication_type_flag": true,
            "ncbi_comments_corrections": [
              "RetractionIn"
            ],
            "source_agreement": "agree"
          }
        },
        {
          "axis": "species_scope",
          "verdict": "SCOPE_CONSISTENT",
          "tier": "medium",
          "provenance": "metadata-grounded (cited) + text-grounded (claim) + metadata-grounded (cited) (claim)",
          "detail": "Claim asserts human scope; cited paper MeSH organism scope includes Humans (['Humans']).",
          "evidence": {
            "cited_organism_tags": [
              {
                "descriptor": "Humans",
                "tree_numbers": [
                  "B01.050.150.900.649.313.988.400.112.400.400"
                ]
              }
            ],
            "cited_has_humans": true,
            "claim_organism": "Humans",
            "claim_organism_provenance": "text-grounded (claim) + metadata-grounded (cited)",
            "claim_evidence": [
              "post-MI heart failure patients",
              "patients"
            ]
          }
        },
        {
          "axis": "population_scope",
          "verdict": "NOT_ASSESSED",
          "tier": "low",
          "provenance": "model-inferred",
          "detail": "No explicit or implicit population scope in the claim; population axis not assessed.",
          "evidence": {
            "cited_population_tags": [
              "Aged",
              "Middle Aged"
            ],
            "cited_pregnancy_mesh": [],
            "claim_population": null,
            "claim_evidence": []
          }
        },
        {
          "axis": "substantive_support",
          "verdict": "supported-with-overreach",
          "tier": "medium",
          "provenance": "model-inferred",
          "detail": "Holding retraction aside, the paper's text does report a small significant LVEF improvement, matching the claim's direction and hedged magnitude — but the claim generalises a phase-1 result to 'currently being used to treat patients'.",
          "evidence": {
            "confidence": {
              "verbalized": "medium",
              "agreement": 0.71,
              "n_samples": 7
            },
            "calibration": {
              "note": ""
            },
            "supporter": {
              "span": "intracoronary infusion of autologous c-kit+ cardiac stem cells produced a small but significant improvement in left ventricular ejection fraction in patients with post-infarction heart failure",
              "point": "Directly matches the claim's 'small, albeit significant functional improvement'."
            },
            "refuter": {
              "span": "We report the initial results of a phase 1 randomised trial",
              "objection": "A phase-1 initial result does not support 'currently being used to treat patients' — the claim over-states clinical adoption."
            },
            "abstained": false,
            "non_substantiating": false,
            "supporter_points": [
              {
                "quote": "intracoronary infusion of autologous c-kit+ cardiac stem cells produced a small but significant improvement in left ventricular ejection fraction in patients with post-infarction heart failure",
                "rationale": "Directly matches the claim's 'small, albeit significant functional improvement'."
              }
            ],
            "refuter_points": [
              {
                "quote": "We report the initial results of a phase 1 randomised trial",
                "objection": "A phase-1 initial result does not support 'currently being used to treat patients' — the claim over-states clinical adoption."
              }
            ],
            "refuter_scope_notes": [],
            "verbatim_guard": {
              "supporter_discarded": 0,
              "refuter_discarded": 0,
              "grounding_corpus": "title+abstract+fulltext"
            },
            "self_consistency": {
              "rounds_configured": 7,
              "rounds_run": 7,
              "rounds_valid": 7,
              "a_exact": 0.71,
              "a_adj": 1.0,
              "conf_hybrid": 0.71,
              "non_adjacent_multimodal": false,
              "ordinal_distribution": {
                "fully-supported": 2,
                "supported-with-overreach": 5
              },
              "n_nei": 0,
              "n_non_substantiating": 0,
              "n_parse_failed": 0,
              "grade_ordinal": null,
              "output_tokens": [
                540,
                561,
                598,
                622,
                605,
                588,
                617
              ],
              "tau_abstain": 0.5,
              "adjacent_floor": 0.7
            }
          }
        }
      ],
      "unverifiable_axes": {
        "dose": "No dose asserted in the claim; not applicable.",
        "effect_direction": "Whether the claim's effect direction matches the cited paper's reported result requires reading the Results text; no structured field. Deferred to the adjudication agent."
      },
      "stub": false,
      "notes": [
        "DEMO FIXTURE (W0-CONTRACTS): the cited-paper abstract / full text rendered here is a CONDENSED, ILLUSTRATIVE stand-in for offline viewing — NOT a verbatim NCBI/PMC record. The verbatim guard is demonstrated against this illustrative text (the mechanism is real; the source text is a stand-in). Objective facts (retraction status/record, organism class, publication types) reflect the real structured record; the axis logic, substantive grade, and confidence are produced by the real citeval pipeline contracts.",
        "Cited-paper metadata is authoritative on objective axes; the supporter/refuter/critic reason only on substantive_support and may not overturn a structured record (metadata-override rule).",
        "Retraction is metadata-grounded: Retraction Watch record 20119 (2019-03-14) AND the NCBI 'Retracted Publication' PublicationType flag agree. The citation relies on the retracted finding, so `overall` gates to NOT SUPPORTED AS STATED regardless of the substantive grade.",
        "The substantive grade is held SEPARATELY and reported alongside the gate — the paper's own text does support the effect, but the paper is retracted, so it must not be relied upon."
      ]
    }
  },
  "timing": {
    "per_stage_ms": {
      "ingest": 910.0,
      "ground_retraction": 1480.0,
      "ground_scope": 1210.0,
      "adjudicate": 84800.0,
      "report": 60.0
    },
    "total_ms": 88460.0,
    "est_total_ms": 93767.6
  },
  "cost": {
    "total_usd": 1.053825,
    "per_role": {
      "supporter": {
        "usd": 0.3807,
        "n_calls": 7,
        "tokens": {
          "input": 1680,
          "output": 2520,
          "cache_read": 36000,
          "cache_write": 6000
        }
      },
      "refuter": {
        "usd": 0.2688,
        "n_calls": 7,
        "tokens": {
          "input": 1820,
          "output": 2380,
          "cache_read": 42000,
          "cache_write": 0
        }
      },
      "critic": {
        "usd": 0.404325,
        "n_calls": 7,
        "tokens": {
          "input": 2100,
          "output": 4131,
          "cache_read": 42000,
          "cache_write": 0
        }
      }
    },
    "tokens": {
      "input": 5600,
      "output": 9031,
      "cache_read": 120000,
      "cache_write": 6000
    },
    "n_model_calls": 21
  },
  "report_html": "<!doctype html>\n<html lang=\"en\"><head>\n<meta charset=\"utf-8\">\n<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n<title>Citation verification report — PMID 22088800</title>\n<style>:root { color-scheme: light dark; }\nbody { font-family: -apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, Helvetica, Arial,\n       sans-serif; line-height: 1.5; color: #1a1a1a; background: #fff;\n       margin: 0 auto; max-width: 62rem; padding: 2rem; }\nh1 { font-size: 1.6rem; margin: 0 0 1rem; }\nh2 { font-size: 1.15rem; margin: 2rem 0 .5rem; border-bottom: 1px solid #e5e5e5; padding-bottom: .25rem; }\n.overall { font-weight: 700; padding: .55rem .8rem; background: #f6f8fa;\n           border-left: 4px solid #444; border-radius: .25rem; }\n.tablewrap { overflow-x: auto; }\ntable { border-collapse: collapse; width: 100%; font-size: .9rem; }\nth, td { border: 1px solid #e2e2e2; padding: .4rem .55rem; text-align: left; vertical-align: top; }\nth { background: #f6f8fa; }\n.badge { display: inline-block; padding: .08rem .45rem; border-radius: .6rem; font-size: .76rem;\n         font-weight: 600; white-space: nowrap; }\n.prov-meta { background: #e6f4ea; color: #137333; }\n.prov-text { background: #e8f0fe; color: #1967d2; }\n.prov-model { background: #fef7e0; color: #99590b; }\n.prov-stub { background: #f1f3f4; color: #5f6368; }\n.prov-composite { background: #f3e8fd; color: #7b2fbe; }\n.graded { background: #fbfbfd; border: 1px solid #e5e5e5; border-radius: .5rem; padding: 1rem 1.2rem; }\n.graded dl { display: grid; grid-template-columns: max-content 1fr; gap: .3rem .8rem; margin: 0; }\n.graded dt { font-weight: 600; }\n.graded dd { margin: 0; }\nblockquote { margin: .35rem 0; padding: .4rem .8rem; border-left: 3px solid #bbb;\n             background: #fafafa; color: #333; }\n.gloss { color: #555; font-size: .9rem; }\n.legend dt { font-weight: 600; }\n.override { font-style: italic; color: #444; }\n.stubnote { border-left: 3px solid #bbb; padding: .4rem .8rem; color: #555; background: #fafafa; }\n@media (prefers-color-scheme: dark) {\n  body { color: #e6e6e6; background: #16181c; }\n  h2 { border-bottom-color: #333; }\n  .overall { background: #22262e; border-left-color: #888; }\n  th { background: #22262e; } th, td { border-color: #333; }\n  .graded { background: #1b1e24; border-color: #333; }\n  blockquote, .stubnote { background: #1b1e24; border-left-color: #555; color: #cfcfcf; }\n  .gloss, .override { color: #b3b3b3; }\n}</style>\n</head><body>\n<main>\n<h1>Citation verification report</h1>\n<p><strong>Claim.</strong> Exogenous c-kit+ cells are currently being used to treat post-MI heart failure patients, and early results have shown small, albeit significant functional improvements in the heart 24.</p>\n<p><strong>Cited paper.</strong> Cardiac stem cells in patients with ischaemic cardiomyopathy (SCIPIO): initial results of a randomised phase 1 trial<br>PMID 22088800</p>\n<p class=\"overall\">Overall: NOT SUPPORTED AS STATED (CITATION RELIES ON A RETRACTED PAPER) — substantive grade: supported-with-overreach (held separately)</p>\n<h2>Per-axis findings</h2>\n<div class=\"tablewrap\"><table>\n<thead><tr><th>Axis</th><th>Verdict</th><th>Confidence</th><th>Provenance</th><th>Basis</th></tr></thead>\n<tbody>\n<tr><td>retraction</td><td><strong>RELIES_ON_RETRACTED</strong></td><td>high</td><td><span class=\"badge prov-meta\">metadata-grounded</span></td><td>Cited paper is retracted per structured records; a claim resting on it inherits the retraction.</td></tr>\n<tr><td>species_scope</td><td><strong>SCOPE_CONSISTENT</strong></td><td>medium</td><td><span class=\"badge prov-meta\">metadata-grounded (cited) + text-grounded (claim) + metadata-grounded (cited) (claim)</span></td><td>Claim asserts human scope; cited paper MeSH organism scope includes Humans ([&#x27;Humans&#x27;]).</td></tr>\n<tr><td>population_scope</td><td><strong>NOT_ASSESSED</strong></td><td>low</td><td><span class=\"badge prov-model\">model-inferred</span></td><td>No explicit or implicit population scope in the claim; population axis not assessed.</td></tr>\n<tr><td>substantive_support</td><td><strong>supported-with-overreach</strong></td><td>medium</td><td><span class=\"badge prov-model\">model-inferred</span></td><td>Holding retraction aside, the paper&#x27;s text does report a small significant LVEF improvement, matching the claim&#x27;s direction and hedged magnitude — but the claim generalises a phase-1 result to &#x27;currently being used to treat patients&#x27;.</td></tr>\n</tbody></table></div>\n<section class=\"graded\">\n<h2>Substantive support (graded)</h2>\n<dl>\n<dt>Grade (RB1 scale)</dt><dd>supported-with-overreach</dd>\n<dt>Confidence</dt><dd>medium — self-consistency agreement 0.71 across 7 samples; verbalized medium</dd>\n<dt>Calibration</dt><dd>not yet available — populated by the scorer/RB3 once the corpus is scored.</dd>\n<dt>Provenance</dt><dd><span class=\"badge prov-model\">model-inferred</span> — grades substance only, holding scope constant (CONTEXT_PACK §6); scope over-reach is on the scope axes above.</dd>\n<dt>Rationale</dt><dd>Holding retraction aside, the paper&#x27;s text does report a small significant LVEF improvement, matching the claim&#x27;s direction and hedged magnitude — but the claim generalises a phase-1 result to &#x27;currently being used to treat patients&#x27;.</dd>\n</dl>\n<p><strong>Adversarial trace.</strong></p>\n<p class=\"gloss\">Supporter — best supporting span:</p>\n<blockquote>intracoronary infusion of autologous c-kit+ cardiac stem cells produced a small but significant improvement in left ventricular ejection fraction in patients with post-infarction heart failure</blockquote>\n<p class=\"gloss\">Directly matches the claim&#x27;s &#x27;small, albeit significant functional improvement&#x27;.</p>\n<p class=\"gloss\">Refuter — strongest objection:</p>\n<blockquote>We report the initial results of a phase 1 randomised trial</blockquote>\n<p class=\"gloss\">A phase-1 initial result does not support &#x27;currently being used to treat patients&#x27; — the claim over-states clinical adoption.</p>\n</section>\n<h2>Axes flagged unverifiable (not fabricated)</h2>\n<ul>\n<li><strong>dose</strong> — No dose asserted in the claim; not applicable.</li>\n<li><strong>effect_direction</strong> — Whether the claim&#x27;s effect direction matches the cited paper&#x27;s reported result requires reading the Results text; no structured field. Deferred to the adjudication agent.</li>\n</ul>\n<h2>Grounding evidence (structured, metadata-grounded)</h2>\n<ul>\n<li><strong>Retraction status:</strong> RETRACTED (source agreement: agree)\n<ul><li>Retraction Watch record 20119: Investigation by Company/Institution; Unreliable Data; Unreliable Results and/or Conclusions; Upgrade/Update of Prior Notice(s) (date 2019-03-14)</li><li>NCBI RetractionIn: PMID 30971817 — Lancet. 2019 Mar 23;393(10177):1084. doi: 10.1016/S0140-6736(19)30542-2.</li><li>NCBI PublicationType flag: 'Retracted Publication' present</li></ul>\n</li>\n<li><strong>Organism MeSH (tree B*):</strong> Humans [B01.050.150.900.649.313.988.400.112.400.400] | Humans present: True</li>\n<li><strong>Population MeSH (tree M01.060*):</strong> Aged [M01.060.116.100], Middle Aged [M01.060.116.630]</li>\n<li><strong>Sex check-tags:</strong> Female, Male</li>\n</ul>\n<h2>Claim scope parse (C3-lite — explicit lexical markers)</h2>\n<ul>\n<li>Asserted organism: <strong>Humans</strong> (provenance: text-grounded (claim) + metadata-grounded (cited), tier: high); evidence: [&#x27;post-MI heart failure patients&#x27;, &#x27;patients&#x27;]</li>\n<li>Asserted population: (none); evidence: (none)</li>\n<li>Dose stated in claim: False</li>\n</ul>\n<h2>Provenance legend</h2>\n<dl class=\"legend\">\n<dt>metadata-grounded</dt><dd>read from a structured record (Retraction Watch, MeSH tags + tree numbers, NCBI linkage). Authoritative.</dd>\n<dt>text-grounded</dt><dd>an explicit lexical marker in the claim wording.</dd>\n<dt>model-inferred</dt><dd>a model judgement — the C3 claim-scope hint plus the graded substantive-support axis, produced by the adversarial supporter/refuter/critic agent with calibration.</dd>\n<dt>stub-not-adjudicated</dt><dd>deliberately not decided in the thin slice.</dd>\n</dl>\n<p class=\"override\">Metadata (grounded) always overrides model/text on objective axes — a conflict is scored as the model being wrong, not the record.</p>\n</main>\n</body></html>\n"
};

export const FIXTURE_SCOPE_MISMATCH: RunResult = {
  "run_id": "run_b01_scope",
  "verdict": {
    "claim_unit": {
      "atomic_claim": "Resveratrol has shown promising clinical benefits as anti-aging [60], anti-inflammatory [61], anti-diabetic [62], anti-viral [63], anti-neoplastic [64], and anti-CVD agents [65].",
      "cited_identifier": {
        "type": "pmid",
        "value": "17086191"
      },
      "citing_source": {
        "pmid": "23442817",
        "pmcid": "PMC3599349",
        "note": "citing review, cited as ref [65]"
      }
    },
    "grounded": {
      "identifier": {
        "type": "pmid",
        "value": "17086191"
      },
      "title": "Resveratrol improves health and survival of mice on a high-calorie diet.",
      "abstract": "Resveratrol, a polyphenol found in red wine, is thought to underlie some of the beneficial effects of caloric restriction. Here we show that resveratrol improves the health and survival of mice on a high-calorie diet. Resveratrol-treated mice on a high-calorie diet showed increased insulin sensitivity, reduced insulin-like growth factor-1 levels, increased mitochondrial number, and improved motor function. Resveratrol shifted the physiology of mice on a high-calorie diet towards that of mice on a standard diet and significantly increased their survival. These data show that an orally available small molecule at doses achievable in humans can safely reduce many of the negative consequences of excess caloric intake in mammals.",
      "mesh_all": [
        "Animals",
        "Caloric Restriction",
        "Diet",
        "Energy Intake",
        "Insulin",
        "Insulin-Like Growth Factor I",
        "Longevity",
        "Male",
        "Mice",
        "Mice, Inbred C57BL",
        "Mitochondria",
        "Motor Activity",
        "Stilbenes",
        "Survival Rate"
      ],
      "organism_tags": [
        {
          "descriptor": "Animals",
          "ui": "D000818",
          "tree_numbers": [
            "B01.050"
          ],
          "major_topic": false
        },
        {
          "descriptor": "Mice",
          "ui": "D051379",
          "tree_numbers": [
            "B01.050.150.900.649.313.992.635.505.500"
          ],
          "major_topic": false
        },
        {
          "descriptor": "Mice, Inbred C57BL",
          "ui": "D008810",
          "tree_numbers": [
            "B01.050.150.900.649.313.992.635.505.500.500.500"
          ],
          "major_topic": false
        }
      ],
      "population_tags": [],
      "sex_tags": [
        {
          "descriptor": "Male",
          "ui": "D008297",
          "tree_numbers": [],
          "major_topic": false
        }
      ],
      "publication_types": [
        "Journal Article",
        "Research Support, N.I.H., Extramural"
      ],
      "retraction": {
        "status": "NONE_FOUND",
        "retraction_watch": {
          "present": false,
          "rw_record_id": null,
          "reason": null,
          "date": null
        },
        "ncbi_publication_type_flag": false,
        "comments_corrections": [],
        "source_agreement": "agree",
        "provenance": "metadata-grounded"
      },
      "has_humans": false,
      "provenance": {
        "abstract": "ILLUSTRATIVE fixture text — condensed from the cited paper for offline rendering; NOT a verbatim NCBI EFetch <AbstractText> record (W0 demo fixture).",
        "mesh": "EFetch <MeshHeading> + NLM MeSH tree numbers",
        "retraction": "Retraction Watch (no record) + EFetch <PublicationType>",
        "_fixture": "W0 demo fixture — grounding text is illustrative; see verdict.notes[0]."
      },
      "grounding_errors": [],
      "full_text": "",
      "full_text_provenance": ""
    },
    "claim_scope": {
      "organism": "Humans",
      "organism_evidence": [
        "clinical benefits"
      ],
      "population": null,
      "population_evidence": [],
      "effect": "clinical benefit",
      "direction": "increase",
      "direction_evidence": [],
      "dose_stated": false,
      "provenance": "model-inferred (claim scope)",
      "tier": "medium"
    },
    "verdict": {
      "claim": "Resveratrol has shown promising clinical benefits as anti-aging [60], anti-inflammatory [61], anti-diabetic [62], anti-viral [63], anti-neoplastic [64], and anti-CVD agents [65].",
      "cited_identifier": {
        "type": "pmid",
        "value": "17086191"
      },
      "overall": "NOT SUPPORTED AS STATED (SPECIES SCOPE MISMATCH) — substantive grade: fully-supported (held separately)",
      "axis_findings": [
        {
          "axis": "retraction",
          "verdict": "NOT_RETRACTED",
          "tier": "high",
          "provenance": "metadata-grounded",
          "detail": "No retraction found in Retraction Watch or NCBI records.",
          "evidence": {
            "retraction_watch": {
              "present": false,
              "record_id": null,
              "reason": null,
              "date": null
            },
            "ncbi_publication_type_flag": false,
            "ncbi_comments_corrections": [],
            "source_agreement": "agree"
          }
        },
        {
          "axis": "species_scope",
          "verdict": "SCOPE_MISMATCH",
          "tier": "medium",
          "provenance": "metadata-grounded (cited) + model-inferred (claim scope) (claim)",
          "detail": "Claim asserts human/clinical relevance, but cited paper MeSH organism scope is ['Animals', 'Mice', 'Mice, Inbred C57BL'] with 'Humans' ABSENT — the human claim is not supported by this animal study. Metadata authoritative.",
          "evidence": {
            "cited_organism_tags": [
              {
                "descriptor": "Animals",
                "tree_numbers": [
                  "B01.050"
                ]
              },
              {
                "descriptor": "Mice",
                "tree_numbers": [
                  "B01.050.150.900.649.313.992.635.505.500"
                ]
              },
              {
                "descriptor": "Mice, Inbred C57BL",
                "tree_numbers": [
                  "B01.050.150.900.649.313.992.635.505.500.500.500"
                ]
              }
            ],
            "cited_has_humans": false,
            "claim_organism": "Humans",
            "claim_organism_provenance": "model-inferred (claim scope)",
            "claim_evidence": [
              "clinical benefits"
            ]
          }
        },
        {
          "axis": "population_scope",
          "verdict": "NOT_ASSESSED",
          "tier": "low",
          "provenance": "model-inferred",
          "detail": "No explicit or implicit population scope in the claim; population axis not assessed.",
          "evidence": {
            "cited_population_tags": [],
            "cited_pregnancy_mesh": [],
            "claim_population": null,
            "claim_evidence": []
          }
        },
        {
          "axis": "substantive_support",
          "verdict": "fully-supported",
          "tier": "high",
          "provenance": "model-inferred",
          "detail": "Holding scope constant, the paper's own (murine) results fully support the listed metabolic/longevity benefits; the species over-generalisation to HUMAN 'clinical benefits' is carried by the species-scope axis, not this grade (CONTEXT_PACK §6).",
          "evidence": {
            "confidence": {
              "verbalized": "high",
              "agreement": 0.86,
              "n_samples": 7
            },
            "calibration": {
              "note": ""
            },
            "supporter": {
              "span": "resveratrol improves the health and survival of mice on a high-calorie diet",
              "point": "The paper substantiates the claimed benefits within its (murine) scope."
            },
            "refuter": {
              "span": "at doses achievable in humans",
              "objection": "The paper only speculates that doses are humans-achievable; it presents NO human clinical data, so 'clinical benefits' over-generalises."
            },
            "abstained": false,
            "non_substantiating": false,
            "supporter_points": [
              {
                "quote": "resveratrol improves the health and survival of mice on a high-calorie diet",
                "rationale": "The paper substantiates the claimed benefits within its (murine) scope."
              }
            ],
            "refuter_points": [
              {
                "quote": "at doses achievable in humans",
                "objection": "The paper only speculates that doses are humans-achievable; it presents NO human clinical data, so 'clinical benefits' over-generalises."
              }
            ],
            "refuter_scope_notes": [
              {
                "quote": "improves the health and survival of mice",
                "objection": "Claim asserts human clinical benefit; cited study is mouse-only.",
                "distortion_type": "over_generalization",
                "routes_to": "rollup"
              }
            ],
            "verbatim_guard": {
              "supporter_discarded": 0,
              "refuter_discarded": 0,
              "grounding_corpus": "title+abstract+fulltext"
            },
            "self_consistency": {
              "rounds_configured": 7,
              "rounds_run": 7,
              "rounds_valid": 7,
              "a_exact": 0.86,
              "a_adj": 1.0,
              "conf_hybrid": 0.86,
              "non_adjacent_multimodal": false,
              "ordinal_distribution": {
                "fully-supported": 6,
                "supported-with-overreach": 1
              },
              "n_nei": 0,
              "n_non_substantiating": 0,
              "n_parse_failed": 0,
              "grade_ordinal": null,
              "output_tokens": [
                505,
                528,
                540,
                560,
                549,
                533,
                571
              ],
              "tau_abstain": 0.5,
              "adjacent_floor": 0.7
            }
          }
        }
      ],
      "unverifiable_axes": {
        "dose": "No dose asserted in the claim; not applicable.",
        "effect_direction": "Whether the claim's effect direction matches the cited paper's reported result requires reading the Results text; no structured field. Deferred to the adjudication agent."
      },
      "stub": false,
      "notes": [
        "DEMO FIXTURE (W0-CONTRACTS): the cited-paper abstract / full text rendered here is a CONDENSED, ILLUSTRATIVE stand-in for offline viewing — NOT a verbatim NCBI/PMC record. The verbatim guard is demonstrated against this illustrative text (the mechanism is real; the source text is a stand-in). Objective facts (retraction status/record, organism class, publication types) reflect the real structured record; the axis logic, substantive grade, and confidence are produced by the real citeval pipeline contracts.",
        "Species scope is metadata-grounded: cited MeSH organism tags are ['Animals','Mice','Mice, Inbred C57BL'] with NO 'Humans' tag, while the claim asserts human 'clinical benefits' — SPECIES SCOPE MISMATCH. This gates `overall` to NOT SUPPORTED AS STATED.",
        "substantive_support grades substance holding scope constant; the over-generalisation to humans is routed to the scope axis and folded into `overall` by the rollup, never used to depress the substantive grade (RB1 §D scope-capping overridden — CONTEXT_PACK §6).",
        "Whether the CLAIM over-generalises to humans is a model reading of the claim wording and is flagged model-inferred; the cited-side animal-only scope is metadata-grounded."
      ]
    }
  },
  "timing": {
    "per_stage_ms": {
      "ingest": 870.0,
      "ground_retraction": 1390.0,
      "ground_scope": 1330.0,
      "adjudicate": 79200.0,
      "report": 55.0
    },
    "total_ms": 82845.0,
    "est_total_ms": 87815.7
  },
  "cost": {
    "total_usd": 1.02795,
    "per_role": {
      "supporter": {
        "usd": 0.3807,
        "n_calls": 7,
        "tokens": {
          "input": 1680,
          "output": 2520,
          "cache_read": 36000,
          "cache_write": 6000
        }
      },
      "refuter": {
        "usd": 0.2688,
        "n_calls": 7,
        "tokens": {
          "input": 1820,
          "output": 2380,
          "cache_read": 42000,
          "cache_write": 0
        }
      },
      "critic": {
        "usd": 0.37845,
        "n_calls": 7,
        "tokens": {
          "input": 2100,
          "output": 3786,
          "cache_read": 42000,
          "cache_write": 0
        }
      }
    },
    "tokens": {
      "input": 5600,
      "output": 8686,
      "cache_read": 120000,
      "cache_write": 6000
    },
    "n_model_calls": 21
  },
  "report_html": "<!doctype html>\n<html lang=\"en\"><head>\n<meta charset=\"utf-8\">\n<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n<title>Citation verification report — PMID 17086191</title>\n<style>:root { color-scheme: light dark; }\nbody { font-family: -apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, Helvetica, Arial,\n       sans-serif; line-height: 1.5; color: #1a1a1a; background: #fff;\n       margin: 0 auto; max-width: 62rem; padding: 2rem; }\nh1 { font-size: 1.6rem; margin: 0 0 1rem; }\nh2 { font-size: 1.15rem; margin: 2rem 0 .5rem; border-bottom: 1px solid #e5e5e5; padding-bottom: .25rem; }\n.overall { font-weight: 700; padding: .55rem .8rem; background: #f6f8fa;\n           border-left: 4px solid #444; border-radius: .25rem; }\n.tablewrap { overflow-x: auto; }\ntable { border-collapse: collapse; width: 100%; font-size: .9rem; }\nth, td { border: 1px solid #e2e2e2; padding: .4rem .55rem; text-align: left; vertical-align: top; }\nth { background: #f6f8fa; }\n.badge { display: inline-block; padding: .08rem .45rem; border-radius: .6rem; font-size: .76rem;\n         font-weight: 600; white-space: nowrap; }\n.prov-meta { background: #e6f4ea; color: #137333; }\n.prov-text { background: #e8f0fe; color: #1967d2; }\n.prov-model { background: #fef7e0; color: #99590b; }\n.prov-stub { background: #f1f3f4; color: #5f6368; }\n.prov-composite { background: #f3e8fd; color: #7b2fbe; }\n.graded { background: #fbfbfd; border: 1px solid #e5e5e5; border-radius: .5rem; padding: 1rem 1.2rem; }\n.graded dl { display: grid; grid-template-columns: max-content 1fr; gap: .3rem .8rem; margin: 0; }\n.graded dt { font-weight: 600; }\n.graded dd { margin: 0; }\nblockquote { margin: .35rem 0; padding: .4rem .8rem; border-left: 3px solid #bbb;\n             background: #fafafa; color: #333; }\n.gloss { color: #555; font-size: .9rem; }\n.legend dt { font-weight: 600; }\n.override { font-style: italic; color: #444; }\n.stubnote { border-left: 3px solid #bbb; padding: .4rem .8rem; color: #555; background: #fafafa; }\n@media (prefers-color-scheme: dark) {\n  body { color: #e6e6e6; background: #16181c; }\n  h2 { border-bottom-color: #333; }\n  .overall { background: #22262e; border-left-color: #888; }\n  th { background: #22262e; } th, td { border-color: #333; }\n  .graded { background: #1b1e24; border-color: #333; }\n  blockquote, .stubnote { background: #1b1e24; border-left-color: #555; color: #cfcfcf; }\n  .gloss, .override { color: #b3b3b3; }\n}</style>\n</head><body>\n<main>\n<h1>Citation verification report</h1>\n<p><strong>Claim.</strong> Resveratrol has shown promising clinical benefits as anti-aging [60], anti-inflammatory [61], anti-diabetic [62], anti-viral [63], anti-neoplastic [64], and anti-CVD agents [65].</p>\n<p><strong>Cited paper.</strong> Resveratrol improves health and survival of mice on a high-calorie diet.<br>PMID 17086191</p>\n<p class=\"overall\">Overall: NOT SUPPORTED AS STATED (SPECIES SCOPE MISMATCH) — substantive grade: fully-supported (held separately)</p>\n<h2>Per-axis findings</h2>\n<div class=\"tablewrap\"><table>\n<thead><tr><th>Axis</th><th>Verdict</th><th>Confidence</th><th>Provenance</th><th>Basis</th></tr></thead>\n<tbody>\n<tr><td>retraction</td><td><strong>NOT_RETRACTED</strong></td><td>high</td><td><span class=\"badge prov-meta\">metadata-grounded</span></td><td>No retraction found in Retraction Watch or NCBI records.</td></tr>\n<tr><td>species_scope</td><td><strong>SCOPE_MISMATCH</strong></td><td>medium</td><td><span class=\"badge prov-meta\">metadata-grounded (cited) + model-inferred (claim scope) (claim)</span></td><td>Claim asserts human/clinical relevance, but cited paper MeSH organism scope is [&#x27;Animals&#x27;, &#x27;Mice&#x27;, &#x27;Mice, Inbred C57BL&#x27;] with &#x27;Humans&#x27; ABSENT — the human claim is not supported by this animal study. Metadata authoritative.</td></tr>\n<tr><td>population_scope</td><td><strong>NOT_ASSESSED</strong></td><td>low</td><td><span class=\"badge prov-model\">model-inferred</span></td><td>No explicit or implicit population scope in the claim; population axis not assessed.</td></tr>\n<tr><td>substantive_support</td><td><strong>fully-supported</strong></td><td>high</td><td><span class=\"badge prov-model\">model-inferred</span></td><td>Holding scope constant, the paper&#x27;s own (murine) results fully support the listed metabolic/longevity benefits; the species over-generalisation to HUMAN &#x27;clinical benefits&#x27; is carried by the species-scope axis, not this grade (CONTEXT_PACK §6).</td></tr>\n</tbody></table></div>\n<section class=\"graded\">\n<h2>Substantive support (graded)</h2>\n<dl>\n<dt>Grade (RB1 scale)</dt><dd>fully-supported</dd>\n<dt>Confidence</dt><dd>high — self-consistency agreement 0.86 across 7 samples; verbalized high</dd>\n<dt>Calibration</dt><dd>not yet available — populated by the scorer/RB3 once the corpus is scored.</dd>\n<dt>Provenance</dt><dd><span class=\"badge prov-model\">model-inferred</span> — grades substance only, holding scope constant (CONTEXT_PACK §6); scope over-reach is on the scope axes above.</dd>\n<dt>Rationale</dt><dd>Holding scope constant, the paper&#x27;s own (murine) results fully support the listed metabolic/longevity benefits; the species over-generalisation to HUMAN &#x27;clinical benefits&#x27; is carried by the species-scope axis, not this grade (CONTEXT_PACK §6).</dd>\n</dl>\n<p><strong>Adversarial trace.</strong></p>\n<p class=\"gloss\">Supporter — best supporting span:</p>\n<blockquote>resveratrol improves the health and survival of mice on a high-calorie diet</blockquote>\n<p class=\"gloss\">The paper substantiates the claimed benefits within its (murine) scope.</p>\n<p class=\"gloss\">Refuter — strongest objection:</p>\n<blockquote>at doses achievable in humans</blockquote>\n<p class=\"gloss\">The paper only speculates that doses are humans-achievable; it presents NO human clinical data, so &#x27;clinical benefits&#x27; over-generalises.</p>\n</section>\n<h2>Axes flagged unverifiable (not fabricated)</h2>\n<ul>\n<li><strong>dose</strong> — No dose asserted in the claim; not applicable.</li>\n<li><strong>effect_direction</strong> — Whether the claim&#x27;s effect direction matches the cited paper&#x27;s reported result requires reading the Results text; no structured field. Deferred to the adjudication agent.</li>\n</ul>\n<h2>Grounding evidence (structured, metadata-grounded)</h2>\n<ul>\n<li><strong>Retraction status:</strong> NONE_FOUND (source agreement: agree)\n</li>\n<li><strong>Organism MeSH (tree B*):</strong> Animals [B01.050], Mice [B01.050.150.900.649.313.992.635.505.500], Mice, Inbred C57BL [B01.050.150.900.649.313.992.635.505.500.500.500] | Humans present: False</li>\n<li><strong>Population MeSH (tree M01.060*):</strong> (none)</li>\n<li><strong>Sex check-tags:</strong> Male</li>\n</ul>\n<h2>Claim scope parse (C3-lite — explicit lexical markers)</h2>\n<ul>\n<li>Asserted organism: <strong>Humans</strong> (provenance: model-inferred (claim scope), tier: medium); evidence: [&#x27;clinical benefits&#x27;]</li>\n<li>Asserted population: (none); evidence: (none)</li>\n<li>Dose stated in claim: False</li>\n</ul>\n<h2>Provenance legend</h2>\n<dl class=\"legend\">\n<dt>metadata-grounded</dt><dd>read from a structured record (Retraction Watch, MeSH tags + tree numbers, NCBI linkage). Authoritative.</dd>\n<dt>text-grounded</dt><dd>an explicit lexical marker in the claim wording.</dd>\n<dt>model-inferred</dt><dd>a model judgement — the C3 claim-scope hint plus the graded substantive-support axis, produced by the adversarial supporter/refuter/critic agent with calibration.</dd>\n<dt>stub-not-adjudicated</dt><dd>deliberately not decided in the thin slice.</dd>\n</dl>\n<p class=\"override\">Metadata (grounded) always overrides model/text on objective axes — a conflict is scored as the model being wrong, not the record.</p>\n</main>\n</body></html>\n"
};

export const FIXTURE_GRADED_OVERREACH: RunResult = {
  "run_id": "run_ce11_overreach",
  "verdict": {
    "claim_unit": {
      "atomic_claim": "Remarkably, recent epidemiological data exhibit an increased association of obesity and allergy [200,201,202,203].",
      "cited_identifier": {
        "type": "pmid",
        "value": "19725894"
      },
      "citing_source": {
        "pmid": "26225961",
        "pmcid": "PMC4581184",
        "note": "citing review, cited as ref [202]"
      }
    },
    "grounded": {
      "identifier": {
        "type": "pmid",
        "value": "19725894"
      },
      "title": "Relationship between infant weight gain and later asthma.",
      "abstract": "This study examined whether the pattern of infant weight gain is associated with later asthma. Infants were followed prospectively and their weight-gain trajectories classified. Early life patterns of weight change were associated with subsequent asthma exacerbations, with fewer exacerbations occurring amongst those with a decelerated weight gain pattern. Weight gain pattern was significantly associated with aeroallergen skin test positivity (P=.03) and IgE level (P=.02), with the decelerated group demonstrating the highest degree of atopy. Given the small sample size, the findings should be viewed as preliminary.",
      "mesh_all": [
        "Asthma",
        "Body Weight",
        "Child",
        "Child, Preschool",
        "Female",
        "Humans",
        "Immunoglobulin E",
        "Infant",
        "Male",
        "Obesity",
        "Prospective Studies",
        "Risk Factors",
        "Skin Tests",
        "Weight Gain"
      ],
      "organism_tags": [
        {
          "descriptor": "Humans",
          "ui": "D006801",
          "tree_numbers": [
            "B01.050.150.900.649.313.988.400.112.400.400"
          ],
          "major_topic": false
        }
      ],
      "population_tags": [
        {
          "descriptor": "Infant",
          "ui": "D007223",
          "tree_numbers": [
            "M01.060.703.520"
          ],
          "major_topic": false
        },
        {
          "descriptor": "Child",
          "ui": "D002648",
          "tree_numbers": [
            "M01.060.406"
          ],
          "major_topic": false
        },
        {
          "descriptor": "Child, Preschool",
          "ui": "D002675",
          "tree_numbers": [
            "M01.060.406.448"
          ],
          "major_topic": false
        }
      ],
      "sex_tags": [
        {
          "descriptor": "Female",
          "ui": "D005260",
          "tree_numbers": [],
          "major_topic": false
        },
        {
          "descriptor": "Male",
          "ui": "D008297",
          "tree_numbers": [],
          "major_topic": false
        }
      ],
      "publication_types": [
        "Journal Article",
        "Research Support, Non-U.S. Gov't"
      ],
      "retraction": {
        "status": "NONE_FOUND",
        "retraction_watch": {
          "present": false,
          "rw_record_id": null,
          "reason": null,
          "date": null
        },
        "ncbi_publication_type_flag": false,
        "comments_corrections": [],
        "source_agreement": "agree",
        "provenance": "metadata-grounded"
      },
      "has_humans": true,
      "provenance": {
        "abstract": "ILLUSTRATIVE fixture text — condensed from the cited paper for offline rendering; NOT a verbatim NCBI EFetch <AbstractText> record (W0 demo fixture).",
        "mesh": "EFetch <MeshHeading> + NLM MeSH tree numbers",
        "full_text": "ILLUSTRATIVE fixture text — condensed excerpt for offline rendering; NOT a verbatim PMC JATS full-text record (W0 demo fixture).",
        "_fixture": "W0 demo fixture — grounding text is illustrative; see verdict.notes[0]."
      },
      "grounding_errors": [],
      "full_text": "This study examined whether the pattern of infant weight gain is associated with later asthma. Infants were followed prospectively and their weight-gain trajectories classified. Early life patterns of weight change were associated with subsequent asthma exacerbations, with fewer exacerbations occurring amongst those with a decelerated weight gain pattern. Weight gain pattern was significantly associated with aeroallergen skin test positivity (P=.03) and IgE level (P=.02), with the decelerated group demonstrating the highest degree of atopy. Given the small sample size, the findings should be viewed as preliminary.\n\nDISCUSSION\n\nOutside of infancy, the prevalence of asthma is associated with increased body mass index during childhood. In a large cohort, females who became overweight or obese between ages 6 and 11 years had an increased risk of developing new asthma symptoms and increased bronchial reactivity during the early adolescent period. Like obesity, the prevalence of asthma has increased over the past several decades. We conclude that early life patterns of weight change were associated with subsequent asthma exacerbations; early life weight gain pattern was not associated with daily asthma symptoms or lung function at the study's conclusion.",
      "full_text_provenance": "illustrative-fixture-excerpt (condensed)"
    },
    "claim_scope": {
      "organism": "Humans",
      "organism_evidence": [
        "epidemiological data"
      ],
      "population": null,
      "population_evidence": [],
      "effect": "association of obesity and allergy",
      "direction": "increase",
      "direction_evidence": [
        "increased association"
      ],
      "dose_stated": false,
      "provenance": "model-inferred (claim scope)",
      "tier": "medium"
    },
    "verdict": {
      "claim": "Remarkably, recent epidemiological data exhibit an increased association of obesity and allergy [200,201,202,203].",
      "cited_identifier": {
        "type": "pmid",
        "value": "19725894"
      },
      "overall": "SUBSTANTIVE SUPPORT: supported-with-overreach",
      "axis_findings": [
        {
          "axis": "retraction",
          "verdict": "NOT_RETRACTED",
          "tier": "high",
          "provenance": "metadata-grounded",
          "detail": "No retraction found in Retraction Watch or NCBI records.",
          "evidence": {
            "retraction_watch": {
              "present": false,
              "record_id": null,
              "reason": null,
              "date": null
            },
            "ncbi_publication_type_flag": false,
            "ncbi_comments_corrections": [],
            "source_agreement": "agree"
          }
        },
        {
          "axis": "species_scope",
          "verdict": "SCOPE_CONSISTENT",
          "tier": "medium",
          "provenance": "metadata-grounded (cited) + model-inferred (claim scope) (claim)",
          "detail": "Claim asserts human scope; cited paper MeSH organism scope includes Humans (['Humans']).",
          "evidence": {
            "cited_organism_tags": [
              {
                "descriptor": "Humans",
                "tree_numbers": [
                  "B01.050.150.900.649.313.988.400.112.400.400"
                ]
              }
            ],
            "cited_has_humans": true,
            "claim_organism": "Humans",
            "claim_organism_provenance": "model-inferred (claim scope)",
            "claim_evidence": [
              "epidemiological data"
            ]
          }
        },
        {
          "axis": "population_scope",
          "verdict": "NOT_ASSESSED",
          "tier": "low",
          "provenance": "model-inferred",
          "detail": "No explicit or implicit population scope in the claim; population axis not assessed.",
          "evidence": {
            "cited_population_tags": [
              "Infant",
              "Child",
              "Child, Preschool"
            ],
            "cited_pregnancy_mesh": [],
            "claim_population": null,
            "claim_evidence": []
          }
        },
        {
          "axis": "substantive_support",
          "verdict": "supported-with-overreach",
          "tier": "low",
          "provenance": "model-inferred",
          "detail": "The source's discussion affirms a positive obesity/BMI–asthma association in the claimed direction, but its direct atopy markers (IgE, skin test) run the OTHER way and the paper is hedged/preliminary — so citing it for a firm 'increased association of obesity and allergy' over-reaches on generality and certainty.",
          "evidence": {
            "confidence": {
              "verbalized": "low",
              "agreement": 0.5714,
              "n_samples": 7
            },
            "calibration": {
              "note": "adjacent-only split (a_adj=1.00): the vote oscillates between two neighbouring grades, so the grade is placed with LOW confidence."
            },
            "supporter": {
              "span": "Outside of infancy, the prevalence of asthma is associated with increased body mass index during childhood",
              "point": "The discussion affirms a positive obesity/BMI–asthma link in the claimed direction."
            },
            "refuter": {
              "span": "Weight gain pattern was significantly associated with aeroallergen skin test positivity (P=.03) and IgE level (P=.02), with the decelerated group demonstrating the highest degree of atopy",
              "objection": "On the direct atopy/allergy markers the LEANER (decelerated) group had the HIGHEST atopy — an inverse obesity–allergy link — so the claim over-generalises 'asthma' to 'allergy'."
            },
            "abstained": false,
            "non_substantiating": false,
            "supporter_points": [
              {
                "quote": "Outside of infancy, the prevalence of asthma is associated with increased body mass index during childhood",
                "rationale": "The discussion affirms a positive obesity/BMI–asthma link in the claimed direction."
              }
            ],
            "refuter_points": [
              {
                "quote": "Weight gain pattern was significantly associated with aeroallergen skin test positivity (P=.03) and IgE level (P=.02), with the decelerated group demonstrating the highest degree of atopy",
                "objection": "On the direct atopy/allergy markers the LEANER (decelerated) group had the HIGHEST atopy — an inverse obesity–allergy link — so the claim over-generalises 'asthma' to 'allergy'."
              }
            ],
            "refuter_scope_notes": [],
            "verbatim_guard": {
              "supporter_discarded": 0,
              "refuter_discarded": 0,
              "grounding_corpus": "title+abstract+fulltext"
            },
            "self_consistency": {
              "rounds_configured": 7,
              "rounds_run": 7,
              "rounds_valid": 7,
              "a_exact": 0.5714,
              "a_adj": 1.0,
              "conf_hybrid": 0.5714,
              "non_adjacent_multimodal": false,
              "ordinal_distribution": {
                "supported-with-overreach": 4,
                "partially-supported": 3
              },
              "n_nei": 0,
              "n_non_substantiating": 0,
              "n_parse_failed": 0,
              "grade_ordinal": null,
              "output_tokens": [
                863,
                826,
                768,
                805,
                818,
                896,
                822
              ],
              "tau_abstain": 0.5,
              "adjacent_floor": 0.7
            }
          }
        }
      ],
      "unverifiable_axes": {
        "dose": "No dose asserted in the claim; not applicable.",
        "effect_direction": "Whether the claim's effect direction matches the cited paper's reported result requires reading the Results text; no structured field. Deferred to the adjudication agent."
      },
      "stub": false,
      "notes": [
        "DEMO FIXTURE (W0-CONTRACTS): the cited-paper abstract / full text rendered here is a CONDENSED, ILLUSTRATIVE stand-in for offline viewing — NOT a verbatim NCBI/PMC record. The verbatim guard is demonstrated against this illustrative text (the mechanism is real; the source text is a stand-in). Objective facts (retraction status/record, organism class, publication types) reflect the real structured record; the axis logic, substantive grade, and confidence are produced by the real citeval pipeline contracts.",
        "No objective gate: the cited paper is not retracted and the human scope matches, so `overall` tracks the substantive grade.",
        "Self-consistency was DISPERSED across two adjacent grades (supported-with-overreach ×4, partially-supported ×3; exact agreement 0.57, adjacent agreement 1.00 over 7 rounds). Because the split is adjacent-only it resolves to the median-aware grade rather than abstaining, but the confidence tier is honestly LOW — this is a genuinely borderline over-reach.",
        "Replay note: these are the four/seven real per-round critic grades from the committed transcript corpus/calibration/transcripts/debate_A27_Ce11.json (Ce11); replaying them through the current aggregation yields supported-with-overreach at a_exact=0.57."
      ]
    }
  },
  "timing": {
    "per_stage_ms": {
      "ingest": 1020.0,
      "ground_retraction": 1510.0,
      "ground_scope": 1240.0,
      "adjudicate": 223600.0,
      "report": 62.0
    },
    "total_ms": 227432.0,
    "est_total_ms": 241077.9
  },
  "cost": {
    "total_usd": 1.17885,
    "per_role": {
      "supporter": {
        "usd": 0.3807,
        "n_calls": 7,
        "tokens": {
          "input": 1680,
          "output": 2520,
          "cache_read": 36000,
          "cache_write": 6000
        }
      },
      "refuter": {
        "usd": 0.2688,
        "n_calls": 7,
        "tokens": {
          "input": 1820,
          "output": 2380,
          "cache_read": 42000,
          "cache_write": 0
        }
      },
      "critic": {
        "usd": 0.52935,
        "n_calls": 7,
        "tokens": {
          "input": 2100,
          "output": 5798,
          "cache_read": 42000,
          "cache_write": 0
        }
      }
    },
    "tokens": {
      "input": 5600,
      "output": 10698,
      "cache_read": 120000,
      "cache_write": 6000
    },
    "n_model_calls": 21
  },
  "report_html": "<!doctype html>\n<html lang=\"en\"><head>\n<meta charset=\"utf-8\">\n<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n<title>Citation verification report — PMID 19725894</title>\n<style>:root { color-scheme: light dark; }\nbody { font-family: -apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, Helvetica, Arial,\n       sans-serif; line-height: 1.5; color: #1a1a1a; background: #fff;\n       margin: 0 auto; max-width: 62rem; padding: 2rem; }\nh1 { font-size: 1.6rem; margin: 0 0 1rem; }\nh2 { font-size: 1.15rem; margin: 2rem 0 .5rem; border-bottom: 1px solid #e5e5e5; padding-bottom: .25rem; }\n.overall { font-weight: 700; padding: .55rem .8rem; background: #f6f8fa;\n           border-left: 4px solid #444; border-radius: .25rem; }\n.tablewrap { overflow-x: auto; }\ntable { border-collapse: collapse; width: 100%; font-size: .9rem; }\nth, td { border: 1px solid #e2e2e2; padding: .4rem .55rem; text-align: left; vertical-align: top; }\nth { background: #f6f8fa; }\n.badge { display: inline-block; padding: .08rem .45rem; border-radius: .6rem; font-size: .76rem;\n         font-weight: 600; white-space: nowrap; }\n.prov-meta { background: #e6f4ea; color: #137333; }\n.prov-text { background: #e8f0fe; color: #1967d2; }\n.prov-model { background: #fef7e0; color: #99590b; }\n.prov-stub { background: #f1f3f4; color: #5f6368; }\n.prov-composite { background: #f3e8fd; color: #7b2fbe; }\n.graded { background: #fbfbfd; border: 1px solid #e5e5e5; border-radius: .5rem; padding: 1rem 1.2rem; }\n.graded dl { display: grid; grid-template-columns: max-content 1fr; gap: .3rem .8rem; margin: 0; }\n.graded dt { font-weight: 600; }\n.graded dd { margin: 0; }\nblockquote { margin: .35rem 0; padding: .4rem .8rem; border-left: 3px solid #bbb;\n             background: #fafafa; color: #333; }\n.gloss { color: #555; font-size: .9rem; }\n.legend dt { font-weight: 600; }\n.override { font-style: italic; color: #444; }\n.stubnote { border-left: 3px solid #bbb; padding: .4rem .8rem; color: #555; background: #fafafa; }\n@media (prefers-color-scheme: dark) {\n  body { color: #e6e6e6; background: #16181c; }\n  h2 { border-bottom-color: #333; }\n  .overall { background: #22262e; border-left-color: #888; }\n  th { background: #22262e; } th, td { border-color: #333; }\n  .graded { background: #1b1e24; border-color: #333; }\n  blockquote, .stubnote { background: #1b1e24; border-left-color: #555; color: #cfcfcf; }\n  .gloss, .override { color: #b3b3b3; }\n}</style>\n</head><body>\n<main>\n<h1>Citation verification report</h1>\n<p><strong>Claim.</strong> Remarkably, recent epidemiological data exhibit an increased association of obesity and allergy [200,201,202,203].</p>\n<p><strong>Cited paper.</strong> Relationship between infant weight gain and later asthma.<br>PMID 19725894</p>\n<p class=\"overall\">Overall: SUBSTANTIVE SUPPORT: supported-with-overreach</p>\n<h2>Per-axis findings</h2>\n<div class=\"tablewrap\"><table>\n<thead><tr><th>Axis</th><th>Verdict</th><th>Confidence</th><th>Provenance</th><th>Basis</th></tr></thead>\n<tbody>\n<tr><td>retraction</td><td><strong>NOT_RETRACTED</strong></td><td>high</td><td><span class=\"badge prov-meta\">metadata-grounded</span></td><td>No retraction found in Retraction Watch or NCBI records.</td></tr>\n<tr><td>species_scope</td><td><strong>SCOPE_CONSISTENT</strong></td><td>medium</td><td><span class=\"badge prov-meta\">metadata-grounded (cited) + model-inferred (claim scope) (claim)</span></td><td>Claim asserts human scope; cited paper MeSH organism scope includes Humans ([&#x27;Humans&#x27;]).</td></tr>\n<tr><td>population_scope</td><td><strong>NOT_ASSESSED</strong></td><td>low</td><td><span class=\"badge prov-model\">model-inferred</span></td><td>No explicit or implicit population scope in the claim; population axis not assessed.</td></tr>\n<tr><td>substantive_support</td><td><strong>supported-with-overreach</strong></td><td>low</td><td><span class=\"badge prov-model\">model-inferred</span></td><td>The source&#x27;s discussion affirms a positive obesity/BMI–asthma association in the claimed direction, but its direct atopy markers (IgE, skin test) run the OTHER way and the paper is hedged/preliminary — so citing it for a firm &#x27;increased association of obesity and allergy&#x27; over-reaches on generality and certainty.</td></tr>\n</tbody></table></div>\n<section class=\"graded\">\n<h2>Substantive support (graded)</h2>\n<dl>\n<dt>Grade (RB1 scale)</dt><dd>supported-with-overreach</dd>\n<dt>Confidence</dt><dd>low — self-consistency agreement 0.57 across 7 samples; verbalized low</dd>\n<dt>Calibration</dt><dd>adjacent-only split (a_adj=1.00): the vote oscillates between two neighbouring grades, so the grade is placed with LOW confidence.</dd>\n<dt>Provenance</dt><dd><span class=\"badge prov-model\">model-inferred</span> — grades substance only, holding scope constant (CONTEXT_PACK §6); scope over-reach is on the scope axes above.</dd>\n<dt>Rationale</dt><dd>The source&#x27;s discussion affirms a positive obesity/BMI–asthma association in the claimed direction, but its direct atopy markers (IgE, skin test) run the OTHER way and the paper is hedged/preliminary — so citing it for a firm &#x27;increased association of obesity and allergy&#x27; over-reaches on generality and certainty.</dd>\n</dl>\n<p><strong>Adversarial trace.</strong></p>\n<p class=\"gloss\">Supporter — best supporting span:</p>\n<blockquote>Outside of infancy, the prevalence of asthma is associated with increased body mass index during childhood</blockquote>\n<p class=\"gloss\">The discussion affirms a positive obesity/BMI–asthma link in the claimed direction.</p>\n<p class=\"gloss\">Refuter — strongest objection:</p>\n<blockquote>Weight gain pattern was significantly associated with aeroallergen skin test positivity (P=.03) and IgE level (P=.02), with the decelerated group demonstrating the highest degree of atopy</blockquote>\n<p class=\"gloss\">On the direct atopy/allergy markers the LEANER (decelerated) group had the HIGHEST atopy — an inverse obesity–allergy link — so the claim over-generalises &#x27;asthma&#x27; to &#x27;allergy&#x27;.</p>\n</section>\n<h2>Axes flagged unverifiable (not fabricated)</h2>\n<ul>\n<li><strong>dose</strong> — No dose asserted in the claim; not applicable.</li>\n<li><strong>effect_direction</strong> — Whether the claim&#x27;s effect direction matches the cited paper&#x27;s reported result requires reading the Results text; no structured field. Deferred to the adjudication agent.</li>\n</ul>\n<h2>Grounding evidence (structured, metadata-grounded)</h2>\n<ul>\n<li><strong>Retraction status:</strong> NONE_FOUND (source agreement: agree)\n</li>\n<li><strong>Organism MeSH (tree B*):</strong> Humans [B01.050.150.900.649.313.988.400.112.400.400] | Humans present: True</li>\n<li><strong>Population MeSH (tree M01.060*):</strong> Infant [M01.060.703.520], Child [M01.060.406], Child, Preschool [M01.060.406.448]</li>\n<li><strong>Sex check-tags:</strong> Female, Male</li>\n</ul>\n<h2>Claim scope parse (C3-lite — explicit lexical markers)</h2>\n<ul>\n<li>Asserted organism: <strong>Humans</strong> (provenance: model-inferred (claim scope), tier: medium); evidence: [&#x27;epidemiological data&#x27;]</li>\n<li>Asserted population: (none); evidence: (none)</li>\n<li>Dose stated in claim: False</li>\n</ul>\n<h2>Provenance legend</h2>\n<dl class=\"legend\">\n<dt>metadata-grounded</dt><dd>read from a structured record (Retraction Watch, MeSH tags + tree numbers, NCBI linkage). Authoritative.</dd>\n<dt>text-grounded</dt><dd>an explicit lexical marker in the claim wording.</dd>\n<dt>model-inferred</dt><dd>a model judgement — the C3 claim-scope hint plus the graded substantive-support axis, produced by the adversarial supporter/refuter/critic agent with calibration.</dd>\n<dt>stub-not-adjudicated</dt><dd>deliberately not decided in the thin slice.</dd>\n</dl>\n<p class=\"override\">Metadata (grounded) always overrides model/text on objective axes — a conflict is scored as the model being wrong, not the record.</p>\n</main>\n</body></html>\n"
};

export const FIXTURE_ABSTENTION: RunResult = {
  "run_id": "run_ch05_abstention",
  "verdict": {
    "claim_unit": {
      "atomic_claim": "VZV reactivation is more common in highly immunosuppressed children who are receiving therapy for cancer or rheumatological diseases 202.",
      "cited_identifier": {
        "type": "pmid",
        "value": "2832088"
      },
      "citing_source": {
        "pmid": "27188665",
        "pmcid": "PMC5381807",
        "note": "citing review, cited as ref [202]"
      }
    },
    "grounded": {
      "identifier": {
        "type": "pmid",
        "value": "2832088"
      },
      "title": "Varicella-zoster virus infection and immunization in the healthy and the immunocompromised host.",
      "abstract": "Varicella-zoster virus (VZV) causes varicella on primary infection and herpes zoster on reactivation. This review surveys VZV infection and immunization in both the healthy and the immunocompromised host. The immunocompromised host is at increased risk of severe and disseminated VZV disease. Antiviral therapy and, more recently, active and passive immunization strategies are discussed. The relative contributions of specific immunosuppressive regimens, underlying disease, and age to reactivation risk remain incompletely defined and warrant further study.",
      "mesh_all": [
        "Animals",
        "Herpes Zoster",
        "Herpesvirus 3, Human",
        "Humans",
        "Immunocompromised Host",
        "Chickenpox",
        "Chickenpox Vaccine",
        "Antiviral Agents"
      ],
      "organism_tags": [
        {
          "descriptor": "Humans",
          "ui": "D006801",
          "tree_numbers": [
            "B01.050.150.900.649.313.988.400.112.400.400"
          ],
          "major_topic": false
        },
        {
          "descriptor": "Animals",
          "ui": "D000818",
          "tree_numbers": [
            "B01.050"
          ],
          "major_topic": false
        }
      ],
      "population_tags": [],
      "sex_tags": [],
      "publication_types": [
        "Journal Article",
        "Review"
      ],
      "retraction": {
        "status": "NONE_FOUND",
        "retraction_watch": {
          "present": false,
          "rw_record_id": null,
          "reason": null,
          "date": null
        },
        "ncbi_publication_type_flag": false,
        "comments_corrections": [],
        "source_agreement": "agree",
        "provenance": "metadata-grounded"
      },
      "has_humans": true,
      "provenance": {
        "abstract": "ILLUSTRATIVE fixture text — condensed from the cited paper for offline rendering; NOT a verbatim NCBI EFetch <AbstractText> record (W0 demo fixture).",
        "mesh": "EFetch <MeshHeading> + NLM MeSH tree numbers",
        "retraction": "Retraction Watch (no record) + EFetch <PublicationType>",
        "_fixture": "W0 demo fixture — grounding text is illustrative; see verdict.notes[0]."
      },
      "grounding_errors": [],
      "full_text": "",
      "full_text_provenance": ""
    },
    "claim_scope": {
      "organism": "Humans",
      "organism_evidence": [
        "children receiving therapy"
      ],
      "population": null,
      "population_evidence": [],
      "effect": "reactivation risk",
      "direction": "increase",
      "direction_evidence": [],
      "dose_stated": false,
      "provenance": "model-inferred (claim scope)",
      "tier": "medium"
    },
    "verdict": {
      "claim": "VZV reactivation is more common in highly immunosuppressed children who are receiving therapy for cancer or rheumatological diseases 202.",
      "cited_identifier": {
        "type": "pmid",
        "value": "2832088"
      },
      "overall": "INSUFFICIENT EVIDENCE TO GRADE SUBSTANTIVE SUPPORT (abstained)",
      "axis_findings": [
        {
          "axis": "retraction",
          "verdict": "NOT_RETRACTED",
          "tier": "high",
          "provenance": "metadata-grounded",
          "detail": "No retraction found in Retraction Watch or NCBI records.",
          "evidence": {
            "retraction_watch": {
              "present": false,
              "record_id": null,
              "reason": null,
              "date": null
            },
            "ncbi_publication_type_flag": false,
            "ncbi_comments_corrections": [],
            "source_agreement": "agree"
          }
        },
        {
          "axis": "species_scope",
          "verdict": "SCOPE_CONSISTENT",
          "tier": "medium",
          "provenance": "metadata-grounded (cited) + model-inferred (claim scope) (claim)",
          "detail": "Claim asserts human scope; cited paper MeSH organism scope includes Humans (['Humans', 'Animals']).",
          "evidence": {
            "cited_organism_tags": [
              {
                "descriptor": "Humans",
                "tree_numbers": [
                  "B01.050.150.900.649.313.988.400.112.400.400"
                ]
              },
              {
                "descriptor": "Animals",
                "tree_numbers": [
                  "B01.050"
                ]
              }
            ],
            "cited_has_humans": true,
            "claim_organism": "Humans",
            "claim_organism_provenance": "model-inferred (claim scope)",
            "claim_evidence": [
              "children receiving therapy"
            ]
          }
        },
        {
          "axis": "population_scope",
          "verdict": "NOT_ASSESSED",
          "tier": "low",
          "provenance": "model-inferred",
          "detail": "No explicit or implicit population scope in the claim; population axis not assessed.",
          "evidence": {
            "cited_population_tags": [],
            "cited_pregnancy_mesh": [],
            "claim_population": null,
            "claim_evidence": []
          }
        },
        {
          "axis": "substantive_support",
          "verdict": "NOT_ENOUGH_INFO",
          "tier": "low",
          "provenance": "model-inferred",
          "detail": "The cited paper is a REVIEW that establishes elevated VZV risk in the immunocompromised host generally, but does NOT provide verbatim-grounded evidence for the SPECIFIC subgroup the claim asserts (children on cancer/rheumatology therapy). The self-consistency vote was non-adjacent multimodal, so the panel ABSTAINS rather than guess — recorded as an abstention, not scored as wrong.",
          "evidence": {
            "confidence": {
              "verbalized": "low",
              "agreement": 0.3333,
              "n_samples": 3
            },
            "calibration": {
              "note": "non-adjacent multimodal split (a_adj=0.67 < 0.70) with only 3 parseable ordinal rounds — below the trust floor, so the panel abstains."
            },
            "supporter": {
              "span": "The immunocompromised host is at increased risk of severe and disseminated VZV disease",
              "point": "Supports elevated risk in the immunocompromised host in general."
            },
            "refuter": {
              "span": "The relative contributions of specific immunosuppressive regimens, underlying disease, and age to reactivation risk remain incompletely defined",
              "objection": "The review explicitly says the subgroup-specific contributions are incompletely defined — it does not substantiate the claim's specific pediatric-cancer/rheumatology comparison."
            },
            "abstained": true,
            "non_substantiating": false,
            "supporter_points": [
              {
                "quote": "The immunocompromised host is at increased risk of severe and disseminated VZV disease",
                "rationale": "Supports elevated risk in the immunocompromised host in general."
              }
            ],
            "refuter_points": [
              {
                "quote": "The relative contributions of specific immunosuppressive regimens, underlying disease, and age to reactivation risk remain incompletely defined",
                "objection": "The review explicitly says the subgroup-specific contributions are incompletely defined — it does not substantiate the claim's specific pediatric-cancer/rheumatology comparison."
              }
            ],
            "refuter_scope_notes": [],
            "verbatim_guard": {
              "supporter_discarded": 0,
              "refuter_discarded": 0,
              "grounding_corpus": "title+abstract+fulltext"
            },
            "self_consistency": {
              "rounds_configured": 7,
              "rounds_run": 7,
              "rounds_valid": 3,
              "a_exact": 0.3333,
              "a_adj": 0.6667,
              "conf_hybrid": 0.3333,
              "non_adjacent_multimodal": true,
              "ordinal_distribution": {
                "partially-supported": 1,
                "technically-true-but-misleading": 1,
                "unsupported-for-the-claim": 1
              },
              "n_nei": 2,
              "n_non_substantiating": 0,
              "n_parse_failed": 2,
              "grade_ordinal": null,
              "output_tokens": [
                742,
                688,
                0,
                715,
                0,
                733,
                701
              ],
              "tau_abstain": 0.5,
              "adjacent_floor": 0.7
            }
          }
        }
      ],
      "unverifiable_axes": {
        "dose": "No dose asserted in the claim; not applicable.",
        "effect_direction": "Whether the claim's effect direction matches the cited paper's reported result requires reading the Results text; no structured field. Deferred to the adjudication agent."
      },
      "stub": false,
      "notes": [
        "DEMO FIXTURE (W0-CONTRACTS): the cited-paper abstract / full text rendered here is a CONDENSED, ILLUSTRATIVE stand-in for offline viewing — NOT a verbatim NCBI/PMC record. The verbatim guard is demonstrated against this illustrative text (the mechanism is real; the source text is a stand-in). Objective facts (retraction status/record, organism class, publication types) reflect the real structured record; the axis logic, substantive grade, and confidence are produced by the real citeval pipeline contracts.",
        "No objective gate: not retracted, and the human scope matches (the record's stray 'Animals' MeSH tag is FP bait — the human claim is correctly scoped to a human study, so species scope does NOT fire).",
        "Abstained on substantive_support (NOT_ENOUGH_INFO): the self-consistency vote was non-adjacent multimodal (a_adj=0.67 < adjacent_floor 0.70) with only 3 of 7 rounds placing a parseable grade — below the trust floor. Recorded as an abstention so it is NOT scored as a wrong grade.",
        "Abstention is a first-class, honest outcome — an unverifiable-from-this-source claim is flagged, never fabricated (CLAUDE.md invariant #3)."
      ]
    }
  },
  "timing": {
    "per_stage_ms": {
      "ingest": 940.0,
      "ground_retraction": 1450.0,
      "ground_scope": 1180.0,
      "adjudicate": 96500.0,
      "report": 58.0
    },
    "total_ms": 100128.0,
    "est_total_ms": 106135.7
  },
  "cost": {
    "total_usd": 1.012425,
    "per_role": {
      "supporter": {
        "usd": 0.3807,
        "n_calls": 7,
        "tokens": {
          "input": 1680,
          "output": 2520,
          "cache_read": 36000,
          "cache_write": 6000
        }
      },
      "refuter": {
        "usd": 0.2688,
        "n_calls": 7,
        "tokens": {
          "input": 1820,
          "output": 2380,
          "cache_read": 42000,
          "cache_write": 0
        }
      },
      "critic": {
        "usd": 0.362925,
        "n_calls": 7,
        "tokens": {
          "input": 2100,
          "output": 3579,
          "cache_read": 42000,
          "cache_write": 0
        }
      }
    },
    "tokens": {
      "input": 5600,
      "output": 8479,
      "cache_read": 120000,
      "cache_write": 6000
    },
    "n_model_calls": 21
  },
  "report_html": "<!doctype html>\n<html lang=\"en\"><head>\n<meta charset=\"utf-8\">\n<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n<title>Citation verification report — PMID 2832088</title>\n<style>:root { color-scheme: light dark; }\nbody { font-family: -apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, Helvetica, Arial,\n       sans-serif; line-height: 1.5; color: #1a1a1a; background: #fff;\n       margin: 0 auto; max-width: 62rem; padding: 2rem; }\nh1 { font-size: 1.6rem; margin: 0 0 1rem; }\nh2 { font-size: 1.15rem; margin: 2rem 0 .5rem; border-bottom: 1px solid #e5e5e5; padding-bottom: .25rem; }\n.overall { font-weight: 700; padding: .55rem .8rem; background: #f6f8fa;\n           border-left: 4px solid #444; border-radius: .25rem; }\n.tablewrap { overflow-x: auto; }\ntable { border-collapse: collapse; width: 100%; font-size: .9rem; }\nth, td { border: 1px solid #e2e2e2; padding: .4rem .55rem; text-align: left; vertical-align: top; }\nth { background: #f6f8fa; }\n.badge { display: inline-block; padding: .08rem .45rem; border-radius: .6rem; font-size: .76rem;\n         font-weight: 600; white-space: nowrap; }\n.prov-meta { background: #e6f4ea; color: #137333; }\n.prov-text { background: #e8f0fe; color: #1967d2; }\n.prov-model { background: #fef7e0; color: #99590b; }\n.prov-stub { background: #f1f3f4; color: #5f6368; }\n.prov-composite { background: #f3e8fd; color: #7b2fbe; }\n.graded { background: #fbfbfd; border: 1px solid #e5e5e5; border-radius: .5rem; padding: 1rem 1.2rem; }\n.graded dl { display: grid; grid-template-columns: max-content 1fr; gap: .3rem .8rem; margin: 0; }\n.graded dt { font-weight: 600; }\n.graded dd { margin: 0; }\nblockquote { margin: .35rem 0; padding: .4rem .8rem; border-left: 3px solid #bbb;\n             background: #fafafa; color: #333; }\n.gloss { color: #555; font-size: .9rem; }\n.legend dt { font-weight: 600; }\n.override { font-style: italic; color: #444; }\n.stubnote { border-left: 3px solid #bbb; padding: .4rem .8rem; color: #555; background: #fafafa; }\n@media (prefers-color-scheme: dark) {\n  body { color: #e6e6e6; background: #16181c; }\n  h2 { border-bottom-color: #333; }\n  .overall { background: #22262e; border-left-color: #888; }\n  th { background: #22262e; } th, td { border-color: #333; }\n  .graded { background: #1b1e24; border-color: #333; }\n  blockquote, .stubnote { background: #1b1e24; border-left-color: #555; color: #cfcfcf; }\n  .gloss, .override { color: #b3b3b3; }\n}</style>\n</head><body>\n<main>\n<h1>Citation verification report</h1>\n<p><strong>Claim.</strong> VZV reactivation is more common in highly immunosuppressed children who are receiving therapy for cancer or rheumatological diseases 202.</p>\n<p><strong>Cited paper.</strong> Varicella-zoster virus infection and immunization in the healthy and the immunocompromised host.<br>PMID 2832088</p>\n<p class=\"overall\">Overall: INSUFFICIENT EVIDENCE TO GRADE SUBSTANTIVE SUPPORT (abstained)</p>\n<h2>Per-axis findings</h2>\n<div class=\"tablewrap\"><table>\n<thead><tr><th>Axis</th><th>Verdict</th><th>Confidence</th><th>Provenance</th><th>Basis</th></tr></thead>\n<tbody>\n<tr><td>retraction</td><td><strong>NOT_RETRACTED</strong></td><td>high</td><td><span class=\"badge prov-meta\">metadata-grounded</span></td><td>No retraction found in Retraction Watch or NCBI records.</td></tr>\n<tr><td>species_scope</td><td><strong>SCOPE_CONSISTENT</strong></td><td>medium</td><td><span class=\"badge prov-meta\">metadata-grounded (cited) + model-inferred (claim scope) (claim)</span></td><td>Claim asserts human scope; cited paper MeSH organism scope includes Humans ([&#x27;Humans&#x27;, &#x27;Animals&#x27;]).</td></tr>\n<tr><td>population_scope</td><td><strong>NOT_ASSESSED</strong></td><td>low</td><td><span class=\"badge prov-model\">model-inferred</span></td><td>No explicit or implicit population scope in the claim; population axis not assessed.</td></tr>\n<tr><td>substantive_support</td><td><strong>NOT_ENOUGH_INFO</strong></td><td>low</td><td><span class=\"badge prov-model\">model-inferred</span></td><td>The cited paper is a REVIEW that establishes elevated VZV risk in the immunocompromised host generally, but does NOT provide verbatim-grounded evidence for the SPECIFIC subgroup the claim asserts (children on cancer/rheumatology therapy). The self-consistency vote was non-adjacent multimodal, so the panel ABSTAINS rather than guess — recorded as an abstention, not scored as wrong.</td></tr>\n</tbody></table></div>\n<section class=\"graded\">\n<h2>Substantive support (graded)</h2>\n<dl>\n<dt>Grade (RB1 scale)</dt><dd>NOT_ENOUGH_INFO — the agent abstained; recorded as an abstention, not scored as wrong.</dd>\n<dt>Confidence</dt><dd>low — self-consistency agreement 0.33 across 3 samples; verbalized low</dd>\n<dt>Calibration</dt><dd>non-adjacent multimodal split (a_adj=0.67 &lt; 0.70) with only 3 parseable ordinal rounds — below the trust floor, so the panel abstains.</dd>\n<dt>Provenance</dt><dd><span class=\"badge prov-model\">model-inferred</span> — grades substance only, holding scope constant (CONTEXT_PACK §6); scope over-reach is on the scope axes above.</dd>\n<dt>Rationale</dt><dd>The cited paper is a REVIEW that establishes elevated VZV risk in the immunocompromised host generally, but does NOT provide verbatim-grounded evidence for the SPECIFIC subgroup the claim asserts (children on cancer/rheumatology therapy). The self-consistency vote was non-adjacent multimodal, so the panel ABSTAINS rather than guess — recorded as an abstention, not scored as wrong.</dd>\n</dl>\n<p><strong>Adversarial trace.</strong></p>\n<p class=\"gloss\">Supporter — best supporting span:</p>\n<blockquote>The immunocompromised host is at increased risk of severe and disseminated VZV disease</blockquote>\n<p class=\"gloss\">Supports elevated risk in the immunocompromised host in general.</p>\n<p class=\"gloss\">Refuter — strongest objection:</p>\n<blockquote>The relative contributions of specific immunosuppressive regimens, underlying disease, and age to reactivation risk remain incompletely defined</blockquote>\n<p class=\"gloss\">The review explicitly says the subgroup-specific contributions are incompletely defined — it does not substantiate the claim&#x27;s specific pediatric-cancer/rheumatology comparison.</p>\n</section>\n<h2>Axes flagged unverifiable (not fabricated)</h2>\n<ul>\n<li><strong>dose</strong> — No dose asserted in the claim; not applicable.</li>\n<li><strong>effect_direction</strong> — Whether the claim&#x27;s effect direction matches the cited paper&#x27;s reported result requires reading the Results text; no structured field. Deferred to the adjudication agent.</li>\n</ul>\n<h2>Grounding evidence (structured, metadata-grounded)</h2>\n<ul>\n<li><strong>Retraction status:</strong> NONE_FOUND (source agreement: agree)\n</li>\n<li><strong>Organism MeSH (tree B*):</strong> Humans [B01.050.150.900.649.313.988.400.112.400.400], Animals [B01.050] | Humans present: True</li>\n<li><strong>Population MeSH (tree M01.060*):</strong> (none)</li>\n<li><strong>Sex check-tags:</strong> (none)</li>\n</ul>\n<h2>Claim scope parse (C3-lite — explicit lexical markers)</h2>\n<ul>\n<li>Asserted organism: <strong>Humans</strong> (provenance: model-inferred (claim scope), tier: medium); evidence: [&#x27;children receiving therapy&#x27;]</li>\n<li>Asserted population: (none); evidence: (none)</li>\n<li>Dose stated in claim: False</li>\n</ul>\n<h2>Provenance legend</h2>\n<dl class=\"legend\">\n<dt>metadata-grounded</dt><dd>read from a structured record (Retraction Watch, MeSH tags + tree numbers, NCBI linkage). Authoritative.</dd>\n<dt>text-grounded</dt><dd>an explicit lexical marker in the claim wording.</dd>\n<dt>model-inferred</dt><dd>a model judgement — the C3 claim-scope hint plus the graded substantive-support axis, produced by the adversarial supporter/refuter/critic agent with calibration.</dd>\n<dt>stub-not-adjudicated</dt><dd>deliberately not decided in the thin slice.</dd>\n</dl>\n<p class=\"override\">Metadata (grounded) always overrides model/text on objective axes — a conflict is scored as the model being wrong, not the record.</p>\n</main>\n</body></html>\n"
};

export interface Fixture {
  /** stable key for routing / lookup */
  key: 'retraction' | 'scope_mismatch' | 'graded_overreach' | 'abstention';
  run_id: string;
  /** one-line 'why this case matters' headline */
  title: string;
  /** 1–2 sentence explanation of what the system caught */
  caption: string;
  /** which axis is the hero of this fixture */
  axisFocus: string;
  /** one-click demo preset: prefill the input form with this cited paper + mode */
  preset: { claim: string; paper_ref: string; mode: RunMode };
  result: RunResult;
}

export const FIXTURES: Fixture[] = [
  {
    key: "retraction",
    run_id: FIXTURE_RETRACTION.run_id,
    title: "Caught a citation to a RETRACTED paper",
    caption: "The cited SCIPIO trial was retracted (Retraction Watch record 20119) \u2014 the metadata gate overrides the model and flags the citation, no matter how well the text reads.",
    axisFocus: "retraction",
    preset: {
      claim: "Exogenous c-kit+ cells are currently being used to treat post-MI heart failure patients, and early results have shown small, albeit significant functional improvements in the heart 24.",
      paper_ref: "22088800",
      mode: "pmid",
    },
    result: FIXTURE_RETRACTION,
  },
  {
    key: "scope_mismatch",
    run_id: FIXTURE_SCOPE_MISMATCH.run_id,
    title: "Caught a species scope mismatch (mouse \u2192 human)",
    caption: "The cited paper is mouse-only (MeSH: Animals, Mice, no Humans); the claim asserts human 'clinical benefits'. The substance is fully supported IN MICE \u2014 scope over-reach is held on its own axis.",
    axisFocus: "species_scope",
    preset: {
      claim: "Resveratrol has shown promising clinical benefits as anti-aging [60], anti-inflammatory [61], anti-diabetic [62], anti-viral [63], anti-neoplastic [64], and anti-CVD agents [65].",
      paper_ref: "17086191",
      mode: "pmid",
    },
    result: FIXTURE_SCOPE_MISMATCH,
  },
  {
    key: "graded_overreach",
    run_id: FIXTURE_GRADED_OVERREACH.run_id,
    title: "Graded a substantive over-reach (with honest LOW confidence)",
    caption: "The source affirms an obesity\u2013asthma link but its direct allergy markers run the other way. The panel oscillated between two adjacent grades (agreement 0.57 over 7 rounds) and reports the grade at LOW confidence.",
    axisFocus: "substantive_support",
    preset: {
      claim: "Remarkably, recent epidemiological data exhibit an increased association of obesity and allergy [200,201,202,203].",
      paper_ref: "19725894",
      mode: "pmid",
    },
    result: FIXTURE_GRADED_OVERREACH,
  },
  {
    key: "abstention",
    run_id: FIXTURE_ABSTENTION.run_id,
    title: "Abstained rather than guess (NOT_ENOUGH_INFO)",
    caption: "The cited review can't verbatim-ground the claim's specific pediatric-cancer subgroup; the vote was non-adjacent multimodal, so the panel abstains \u2014 recorded as an abstention, never scored as wrong.",
    axisFocus: "substantive_support",
    preset: {
      claim: "VZV reactivation is more common in highly immunosuppressed children who are receiving therapy for cancer or rheumatological diseases 202.",
      paper_ref: "2832088",
      mode: "pmid",
    },
    result: FIXTURE_ABSTENTION,
  },
];

/** RunResult lookup by run_id — the mock's GET /api/runs/{id} + the showcase gallery. */
export const FIXTURE_BY_RUN_ID: Record<string, RunResult> = Object.fromEntries(
  FIXTURES.map((f) => [f.run_id, f.result]),
);

/** The cached RunResult[] served by GET /api/showcase (no key needed). */
export const SHOWCASE_RUNS: RunResult[] = FIXTURES.map((f) => f.result);
