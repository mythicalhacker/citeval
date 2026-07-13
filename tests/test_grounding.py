"""Unit tests for C2 grounding — PMC full-text extraction (WO-C4 full-text grounding, Part A).

Stdlib `unittest` only; NO network — the PMC fetch is mocked and the JATS parsing/budgeting are
pure functions exercised on hand-built JATS XML. Run:

    python -m unittest discover -s tests
"""
from __future__ import annotations

import http.client
import pathlib
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import xml.etree.ElementTree as ET
from unittest import mock

_SRC = pathlib.Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from citeval import grounding as G

# A minimal but realistic PMC JATS article: IMRaD sections + a reference list to be dropped, plus
# an inline <sub> to prove inline markup is NOT space-separated (gene-name safety).
JATS_WITH_BODY = (
    "<pmc-articleset><article>"
    "<front><article-meta>"
    '<article-id pub-id-type="pmid">111</article-id>'
    '<article-id pub-id-type="pmc">999</article-id>'
    "</article-meta></front>"
    "<body>"
    "<sec><title>Introduction</title><p>Background on the topic.</p></sec>"
    "<sec><title>Results</title><p>The treatment increased survival by 40% in the cohort. "
    "Expression of NUF<sub>2</sub> was unchanged.</p></sec>"
    "<sec><title>Discussion</title><p>These findings suggest a clinical benefit.</p></sec>"
    "<sec><title>Conclusions</title><p>We conclude the intervention helps.</p></sec>"
    '<ref-list><ref id="r1"><mixed-citation>Smith et al. THIS_IS_A_REFERENCE 2020.</mixed-citation>'
    "</ref></ref-list>"
    "</body>"
    "</article></pmc-articleset>"
)

# An abstract-only PMC record (front matter present, NO <body>) — the honest-empty path.
JATS_NO_BODY = (
    "<pmc-articleset><article><front><article-meta>"
    '<article-id pub-id-type="pmc">888</article-id>'
    "<abstract><p>Only an abstract here.</p></abstract>"
    "</article-meta></front></article></pmc-articleset>"
)

# Europe PMC's fullTextXML commonly tags the id as pub-id-type="pmcid" (vs NCBI's "pmc") — exercise
# that the provenance still resolves to ":PMC…" from the SD-09 fallback source.
JATS_PMCID_TYPE = (
    "<pmc-articleset><article><front><article-meta>"
    '<article-id pub-id-type="pmcid">PMC777</article-id>'
    "</article-meta></front>"
    "<body><sec><title>Results</title><p>The drug cut mortality by 30%.</p></sec></body>"
    "</article></pmc-articleset>"
)

# A body-bearing JATS with NO article-id at all → the bare-provenance branch (label with no :PMCID).
JATS_BODY_NO_ID = (
    "<pmc-articleset><article>"
    "<body><sec><title>Results</title><p>The drug cut mortality by 30%.</p></sec></body>"
    "</article></pmc-articleset>"
)


class JatsExtractionTests(unittest.TestCase):
    def test_body_sections_and_reflist_dropped(self):
        root = ET.fromstring(JATS_WITH_BODY)
        body, sections = G._jats_body_sections(root)
        titles = [t for t, _ in sections]
        self.assertEqual(titles, ["Introduction", "Results", "Discussion", "Conclusions"])
        # Reference list content is dropped from the body (WO §3).
        self.assertNotIn("THIS_IS_A_REFERENCE", body)
        # Block elements are separated; the section title does not glue to its paragraph.
        self.assertIn("Results The treatment increased survival by 40%", body)
        # Inline markup stays glued — gene name NUF2 is not corrupted to "NUF 2".
        self.assertIn("NUF2", body)

    def test_no_body_returns_empty(self):
        root = ET.fromstring(JATS_NO_BODY)
        body, sections = G._jats_body_sections(root)
        self.assertEqual(body, "")
        self.assertEqual(sections, [])

    def test_pmcid_from_xml(self):
        self.assertEqual(G._pmcid_from_xml(ET.fromstring(JATS_WITH_BODY)), "PMC999")
        self.assertEqual(G._pmcid_from_xml(ET.fromstring(JATS_NO_BODY)), "PMC888")


class BudgetSelectionTests(unittest.TestCase):
    def test_abstract_prepended_and_priority_sections_chosen(self):
        root = ET.fromstring(JATS_WITH_BODY)
        body, sections = G._jats_body_sections(root)
        out = G.select_budgeted_fulltext(sections, body, "ABSTRACT SENTENCE.", budget=10000)
        self.assertTrue(out.startswith("ABSTRACT SENTENCE."))     # abstract always first
        self.assertIn("increased survival by 40%", out)           # Results (priority)
        self.assertIn("suggest a clinical benefit", out)          # Discussion (priority)
        self.assertIn("intervention helps", out)                  # Conclusions (priority)
        self.assertNotIn("Background on the topic", out)          # Introduction not a priority section

    def test_budget_truncates(self):
        root = ET.fromstring(JATS_WITH_BODY)
        body, sections = G._jats_body_sections(root)
        out = G.select_budgeted_fulltext(sections, body, "ABSTRACT.", budget=25)
        self.assertLessEqual(len(out), 25)
        self.assertTrue(out.startswith("ABSTRACT."))

    def test_fallback_to_leading_body_when_no_priority_sections(self):
        # A body whose only section is non-IMRaD → fall back to leading body text.
        jats = ("<pmc-articleset><article><body>"
                "<sec><title>Supplementary Material</title><p>Leading body content only.</p></sec>"
                "</body></article></pmc-articleset>")
        root = ET.fromstring(jats)
        body, sections = G._jats_body_sections(root)
        out = G.select_budgeted_fulltext(sections, body, "ABS.", budget=10000)
        self.assertIn("Leading body content only", out)


class FetchFullTextTests(unittest.TestCase):
    """The primary path is NCBI PMC EFetch JATS; the SD-09 Europe PMC fallback fires only when the
    primary yields no usable <body>. Every test mocks BOTH sources so nothing touches the network."""

    def test_neither_source_has_it_yields_empty_provenance(self):
        """Not in NCBI PMC and not in Europe PMC → ('', '') — the honest empty, never fabricated."""
        with mock.patch.object(G, "_efetch_pmc_cached", return_value=None), \
                mock.patch.object(G, "_europepmc_fulltext_cached", return_value=None):
            ft, prov = G.fetch_full_text("222", "the abstract")
        self.assertEqual(ft, "")
        self.assertEqual(prov, "")

    def test_body_present_populates_fulltext_and_provenance(self):
        """NCBI PMC has a body → primary wins and the Europe PMC fallback is never consulted."""
        with mock.patch.object(G, "_efetch_pmc_cached", return_value=JATS_WITH_BODY.encode()), \
                mock.patch.object(G, "_europepmc_fulltext_cached",
                                  side_effect=AssertionError("fallback must not run")) as ep:
            ft, prov = G.fetch_full_text("111", "ABS.")
        self.assertIn("increased survival by 40%", ft)
        self.assertEqual(prov, "pmc-jats:PMC999")
        self.assertFalse(ep.called)

    def test_europepmc_fallback_when_not_in_ncbi_pmc(self):
        """SD-09: not in NCBI PMC (None) but Europe PMC serves full text → fallback populates it,
        tagged with europepmc provenance so a consumer can tell which source grounded the grade."""
        with mock.patch.object(G, "_efetch_pmc_cached", return_value=None), \
                mock.patch.object(G, "_europepmc_fulltext_cached",
                                  return_value=JATS_WITH_BODY.encode()):
            ft, prov = G.fetch_full_text("222", "ABS.")
        self.assertIn("increased survival by 40%", ft)
        self.assertEqual(prov, "europepmc-jats:PMC999")

    def test_europepmc_fallback_when_ncbi_pmc_abstract_only(self):
        """SD-09: NCBI PMC record has no <body> (abstract-only) → fall back to Europe PMC full text
        rather than degrade to abstract-only."""
        with mock.patch.object(G, "_efetch_pmc_cached", return_value=JATS_NO_BODY.encode()), \
                mock.patch.object(G, "_europepmc_fulltext_cached",
                                  return_value=JATS_WITH_BODY.encode()):
            ft, prov = G.fetch_full_text("333", "ABS.")
        self.assertIn("increased survival by 40%", ft)
        self.assertEqual(prov, "europepmc-jats:PMC999")

    def test_fallback_also_empty_yields_honest_empty(self):
        """Abstract-only in NCBI PMC AND Europe PMC has none → still the honest empty value."""
        with mock.patch.object(G, "_efetch_pmc_cached", return_value=JATS_NO_BODY.encode()), \
                mock.patch.object(G, "_europepmc_fulltext_cached", return_value=None):
            ft, prov = G.fetch_full_text("333", "ABS.")
        self.assertEqual((ft, prov), ("", ""))

    def test_fetch_never_raises_on_bad_xml_then_falls_back(self):
        """A garbled primary XML is recorded and the fallback still runs; when the fallback also has
        nothing the result is the honest empty — and the parse error names the primary source."""
        with mock.patch.object(G, "_efetch_pmc_cached", return_value=b"<not-valid-xml"), \
                mock.patch.object(G, "_europepmc_fulltext_cached", return_value=None):
            errors: list[str] = []
            ft, prov = G.fetch_full_text("444", "ABS.", errors)
        self.assertEqual((ft, prov), ("", ""))
        self.assertTrue(any("full_text parse failed (pmc-jats)" in e for e in errors))

    def test_bad_primary_recovered_by_europepmc(self):
        """A garbled primary XML must not block the fallback: Europe PMC still yields full text."""
        with mock.patch.object(G, "_efetch_pmc_cached", return_value=b"<not-valid-xml"), \
                mock.patch.object(G, "_europepmc_fulltext_cached",
                                  return_value=JATS_WITH_BODY.encode()):
            errors: list[str] = []
            ft, prov = G.fetch_full_text("444", "ABS.", errors)
        self.assertIn("increased survival by 40%", ft)
        self.assertEqual(prov, "europepmc-jats:PMC999")

    def test_europepmc_pmcid_type_id_shape_keeps_pmcid_in_provenance(self):
        """Europe PMC's common <article-id pub-id-type="pmcid"> shape still tags the PMCID."""
        with mock.patch.object(G, "_efetch_pmc_cached", return_value=None), \
                mock.patch.object(G, "_europepmc_fulltext_cached",
                                  return_value=JATS_PMCID_TYPE.encode()):
            ft, prov = G.fetch_full_text("777", "ABS.")
        self.assertIn("cut mortality by 30%", ft)
        self.assertEqual(prov, "europepmc-jats:PMC777")

    def test_body_without_article_id_yields_bare_provenance(self):
        """Full text with no article-id → provenance is the bare source label (no ':PMCID'), and the
        honest full text is still returned (invariant #6 body is what matters, not the id)."""
        with mock.patch.object(G, "_efetch_pmc_cached", return_value=None), \
                mock.patch.object(G, "_europepmc_fulltext_cached",
                                  return_value=JATS_BODY_NO_ID.encode()):
            ft, prov = G.fetch_full_text("888", "ABS.")
        self.assertIn("cut mortality by 30%", ft)
        self.assertEqual(prov, "europepmc-jats")


class EuropePmcFallbackTests(unittest.TestCase):
    """The SD-09 helpers in isolation: PMID→PMCID resolution and the disk-cached fullTextXML fetch.
    Every network call (`_get`) is injected, so these never touch the wire."""

    _SEARCH_HIT = b'{"resultList":{"result":[{"pmid":"555","inEPMC":"Y","pmcid":"PMC12345"}]}}'

    def test_resolver_returns_pmcid_on_in_epmc_hit(self):
        with mock.patch.object(G, "_get", return_value=self._SEARCH_HIT):
            self.assertEqual(G._europepmc_pmcid("555"), "PMC12345")

    def test_resolver_none_when_not_in_epmc(self):
        body = b'{"resultList":{"result":[{"pmid":"555","inEPMC":"N","pmcid":"PMC12345"}]}}'
        with mock.patch.object(G, "_get", return_value=body):
            self.assertIsNone(G._europepmc_pmcid("555"))

    def test_resolver_none_on_pmid_mismatch(self):
        body = b'{"resultList":{"result":[{"pmid":"999","inEPMC":"Y","pmcid":"PMC1"}]}}'
        with mock.patch.object(G, "_get", return_value=body):
            self.assertIsNone(G._europepmc_pmcid("555"))

    def test_resolver_prefixes_bare_pmcid(self):
        body = b'{"resultList":{"result":[{"pmid":"555","inEPMC":"Y","pmcid":"12345"}]}}'
        with mock.patch.object(G, "_get", return_value=body):
            self.assertEqual(G._europepmc_pmcid("555"), "PMC12345")

    def test_resolver_swallows_network_and_json_errors(self):
        with mock.patch.object(G, "_get", side_effect=urllib.error.URLError("down")):
            self.assertIsNone(G._europepmc_pmcid("555"))
        with mock.patch.object(G, "_get", return_value=b"not json"):
            self.assertIsNone(G._europepmc_pmcid("555"))

    def test_fulltext_cached_caches_success_only(self):
        """Successful, non-empty fetches are cached by PMID; a miss (no PMCID) is never cached and
        never fetches fullTextXML."""
        with tempfile.TemporaryDirectory() as td, \
                mock.patch.object(G, "_EUROPEPMC_DIR", pathlib.Path(td)):
            # Miss: not in EPMC → None, no cache file, and fullTextXML is never requested.
            with mock.patch.object(G, "_europepmc_pmcid", return_value=None), \
                    mock.patch.object(G, "_get", side_effect=AssertionError("no fetch on a miss")):
                self.assertIsNone(G._europepmc_fulltext_cached("777"))
            self.assertEqual(list(pathlib.Path(td).glob("*.xml")), [])
            # Hit: fetched once, written to disk, then served from cache without re-fetching.
            calls = {"n": 0}

            def _once(url, **kw):
                calls["n"] += 1
                return b"<xml/>"

            with mock.patch.object(G, "_europepmc_pmcid", return_value="PMC1"), \
                    mock.patch.object(G, "_get", _once):
                self.assertEqual(G._europepmc_fulltext_cached("777"), b"<xml/>")
                self.assertEqual(G._europepmc_fulltext_cached("777"), b"<xml/>")
            self.assertEqual(calls["n"], 1)                 # 2nd call served from the disk cache
            self.assertTrue((pathlib.Path(td) / "777.xml").exists())

    def test_fulltext_cached_network_error_returns_none_uncached(self):
        with tempfile.TemporaryDirectory() as td, \
                mock.patch.object(G, "_EUROPEPMC_DIR", pathlib.Path(td)), \
                mock.patch.object(G, "_europepmc_pmcid", return_value="PMC1"), \
                mock.patch.object(G, "_get", side_effect=urllib.error.URLError("down")):
            self.assertIsNone(G._europepmc_fulltext_cached("777"))
            self.assertEqual(list(pathlib.Path(td).glob("*.xml")), [])   # a failure is never cached

    def test_fulltext_cached_empty_body_not_cached(self):
        """A 200 with an empty body is NOT a success — `if not data` returns None and never writes
        an empty file that would poison the cache forever (docstring: non-empty successes only)."""
        with tempfile.TemporaryDirectory() as td, \
                mock.patch.object(G, "_EUROPEPMC_DIR", pathlib.Path(td)), \
                mock.patch.object(G, "_europepmc_pmcid", return_value="PMC1"), \
                mock.patch.object(G, "_get", return_value=b""):
            self.assertIsNone(G._europepmc_fulltext_cached("777"))
            self.assertEqual(list(pathlib.Path(td).glob("*.xml")), [])

    def test_resolver_none_on_empty_resultlist_and_missing_keys(self):
        """No hit (empty resultList) and a result dict lacking inEPMC/pmcid both → None (never an
        indexing error, never a dead fullTextXML URL)."""
        with mock.patch.object(G, "_get", return_value=b'{"resultList":{"result":[]}}'):
            self.assertIsNone(G._europepmc_pmcid("555"))
        with mock.patch.object(G, "_get", return_value=b'{"resultList":{"result":[{"pmid":"555"}]}}'):
            self.assertIsNone(G._europepmc_pmcid("555"))
        with mock.patch.object(G, "_get", return_value=b'{}'):    # no resultList key at all
            self.assertIsNone(G._europepmc_pmcid("555"))


class ThrottleThreadSafetyTests(unittest.TestCase):
    """The NCBI throttle guards a shared timestamp; the batch orchestrator drives grounding
    concurrently, so `_throttle` must serialize under a lock and honor the global rate."""

    def test_concurrent_throttle_serializes_calls(self):
        """With a short interval, N threads released together take ~N intervals of wall time when
        serialized — and would finish in ~1 interval if the lock were missing (all sleeping at
        once). Lower-bound assertion only, so it is not timing-flaky."""
        n, interval = 4, 0.05
        with mock.patch.object(G, "_MIN_INTERVAL", interval), \
                mock.patch.object(G, "_last_call", [time.time()]):
            barrier = threading.Barrier(n)

            def worker():
                barrier.wait()                  # release all threads into _throttle together
                G._throttle()

            threads = [threading.Thread(target=worker) for _ in range(n)]
            start = time.perf_counter()
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            elapsed = time.perf_counter() - start
        self.assertGreaterEqual(elapsed, (n - 1) * interval,
                                f"throttle not serialized across threads: {elapsed:.3f}s")


class _Resp:
    """Minimal urlopen() return whose .read() yields the body (no network)."""
    def __init__(self, body: bytes = b"OK"):
        self._body = body

    def read(self):
        return self._body


class GetRetryTests(unittest.TestCase):
    """WO-C4 resilience §1: `_get` must survive a transient NCBI blip (IncompleteRead / dropped
    connection / 429 / 5xx) by retrying with backoff — one blip must not abort a long run — while a
    non-transient status (404) fails fast. `_throttle` is stubbed out and backoff_base=0 so no real
    time is spent; `urllib.request.urlopen` is injected."""

    def _run(self, urlopen_fn, **kw):
        with mock.patch.object(G, "_throttle", lambda: None), \
                mock.patch.object(G.urllib.request, "urlopen", urlopen_fn):
            return G._get("http://ncbi.example/efetch", backoff_base=0, **kw)

    def test_retries_then_succeeds_on_incomplete_read(self):
        """The exact crash reported on case 3: http.client.IncompleteRead during EFetch — retried."""
        calls = {"n": 0}

        def _flaky(req, timeout=30):
            calls["n"] += 1
            if calls["n"] == 1:
                raise http.client.IncompleteRead(b"partial")
            return _Resp(b"OK")

        self.assertEqual(self._run(_flaky), b"OK")
        self.assertEqual(calls["n"], 2)                     # failed once, retried, recovered

    def test_retries_dropped_connection_and_timeout(self):
        for exc in (urllib.error.URLError("connection reset"),
                    TimeoutError("timed out"),               # socket.timeout is TimeoutError in 3.10+
                    ConnectionResetError("peer reset")):
            calls = {"n": 0}

            def _flaky(req, timeout=30, _e=exc):
                calls["n"] += 1
                if calls["n"] == 1:
                    raise _e
                return _Resp(b"OK")

            self.assertEqual(self._run(_flaky), b"OK", f"{type(exc).__name__} should retry")
            self.assertEqual(calls["n"], 2)

    def test_retries_transient_http_statuses(self):
        for code in (429, 500, 502, 503):
            calls = {"n": 0}

            def _flaky(req, timeout=30, _c=code):
                calls["n"] += 1
                if calls["n"] == 1:
                    raise urllib.error.HTTPError("http://x", _c, "transient", {}, None)
                return _Resp(b"OK")

            self.assertEqual(self._run(_flaky), b"OK", f"HTTP {code} should retry")
            self.assertEqual(calls["n"], 2)

    def test_reraises_after_exhausting_attempts(self):
        def _always(req, timeout=30):
            raise http.client.IncompleteRead(b"")

        with self.assertRaises(http.client.IncompleteRead):
            self._run(_always, attempts=3)

    def test_fails_fast_on_non_retryable_http_error(self):
        """A 404 is not transient — retrying wastes time and rate budget, so it raises on attempt 1."""
        calls = {"n": 0}

        def _404(req, timeout=30):
            calls["n"] += 1
            raise urllib.error.HTTPError("http://x", 404, "Not Found", {}, None)

        with self.assertRaises(urllib.error.HTTPError) as cm:
            self._run(_404, attempts=4)
        cm.exception.close()                                # HTTPError is file-like — release it now
        self.assertEqual(calls["n"], 1)                     # not retried


if __name__ == "__main__":
    unittest.main(verbosity=2)
