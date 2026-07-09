"""C3-lite — claim scope hint from explicit lexical markers (slice placeholder).

Honest by construction: it asserts only what explicit wording licenses and labels
provenance accordingly (explicit marker -> text-grounded; otherwise model-inferred,
low tier). The full Opus-based scope frame replaces this behind the ScopeFrame
contract in the depth phase.
"""
from __future__ import annotations

import re

from .contracts import ScopeFrame

HUMAN_MARKERS = [r"\bhumans?\b", r"\bpatients?\b", r"\bclinical(?:ly)?\b",
                 r"\bhuman health\b", r"\bin people\b", r"\bin men\b", r"\bin women\b"]
ANIMAL_MARKERS = {
    "Mice": [r"\bmice\b", r"\bmurine\b", r"\bmouse\b"],
    "Rats": [r"\brats?\b"],
    "Macaca mulatta": [r"\brhesus\b", r"\bmonkeys?\b", r"\bnon-human primates?\b"],
    "Animals": [r"\banimals?\b", r"\bin vivo\b"],
}
PED_MARKERS = [r"\bchildren\b", r"\bpediatric\b", r"\bpaediatric\b", r"\binfants?\b", r"\bneonat"]
ADULT_MARKERS = [r"\badults?\b", r"\belderly\b", r"\bolder adults?\b"]
DOSE_MARKERS = [r"\bmg/kg\b", r"\bµM\b", r"\buM\b", r"\bmg\b", r"\bdoses?d?\b", r"\bµg\b", r"\bmmol\b", r"\bnmol\b"]


def _find(text: str, patterns: list[str]) -> list[str]:
    hits: list[str] = []
    for p in patterns:
        hits += [m.group(0) for m in re.finditer(p, text, re.I)]
    return hits


def parse_claim_scope(claim_text: str) -> ScopeFrame:
    organism, org_ev, prov, tier = None, [], "model-inferred", "low"
    human = _find(claim_text, HUMAN_MARKERS)
    if human:
        organism, org_ev, prov, tier = "Humans", human, "text-grounded", "medium"
    else:
        for org, pats in ANIMAL_MARKERS.items():
            h = _find(claim_text, pats)
            if h:
                organism, org_ev, prov, tier = org, h, "text-grounded", "medium"
                break

    population, pop_ev = None, []
    ped, adult = _find(claim_text, PED_MARKERS), _find(claim_text, ADULT_MARKERS)
    if ped:
        population, pop_ev = "pediatric", ped
    elif adult:
        population, pop_ev = "adult", adult

    return ScopeFrame(
        organism=organism, organism_evidence=org_ev,
        population=population, population_evidence=pop_ev,
        effect=None, dose_stated=bool(_find(claim_text, DOSE_MARKERS)),
        provenance=prov, tier=tier,
    )
