"""citeval — grounded-and-measured citation verification.

Thin vertical slice (spine):
    C1 ingestion -> C2 grounding -> C3-lite scope -> C4-stub adjudication -> C5 report

Depth (adversarial adjudication, calibration, corpus, scorer) is layered behind the
contracts in contracts.py without changing them. See design/03_thin_slice_contracts.md.
"""

__all__ = ["contracts", "grounding", "claim_scope", "adjudicator_stub", "reporting", "slice_runner"]
