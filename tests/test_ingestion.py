"""Unit tests for C1 ingestion (src/citeval/ingestion.py).

Every acceptance criterion in design/worker_orders/WO-C1_ingestion_extraction.md is
covered, plus the compound-split behavior and the verbatim-guard invariant. All network
entry points are mocked — nothing here touches NCBI/Crossref, so it is CI-safe.

Run from the repo root:

    python -m unittest discover -s tests
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
import urllib.parse
from pathlib import Path
from unittest import mock

# Put src/ on the path so `citeval` imports like it does inside the package.
_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "src"))

from citeval import ingestion                              # noqa: E402
from citeval.contracts import CitedIdentifier, ClaimUnit   # noqa: E402

# The A01 claim, verbatim including its trailing citation marker "24" (the <xref> text).
A01_SENTENCE = ("Exogenous c-kit+ cells are currently being used to treat post-MI heart "
                "failure patients, and early results have shown small, albeit significant "
                "functional improvements in the heart 24.")

# Minimal JATS shaped like an EFetch db=pmc article: a <body> with citing sentences and a
# <ref-list> whose <ref>s carry (or lack) <pub-id> linkage.
#   B24 -> pmid 22088800 (+doi)   B60 -> pmid 17086191   B99 -> no pub-id (unbindable)
FIXTURE_JATS = (
    "<pmc-articleset><article>"
    "<body>"
    "<sec><p>Exogenous c-kit+ cells are currently being used to treat post-MI heart "
    "failure patients, and early results have shown small, albeit significant functional "
    'improvements in the heart <xref ref-type="bibr" rid="B24">24</xref>.</p>'
    "<p>Both SCIPIO and the resveratrol study reported improvements "
    '<xref ref-type="bibr" rid="B24">24</xref>, <xref ref-type="bibr" rid="B60">60</xref>.</p>'
    "<p>This background statement cites only an untracked source "
    '<xref ref-type="bibr" rid="B99">7</xref>.</p></sec>'
    "</body>"
    "<back><ref-list>"
    '<ref id="B24"><element-citation>'
    '<pub-id pub-id-type="pmid">22088800</pub-id>'
    '<pub-id pub-id-type="doi">10.1016/S0140-6736(11)61590-0</pub-id>'
    "</element-citation></ref>"
    '<ref id="B60"><element-citation>'
    '<pub-id pub-id-type="pmid">17086191</pub-id>'
    "</element-citation></ref>"
    '<ref id="B99"><element-citation>'
    "<article-title>An untracked reference with no identifiers</article-title>"
    "</element-citation></ref>"
    "</ref-list></back>"
    "</article></pmc-articleset>"
)


class ModeAPassthrough(unittest.TestCase):
    """AC: Mode a passthrough -> one ClaimUnit."""

    def test_passthrough_with_cited_identifier_object(self):
        units = ingestion.ingest({
            "mode": "claim_pmid",
            "claim_text": "Some claim.",
            "cited_identifier": CitedIdentifier("pmid", "22088800"),
        })
        self.assertEqual(len(units), 1)
        self.assertIsInstance(units[0], ClaimUnit)
        self.assertEqual(units[0].atomic_claim, "Some claim.")
        self.assertEqual(units[0].cited_identifier, CitedIdentifier("pmid", "22088800"))
        self.assertIsNone(units[0].citing_source)

    def test_passthrough_accepts_plain_dict_identifier(self):
        units = ingestion.ingest({
            "mode": "claim_pmid",
            "claim_text": "Some claim.",
            "cited_identifier": {"type": "doi", "value": "10.1000/xyz"},
        })
        self.assertEqual(units[0].cited_identifier, CitedIdentifier("doi", "10.1000/xyz"))


class ModeBResolution(unittest.TestCase):
    """AC: Mode b resolves at least the eval-set DOIs to the correct PMID."""

    def test_bare_doi_resolves_to_pmid(self):
        def fake_get(url, timeout=60):
            self.assertIn("esearch", url)
            term = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["term"][0]
            self.assertEqual(term, "10.1016/S0140-6736(11)61590-0[AID]")
            return json.dumps({"esearchresult": {"idlist": ["22088800"]}}).encode()

        with mock.patch.object(ingestion, "_http_get", fake_get):
            units = ingestion.ingest({
                "mode": "claim_citation",
                "claim_text": "A claim.",
                "citation_string": "10.1016/S0140-6736(11)61590-0",
            })
        self.assertEqual(units[0].cited_identifier, CitedIdentifier("pmid", "22088800"))
        self.assertEqual(units[0].citing_source["resolver"], "ncbi_aid")

    def test_doi_prefix_forms_are_stripped(self):
        for cs in ("doi:10.1000/abc", "https://doi.org/10.1000/abc", "10.1000/abc"):
            self.assertEqual(ingestion._extract_doi(cs), "10.1000/abc")
        self.assertIsNone(ingestion._extract_doi("Bolli R et al. Lancet 2011;378:1847."))

    def test_bibliographic_string_routes_through_crossref(self):
        def fake_get(url, timeout=60):
            if "crossref" in url:
                q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                self.assertIn("query.bibliographic", q)
                return json.dumps(
                    {"message": {"items": [{"DOI": "10.1016/s0140-6736(11)61590-0"}]}}).encode()
            # then DOI -> PMID
            return json.dumps({"esearchresult": {"idlist": ["22088800"]}}).encode()

        with mock.patch.object(ingestion, "_http_get", fake_get):
            units = ingestion.ingest({
                "mode": "claim_citation",
                "claim_text": "A claim.",
                "citation_string": "Bolli R, et al. Cardiac stem cells (SCIPIO). Lancet. 2011.",
            })
        self.assertEqual(units[0].cited_identifier, CitedIdentifier("pmid", "22088800"))
        self.assertEqual(units[0].citing_source["resolver"], "crossref->ncbi_aid")

    def test_all_eval_set_dois_resolve_to_their_pmid(self):
        cases = json.loads((_REPO / "data" / "eval" / "eval_set.json").read_text())["cases"]
        doi_to_pmid = {c["cited_doi"]: c["cited_pmid"] for c in cases}

        def fake_get(url, timeout=60):
            term = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["term"][0]
            pmid = doi_to_pmid.get(term.replace("[AID]", ""))
            return json.dumps(
                {"esearchresult": {"idlist": [pmid] if pmid else []}}).encode()

        with mock.patch.object(ingestion, "_http_get", fake_get):
            for c in cases:
                units = ingestion.ingest({
                    "mode": "claim_citation",
                    "claim_text": c["claim_text"],
                    "citation_string": c["cited_doi"],
                })
                self.assertEqual(units[0].cited_identifier,
                                 CitedIdentifier("pmid", c["cited_pmid"]),
                                 msg=f"{c['case_id']} DOI did not resolve to its PMID")

    def test_doi_only_when_pmid_lookup_empty(self):
        def fake_get(url, timeout=60):
            return json.dumps({"esearchresult": {"idlist": []}}).encode()

        with mock.patch.object(ingestion, "_http_get", fake_get):
            units = ingestion.ingest({
                "mode": "claim_citation",
                "claim_text": "A claim.",
                "citation_string": "10.9999/not.in.pubmed",
            })
        self.assertEqual(units[0].cited_identifier, CitedIdentifier("doi", "10.9999/not.in.pubmed"))


class ModeCExtraction(unittest.TestCase):
    """AC: Mode c extracts the known sentence, links it by rid<->pub-id, guard passes."""

    def test_extracts_known_sentence_and_links_pmid_via_text(self):
        units = ingestion.ingest({"mode": "manuscript", "text": FIXTURE_JATS})
        a01 = [u for u in units if u.atomic_claim == A01_SENTENCE
               and u.cited_identifier == CitedIdentifier("pmid", "22088800")]
        self.assertEqual(len(a01), 1, "known A01 sentence not extracted/linked exactly once")
        self.assertEqual(a01[0].citing_source["rid"], "B24")
        self.assertEqual(a01[0].citing_source["source"], "jats_text")

    def test_every_emitted_claim_passes_the_verbatim_guard(self):
        root = ingestion._load_jats_root({"text": FIXTURE_JATS})
        body = ingestion.body_text_of(root)
        units = ingestion.ingest({"mode": "manuscript", "text": FIXTURE_JATS})
        self.assertTrue(units)
        for u in units:
            self.assertTrue(ingestion.verbatim_ok(u.atomic_claim, body),
                            msg=f"emitted a non-verbatim claim: {u.atomic_claim!r}")
            # stricter than the guard: the STORED claim must itself be a literal substring
            # of the normalized body (catches internal-whitespace artifacts the guard's
            # re-normalization would otherwise mask).
            self.assertIn(u.atomic_claim, body,
                          msg=f"stored claim not a literal substring of body: {u.atomic_claim!r}")

    def test_compound_sentence_splits_by_distinct_cited_id(self):
        units = ingestion.ingest({"mode": "manuscript", "text": FIXTURE_JATS})
        compound = [u for u in units if u.atomic_claim.startswith("Both SCIPIO")]
        self.assertEqual(len(compound), 2, "co-citing sentence must yield one unit per cited paper")
        self.assertEqual({u.cited_identifier.value for u in compound}, {"22088800", "17086191"})
        # same verbatim sentence on both, and each records the full co-cite set
        self.assertEqual({u.atomic_claim for u in compound}, {compound[0].atomic_claim})
        for u in compound:
            self.assertEqual(len(u.citing_source["co_cited"]), 2)

    def test_reference_without_pubid_yields_no_pair(self):
        units = ingestion.ingest({"mode": "manuscript", "text": FIXTURE_JATS})
        self.assertFalse([u for u in units if u.atomic_claim.startswith("This background")],
                         "a ref with no <pub-id> is unbindable and must not produce a claim")
        # exactly: p1 -> 1, p2 -> 2, p3 -> 0
        self.assertEqual(len(units), 3)

    def test_pmcid_path_fetches_and_extracts(self):
        with mock.patch.object(ingestion, "efetch_pmc_xml_cached",
                               return_value=FIXTURE_JATS.encode()) as fetch:
            units = ingestion.ingest({"mode": "manuscript", "pmcid": "PMC4127035"})
        fetch.assert_called_once_with("PMC4127035")
        a01 = [u for u in units if u.atomic_claim == A01_SENTENCE]
        self.assertEqual(len(a01), 1)
        self.assertEqual(a01[0].citing_source["source"], "jats_efetch")
        self.assertEqual(a01[0].citing_source["pmcid"], "PMC4127035")

    def test_jats_path_input(self):
        with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False) as fh:
            fh.write(FIXTURE_JATS)
            path = fh.name
        try:
            units = ingestion.ingest({"mode": "manuscript", "jats_path": path})
        finally:
            Path(path).unlink()
        a01 = [u for u in units if u.atomic_claim == A01_SENTENCE]
        self.assertEqual(len(a01), 1)
        self.assertEqual(a01[0].citing_source["source"], "jats_path")


class LinkageAndGuard(unittest.TestCase):
    """Behavior: linkage is by <pub-id>, not proximity; the guard rejects fabrication."""

    def setUp(self):
        self.root = ingestion._load_jats_root({"text": FIXTURE_JATS})

    def test_find_rids_matches_by_pmid(self):
        self.assertEqual(ingestion.find_rids_for_source(self.root, target_pmid="22088800"), {"B24"})
        self.assertEqual(ingestion.find_rids_for_source(self.root, target_pmid="17086191"), {"B60"})

    def test_find_rids_matches_by_doi_case_insensitive(self):
        self.assertEqual(
            ingestion.find_rids_for_source(self.root, target_doi="10.1016/s0140-6736(11)61590-0"),
            {"B24"})

    def test_find_rids_no_false_match(self):
        self.assertEqual(ingestion.find_rids_for_source(self.root, target_pmid="99999999"), set())

    def test_verbatim_guard_rejects_non_substring(self):
        body = ingestion.body_text_of(self.root)
        self.assertTrue(ingestion.verbatim_ok(A01_SENTENCE, body))
        self.assertFalse(ingestion.verbatim_ok("This claim was never written in the paper.", body))

    def test_clean_display_is_the_safe_variant(self):
        # strips bracket/paren numeric markers ...
        self.assertEqual(
            ingestion.clean_display("X inhibits growth [60], and Y improves survival (97)."),
            "X inhibits growth, and Y improves survival.")
        # ... but never word-glued digits (would corrupt gene names like NUF2)
        self.assertEqual(ingestion.clean_display("knocked down NUF2 by siRNA"),
                         "knocked down NUF2 by siRNA")


class NoLiveNetwork(unittest.TestCase):
    """Invariant #6 / CI safety: modes without a citing paper never hit the network,
    and the ones that do route through the single _http_get seam."""

    def test_offline_modes_never_call_http_get(self):
        def explode(url, timeout=60):
            raise AssertionError(f"unexpected network call: {url}")

        with mock.patch.object(ingestion, "_http_get", explode):
            # mode a and manuscript(text) are fully offline
            self.assertEqual(len(ingestion.ingest({
                "mode": "claim_pmid", "claim_text": "c",
                "cited_identifier": {"type": "pmid", "value": "1"}})), 1)
            self.assertTrue(ingestion.ingest({"mode": "manuscript", "text": FIXTURE_JATS}))
            # mode b DOES depend on the seam (proves it isn't bypassing it)
            with self.assertRaises(AssertionError):
                ingestion.ingest({"mode": "claim_citation", "claim_text": "c",
                                  "citation_string": "10.1/x"})

    def test_efetch_requests_raw_jats_db_pmc(self):
        captured = {}

        def fake_get(url, timeout=60):
            captured["url"] = url
            return FIXTURE_JATS.encode()

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(ingestion, "_CACHE_DIR", Path(tmp)), \
                    mock.patch.object(ingestion, "_http_get", fake_get):
                data = ingestion.efetch_pmc_xml_cached("PMC4127035")
                self.assertEqual(data, FIXTURE_JATS.encode())
                self.assertTrue((Path(tmp) / "4127035.xml").exists())
        self.assertIn("efetch.fcgi", captured["url"])
        self.assertIn("db=pmc", captured["url"])


def _one_ref_doc(body_p: str, rid: str = "R1", pmid: str = "111") -> str:
    return (f"<article><body><sec>{body_p}</sec></body>"
            f'<back><ref-list><ref id="{rid}"><element-citation>'
            f'<pub-id pub-id-type="pmid">{pmid}</pub-id>'
            f"</element-citation></ref></ref-list></back></article>")


class ReviewRegressions(unittest.TestCase):
    """Regression tests for the six defects found by the adversarial review — each fails
    on the pre-fix code and passes after. Inputs are edge-case JATS the original fixture
    (flat <sec><p>, plain xref labels, no entities, single article) never exercised."""

    def test_nested_p_is_not_double_counted(self):
        # A citing <p> inside a <fig><caption> is its own paragraph; it must be emitted
        # once, not once by the caption's iteration AND again by the ancestor <p>'s render.
        doc = ("<article><body><sec>"
               "<p>The compound reduced tumor size in mice "
               '<xref ref-type="bibr" rid="R1">1</xref>.'
               "<fig><caption><p>Overexpression increased proliferation "
               '<xref ref-type="bibr" rid="R2">2</xref>.</p></caption></fig></p>'
               "</sec></body>"
               '<back><ref-list>'
               '<ref id="R1"><element-citation><pub-id pub-id-type="pmid">111</pub-id></element-citation></ref>'
               '<ref id="R2"><element-citation><pub-id pub-id-type="pmid">222</pub-id></element-citation></ref>'
               "</ref-list></back></article>")
        units = ingestion.ingest({"mode": "manuscript", "text": doc})
        by_pmid = [u.cited_identifier.value for u in units]
        self.assertEqual(by_pmid.count("222"), 1, "nested caption sentence double-counted")
        self.assertEqual(by_pmid.count("111"), 1)
        self.assertEqual(len(units), 2)

    def test_nested_p_via_list_item_not_double_counted(self):
        doc = _one_ref_doc(
            "<p>Intro sentence with no cite. "
            "<list><list-item><p>The engineered cells restored function "
            '<xref ref-type="bibr" rid="R1">1</xref>.</p></list-item></list></p>')
        units = ingestion.ingest({"mode": "manuscript", "text": doc})
        self.assertEqual(len(units), 1, "list-item <p> nested in a <p> was double-counted")

    def test_abbreviation_does_not_truncate_the_claim(self):
        # "Fig. 2" must not split the sentence and drop the species qualifier "in mice".
        doc = _one_ref_doc("<p>As demonstrated in mice in Fig. 2, the compound reduced "
                           'tumor size <xref ref-type="bibr" rid="R1">1</xref>.</p>')
        units = ingestion.ingest({"mode": "manuscript", "text": doc})
        self.assertEqual(len(units), 1)
        self.assertTrue(units[0].atomic_claim.startswith("As demonstrated in mice in Fig. 2"),
                        msg=f"claim was truncated at the abbreviation: {units[0].atomic_claim!r}")
        self.assertIn("in mice", units[0].atomic_claim)

    def test_et_al_abbreviation_does_not_truncate(self):
        doc = _one_ref_doc("<p>Smith et al. Reported a reduced tumor burden "
                           '<xref ref-type="bibr" rid="R1">1</xref>.</p>')
        units = ingestion.ingest({"mode": "manuscript", "text": doc})
        self.assertEqual(len(units), 1)
        self.assertTrue(units[0].atomic_claim.startswith("Smith et al. Reported"),
                        msg=units[0].atomic_claim)

    def test_empty_xref_leaves_no_internal_double_space(self):
        doc = _one_ref_doc('<p>The effect was significant <xref ref-type="bibr" '
                           'rid="R1"></xref> in the trial.</p>')
        root = ingestion._load_jats_root({"text": doc})
        body = ingestion.body_text_of(root)
        units = ingestion.ingest({"mode": "manuscript", "text": doc})
        self.assertEqual(len(units), 1)
        self.assertNotIn("  ", units[0].atomic_claim)
        self.assertIn(units[0].atomic_claim, body)   # literal substring, invariant #5

    def test_marked_up_xref_label_is_not_dropped(self):
        # <sup>-wrapped citation label: the sentence must still extract (not fail the guard).
        doc = _one_ref_doc('<p>This mechanism is well established '
                           '<xref ref-type="bibr" rid="R1"><sup>24</sup></xref>.</p>')
        units = ingestion.ingest({"mode": "manuscript", "text": doc})
        self.assertEqual(len(units), 1, "sentence with a <sup> citation label was dropped")
        self.assertEqual(units[0].atomic_claim, "This mechanism is well established 24.")

    def test_subarticle_ref_does_not_clobber_main_binding(self):
        # A peer-review <sub-article> reuses rid B1 for a DIFFERENT paper; the main-body
        # citation must still bind to the main article's B1.
        doc = ("<article>"
               "<body><sec><p>Main body claim about cardiac cells "
               '<xref ref-type="bibr" rid="B1">1</xref>.</p></sec></body>'
               '<back><ref-list><ref id="B1"><element-citation>'
               '<pub-id pub-id-type="pmid">22088800</pub-id></element-citation></ref></ref-list></back>'
               '<sub-article article-type="peer-review">'
               "<body><sec><p>A reviewer comment.</p></sec></body>"
               '<back><ref-list><ref id="B1"><element-citation>'
               '<pub-id pub-id-type="pmid">99999999</pub-id></element-citation></ref></ref-list></back>'
               "</sub-article></article>")
        units = ingestion.ingest({"mode": "manuscript", "text": doc})
        self.assertEqual(len(units), 1)
        self.assertEqual(units[0].cited_identifier, CitedIdentifier("pmid", "22088800"))

    def test_named_entities_parse_and_extract(self):
        doc = _one_ref_doc("<p>The &beta;-cells improved survival &mdash; a strong effect "
                           '<xref ref-type="bibr" rid="R1">1</xref>.</p>')
        units = ingestion.ingest({"mode": "manuscript", "text": doc})
        self.assertEqual(len(units), 1)
        self.assertIn("β", units[0].atomic_claim)   # &beta; -> β
        self.assertIn("—", units[0].atomic_claim)   # &mdash; -> em dash

    def test_undefined_entity_raises_clear_error(self):
        doc = _one_ref_doc('<p>Uses an &nonsenseent; entity '
                           '<xref ref-type="bibr" rid="R1">1</xref>.</p>')
        with self.assertRaises(ValueError):
            ingestion.ingest({"mode": "manuscript", "text": doc})


class Dispatch(unittest.TestCase):
    def test_unknown_mode_raises(self):
        with self.assertRaises(ValueError):
            ingestion.ingest({"mode": "nope"})

    def test_manuscript_requires_a_source(self):
        with self.assertRaises(ValueError):
            ingestion.ingest({"mode": "manuscript"})


if __name__ == "__main__":
    unittest.main()
