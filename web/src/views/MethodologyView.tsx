/**
 * MethodologyView — the "why trust this" view.
 *
 * It walks a judge through the one idea that shapes every decision (grounded-and-measured, not
 * model-checks-model), the three axes and the pipeline that produces them, the provenance / tier
 * discipline stamped on every finding, the six-level graded scale and its two off-scale outcomes,
 * how confidence is derived and recalibrated, the headline results (weak spots included), and the
 * deliberately-expensive cost model.
 *
 * Ownership: this file (a W2 view). It reuses the W1 design system (Stepper, AxisScale,
 * ProvenanceBadge, Stat, CostChip, ConfidenceChip) and reads live pricing via `api.getPricing()`;
 * it never edits the shell, the api client, or the design system.
 *
 * COPY DISCIPLINE (reviews/improvements/07_uiux.md §Principle 3 / PP-05): the graded reference is an
 * INDEPENDENT AI reviewer (Claude Science), human spot-check pending — never "human ground truth".
 */
import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import {
  Stat,
  Stepper,
  AxisScale,
  GradeBadge,
  ProvenanceBadge,
  ConfidenceChip,
  CostChip,
  HEADLINE_STATS,
} from '../components/common';
import { RB1_GRADES } from '../lib/types';
import type { PricingInfo } from '../lib/types';
import { api } from '../lib/api';
import { FIXTURE_GRADED_OVERREACH } from '../lib/fixtures';
import { usd } from '../lib/format';

/* ------------------------------------------------------------------------------ layout helpers -- */

function Section({ id, eyebrow, title, lead, children }: {
  id: string; eyebrow: string; title: string; lead?: ReactNode; children: ReactNode;
}) {
  return (
    <section aria-labelledby={id} className="scroll-mt-4">
      <div className="text-xs font-bold uppercase tracking-widest" style={{ color: 'var(--cv-brand)' }}>
        {eyebrow}
      </div>
      <h2 id={id} className="mt-1 text-xl font-black tracking-tight text-ink sm:text-2xl">{title}</h2>
      {lead ? <p className="mt-2 max-w-3xl text-sm text-ink-muted">{lead}</p> : null}
      <div className="mt-4">{children}</div>
    </section>
  );
}

/* ---------------------------------------------------------------------------------------- thesis -- */

function ThesisBand() {
  return (
    <section className="cv-card p-6 sm:p-8" aria-labelledby="mv-thesis-title">
      <div className="text-xs font-bold uppercase tracking-widest" style={{ color: 'var(--cv-brand)' }}>
        The thesis
      </div>
      <h1 id="mv-thesis-title" className="mt-2 max-w-3xl text-2xl font-black leading-tight tracking-tight text-ink sm:text-3xl">
        Grounded-and-measured, <span style={{ color: 'var(--cv-brand)' }}>not model-checks-model.</span>
      </h1>
      <p className="mt-3 max-w-3xl text-base text-ink-muted">
        One principle shapes every design decision: <strong className="text-ink">if a choice trades
        provable grounding for impressive-looking model output, it is the wrong choice.</strong>{' '}
        Objective facts — retraction, species / population scope — are decided by external structured
        records, not by asking a model to grade a model. The one subjective axis is decided by an
        adversarial process and then <em>measured</em> against a reference independent of the grader,
        reporting not just whether the labels are right but whether the <em>confidence</em> is honest —
        and whether any of it survives on data we never tuned on.
      </p>
    </section>
  );
}

/* ------------------------------------------------------------------------- how it works / axes -- */

interface AxisSpec {
  n: string;
  axis: string;
  provenance: string;
  headline: string;
  body: ReactNode;
}

const AXES: AxisSpec[] = [
  {
    n: '1',
    axis: 'Retraction',
    provenance: 'metadata-grounded',
    headline: 'Two independent records, and the model can’t overturn either.',
    body: (
      <>
        The cited identifier is checked against a Retraction Watch index (~29k records)
        cross-referenced with NCBI publication-type flags. A positive from <em>either</em> source is a
        fact the model cannot overturn — a claim resting on a retracted paper inherits the retraction,
        regardless of how well the text reads.
      </>
    ),
  },
  {
    n: '2',
    axis: 'Species / population scope',
    provenance: 'metadata-grounded + model-inferred',
    headline: 'MeSH sets the scope; the model only judges over-reach against it.',
    body: (
      <>
        MeSH organism and age check-tags, keyed on tree number, establish the cited paper’s actual
        scope <em>deterministically</em>. Opus 4.8 then judges whether the claim over-generalises
        beyond it — a claim that silently drops “in mice,” or stretches an infant-only finding to
        adults. A mismatch requires <strong>both</strong> a scope-narrow source (by MeSH){' '}
        <strong>and</strong> an over-reaching claim, so the metadata gates the model.
      </>
    ),
  },
  {
    n: '3',
    axis: 'Substantive support',
    provenance: 'model-inferred',
    headline: 'An adversarial triad, graded on a six-level scale, on Opus 4.8.',
    body: (
      <>
        Holding scope constant, a <strong>supporter</strong> argues the paper backs the claim, a{' '}
        <strong>refuter</strong> argues it doesn’t, and a <strong>critic</strong> adjudicates from a
        verbatim decisive span — over up to seven order-randomised, identity-blinded self-consistency
        rounds. A <code style={{ fontFamily: 'var(--font-mono, monospace)' }}>contradicted</code> grade
        is structurally required to rest on a span showing the source’s primary finding runs opposite
        the claim, so a reversal must be grounded, not rhetorical.
      </>
    ),
  },
];

function AxisCards() {
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      {AXES.map((a) => (
        <article key={a.axis} className="flex flex-col cv-card p-4">
          <div className="flex items-center gap-2">
            <span
              aria-hidden
              className="grid h-7 w-7 place-items-center rounded-full text-xs font-black"
              style={{ background: 'var(--cv-brand)', color: 'var(--cv-brand-contrast)' }}
            >
              {a.n}
            </span>
            <h3 className="text-base font-bold text-ink">{a.axis}</h3>
          </div>
          <div className="mt-2">
            <ProvenanceBadge provenance={a.provenance} />
          </div>
          <p className="mt-2 text-sm font-semibold text-ink">{a.headline}</p>
          <p className="mt-1.5 flex-1 text-sm text-ink-muted">{a.body}</p>
        </article>
      ))}
    </div>
  );
}

/* ----------------------------------------------------------------------------------- invariants -- */

const INVARIANTS: { title: string; body: string }[] = [
  {
    title: 'Metadata overrides model',
    body: 'On the objective axes a model value never overturns a structured record; a conflict is scored as the model being wrong, not the record.',
  },
  {
    title: 'Tier + provenance on every finding',
    body: 'Each axis verdict is stamped metadata-grounded / text-grounded / model-inferred / stub — so a reader always knows whether it rests on a database record or a model judgement.',
  },
  {
    title: 'Unverifiable is flagged, never fabricated',
    body: 'Where a fact can’t be checked from the record (e.g. dose), the axis is flagged as unverifiable rather than filled with a guess.',
  },
  {
    title: 'Opus 4.8 on every model call',
    body: 'No cheaper or faster model anywhere in the pipeline — the adversarial triad and the scope judge all run on Opus 4.8.',
  },
  {
    title: 'Verbatim guard',
    body: 'Any stored claim or quoted span must be a verbatim substring of the citing paper’s whitespace-normalised full text — a structural defence against fabricated support.',
  },
  {
    title: 'Scope is held separate from substance',
    body: 'substantive_support grades substance holding scope constant; scope over-reach lives on its own axes; the overall rollup is swappable.',
  },
];

function InvariantGrid() {
  return (
    <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {INVARIANTS.map((inv, i) => (
        <li key={inv.title} className="cv-card p-4">
          <div className="flex items-baseline gap-2">
            <span className="text-xs font-black tabular-nums" style={{ color: 'var(--cv-brand)' }}>
              #{i + 1}
            </span>
            <span className="text-sm font-bold text-ink">{inv.title}</span>
          </div>
          <p className="mt-1 text-sm text-ink-muted">{inv.body}</p>
        </li>
      ))}
    </ul>
  );
}

/* ---------------------------------------------------------------------------- provenance legend -- */

const PROV_LEGEND: { atom: string; gloss: string }[] = [
  { atom: 'metadata-grounded', gloss: 'Read from a structured record (Retraction Watch, MeSH tree numbers, NCBI). Authoritative.' },
  { atom: 'text-grounded', gloss: 'An explicit lexical marker in the claim wording.' },
  { atom: 'model-inferred', gloss: 'A model judgement — the claim-scope hint plus the graded substantive-support axis.' },
  { atom: 'stub-not-adjudicated', gloss: 'Deliberately not decided in a thin slice.' },
];

function ProvenanceLegend() {
  return (
    <div className="cv-card p-4">
      <dl className="grid gap-x-4 gap-y-3 sm:grid-cols-2">
        {PROV_LEGEND.map((p) => (
          <div key={p.atom} className="flex flex-col gap-1">
            <dt>
              <ProvenanceBadge provenance={p.atom} />
            </dt>
            <dd className="text-sm text-ink-muted">{p.gloss}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-4 border-t border-line pt-3 text-sm italic text-ink-muted">
        Metadata (grounded) always overrides model or text on the objective axes — a conflict is
        scored as the model being wrong, not the record.
      </p>
    </div>
  );
}

/* --------------------------------------------------------------------------------- graded scale -- */

function GradedScale() {
  return (
    <div className="space-y-5">
      <div className="cv-card p-5">
        <p className="text-sm text-ink-muted">
          The exact non-binary “spin” that flat SUPPORT / REFUTE / NOT-ENOUGH-INFO labels can’t
          express — best (0) at the top, worst (5) at the bottom:
        </p>
        <ol className="mt-3 grid gap-1.5 sm:grid-cols-2">
          {RB1_GRADES.map((g) => (
            <li key={g}>
              <GradeBadge verdict={g} />
            </li>
          ))}
        </ol>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <figure className="cv-card p-4">
          <figcaption className="text-sm font-bold text-ink">A grade lands on the ramp</figcaption>
          <p className="mt-0.5 text-xs text-ink-muted">e.g. partially-supported (grade 2 of 5)</p>
          <div className="mt-3">
            <AxisScale verdict="partially-supported" />
          </div>
        </figure>

        <figure className="cv-card p-4">
          <figcaption className="text-sm font-bold text-ink">Abstention is off the scale</figcaption>
          <p className="mt-0.5 text-xs text-ink-muted">NOT_ENOUGH_INFO — a deliberate, honest outcome</p>
          <div className="mt-3">
            <AxisScale verdict="NOT_ENOUGH_INFO" />
          </div>
        </figure>

        <figure className="cv-card p-4">
          <figcaption className="text-sm font-bold text-ink">Non-substantiating is off the scale</figcaption>
          <p className="mt-0.5 text-xs text-ink-muted">N/A — the citation makes no substantive claim</p>
          <div className="mt-3">
            <AxisScale verdict="N/A — non-substantiating" />
          </div>
        </figure>
      </div>
      <p className="text-sm text-ink-muted">
        The two off-scale outcomes get a distinct dashed treatment — never a low point <em>on</em> the
        ramp — so “the system honestly declined” can never be mistaken for “the system scored it
        badly”.
      </p>
    </div>
  );
}

/* ----------------------------------------------------------------------- confidence + calibration -- */

function ConfidenceCalibration() {
  return (
    <div className="space-y-5">
      <div className="cv-card p-5">
        <p className="text-sm text-ink-muted">
          Confidence is the triad’s <strong className="text-ink">self-consistency agreement</strong>{' '}
          across resampled rounds, reported as a tier. A non-adjacent, multi-modal split below the
          trust floor doesn’t lower the score — it triggers an abstention.
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <ConfidenceChip tier="high" agreement={0.86} nSamples={7} />
          <ConfidenceChip tier="medium" agreement={0.71} nSamples={7} />
          <ConfidenceChip tier="low" agreement={0.57} nSamples={7} />
          <ConfidenceChip tier="low" abstained agreement={0.33} nSamples={3} />
        </div>
      </div>

      <div
        className="rounded-card border p-5"
        style={{ background: 'var(--cv-conf-high-bg)', borderColor: 'var(--cv-conf-high-fg)' }}
      >
        <h3 className="text-sm font-bold" style={{ color: 'var(--cv-conf-high-fg)' }}>
          Recalibrated, and measured against an independent reference
        </h3>
        <p className="mt-1.5 text-sm" style={{ color: 'var(--cv-conf-high-fg)' }}>
          The agreement is Platt-recalibrated against the reference. Because the map is monotone,
          recalibration cut expected calibration error (raw ECE <strong>0.32</strong> → leave-one-out
          ECE <strong>0.08</strong>) <em>without touching discrimination</em> — AUROC is identical
          before and after (0.64).
        </p>
        <p className="mt-2 text-sm font-semibold" style={{ color: 'var(--cv-conf-high-fg)' }}>
          The reference is an independent AI reviewer (Claude Science) — independent of the grader,
          the anti-circularity property that matters — with a human spot-check still pending. Not a
          human gold standard, and we don’t claim one.
        </p>
      </div>
    </div>
  );
}

/* --------------------------------------------------------------------------------------- results -- */

interface ResultRow { metric: string; value: string; note: string; tone: 'strong' | 'weak' | 'neutral' }

const RESULTS: ResultRow[] = [
  { metric: 'Retraction P / R / F', value: '1.00', note: 'in-domain and 45-case held-out — generalises perfectly', tone: 'strong' },
  { metric: 'Quadratic-weighted κ (graded)', value: '0.90', note: 'N=27 vs. the independent reference', tone: 'strong' },
  { metric: 'Within-one-level agreement', value: '1.00', note: 'every graded case within ±1 of the reference', tone: 'strong' },
  { metric: 'Exact agreement', value: '0.59', note: '16/27 — a mild supported-with-overreach lean', tone: 'neutral' },
  { metric: 'Recalibrated ECE', value: '0.08', note: 'leave-one-out, from 0.32 raw', tone: 'strong' },
  { metric: 'AUROC (confidence vs. correctness)', value: '0.64', note: 'unchanged by recalibration', tone: 'neutral' },
  { metric: 'Confident-but-wrong grades', value: '0', note: 'high confidence, off by ≥2 levels', tone: 'strong' },
  { metric: 'Coverage (gradable cases graded)', value: '0.96', note: 'one honest abstention', tone: 'strong' },
  { metric: 'Scope recall (held-out)', value: '0.71', note: 'species 0.83, population 0.40 — the one weak axis, named not hidden', tone: 'weak' },
];

function toneColor(tone: ResultRow['tone']): string | undefined {
  if (tone === 'strong') return 'var(--cv-conf-high-fg)';
  if (tone === 'weak') return 'var(--cv-conf-medium-fg)';
  return undefined;
}

function ResultsTable() {
  return (
    <div className="cv-card overflow-x-auto">
      <table className="w-full text-sm">
        <caption className="sr-only">citeval headline evaluation results</caption>
        <thead>
          <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-muted">
            <th scope="col" className="px-4 py-2.5 font-semibold">Metric</th>
            <th scope="col" className="px-4 py-2.5 text-right font-semibold">Value</th>
            <th scope="col" className="px-4 py-2.5 font-semibold">Basis</th>
          </tr>
        </thead>
        <tbody>
          {RESULTS.map((r) => (
            <tr key={r.metric} className="border-b border-line last:border-0">
              <th scope="row" className="px-4 py-2.5 text-left font-semibold text-ink">{r.metric}</th>
              <td className="px-4 py-2.5 text-right">
                <span className="cv-stat-value text-lg tabular-nums" style={{ color: toneColor(r.tone) }}>
                  {r.value}
                </span>
              </td>
              <td className="px-4 py-2.5 text-ink-muted">{r.note}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ------------------------------------------------------------------------------------- cost model -- */

function CostModel() {
  const [pricing, setPricing] = useState<PricingInfo | null>(null);

  useEffect(() => {
    let alive = true;
    api.getPricing().then((p) => { if (alive) setPricing(p); }).catch(() => { /* keep the placeholder */ });
    return () => { alive = false; };
  }, []);

  const perVerdict = FIXTURE_GRADED_OVERREACH.cost;

  const tiers: { key: keyof PricingInfo; label: string; hint: string }[] = [
    { key: 'input', label: 'Input', hint: 'fresh prompt tokens' },
    { key: 'output', label: 'Output', hint: 'generated tokens' },
    { key: 'cache_write', label: 'Cache write', hint: 'first-time evidence block' },
    { key: 'cache_read', label: 'Cache read', hint: 'reused across the 21 calls' },
  ];

  return (
    <div className="space-y-5">
      <p className="max-w-3xl text-sm text-ink-muted">
        An adversarial triad on Opus 4.8, resampled for self-consistency, is <em>deliberately</em>{' '}
        expensive — ~21 model calls per verdict. Cost is surfaced honestly, because a deep checker
        that costs real money is the point, not an embarrassment. The ~6000-token evidence block is
        cache-broken once and <strong className="text-ink">read</strong> by the rest of the triad, so
        most of the 21 calls are cheap cache reads rather than fresh writes.
      </p>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {tiers.map((t) => (
          <div key={t.key} className="cv-card p-4">
            <Stat
              value={pricing ? usd(pricing[t.key] as number) : '—'}
              label={t.label}
              sub={t.hint}
            />
          </div>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-3 rounded-card border border-line bg-surface-2 p-4">
        <span className="text-sm font-semibold text-ink">Cost of one worked verdict:</span>
        <CostChip usd={perVerdict.total_usd} tokens={perVerdict.tokens} nCalls={perVerdict.n_model_calls} label="Ce11 (7 rounds)" />
        <span className="text-xs text-ink-muted">
          {pricing?.unit === 'usd_per_million_tokens' ? 'USD per million tokens' : ''} ·{' '}
          {pricing?.note ?? 'illustrative Opus-class placeholders'}
        </span>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------------------------- pipeline strip -- */

function PipelineStrip() {
  const timing = FIXTURE_GRADED_OVERREACH.timing.per_stage_ms;
  return (
    <div className="cv-card p-5">
      <Stepper
        statuses={{
          ingest: 'done',
          ground_retraction: 'done',
          ground_scope: 'done',
          adjudicate: 'done',
          report: 'done',
        }}
        timing={timing}
      />
      <p className="mt-3 text-xs text-ink-muted">
        Five stages, in canonical order — the objective axes (Retraction, Scope) are grounded before
        the model ever grades, so a structured record is already in hand to override it. Durations are
        from a real Opus 4.8 run; adjudication dominates because it is 21 calls, not one.
      </p>
    </div>
  );
}

/* ============================================================================================ view */

export default function MethodologyView() {
  return (
    <div className="space-y-10 px-4 py-8">
      <ThesisBand />

      {/* Headline stats, echoed for a reader who lands here first. */}
      <section aria-label="Headline results" className="grid grid-cols-2 gap-x-6 gap-y-5 sm:grid-cols-4">
        {HEADLINE_STATS.map((s) => (
          <Stat
            key={s.label}
            value={s.value}
            label={s.label}
            sub={s.sub}
            accent={s.tone === 'strong' ? 'var(--cv-conf-high-fg)' : 'var(--cv-conf-medium-fg)'}
          />
        ))}
      </section>

      <Section
        id="mv-how"
        eyebrow="How it works"
        title="Three axes, grounded before graded"
        lead="One claim, one cited paper, three questions — and the objective two are answered from structured records before the subjective one is graded."
      >
        <div className="space-y-4">
          <PipelineStrip />
          <AxisCards />
        </div>
      </Section>

      <Section
        id="mv-invariants"
        eyebrow="Enforced structurally, not by convention"
        title="The non-negotiable invariants"
        lead="These aren’t style guidelines — they’re structural rules the pipeline enforces, which is why the tool can overrule its own makers."
      >
        <InvariantGrid />
      </Section>

      <Section
        id="mv-provenance"
        eyebrow="Provenance & tier"
        title="No surface says more than the data supports"
        lead="The badge palette is 1:1 with the embedded report, so a verdict reads identically in the app and in the exported HTML."
      >
        <ProvenanceLegend />
      </Section>

      <Section
        id="mv-graded"
        eyebrow="The graded axis"
        title="A six-level ordinal for spin — with two honest off-scale outcomes"
      >
        <GradedScale />
      </Section>

      <Section
        id="mv-confidence"
        eyebrow="Calibrated confidence"
        title="Honest about how sure it is"
      >
        <ConfidenceCalibration />
      </Section>

      <Section
        id="mv-results"
        eyebrow="The numbers"
        title="What the results actually say"
        lead="Proven and generalising on the objective half; well-calibrated in-domain on the graded half; and one measured, named weakness."
      >
        <ResultsTable />
      </Section>

      <Section
        id="mv-cost"
        eyebrow="Cost model"
        title="Deliberately expensive — and honest about it"
      >
        <CostModel />
      </Section>
    </div>
  );
}
