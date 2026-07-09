"""Build a lightweight Retraction Watch lookup index from the parquet.

Decouples runtime grounding from pyarrow/pandas: emits JSON maps keyed by
original-paper PMID and DOI. Run once:

    python -m citeval.build_rw_index
"""
from __future__ import annotations

import json
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
PARQUET = WORKSPACE / "data" / "retraction_watch" / "retraction_candidates.parquet"
DATA_DIR = Path(__file__).resolve().parent / "data"


def build() -> tuple[int, int]:
    import pandas as pd  # only needed at build time
    df = pd.read_parquet(PARQUET)
    df["orig_pmid"] = df["orig_pmid"].astype(str)
    by_pmid: dict[str, dict] = {}
    by_doi: dict[str, dict] = {}
    for _, r in df.iterrows():
        rec = {
            "rw_record_id": str(r.get("rw_record_id", "")),
            "reason": str(r.get("reasons_joined", "") or r.get("reason_raw", "")),
            "date": str(r.get("retraction_date", "")),
            "orig_doi": str(r.get("orig_doi", "") or ""),
            "title": str(r.get("title", "") or ""),
        }
        pmid = rec_pmid = str(r["orig_pmid"]).strip()
        if pmid and pmid.lower() != "nan":
            by_pmid.setdefault(pmid, rec)
        doi = (rec["orig_doi"] or "").strip().lower()
        if doi and doi != "nan":
            by_doi.setdefault(doi, rec)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "rw_index_pmid.json").write_text(json.dumps(by_pmid))
    (DATA_DIR / "rw_index_doi.json").write_text(json.dumps(by_doi))
    return len(by_pmid), len(by_doi)


if __name__ == "__main__":
    n_pmid, n_doi = build()
    print(f"Retraction Watch index built: {n_pmid} PMIDs, {n_doi} DOIs -> {DATA_DIR}")
