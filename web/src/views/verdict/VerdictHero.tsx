/**
 * VerdictHero (VV-01) — the signature interaction. The verdict gate (padlock) makes CLAUDE.md
 * invariant #1 ("metadata overrides model") literally visible:
 *   • fired  → closed padlock, red accent, "NOT SUPPORTED AS STATED" as the headline, and the
 *              substantive grade demoted to a visibly secondary / parenthetical position;
 *   • clear  → open padlock, green accent, `overall` tracks the substantive grade directly;
 *   • abstained → open padlock (no objective gate), neutral accent, an honest "insufficient evidence".
 * A one-line reason spells out WHY, naming the metadata source that overrode the model.
 */
import type { RenderJson } from '../../lib/types';
import { GateBadge, GradeBadge } from '../../components/common';
import { citedPmidLabel, gateFired, gateReasonAxis, substantiveAxis, verdictMood } from './model';

const ACCENT = {
  gated: { fg: 'var(--cv-gate-fired-fg)', bg: 'var(--cv-gate-fired-bg)', border: 'var(--cv-gate-fired-border)' },
  graded: { fg: 'var(--cv-gate-clear-fg)', bg: 'var(--cv-gate-clear-bg)', border: 'var(--cv-gate-clear-border)' },
  abstained: { fg: 'var(--cv-offscale-nei-fg)', bg: 'var(--cv-offscale-nei-bg)', border: 'var(--cv-offscale-nei-border)' },
} as const;

function gateReason(rj: RenderJson): string {
  const v = rj.verdict;
  // Drive off gateFired() so the reason can never contradict a fired padlock, even when the gate
  // trips via the overall-string rollup rather than a recognised axis verdict.
  if (gateFired(v)) {
    const axis = gateReasonAxis(v);
    if (axis?.verdict === 'RELIES_ON_RETRACTED') {
      return 'Objective gate fired: the cited paper is retracted per structured records (metadata-grounded). '
        + 'Metadata overrides the model — the citation is flagged no matter how well the text reads.';
    }
    if (axis?.verdict === 'CITED_PAPER_HAS_EOC') {
      return 'Objective gate fired: the cited paper carries an Expression of Concern (metadata-grounded). '
        + 'Metadata overrides the model — the citation is flagged regardless of the substantive grade.';
    }
    if (axis?.verdict === 'SCOPE_MISMATCH') {
      const isPop = axis.axis === 'population_scope';
      const kind = isPop ? 'population' : 'species';
      const mesh = isPop ? 'population' : 'organism';
      return `Objective gate fired: ${kind} scope mismatch (metadata-grounded). The cited paper’s MeSH `
        + `${mesh} scope does not cover the claim’s scope — metadata overrides the model.`;
    }
    return 'Objective gate fired (metadata-grounded) — see the overall verdict above. '
      + 'Metadata overrides the model, regardless of the substantive grade.';
  }
  if (verdictMood(v) === 'abstained') {
    return 'No objective gate tripped. The panel could not verbatim-ground a grade and abstained — '
      + 'an honest “insufficient evidence”, not a failure.';
  }
  return 'No objective gate tripped — not retracted, scope consistent. Overall tracks the substantive grade directly.';
}

export interface VerdictHeroProps {
  result: RenderJson;
}

export function VerdictHero({ result }: VerdictHeroProps) {
  const { claim_unit, grounded, verdict: v } = result;
  const mood = verdictMood(v);
  const fired = gateFired(v);
  const sub = substantiveAxis(v);
  const accent = ACCENT[mood];

  return (
    <section className="cv-card overflow-hidden" aria-labelledby="verdict-hero-heading">
      {/* claim + cited paper */}
      <header className="border-b border-line px-5 py-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Claim under test</p>
        <p className="mt-1 text-base leading-snug text-ink">{v.claim}</p>
        <p className="mt-3 text-sm text-ink-muted">
          <span className="font-semibold text-ink">Cited paper.</span> {grounded.title}{' '}
          <span className="font-mono text-xs text-ink-muted">· {citedPmidLabel(grounded)}</span>
          {claim_unit.citing_source && typeof claim_unit.citing_source === 'object'
            && 'note' in claim_unit.citing_source
            ? <span className="text-ink-muted"> · {String((claim_unit.citing_source as { note?: unknown }).note ?? '')}</span>
            : null}
        </p>
      </header>

      {/* the gate hero */}
      <div
        className="flex flex-col gap-3 border-l-4 px-5 py-4"
        style={{ borderLeftColor: accent.fg, background: accent.bg }}
      >
        <div className="flex flex-wrap items-center gap-3">
          <GateBadge
            fired={fired}
            title={gateReason(result)}
            label={fired ? 'GATE FIRED' : mood === 'abstained' ? 'No gate · abstained' : 'No gate tripped'}
          />
          <h2 id="verdict-hero-heading" className="text-xl font-extrabold leading-tight" style={{ color: accent.fg }}>
            {v.overall}
          </h2>
        </div>

        {/* substantive grade — headline when clear, demoted/parenthetical when the gate fired */}
        {sub ? (
          fired ? (
            <p className="text-sm text-ink-muted">
              Substantive grade, <span className="italic">held separately</span>:{' '}
              <GradeBadge verdict={sub.verdict} className="align-middle" />{' '}
              <span>— the paper’s own text is assessed independently, but the objective gate stands.</span>
            </p>
          ) : (
            <p className="flex flex-wrap items-center gap-2 text-sm text-ink">
              <span className="font-semibold">Substantive grade:</span>
              <GradeBadge verdict={sub.verdict} />
            </p>
          )
        ) : null}

        <p className="text-sm" style={{ color: accent.fg }}>{gateReason(result)}</p>
      </div>
    </section>
  );
}

export default VerdictHero;
