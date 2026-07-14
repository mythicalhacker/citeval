/**
 * ShowcaseView — the judge's landing page and the product's story in one scroll.
 *
 * The register is a research-integrity / decision-support console (dense, hierarchical, serious),
 * not a marketing splash. It leads with the numbers (SP-01), tells the four self-correction stories
 * the system actually produced (SP-03 "what it caught"), states the weaknesses up front rather than
 * in fine print (SP-04), and hands the judge a gallery of four cached cases (SP-05) — each rendered
 * from a real fixture, no key, no backend — that open the full Verdict view on click.
 *
 * Ownership: this file (a W2 view). It composes the W1 design system + the W0 fixtures + the shell
 * seam only; it never edits them. Every headline number is the one HEADLINE_STATS / SUBMISSION.md
 * reports, weak figures included and labelled.
 */
import type { ReactNode } from 'react';
import {
  HEADLINE_STATS,
  Stat,
  GateBadge,
  gateFiredFromOverall,
  GradeBadge,
  ConfidenceChip,
  ProvenanceBadge,
} from '../components/common';
import type { ConfKey } from '../design/tokens';
import { useShell } from '../shell/ShellContext';
import { FIXTURES, type Fixture } from '../lib/fixtures';
import type { RunResult, AxisFinding } from '../lib/types';

/* ------------------------------------------------------------------ small local layout helpers -- */

function SectionHeading({ id, eyebrow, title, children }: { id?: string; eyebrow: string; title: string; children?: ReactNode }) {
  return (
    <div className="mb-4">
      <div className="text-xs font-bold uppercase tracking-widest" style={{ color: 'var(--cv-brand)' }}>
        {eyebrow}
      </div>
      <h2 id={id} className="mt-1 text-xl font-black tracking-tight text-ink sm:text-2xl">{title}</h2>
      {children ? <p className="mt-1.5 max-w-3xl text-sm text-ink-muted">{children}</p> : null}
    </div>
  );
}

/* ---------------------------------------------------------------- fixture → hero-badge accessors -- */

/** Pull the graded substantive_support finding out of a RunResult (every fixture has one). */
function substantiveFinding(result: RunResult): AxisFinding | undefined {
  return result.verdict.verdict.axis_findings.find((a) => a.axis === 'substantive_support');
}

interface SubstantiveSummary {
  grade: string;
  tier: ConfKey;
  agreement?: number;
  nSamples?: number;
  abstained: boolean;
}

function summariseSubstantive(result: RunResult): SubstantiveSummary {
  const f = substantiveFinding(result);
  const conf = f?.evidence?.confidence;
  const verbalized = (conf?.verbalized ?? 'low') as string;
  const tier: ConfKey = verbalized === 'high' || verbalized === 'medium' || verbalized === 'low' ? verbalized : 'low';
  return {
    grade: (f?.verdict ?? '') as string,
    tier,
    agreement: conf?.agreement,
    nSamples: conf?.n_samples,
    abstained: Boolean(f?.evidence?.abstained),
  };
}

/* ------------------------------------------------------------------------------ the "hero" band -- */

function Hero({ onVerify, onMethodology }: { onVerify: () => void; onMethodology: () => void }) {
  return (
    <section className="cv-card overflow-hidden p-6 sm:p-8" aria-labelledby="sc-hero-title">
      <p className="text-xs font-bold uppercase tracking-widest" style={{ color: 'var(--cv-brand)' }}>
        Built with Claude · Life Sciences
      </p>
      <h1 id="sc-hero-title" className="mt-2 max-w-3xl text-3xl font-black leading-tight tracking-tight text-ink sm:text-4xl">
        Does the cited paper actually support the claim?
      </h1>
      <p className="mt-3 max-w-2xl text-base text-ink-muted">
        citeval is a referee for scientific citations: one claim, one cited paper, one question. It
        detects <strong className="text-ink">retraction</strong>, flags{' '}
        <strong className="text-ink">species / population scope</strong> mismatch, and grades{' '}
        <strong className="text-ink">substantive over-reach</strong> on a six-level scale — every
        verdict carrying a confidence <em>tier</em> and a <em>provenance</em> label.
      </p>
      <p className="mt-3 max-w-2xl text-sm font-semibold text-ink">
        The thesis, in five words: <span style={{ color: 'var(--cv-brand)' }}>grounded-and-measured, not model-checks-model.</span>{' '}
        <span className="font-normal text-ink-muted">
          Objective facts are decided by external structured records, not by asking a model to grade
          a model — and where a fact can’t be verified, it’s flagged, never fabricated.
        </span>
      </p>

      <div className="mt-5 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={onVerify}
          className="rounded-lg px-4 py-2 text-sm font-bold"
          style={{ background: 'var(--cv-brand)', color: 'var(--cv-brand-contrast)' }}
        >
          Verify a citation →
        </button>
        <button
          type="button"
          onClick={onMethodology}
          className="rounded-lg border border-line bg-surface-2 px-4 py-2 text-sm font-bold text-ink"
        >
          How it’s measured
        </button>
      </div>

      {/* Headline-stat strip — SP-01: the numbers get the dedicated large-numeral treatment, with the
          honest weak figure (scope recall) shown in amber rather than hidden. */}
      <div className="mt-7 grid grid-cols-2 gap-x-6 gap-y-5 border-t border-line pt-6 sm:grid-cols-4">
        {HEADLINE_STATS.map((s) => (
          <Stat
            key={s.label}
            value={s.value}
            label={s.label}
            sub={s.sub}
            size="lg"
            accent={s.tone === 'strong' ? 'var(--cv-conf-high-fg)' : 'var(--cv-conf-medium-fg)'}
          />
        ))}
      </div>
      <p className="mt-3 text-xs text-ink-muted">
        In-domain (N=27) <span aria-hidden>·</span> and a 45-case held-out set the system was never
        tuned on. Retraction generalises perfectly (1.00); the one weak axis — population scope
        (recall 0.40 held-out) — is measured and named, not papered over.
      </p>
    </section>
  );
}

/* --------------------------------------------------------------------- "what it caught" timeline -- */

interface CaughtStory {
  tag: string;
  title: string;
  body: ReactNode;
  /** the invariant / property this story proves */
  proves: string;
}

const CAUGHT_STORIES: CaughtStory[] = [
  {
    tag: 'Overruled its own answer key',
    title: 'Metadata beat the model — even when the model was us',
    body: (
      <>
        Building the objective corpus, the dual-source retraction check flagged three citations — two
        distinct papers, one cited twice — as retracted that the corpus’s own labels had marked{' '}
        <em>clean</em>. Retraction Watch and NCBI agreed; the labels were wrong.
      </>
    ),
    proves: 'Invariant #1 — a structured record overrides a model guess',
  },
  {
    tag: 'Caught a fabricated attribution',
    title: 'A named researcher credited with a finding that isn’t in the paper',
    body: (
      <>
        One claim credited a named researcher with showing a protein “significantly inhibits vascular
        smooth-muscle-cell proliferation,” citing a paper actually about a microRNA in pelvic-floor
        dysfunction <em>in rats</em> — a different finding, and the named author isn’t among its
        authors. All three independent graders returned <strong>unsupported-for-the-claim</strong> at
        full confidence.
      </>
    ),
    proves: 'The adversarial triad, grounded on verbatim spans',
  },
  {
    tag: 'Abstained rather than bluff',
    title: 'Declined to grade what genuinely couldn’t be graded',
    body: (
      <>
        On cases it could not verbatim-ground — a review that only speaks to a subgroup in general
        terms, a background citation making no substantive claim — the panel returned{' '}
        <strong>NOT_ENOUGH_INFO</strong> and recorded an <em>abstention</em> instead of inventing a
        grade. Failing safe is the property the whole design exists to guarantee.
      </>
    ),
    proves: 'Invariant #3 — unverifiable is flagged, never fabricated',
  },
  {
    tag: 'Caught itself on a held-out set',
    title: 'A “perfect” scope number that didn’t generalise — fixed honestly',
    body: (
      <>
        A separate 45-case set the system was never tuned on exposed that an in-domain scope recall
        we’d reported as a perfect 1.00 was <em>propped up</em> — real out-of-sample recall was ~0.29.
        We fixed the underlying logic (recall to <strong>0.71</strong>, precision <em>rising</em>),
        removed the prop, and let the in-domain number stand on its own.
      </>
    ),
    proves: 'A grounded-and-measured system has to catch itself',
  },
];

function CaughtTimeline() {
  return (
    <ol className="relative space-y-4 border-l-2 border-line pl-6" aria-label="What citeval caught">
      {CAUGHT_STORIES.map((s, i) => (
        <li key={s.tag} className="relative">
          <span
            aria-hidden
            className="absolute -left-[1.9rem] top-1 grid h-6 w-6 place-items-center rounded-full text-xs font-black"
            style={{ background: 'var(--cv-brand)', color: 'var(--cv-brand-contrast)' }}
          >
            {i + 1}
          </span>
          <article className="cv-card p-4">
            <div className="text-xs font-bold uppercase tracking-wide" style={{ color: 'var(--cv-brand)' }}>
              {s.tag}
            </div>
            <h3 className="mt-1 text-base font-bold text-ink">{s.title}</h3>
            <p className="mt-1.5 text-sm text-ink-muted">{s.body}</p>
            <p className="mt-2.5 text-xs font-semibold text-ink">
              <span aria-hidden>▸ </span>
              {s.proves}
            </p>
          </article>
        </li>
      ))}
    </ol>
  );
}

/* ------------------------------------------------------------------------ honest-limitations card -- */

const LIMITATIONS: { title: string; body: ReactNode }[] = [
  {
    title: 'Population-scope recall is genuinely weak (0.40 held-out)',
    body: (
      <>
        A general claim citing a pediatric-only paper is unresolvable from the claim text alone — our
        own reference labels the identical shape <em>both</em> ways depending on context we can’t see.
        We hold precision and accept the false-negative rather than flag real controls. An honest
        ceiling, not a bug we can wish away.
      </>
    ),
  },
  {
    title: 'The reference is an independent AI reviewer, not a human gold standard',
    body: (
      <>
        The graded axis is checked against an <strong>independent AI reviewer (Claude Science)</strong>{' '}
        — independent of the grader, which is the anti-circularity property that matters — with a{' '}
        <strong>human spot-check still pending</strong>. The held-out graded reference is a single-pass
        grade, so its out-of-sample accuracy is preliminary.
      </>
    ),
  },
  {
    title: 'N is small and the calibration map is provisional',
    body: (
      <>
        27 in-domain + 45 held-out cases. AUROC-on-exact is a modest 0.64 because a mild
        “supported-with-overreach” lean keeps exact agreement at 0.59 — even though <em>every</em>{' '}
        grade lands within one level of the reference.
      </>
    ),
  },
  {
    title: 'Deliberately slow and costly — a deep checker, not a bulk screener',
    body: (
      <>
        An adversarial Opus 4.8 triad, resampled for self-consistency, runs ~21 model calls per
        verdict (~$1 each). This is the checker you trust on the one citation that matters, not a
        literature-scale bibliography scanner. Two residual graded errors remain out-of-sample.
      </>
    ),
  },
];

function LimitationsCallout() {
  return (
    <section
      className="rounded-card border p-5 sm:p-6"
      style={{
        background: 'var(--cv-conf-medium-bg)',
        borderColor: 'var(--cv-conf-medium-fg)',
      }}
      aria-labelledby="sc-limits-title"
    >
      <div className="flex items-center gap-2">
        <span aria-hidden className="text-lg">⚠️</span>
        <h2 id="sc-limits-title" className="text-lg font-black tracking-tight" style={{ color: 'var(--cv-conf-medium-fg)' }}>
          Where it’s weak — said out loud, not in fine print
        </h2>
      </div>
      <p className="mt-1 text-sm" style={{ color: 'var(--cv-conf-medium-fg)' }}>
        The same discipline that grades the citations grades the tool. These are reported because
        hiding them would violate the thesis.
      </p>
      <dl className="mt-4 grid gap-4 sm:grid-cols-2">
        {LIMITATIONS.map((l) => (
          <div key={l.title} className="rounded-lg border border-line bg-surface p-4">
            <dt className="text-sm font-bold text-ink">{l.title}</dt>
            <dd className="mt-1 text-sm text-ink-muted">{l.body}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

/* ---------------------------------------------------------------------------- gallery case card -- */

/** The one-line "hero axis" descriptor shown as a tag on each gallery card. */
const AXIS_TAG: Record<string, string> = {
  retraction: 'Retraction gate',
  species_scope: 'Species scope',
  population_scope: 'Population scope',
  substantive_support: 'Graded support',
};

function truncate(s: string, n: number): string {
  return s.length > n ? `${s.slice(0, n - 1).trimEnd()}…` : s;
}

function CaseCard({ fixture, onOpen }: { fixture: Fixture; onOpen: (r: RunResult) => void }) {
  const core = fixture.result.verdict.verdict;
  const grounded = fixture.result.verdict.grounded;
  const gateFired = gateFiredFromOverall(core.overall);
  const sub = summariseSubstantive(fixture.result);
  const pmid = fixture.result.verdict.claim_unit.cited_identifier.value;
  const retraction = grounded.retraction;
  const gateTitle = gateFired
    ? retraction.status === 'RETRACTED'
      ? `Cited paper is retracted (${retraction.retraction_watch?.reason ?? 'Retraction Watch record'})`
      : 'An objective gate (retraction or scope) fired — overall is NOT SUPPORTED AS STATED'
    : 'No objective gate tripped — overall tracks the substantive grade';

  return (
    <article className="flex flex-col cv-card p-4" aria-label={fixture.title}>
      <header className="flex items-start justify-between gap-2">
        <span className="cv-chip text-xs">{AXIS_TAG[fixture.axisFocus] ?? fixture.axisFocus}</span>
        <code className="text-xs text-ink-muted" style={{ fontFamily: 'var(--font-mono, monospace)' }}>
          PMID {pmid}
        </code>
      </header>

      <h3 className="mt-2 text-base font-bold leading-snug text-ink">{fixture.title}</h3>

      {/* The verdict at a glance: the gate (metadata), the grade (held separately), the confidence. */}
      <div className="mt-3 flex flex-wrap items-center gap-1.5">
        <GateBadge fired={gateFired} title={gateTitle} label={gateFired ? 'NOT SUPPORTED AS STATED' : 'No gate tripped'} />
        <GradeBadge verdict={sub.grade} />
        <ConfidenceChip tier={sub.tier} agreement={sub.agreement} nSamples={sub.nSamples} abstained={sub.abstained} />
      </div>

      <p className="mt-3 text-xs uppercase tracking-wide text-ink-muted">Claim</p>
      <p className="text-sm text-ink" style={{ fontFamily: 'var(--font-mono, monospace)' }}>
        “{truncate(fixture.result.verdict.claim_unit.atomic_claim, 150)}”
      </p>

      <p className="mt-2.5 text-xs uppercase tracking-wide text-ink-muted">Cited paper</p>
      <p className="text-sm text-ink">{truncate(grounded.title, 110)}</p>

      <p className="mt-3 flex-1 text-sm text-ink-muted">{fixture.caption}</p>

      <button
        type="button"
        onClick={() => onOpen(fixture.result)}
        className="mt-4 w-full rounded-lg px-3 py-2 text-sm font-bold"
        style={{ background: 'var(--cv-brand)', color: 'var(--cv-brand-contrast)' }}
      >
        Open the full verdict →
      </button>
    </article>
  );
}

/* -------------------------------------------------------------------------------------- provenance -- */

function ProvenanceLegendStrip() {
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-card border border-line bg-surface-2 px-4 py-3">
      <span className="text-xs font-semibold uppercase tracking-wide text-ink-muted">
        Every finding is stamped
      </span>
      <ProvenanceBadge provenance="metadata-grounded" />
      <ProvenanceBadge provenance="text-grounded" />
      <ProvenanceBadge provenance="model-inferred" />
      <ProvenanceBadge provenance="stub-not-adjudicated" />
      <span className="text-xs text-ink-muted">— so a reader always knows what a verdict rests on.</span>
    </div>
  );
}

/* ============================================================================================ view */

export default function ShowcaseView() {
  const { select, goTo } = useShell();

  const openVerdict = (result: RunResult) => {
    select(result);
    goTo('verdict');
  };

  return (
    <div className="space-y-10 px-4 py-8">
      <Hero onVerify={() => goTo('run')} onMethodology={() => goTo('methodology')} />

      {/* Gallery of cached cases — the demo-safe payload: four real fixtures, no key, no backend. */}
      <section aria-labelledby="sc-gallery-title">
        <SectionHeading id="sc-gallery-title" eyebrow="Four proof cases · rendered from cached results, no key" title="See it decide">
          Each card is a real <code className="text-ink" style={{ fontFamily: 'var(--font-mono, monospace)' }}>RunResult</code>{' '}
          served from disk — open any one for the full per-axis verdict, the graded ramp, and the
          decisive verbatim span. The abstention case shows <strong className="text-ink">NOT_ENOUGH_INFO</strong> as
          an off-scale outcome, never as a low grade.
        </SectionHeading>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {FIXTURES.map((f) => (
            <CaseCard key={f.key} fixture={f} onOpen={openVerdict} />
          ))}
        </div>
        <div className="mt-4">
          <ProvenanceLegendStrip />
        </div>
      </section>

      {/* What it caught. */}
      <section aria-labelledby="sc-caught-title">
        <SectionHeading id="sc-caught-title" eyebrow="Self-correction, on the record" title="What it caught">
          The most convincing evidence a grounded checker is honest is the moment it corrects{' '}
          <em>itself</em>. Each of these actually happened while building the corpus.
        </SectionHeading>
        <CaughtTimeline />
      </section>

      {/* Honest limitations — prominent. */}
      <LimitationsCallout />

      {/* Cross-links + fallback pointer. */}
      <footer className="flex flex-col gap-3 border-t border-line pt-6 text-sm text-ink-muted sm:flex-row sm:items-center sm:justify-between">
        <p>
          Read the full method and the honest numbers on the{' '}
          <button
            type="button"
            onClick={() => goTo('methodology')}
            className="font-semibold underline decoration-dotted underline-offset-2"
            style={{ color: 'var(--cv-brand)' }}
          >
            Methodology
          </button>{' '}
          view, or run your own citation on{' '}
          <button
            type="button"
            onClick={() => goTo('run')}
            className="font-semibold underline decoration-dotted underline-offset-2"
            style={{ color: 'var(--cv-brand)' }}
          >
            Verify
          </button>
          .
        </p>
        <p className="text-xs">
          Offline fallback: <code style={{ fontFamily: 'var(--font-mono, monospace)' }}>web/standalone/app.html</code>{' '}
          renders a worked example with no build, no backend, no key.
        </p>
      </footer>
    </div>
  );
}
