/**
 * GroundingEvidence — the structured, metadata-grounded record behind the objective axes: the
 * retraction record, MeSH organism / population / sex tags (with tree numbers), the C3-lite claim
 * scope parse, and the axes deliberately flagged unverifiable (never fabricated — CLAUDE.md
 * invariant #3). This is the "show your sources" panel: everything the gate stands on, verbatim.
 */
import type { ReactNode } from 'react';
import type { RenderJson, MeshTag } from '../../lib/types';

function TagList({ tags, empty }: { tags: MeshTag[]; empty: string }) {
  if (!tags.length) return <span className="text-ink-muted">{empty}</span>;
  return (
    <span className="flex flex-wrap gap-1.5">
      {tags.map((t) => (
        <span key={t.ui || t.descriptor} className="cv-chip text-xs">
          <span className="font-semibold text-ink">{t.descriptor}</span>
          <span className="font-mono text-[0.68rem] text-ink-muted">
            {t.tree_numbers.length ? t.tree_numbers.join('; ') : 'no-tree'}
          </span>
        </span>
      ))}
    </span>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid gap-1 sm:grid-cols-[11rem_1fr] sm:gap-3">
      <div className="text-xs font-semibold uppercase tracking-wide text-ink-muted">{label}</div>
      <div className="text-sm text-ink">{children}</div>
    </div>
  );
}

export interface GroundingEvidenceProps {
  result: RenderJson;
}

export function GroundingEvidence({ result }: GroundingEvidenceProps) {
  const g = result.grounded;
  const scope = result.claim_scope;
  const r = g.retraction;
  const unverifiable = Object.entries(result.verdict.unverifiable_axes);
  const integrityNote = result.verdict.notes[0];

  return (
    <section className="cv-card p-5" aria-labelledby="grounding-heading">
      <h3 id="grounding-heading" className="mb-1 text-lg font-bold text-ink">
        Grounding evidence
      </h3>
      <p className="mb-4 text-xs text-ink-muted">
        Structured records the objective axes read from — authoritative, and what the gate overrides
        the model with.
      </p>

      <div className="grid gap-3">
        <Field label="Retraction status">
          <span className="flex flex-col gap-1">
            <span className="font-semibold text-ink">
              {r.status} <span className="font-normal text-ink-muted">(source agreement: {r.source_agreement})</span>
            </span>
            {r.retraction_watch?.present ? (
              <span className="text-ink-muted">
                Retraction Watch record {r.retraction_watch.rw_record_id}: {r.retraction_watch.reason}{' '}
                (date {r.retraction_watch.date})
              </span>
            ) : null}
            {r.comments_corrections.map((c, i) => (
              <span key={i} className="text-ink-muted">
                NCBI {c.ref_type}: PMID {c.pmid} — {c.source}
              </span>
            ))}
            {r.ncbi_publication_type_flag ? (
              <span className="text-ink-muted">NCBI PublicationType flag: “Retracted Publication” present</span>
            ) : null}
          </span>
        </Field>

        <Field label="Organism MeSH (tree B*)">
          <span className="flex flex-col gap-1">
            <TagList tags={g.organism_tags} empty="(none)" />
            <span className="text-xs text-ink-muted">Humans present: {String(g.has_humans)}</span>
          </span>
        </Field>

        <Field label="Population MeSH (M01.060*)">
          <TagList tags={g.population_tags} empty="(none)" />
        </Field>

        <Field label="Sex check-tags">
          {g.sex_tags.length ? (
            <span>{g.sex_tags.map((t) => t.descriptor).join(', ')}</span>
          ) : (
            <span className="text-ink-muted">(none)</span>
          )}
        </Field>

        <div className="my-1 h-px bg-line" />

        <Field label="Claim scope (C3-lite)">
          <span className="flex flex-col gap-1">
            <span>
              Asserted organism: <span className="font-semibold">{scope.organism ?? '(none)'}</span>{' '}
              <span className="text-xs text-ink-muted">(provenance: {scope.provenance}, tier: {scope.tier})</span>
            </span>
            {scope.organism_evidence.length ? (
              <span className="text-xs text-ink-muted">evidence: {scope.organism_evidence.map((e) => `“${e}”`).join(', ')}</span>
            ) : null}
            <span>
              Asserted population: <span className="font-semibold">{scope.population ?? '(none)'}</span>
            </span>
            <span className="text-xs text-ink-muted">Dose stated in claim: {String(scope.dose_stated)}</span>
          </span>
        </Field>

        {unverifiable.length ? (
          <>
            <div className="my-1 h-px bg-line" />
            <Field label="Flagged unverifiable">
              <span className="flex flex-col gap-1.5">
                <span className="text-xs text-ink-muted">
                  Axes with no structured field — surfaced as unknown, never fabricated (invariant #3).
                </span>
                <ul className="grid gap-1">
                  {unverifiable.map(([k, val]) => (
                    <li key={k} className="text-sm text-ink">
                      <span className="font-mono text-xs font-semibold">{k}</span>{' '}
                      <span className="text-ink-muted">— {val}</span>
                    </li>
                  ))}
                </ul>
              </span>
            </Field>
          </>
        ) : null}
      </div>

      {integrityNote ? (
        <p className="mt-4 border-t border-line pt-3 text-xs italic text-ink-muted">{integrityNote}</p>
      ) : null}
    </section>
  );
}

export default GroundingEvidence;
