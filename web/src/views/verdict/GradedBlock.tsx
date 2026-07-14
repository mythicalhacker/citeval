/**
 * GradedBlock — the graded `substantive_support` payload, held SEPARATELY from the objective gate
 * (CLAUDE.md invariant #7). Composes:
 *   VV-03  the 6-level RB1 ramp (AxisScale) with the grade lit — abstention renders off the track;
 *   VV-04  the calibrated confidence gauge + chip, with HONEST copy (checked against an independent
 *          AI reviewer, human spot-check pending — never "human ground truth");
 *   VV-05  the decisive supporter/refuter verbatim spans (via VerbatimSpan);
 *   plus the self-consistency machinery (rounds, exact/adjacent agreement, ordinal dispersion) —
 *          shown on purpose: the adversarial vote IS the pitch, not an embarrassment.
 */
import type { ReactNode } from 'react';
import type { AxisFinding } from '../../lib/types';
import { AxisScale, GradeBadge, ConfidenceGauge, ConfidenceChip, ProvenanceBadge } from '../../components/common';
import { gradeStyle, classifySubstantive } from '../../design/tokens';
import { ratio } from '../../lib/format';
import VerbatimSpan from './VerbatimSpan';
import {
  confKeyOf, confidenceOf, calibrationNoteOf, selfConsistencyOf, verbatimGuardOf, spanOf,
  isAbstained,
} from './model';

const SCOPE_CONSTANT_NOTE =
  'grades substance only, holding scope constant (CONTEXT_PACK §6) — species/population scope '
  + 'over-reach is carried by the scope axes above, not reflected in this grade.';

/** The honest-provenance disclosure (VV-04 / Principle 3). This exact framing — an *independent AI
 *  reviewer*, human spot-check *pending* — is the required copy; "human ground truth" is forbidden.
 *  Worded as a methodology statement ("tiers are calibrated against …"), NOT a per-run claim, so it
 *  never asserts a reference check that this particular run did not undergo (the per-run recalibration
 *  status lives in the Calibration row below). */
const HONEST_CALIBRATION_COPY =
  'Confidence tiers are calibrated against an independent AI reviewer (Claude Science); human spot-check pending.';

function Row({ term, children }: { term: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[max-content_1fr] gap-x-3 gap-y-1 sm:gap-x-4">
      <dt className="text-xs font-semibold uppercase tracking-wide text-ink-muted">{term}</dt>
      <dd className="text-sm text-ink">{children}</dd>
    </div>
  );
}

/** The per-round ordinal vote, as a segmented bar coloured by grade — makes dispersion visible. */
function DistributionBar({ dist }: { dist: Record<string, number> }) {
  const entries = Object.entries(dist).filter(([, n]) => n > 0);
  const total = entries.reduce((s, [, n]) => s + n, 0);
  if (!total) return null;
  return (
    <div className="grid gap-1.5">
      <div className="flex h-4 overflow-hidden rounded" role="img" aria-label={`Per-round grade vote: ${entries.map(([g, n]) => `${g} ×${n}`).join(', ')}`}>
        {entries.map(([grade, n]) => {
          const b = classifySubstantive(grade);
          const style = b.kind === 'grade' ? gradeStyle(b.index) : { background: 'var(--cv-offscale-nei-bg)', color: 'var(--cv-offscale-nei-fg)' };
          return (
            <div
              key={grade}
              style={{ ...style, flex: n, minWidth: 2 }}
              title={`${grade}: ${n} of ${total} rounds`}
              className="h-full"
            />
          );
        })}
      </div>
      <ul className="flex flex-wrap gap-x-3 gap-y-0.5 text-[0.7rem] text-ink-muted">
        {entries.map(([grade, n]) => {
          const b = classifySubstantive(grade);
          const swatch = b.kind === 'grade' ? gradeStyle(b.index) : undefined;
          return (
            <li key={grade} className="flex items-center gap-1">
              <span aria-hidden className="h-2 w-2 rounded-sm border border-line" style={swatch} />
              <span className="tabular-nums">{grade} ×{n}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function Metric({ label, value, title }: { label: string; value: string; title?: string }) {
  return (
    <div className="flex flex-col" title={title}>
      <span className="text-sm font-semibold tabular-nums text-ink">{value}</span>
      <span className="text-[0.68rem] uppercase tracking-wide text-ink-muted">{label}</span>
    </div>
  );
}

export interface GradedBlockProps {
  finding: AxisFinding;
}

export function GradedBlock({ finding }: GradedBlockProps) {
  const abstained = isAbstained(finding);
  const conf = confidenceOf(finding);
  const hasAgreement = typeof conf.agreement === 'number';
  const agreement = hasAgreement ? (conf.agreement as number) : 0;
  const nSamples = conf.n_samples;
  const calNote = calibrationNoteOf(finding);
  const sc = selfConsistencyOf(finding);
  const guard = verbatimGuardOf(finding);
  const sup = spanOf(finding, 'supporter');
  const ref = spanOf(finding, 'refuter');
  const key = confKeyOf(finding);

  return (
    <section className="cv-card p-5" aria-labelledby="graded-heading">
      <div className="mb-4 flex items-baseline justify-between gap-3">
        <h3 id="graded-heading" className="text-lg font-bold text-ink">
          Substantive support <span className="font-normal text-ink-muted">— graded, held separately</span>
        </h3>
        <span className="text-xs text-ink-muted">RB1 ordinal scale</span>
      </div>

      {/* VV-03 ramp + VV-04 gauge, side by side on wide screens */}
      <div className="mb-5 flex flex-col gap-5 sm:flex-row sm:items-center sm:gap-8">
        <div className="min-w-0 flex-1">
          <AxisScale verdict={finding.verdict} />
        </div>
        <div className="shrink-0 self-center sm:self-auto">
          {hasAgreement || abstained ? (
            <ConfidenceGauge
              agreement={agreement}
              tier={key === 'abstain' ? 'medium' : key}
              nSamples={nSamples}
              abstained={abstained}
            />
          ) : (
            <div className="grid h-16 w-24 place-items-center rounded-lg border border-line text-xs text-ink-muted" title="No self-consistency agreement recorded for this run.">
              agreement n/a
            </div>
          )}
        </div>
      </div>

      <dl className="grid gap-2.5">
        <Row term="Grade">
          <span className="flex flex-wrap items-center gap-2">
            <GradeBadge verdict={finding.verdict} />
            {abstained ? (
              <span className="text-ink-muted">the panel abstained — recorded as an abstention, not scored as wrong.</span>
            ) : null}
          </span>
        </Row>

        <Row term="Confidence">
          <span className="flex flex-col gap-1.5">
            <span className="flex flex-wrap items-center gap-2">
              <ConfidenceChip
                tier={key === 'abstain' ? 'low' : key}
                agreement={typeof conf.agreement === 'number' ? conf.agreement : undefined}
                nSamples={nSamples}
                abstained={abstained}
              />
              {conf.verbalized ? <span className="text-ink-muted">verbalized {conf.verbalized}</span> : null}
            </span>
            <span className="text-xs text-ink-muted">{HONEST_CALIBRATION_COPY}</span>
          </span>
        </Row>

        <Row term="Calibration">
          <span className="text-ink-muted">
            {calNote || 'not yet available — populated by the scorer/RB3 once the corpus is scored.'}
          </span>
        </Row>

        <Row term="Provenance">
          <span className="flex flex-wrap items-center gap-2">
            <ProvenanceBadge provenance={finding.provenance} />
            <span className="text-ink-muted">{SCOPE_CONSTANT_NOTE}</span>
          </span>
        </Row>

        {finding.detail ? (
          <Row term="Rationale">
            <span>{finding.detail}</span>
          </Row>
        ) : null}
      </dl>

      {/* Self-consistency machinery — the adversarial vote made visible */}
      {sc ? (
        <div className="mt-5 rounded-lg border border-line bg-surface-2 p-4">
          <h4 className="mb-3 text-xs font-bold uppercase tracking-wide text-ink-muted">
            Self-consistency vote
          </h4>
          <div className="mb-3 flex flex-wrap gap-x-6 gap-y-2">
            <Metric label="exact agree" value={ratio(sc.a_exact)} title="a_exact — fraction of rounds landing on the modal grade" />
            <Metric label="adjacent agree" value={ratio(sc.a_adj)} title="a_adj — fraction within one ordinal step of the modal grade" />
            <Metric
              label="rounds"
              value={`${sc.rounds_valid ?? '—'}/${sc.rounds_run ?? '—'}`}
              title={`${sc.rounds_valid ?? 0} of ${sc.rounds_run ?? 0} run rounds placed a parseable ordinal grade (configured ${sc.rounds_configured ?? '—'})`}
            />
            {sc.n_parse_failed ? <Metric label="unparsed" value={String(sc.n_parse_failed)} title="rounds whose critic output failed to parse an ordinal grade" /> : null}
            {sc.n_nei ? <Metric label="NEI rounds" value={String(sc.n_nei)} title="rounds that returned NOT_ENOUGH_INFO" /> : null}
          </div>
          {sc.ordinal_distribution ? <DistributionBar dist={sc.ordinal_distribution} /> : null}
          {sc.non_adjacent_multimodal ? (
            <p className="mt-3 text-xs text-ink-muted">
              ⚠ Non-adjacent multimodal split (adjacent agreement {ratio(sc.a_adj)} below the trust
              floor {ratio(sc.adjacent_floor)}) — the panel abstains rather than guess.
            </p>
          ) : null}
        </div>
      ) : null}

      {/* VV-05 adversarial trace */}
      <div className="mt-5">
        <h4 className="mb-3 text-xs font-bold uppercase tracking-wide text-ink-muted">Adversarial trace</h4>
        <div className="grid gap-4">
          <VerbatimSpan role="supporter" span={sup} guard={guard} />
          <VerbatimSpan role="refuter" span={ref} guard={guard} />
        </div>
      </div>
    </section>
  );
}

export default GradedBlock;
