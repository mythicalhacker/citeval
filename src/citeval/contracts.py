"""Frozen data contracts for the citation-verification pipeline.

These dataclasses ARE the component interfaces. Independent workers build against
them; the thin slice and the depth build share them unchanged. Keep field names
stable — they are the parallelization seam.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Optional

# Provenance is intentionally a str (not a strict enum) so composite labels like
# "metadata-grounded (cited) + text-grounded (claim)" are representable. Canonical
# atoms: "metadata-grounded", "text-grounded", "model-inferred", "stub-not-adjudicated".
Provenance = str
Tier = str  # "high" | "medium" | "low"


@dataclass
class CitedIdentifier:
    type: str          # "pmid" | "doi"
    value: str


@dataclass
class ClaimUnit:
    atomic_claim: str
    cited_identifier: CitedIdentifier
    citing_source: Optional[dict] = None   # provenance of the citing paper, if known


@dataclass
class MeshTag:
    descriptor: str
    ui: str
    tree_numbers: list[str] = field(default_factory=list)
    major_topic: bool = False


@dataclass
class RetractionWatchHit:
    present: bool
    rw_record_id: Optional[str] = None
    reason: Optional[str] = None
    date: Optional[str] = None


@dataclass
class CommentsCorrection:
    ref_type: str                     # e.g. RetractionIn, ExpressionOfConcernIn, CommentIn
    pmid: Optional[str] = None
    source: Optional[str] = None


@dataclass
class RetractionInfo:
    status: str                       # RETRACTED | EXPRESSION_OF_CONCERN | NONE_FOUND
    retraction_watch: Optional[RetractionWatchHit] = None
    ncbi_publication_type_flag: bool = False
    comments_corrections: list[CommentsCorrection] = field(default_factory=list)
    source_agreement: str = "none"    # agree | rw_only | ncbi_only | none
    provenance: Provenance = "metadata-grounded"


@dataclass
class GroundedRecord:
    identifier: CitedIdentifier
    title: str
    abstract: str
    mesh_all: list[str]
    organism_tags: list[MeshTag]
    population_tags: list[MeshTag]
    sex_tags: list[MeshTag]
    publication_types: list[str]
    retraction: RetractionInfo
    has_humans: bool
    provenance: dict = field(default_factory=dict)
    grounding_errors: list[str] = field(default_factory=list)


@dataclass
class ScopeFrame:
    organism: Optional[str]                       # "Humans", "Mice", ... or None
    organism_evidence: list[str] = field(default_factory=list)
    population: Optional[str] = None
    population_evidence: list[str] = field(default_factory=list)
    effect: Optional[str] = None
    dose_stated: bool = False
    provenance: Provenance = "model-inferred"
    tier: Tier = "low"
    # NOTE: `direction` (asserted effect direction) is a PLANNED field, deferred until C4's
    # refuter consumes it — added then in one coordinated contract bump. Do not add it now.


@dataclass
class AxisFinding:
    axis: str                                     # retraction | species_scope | population_scope | substantive_support
    verdict: str
    tier: Tier
    provenance: Provenance
    detail: str
    evidence: dict = field(default_factory=dict)


@dataclass
class Verdict:
    claim: str
    cited_identifier: CitedIdentifier
    overall: str
    axis_findings: list[AxisFinding] = field(default_factory=list)
    unverifiable_axes: dict = field(default_factory=dict)
    stub: bool = True
    notes: list[str] = field(default_factory=list)


def to_jsonable(obj: Any) -> Any:
    """Recursively convert contract dataclasses to JSON-serializable structures."""
    from dataclasses import is_dataclass
    if is_dataclass(obj):
        return {k: to_jsonable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]
    return obj
