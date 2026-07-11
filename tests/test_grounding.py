"""Unit tests for C2 grounding — PMC full-text extraction (WO-C4 full-text grounding, Part A).

Stdlib `unittest` only; NO network — the PMC fetch is mocked and the JATS parsing/budgeting are
pure functions exercised on hand-built JATS XML. Run:

    python -m unittest discover -s tests
"""
from __future__ import annotations

import http.client
import pathlib
import sys
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
    def test_no_pmcid_yields_abstract_only_empty_provenance(self):
        """Not in PMC (fetch returns None) → ('', '') — the honest empty value, never fabricated."""
        with mock.patch.object(G, "_efetch_pmc_cached", return_value=None):
            ft, prov = G.fetch_full_text("222", "the abstract")
        self.assertEqual(ft, "")
        self.assertEqual(prov, "")

    def test_body_present_populates_fulltext_and_provenance(self):
        with mock.patch.object(G, "_efetch_pmc_cached", return_value=JATS_WITH_BODY.encode()):
            ft, prov = G.fetch_full_text("111", "ABS.")
        self.assertIn("increased survival by 40%", ft)
        self.assertEqual(prov, "pmc-jats:PMC999")

    def test_abstract_only_pmc_record_yields_empty(self):
        """A PMC record with no <body> is a successful fetch but still empty full text."""
        with mock.patch.object(G, "_efetch_pmc_cached", return_value=JATS_NO_BODY.encode()):
            ft, prov = G.fetch_full_text("333", "ABS.")
        self.assertEqual(ft, "")
        self.assertEqual(prov, "")

    def test_fetch_never_raises_on_bad_xml(self):
        with mock.patch.object(G, "_efetch_pmc_cached", return_value=b"<not-valid-xml"):
            errors: list[str] = []
            ft, prov = G.fetch_full_text("444", "ABS.", errors)
        self.assertEqual((ft, prov), ("", ""))
        self.assertTrue(any("full_text parse failed" in e for e in errors))


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
