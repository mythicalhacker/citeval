/**
 * ProvenanceBadge — the metadata-grounded / text-grounded / model-inferred / stub /
 * composite badge. Colours + classification are 1:1 with `reporting.py` so a badge here reads
 * identically to the same badge in the embedded `report_html`.
 */
import { provAtom, provStyle } from '../../design/tokens';

const ATOM_GLOSS: Record<string, string> = {
  'metadata-grounded': 'Read from a structured record (Retraction Watch, MeSH tree numbers, NCBI). Authoritative.',
  'text-grounded': 'An explicit lexical marker in the claim wording.',
  'model-inferred': 'A model judgement (claim-scope hint + the graded substantive-support axis).',
  'stub-not-adjudicated': 'Deliberately not decided in this slice.',
  composite: 'A composite of provenance atoms; coloured by the dominant (leading) atom.',
};

export interface ProvenanceBadgeProps {
  provenance: string;
  /** Show the full provenance string (default) or just the leading atom. */
  short?: boolean;
  className?: string;
}

export function ProvenanceBadge({ provenance, short = false, className = '' }: ProvenanceBadgeProps) {
  const atom = provAtom(provenance);
  const text = short ? atom : provenance;
  return (
    <span
      className={`cv-badge ${className}`}
      style={provStyle(provenance)}
      title={ATOM_GLOSS[atom]}
      aria-label={`Provenance: ${provenance}`}
    >
      {text}
    </span>
  );
}

export default ProvenanceBadge;
