/**
 * ConcurrencyMeter (W2-FE-BATCH) — the honest true-parallel-vs-queued indicator.
 *
 * The headline number is read from the STREAM, not asserted: `running` is how many items are in
 * flight right now, `peak` is the most ever seen at once — i.e. the real worker ceiling. Against
 * the mock we can also show the *configured* pool (MOCK_BATCH_CONCURRENCY) as corroboration; against
 * a live backend the empirical peak stands on its own. Each slot is a worker: filled = busy,
 * hollow = idle. A separate count shows how many items are still queued behind the pool.
 */
import { MOCK_BATCH_CONCURRENCY } from '../../lib/mockServer';

export interface ConcurrencyMeterProps {
  running: number;
  queued: number;
  peakInFlight: number;
  usingMock: boolean;
  className?: string;
}

export function ConcurrencyMeter({ running, queued, peakInFlight, usingMock, className = '' }: ConcurrencyMeterProps) {
  // The configured pool is only known for the mock; for a live backend, the observed peak IS the
  // pool. Never render fewer slots than are currently busy.
  const configured = usingMock ? MOCK_BATCH_CONCURRENCY : 0;
  const poolSize = Math.max(configured, peakInFlight, running, 1);
  const slots = Array.from({ length: poolSize }, (_, i) => i < running);

  const poolNote = usingMock
    ? `pool ${configured} · peak ${peakInFlight}`
    : `peak ${peakInFlight} workers (observed)`;

  return (
    <div className={`flex flex-col gap-1 ${className}`}>
      <div className="flex items-center gap-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Concurrency</span>
        <span
          className="text-xs tabular-nums text-ink-muted"
          title="Read live from the stream — the real worker occupancy, not a fixed guess."
        >
          {poolNote}
        </span>
      </div>
      <div className="flex items-center gap-2">
        <div
          className="flex items-center gap-1"
          role="img"
          aria-label={`${running} of ${poolSize} workers busy; ${queued} items queued; peak parallelism ${peakInFlight}.`}
        >
          {slots.map((busy, i) => (
            <span
              key={i}
              aria-hidden
              className="h-3.5 w-3.5 rounded-full border transition-colors"
              style={
                busy
                  ? { background: 'var(--cv-brand)', borderColor: 'var(--cv-brand)' }
                  : { background: 'transparent', borderColor: 'var(--cv-border)' }
              }
            />
          ))}
        </div>
        <span className="text-sm tabular-nums text-ink">
          <span className="font-bold" style={{ color: 'var(--cv-brand)' }}>{running}</span>
          <span className="text-ink-muted"> in flight</span>
          {queued > 0 ? (
            <span className="text-ink-muted"> · {queued} queued</span>
          ) : null}
        </span>
      </div>
    </div>
  );
}

export default ConcurrencyMeter;
