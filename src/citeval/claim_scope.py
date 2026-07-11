"""C3 — claim scope parser.

Extracts the scope the *claim itself* asserts (organism, population, effect,
dose) as a `ScopeFrame`, each populated field carrying a verbatim evidence span
from the claim plus a provenance label and a confidence tier. It states only
what the claim asserts about its own finding — it never compares against the
cited paper and never decides an objective axis (that is C4's job against C2's
metadata).

Two paths behind the same `ScopeFrame` contract:
  * `parse_claim_scope_model` — an **Opus 4.8** call (invariant #4) that reads
    explicit markers *and* reasonable implicit therapeutic/clinical scope (the
    B05 case), without over-asserting on hedged or correctly-scoped wording.
  * `parse_claim_scope_lexical` — the honest lexical fallback used offline when
    `ANTHROPIC_API_KEY` is absent, so the pipeline still runs.

`parse_claim_scope` dispatches to the model path when a key is present, else the
lexical path. A model failure degrades to lexical **with a logged warning** — a
silent downgrade would masquerade as a normal parse and violate the system's
grounded-and-measured thesis.
"""
from __future__ import annotations

import json
import logging
import os
import re

from .contracts import ScopeFrame

logger = logging.getLogger(__name__)

# Opus 4.8 on every model call (CLAUDE.md invariant #4). No cheaper/faster model.
MODEL = "claude-opus-4-8"

# --------------------------------------------------------------------------- #
# Lexical fallback (slice placeholder; kept as the no-API path).              #
# Honest by construction: asserts only what explicit wording licenses.        #
# --------------------------------------------------------------------------- #

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

# Asserted effect direction (ScopeFrame.direction; C4's refuter direction-reversal probe +
# RB1's direction test). Conservative: only set on a clear lexical marker, ordered so the
# lexical path never invents a direction the wording does not license.
DIRECTION_MARKERS = {
    "increase": [r"\bincreas\w*", r"\bimprov\w*", r"\benhanc\w*", r"\bpromot\w*", r"\bprolong\w*",
                 r"\bextend\w*", r"\belevat\w*", r"\bupregulat\w*", r"\bhigher\b", r"\bgreater\b",
                 r"\bboost\w*", r"\brais\w*", r"\bgain\w*"],
    "decrease": [r"\bdecreas\w*", r"\breduc\w*", r"\blower\w*", r"\binhibit\w*", r"\bsuppress\w*",
                 r"\battenuat\w*", r"\bimpair\w*", r"\bdownregulat\w*", r"\bdeclin\w*",
                 r"\bworsen\w*", r"\bloss\b", r"\bblock\w*", r"\bprevent\w*"],
    "no_change": [r"\bno change\b", r"\bno effect\b", r"\bno difference\b", r"\bunchanged\b",
                  r"\bnot associated\b", r"\bno significant\b", r"\bno impact\b"],
}


def _find(text: str, patterns: list[str]) -> list[str]:
    hits: list[str] = []
    for p in patterns:
        hits += [m.group(0) for m in re.finditer(p, text, re.I)]
    return hits


# A negator immediately before a directional verb reverses it ("did not improve", "failed to
# reduce", "no longer increases"). The lexical path drops such a match rather than assert the
# reversed direction (honesty rule); the model path handles negation properly.
_NEGATOR = re.compile(
    r"\b(?:no|not|n't|never|without|fail(?:s|ed|ing)?|lack(?:s|ing|ed)?|absence|cannot|can't|"
    r"no longer)\b", re.I)


def _find_unnegated(text: str, patterns: list[str], window: int = 16) -> list[str]:
    """Marker hits whose short preceding context contains no negator."""
    hits: list[str] = []
    for p in patterns:
        for m in re.finditer(p, text, re.I):
            if _NEGATOR.search(text[max(0, m.start() - window):m.start()]):
                continue
            hits.append(m.group(0))
    return hits


def _direction_lexical(atomic_claim: str) -> tuple[str | None, list[str]]:
    """Explicit-marker-only effect direction. Returns (direction, verbatim_evidence).

    `no_change` phrases win (most specific). Otherwise a direction is asserted only when
    exactly ONE of increase/decrease markers is present AND it is not negated — a mixed or
    negated claim is left None rather than guessed (honesty rule; the model path handles the
    nuanced cases)."""
    nc = _find(atomic_claim, DIRECTION_MARKERS["no_change"])
    if nc:
        return "no_change", nc
    inc = _find_unnegated(atomic_claim, DIRECTION_MARKERS["increase"])
    dec = _find_unnegated(atomic_claim, DIRECTION_MARKERS["decrease"])
    if inc and not dec:
        return "increase", inc
    if dec and not inc:
        return "decrease", dec
    return None, []


def parse_claim_scope_lexical(atomic_claim: str) -> ScopeFrame:
    """Explicit-marker-only scope hint. Never over-asserts implicit scope, so it
    misses the B05 case (asserted human relevance with no lexical marker)."""
    organism, org_ev, prov, tier = None, [], "model-inferred", "low"
    human = _find(atomic_claim, HUMAN_MARKERS)
    if human:
        organism, org_ev, prov, tier = "Humans", human, "text-grounded", "medium"
    else:
        for org, pats in ANIMAL_MARKERS.items():
            h = _find(atomic_claim, pats)
            if h:
                organism, org_ev, prov, tier = org, h, "text-grounded", "medium"
                break

    population, pop_ev = None, []
    ped, adult = _find(atomic_claim, PED_MARKERS), _find(atomic_claim, ADULT_MARKERS)
    if ped:
        population, pop_ev = "pediatric", ped
    elif adult:
        population, pop_ev = "adult", adult

    direction, dir_ev = _direction_lexical(atomic_claim)

    return ScopeFrame(
        organism=organism, organism_evidence=org_ev,
        population=population, population_evidence=pop_ev,
        effect=None, direction=direction, direction_evidence=dir_ev,
        dose_stated=bool(_find(atomic_claim, DOSE_MARKERS)),
        provenance=prov, tier=tier,
    )


# --------------------------------------------------------------------------- #
# Opus 4.8 path.                                                              #
# --------------------------------------------------------------------------- #

_TIERS = ("high", "medium", "low")
_DIRECTIONS = ("increase", "decrease", "no_change")

# Canonicalize model organism values to the vocabulary the downstream metadata
# comparison (adjudicator_stub._species_axis) matches against — an off-list or
# case-variant value ("human", "Mouse") would silently misroute the axis.
_ORGANISM_CANON = {
    "human": "Humans", "humans": "Humans", "patient": "Humans", "patients": "Humans",
    "clinical": "Humans", "people": "Humans",
    "mouse": "Mice", "mice": "Mice", "murine": "Mice",
    "rat": "Rats", "rats": "Rats",
    "rhesus": "Macaca mulatta", "macaque": "Macaca mulatta", "monkey": "Macaca mulatta",
    "monkeys": "Macaca mulatta", "non-human primate": "Macaca mulatta",
    "non-human primates": "Macaca mulatta", "macaca mulatta": "Macaca mulatta",
    "animal": "Animals", "animals": "Animals",
}

SYSTEM_PROMPT = """\
You extract the scope that a scientific CLAIM asserts, for a citation-verification \
system. You state ONLY what the claim asserts about its own finding. Return ONLY a \
JSON object, no prose and no code fences.

You are NOT judging whether the claim is correct, and you have NOT seen the cited \
paper. Do not compare against any source. Do not decide any objective axis. Report \
only the scope the claim's wording asserts.

Fields (all required):
- "organism": the species/population the claim asserts its finding APPLIES TO — one of \
"Humans", "Mice", "Rats", "Macaca mulatta", "Animals", or null. Use null when the \
claim asserts no organism scope.
- "organism_evidence": array of the EXACT words copied verbatim from the claim that \
establish the organism (e.g. "in mice", "clinical benefits"). Empty array if organism is null.
- "organism_provenance": "text-grounded" if an explicit species/human marker word is \
present ("humans", "patients", "clinical", "in mice", "rats", ...); "model-inferred" if \
the organism is inferred from an implicit relevance claim with no explicit marker; \
"none" if organism is null.
- "population": "pediatric", "adult", or null.
- "population_evidence": array of exact verbatim words for the population, else [].
- "effect": a short verbatim phrase naming the asserted effect/finding, or null.
- "direction": the asserted direction of the effect — "increase", "decrease", \
"no_change", or null when the claim asserts no clear direction. "increase" = the claim \
says something goes up / improves / is promoted / prolonged; "decrease" = goes down / is \
reduced / inhibited / suppressed / impaired; "no_change" = explicitly no effect / no \
difference.
- "direction_evidence": array of the EXACT words copied verbatim from the claim that \
establish the direction (e.g. "increased their survival", "inhibits"). Empty array if \
direction is null.
- "dose_stated": true if the claim states a dose or concentration, else false.
- "tier": your confidence — "high", "medium", or "low".
- "rationale": <= 25 words.

Scope rules:
- Explicit human/clinical markers ("humans", "patients", "clinical benefits", "human \
health") => organism "Humans", organism_provenance "text-grounded".
- IMPLICIT therapeutic/clinical relevance with NO explicit human word — e.g. "promote \
the recovery of motor function", "can be targeted for various therapeutic purposes", \
"used to treat ... patients" — asserts human/clinical scope => organism "Humans", \
organism_provenance "model-inferred". Set "tier" to "medium" when the relevance claim \
is clear, lower when weak.
- Do NOT over-assert. "in mice" => "Mice", never "Humans". A claim that only DESCRIBES \
a mechanism with no relevance claim asserts no organism => null. A HEDGED claim \
("whether this holds in humans is unknown", "may eventually translate to humans") does \
NOT assert human scope — do not report "Humans".
- When genuinely unsure whether an implicit relevance claim is present, LOWER the tier \
rather than force the call.
- Every string in the *_evidence arrays MUST be an exact substring copied verbatim from \
the claim.\
"""


def _get_client():  # pragma: no cover - thin SDK constructor
    import anthropic

    return anthropic.Anthropic()


def _extract_text(response) -> str:
    """Concatenate the text of every text block (thinking blocks carry no text)."""
    parts = []
    for block in getattr(response, "content", []) or []:
        text = getattr(block, "text", None)
        if isinstance(text, str) and text:
            parts.append(text)
    return "".join(parts)


def _extract_json(raw: str) -> dict:
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON object in model response")
    obj = json.loads(raw[start:end + 1])
    if not isinstance(obj, dict):
        raise ValueError("model JSON is not an object")
    return obj


def _norm(s: str) -> str:
    return " ".join(str(s).split())


def _as_bool(value) -> bool:
    """Coerce a model value to bool without treating the STRING 'false'/'no' as
    True (plain bool(value) would, fabricating a dose flag — invariant #3)."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("true", "yes", "1")
    if isinstance(value, (int, float)):
        return bool(value)
    return False


def _verbatim_spans(spans, atomic_claim: str) -> list[str]:
    """Keep only spans that appear verbatim in the (whitespace-normalized) claim,
    storing the claim's ACTUAL substring so the stored evidence is truly verbatim.
    Case-insensitive lookup tolerates a re-cased model echo (e.g. sentence-initial
    capitals) without a false drop; a lone string is treated as one span, not
    iterated character-by-character."""
    if isinstance(spans, str):
        spans = [spans]
    elif not isinstance(spans, list):
        return []
    nclaim = _norm(atomic_claim)
    low = nclaim.lower()
    kept: list[str] = []
    for s in spans:
        if not (isinstance(s, str) and s.strip()):
            continue
        ns = _norm(s)
        idx = low.find(ns.lower())
        if idx != -1:
            kept.append(nclaim[idx:idx + len(ns)])
    return kept


def _frame_from_model(atomic_claim: str, data: dict) -> ScopeFrame:
    organism = data.get("organism")
    organism = _ORGANISM_CANON.get(organism.strip().lower(), organism.strip()) \
        if isinstance(organism, str) and organism.strip() else None
    org_ev = _verbatim_spans(data.get("organism_evidence"), atomic_claim)
    # Honesty rule (WO): a populated scope field carries a verbatim span. If the
    # model asserts an organism but no span survives the guard, the assertion is
    # ungrounded on the claim side — drop it rather than over-assert human scope
    # with a "text-grounded" label and zero evidence.
    if organism is not None and not org_ev:
        organism = None
        org_ev = []

    population = data.get("population")
    population = population.strip().lower() \
        if isinstance(population, str) and population.strip().lower() in ("pediatric", "adult") else None
    pop_ev = _verbatim_spans(data.get("population_evidence"), atomic_claim)
    if population is not None and not pop_ev:
        population = None
        pop_ev = []

    # effect is descriptive; keep it only when it too is a verbatim claim substring.
    effect_hit = _verbatim_spans([data.get("effect")], atomic_claim) \
        if isinstance(data.get("effect"), str) else []
    effect = effect_hit[0] if effect_hit else None

    # direction is the asserted effect direction (C4's refuter direction-reversal probe).
    # Coerce to the {increase, decrease, no_change} vocabulary; same honesty rule as organism —
    # a direction with no surviving verbatim span on the claim side is ungrounded, so drop it.
    direction = data.get("direction")
    direction = direction.strip().lower() \
        if isinstance(direction, str) and direction.strip().lower() in _DIRECTIONS else None
    dir_ev = _verbatim_spans(data.get("direction_evidence"), atomic_claim)
    if direction is not None and not dir_ev:
        direction = None
        dir_ev = []

    tier = str(data.get("tier", "")).strip().lower()
    if tier not in _TIERS:
        tier = "low"

    # provenance reflects the ORGANISM determination (the claim-side field C4
    # composites against C2 metadata): text-grounded only when an explicit marker
    # licenses it, else model-inferred.
    if organism is None:
        provenance = "model-inferred"
    else:
        prov = str(data.get("organism_provenance", "")).strip().lower()
        provenance = "text-grounded" if prov == "text-grounded" else "model-inferred"

    return ScopeFrame(
        organism=organism,
        organism_evidence=org_ev,
        population=population,
        population_evidence=pop_ev,
        effect=effect,
        direction=direction,
        direction_evidence=dir_ev,
        dose_stated=_as_bool(data.get("dose_stated")),
        provenance=provenance,
        tier=tier,
    )


def parse_claim_scope_model(atomic_claim: str, *, client=None) -> ScopeFrame:
    """Opus 4.8 scope parse. Degrades to the lexical fallback on any failure
    (network, rate limit, malformed output) with a logged warning — never a
    silent downgrade. `client` is injectable so tests never hit a live API."""
    try:
        if client is None:
            client = _get_client()
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": f"CLAIM:\n{atomic_claim}"}],
        )
        data = _extract_json(_extract_text(response))
        return _frame_from_model(atomic_claim, data)
    except Exception as exc:  # noqa: BLE001 - resilience layer; must not crash the pipeline
        logger.warning(
            "claim_scope: Opus path failed (%s); falling back to lexical parse", exc
        )
        return parse_claim_scope_lexical(atomic_claim)


def parse_claim_scope(atomic_claim: str) -> ScopeFrame:
    """Dispatch: Opus 4.8 when ANTHROPIC_API_KEY is set, else the lexical fallback
    so the pipeline runs offline."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return parse_claim_scope_model(atomic_claim)
    return parse_claim_scope_lexical(atomic_claim)
