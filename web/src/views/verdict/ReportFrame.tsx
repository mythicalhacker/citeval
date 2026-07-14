/**
 * ReportFrame — the verbatim `report_html` document, offered as the downloadable artifact and
 * previewed inline in a sandboxed iframe. `sandbox=""` disables scripts, forms, and same-origin
 * access, so the embedded (self-contained, theme-aware) report renders exactly as it downloads
 * while carrying zero execution risk. Collapsed by default (progressive disclosure).
 */
export interface ReportFrameProps {
  html: string;
  title: string;
}

export function ReportFrame({ html, title }: ReportFrameProps) {
  return (
    <details className="group cv-card overflow-hidden">
      <summary className="cursor-pointer list-none px-5 py-3 text-sm font-semibold text-ink marker:content-none">
        <span className="inline-block text-ink-muted transition-transform group-open:rotate-90">▸</span> Verbatim report document (<span className="font-mono text-xs">report_html</span>)
        <span className="ml-2 font-normal text-ink-muted">— the exact downloadable artifact, sandboxed</span>
      </summary>
      <div className="border-t border-line bg-surface">
        <iframe
          title={title}
          srcDoc={html}
          sandbox=""
          className="block h-[32rem] w-full border-0 bg-surface"
          loading="lazy"
        />
      </div>
    </details>
  );
}

export default ReportFrame;
