/**
 * VerdictPanel — the inline payoff (07_uiux.md VV, condensed). On run_complete this renders the
 * full RunResult in the order a skimming judge should read it: the gated `overall` with the
 * substantive grade held separately, the per-axis table (each with tier + provenance), the graded
 * self-consistency block, the structured grounding evidence + flagged-unverifiable axes, and the
 * honest cost. A "See full verdict" button hands the same RunResult to the Verdict view via the
 * shell seam; the verbatim report_html is offered in a sandboxed iframe.
 *
 * The full Verdict view (sprint/w2-fe-verdict) owns the richest presentation; this panel keeps the
 * Run view self-sufficient so a run always ends in a readable verdict, no navigation required.
 */
import {
  GateBadge, AxisScale, GradeBadge, ConfidenceGauge, ConfidenceChip, ProvenanceBadge, CostChip,
} from '../../components/common';
import type { ReactNode, RefObject } from 'react';
import { confStyle, type ConfKey } from '../../design/tokens';
import { usd, humanize } from '../../lib/format';
import type { RunResult, AxisFinding } from '../../lib/types';
import { substantiveAxis, confidenceRead, gateFired } from './model';
import { Panel, PrimaryButton, GhostButton } from './bits';

export interface VerdictPanelProps {
  result: RunResult;
  /** Focused when the verdict mounts so keyboard/AT users land on the result (RunView owns it). */
  headingRef?: RefObject<HTMLHeadingElement>;
  onOpenVerdict: () => void;
  onRunAnother: () => void;
}

export function VerdictPanel({ result, headingRef, onOpenVerdict, onRunAnother }: VerdictPanelProps) {
  const rj = result.verdict;
  const v = rj.verdict;
  const g = rj.grounded;
  const sub = substantiveAxis(result);
  const fired = gateFired(result);
  const read = confidenceRead(result);
  const sc = (sub?.evidence as AxisFinding['evidence'] | undefined)?.self_consistency;

  return (
    <div className="grid gap-4">
      {/* ---- Hero + gate ------------------------------------------------------------------- */}
      <section className="cv-card p-4 sm:p-5" aria-labelledby="cv-verdict-title">
        <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
          <h3 ref={headingRef} tabIndex={-1} id="cv-verdict-title" className="text-sm font-bold uppercase tracking-wide text-ink outline-none">Verdict</h3>
          <div className="flex items-center gap-2">
            <GhostButton size="sm" type="button" onClick={onRunAnother}>Run another</GhostButton>
            <PrimaryButton size="sm" type="button" onClick={onOpenVerdict}>See full verdict →</PrimaryButton>
          </div>
        </div>

        <p className="text-xs uppercase tracking-wide text-ink-muted">Claim</p>
        <p className="text-ink">{v.claim}</p>
        <p className="mt-2 text-xs uppercase tracking-wide text-ink-muted">Cited paper</p>
        <p className="text-sm text-ink">
          {g.title}{' '}
          <span className="text-ink-muted">
            · {v.cited_identifier.type.toUpperCase()} {v.cited_identifier.value}
          </span>
        </p>

        <div className="my-4 h-px bg-line" />

        {/* The gate is the signature interaction: a fired gate forces `overall`, the substantive
            grade is shown alongside, held separately. */}
        <div className="grid gap-4 sm:grid-cols-[auto_1fr] sm:items-center">
          <GateBadge fired={fired} title={v.overall} />
          <div className="min-w-0">
            <p className="text-sm font-semibold text-ink">{v.overall}</p>
          </div>
        </div>

        <div className="mt-4 rounded-lg border border-line p-3">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-muted">
            Substantive support — graded separately, holding scope constant
          </p>
          <AxisScale verdict={sub?.verdict ?? 'NOT_ENOUGH_INFO'} />
        </div>
      </section>

      {/* ---- Per-axis table --------------------------------------------------------------- */}
      <Panel title="Per-axis findings" labelledBy="cv-axes-title">
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-muted">
                <th className="py-1.5 pr-3 font-semibold">Axis</th>
                <th className="py-1.5 pr-3 font-semibold">Verdict</th>
                <th className="py-1.5 pr-3 font-semibold">Confidence</th>
                <th className="py-1.5 pr-3 font-semibold">Provenance</th>
                <th className="py-1.5 font-semibold">Basis</th>
              </tr>
            </thead>
            <tbody>
              {v.axis_findings.map((a) => (
                <tr key={a.axis} className="border-b border-line align-top">
                  <td className="py-2 pr-3 font-semibold text-ink whitespace-nowrap">{humanize(a.axis)}</td>
                  <td className="py-2 pr-3">
                    {a.axis === 'substantive_support' ? (
                      <GradeBadge verdict={String(a.verdict)} />
                    ) : (
                      <span className="font-semibold text-ink">{String(a.verdict)}</span>
                    )}
                  </td>
                  <td className="py-2 pr-3"><TierPill tier={a.tier} /></td>
                  <td className="py-2 pr-3"><ProvenanceBadge provenance={a.provenance} short /></td>
                  <td className="py-2 text-ink-muted">{a.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      {/* ---- Graded substantive block ----------------------------------------------------- */}
      {sub ? (
        <Panel title="Substantive support (graded)" labelledBy="cv-graded-title">
          <div className="grid gap-5 sm:grid-cols-[12rem_1fr] sm:items-start">
            <div className="justify-self-center">
              <ConfidenceGauge agreement={read.agreement} tier={read.tier} nSamples={read.nSamples} abstained={read.abstained} size={132} />
            </div>
            <div className="grid gap-3">
              <Trace label="Supporter — best supporting span" role="supporter"
                span={strOf(sub.evidence, 'supporter', 'span')} note={strOf(sub.evidence, 'supporter', 'point')} />
              <Trace label="Refuter — strongest objection" role="refuter"
                span={strOf(sub.evidence, 'refuter', 'span')} note={strOf(sub.evidence, 'refuter', 'objection')} />
              {sc ? (
                <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs sm:grid-cols-4">
                  <Metric k="rounds" val={`${sc.rounds_run}/${sc.rounds_configured}`} />
                  <Metric k="a_exact" val={sc.a_exact?.toFixed(2)} />
                  <Metric k="a_adj" val={sc.a_adj?.toFixed(2)} />
                  <Metric k="parse-failed" val={String(sc.n_parse_failed ?? 0)} />
                  {sc.rounds_run != null && sc.rounds_configured != null && sc.rounds_run < sc.rounds_configured ? (
                    <p className="col-span-full text-[0.7rem]" style={{ color: 'var(--cv-conf-medium-fg)' }}>
                      ⏭ Early stop — {sc.rounds_run} of {sc.rounds_configured} rounds were enough.
                    </p>
                  ) : null}
                </dl>
              ) : null}
            </div>
          </div>
        </Panel>
      ) : null}

      {/* ---- Grounding evidence + flagged-unverifiable axes ------------------------------- */}
      <Panel title="Grounding evidence" subtitle="Structured records — authoritative on the objective axes." labelledBy="cv-ground-title">
        <div className="grid gap-3 text-sm sm:grid-cols-2">
          <Ground label="Retraction">
            <span className="font-semibold text-ink">{g.retraction.status}</span>
            <span className="text-ink-muted"> · sources {g.retraction.source_agreement}</span>
            {g.retraction.retraction_watch?.present ? (
              <p className="mt-1 text-xs text-ink-muted">
                Retraction Watch #{g.retraction.retraction_watch.rw_record_id}
                {g.retraction.retraction_watch.date ? ` · ${g.retraction.retraction_watch.date}` : ''}
                {g.retraction.retraction_watch.reason ? ` — ${g.retraction.retraction_watch.reason}` : ''}
              </p>
            ) : null}
          </Ground>
          <Ground label="Organism (MeSH tree B*)">
            <TagList tags={g.organism_tags.map((t) => t.descriptor)} empty="(none)" />
            <span className="text-ink-muted"> · Humans present: {String(g.has_humans)}</span>
          </Ground>
          <Ground label="Population (MeSH M01.060*)">
            <TagList tags={g.population_tags.map((t) => t.descriptor)} empty="(none)" />
          </Ground>
          <Ground label="Claim scope (parsed)">
            <span className="text-ink">{rj.claim_scope.organism ?? '(unspecified)'}</span>
            {rj.claim_scope.population ? <span className="text-ink-muted"> · {rj.claim_scope.population}</span> : null}
            <span className="text-ink-muted"> · tier {String(rj.claim_scope.tier)}</span>
          </Ground>
        </div>

        {Object.keys(v.unverifiable_axes).length > 0 ? (
          <div className="mt-4">
            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-ink-muted">
              Flagged unverifiable — never fabricated
            </p>
            <ul className="grid gap-1 text-xs text-ink-muted">
              {Object.entries(v.unverifiable_axes).map(([k, why]) => (
                <li key={k}>
                  <span className="font-semibold text-ink">{humanize(k)}</span> — {why}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </Panel>

      {/* ---- Cost + verbatim report ------------------------------------------------------- */}
      <Panel
        title="Cost"
        subtitle="An adversarial triad on Opus 4.8 is deliberately expensive — the bill is shown honestly."
        labelledBy="cv-cost-title"
        aside={<CostChip usd={result.cost.total_usd} tokens={result.cost.tokens} nCalls={result.cost.n_model_calls} label="total" />}
      >
        <div className="flex flex-wrap gap-2">
          {Object.entries(result.cost.per_role).map(([role, rc]) => (
            <CostChip key={role} usd={rc.usd} tokens={rc.tokens} nCalls={rc.n_calls} label={role} size="sm" />
          ))}
        </div>
        <details className="mt-4 text-sm">
          <summary className="cursor-pointer select-none text-xs font-semibold text-ink-muted">
            View the verbatim report (render_html)
          </summary>
          <iframe
            title="citeval report_html"
            sandbox=""
            srcDoc={result.report_html}
            className="mt-2 h-[28rem] w-full rounded-lg border border-line bg-white"
          />
        </details>
      </Panel>
    </div>
  );
}

/* ---- small parts ----------------------------------------------------------------------------- */
function TierPill({ tier }: { tier: string }) {
  const known = tier === 'high' || tier === 'medium' || tier === 'low';
  if (!known) return <span className="text-xs text-ink-muted">{tier}</span>;
  return (
    <span className="cv-badge" style={confStyle(tier as ConfKey)}>
      <span className="font-bold uppercase tracking-wide">{tier}</span>
    </span>
  );
}

function Trace({ label, role, span, note }: { label: string; role: 'supporter' | 'refuter'; span?: string; note?: string }) {
  const color = role === 'supporter' ? 'var(--cv-conf-high-fg)' : 'var(--cv-gate-fired-fg)';
  return (
    <div>
      <p className="text-[0.7rem] font-bold uppercase tracking-wide" style={{ color }}>{label}</p>
      {span ? (
        <blockquote className="mt-1 border-l-2 pl-2.5 text-sm italic text-ink" style={{ borderColor: color }}>
          “{span}”
        </blockquote>
      ) : null}
      {note ? <p className="mt-1 text-xs text-ink-muted">{note}</p> : null}
    </div>
  );
}

function Metric({ k, val }: { k: string; val?: string }) {
  return (
    <div>
      <dt className="text-[0.7rem] uppercase tracking-wide text-ink-muted">{k}</dt>
      <dd className="tabular-nums font-semibold text-ink">{val ?? '—'}</dd>
    </div>
  );
}

function Ground({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="rounded-lg border border-line p-2.5">
      <p className="mb-0.5 text-xs font-semibold uppercase tracking-wide text-ink-muted">{label}</p>
      <div className="text-sm">{children}</div>
    </div>
  );
}

function TagList({ tags, empty }: { tags: string[]; empty: string }) {
  if (tags.length === 0) return <span className="text-ink-muted">{empty}</span>;
  return <span className="text-ink">{tags.join(', ')}</span>;
}

/** Read a nested string off the open substantive-evidence dict, defensively. */
function strOf(evidence: AxisFinding['evidence'] | undefined, group: 'supporter' | 'refuter', key: string): string | undefined {
  const g = evidence?.[group] as Record<string, unknown> | undefined;
  const val = g?.[key];
  return typeof val === 'string' ? val : undefined;
}

export default VerdictPanel;
