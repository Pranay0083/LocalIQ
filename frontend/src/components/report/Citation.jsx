import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { ArrowSquareOut, Info } from "@phosphor-icons/react";
import { SOURCE_META, fmtDate } from "@/lib/api";

const hostOf = (url) => {
  try {
    return new URL(url).hostname.replace("www.", "");
  } catch {
    return "source";
  }
};

export const SourceBadge = ({ type, className = "" }) => {
  const meta = SOURCE_META[type] || SOURCE_META.forum;
  return (
    <span
      data-testid={`source-badge-${type}`}
      className={`overline inline-flex items-center border px-1.5 py-[3px] leading-none ${meta.cls} ${className}`}
    >
      {meta.label}
    </span>
  );
};

export const CitationDrawer = ({ citations = [], label = "sources", testId }) => {
  if (!citations.length) return null;
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          data-testid={testId || "citation-trigger"}
          className="mono inline-flex items-center gap-1 border border-zinc-800 bg-surface2 px-2 py-[3px] text-xs text-zinc-400 transition-colors hover:border-zinc-50/60 hover:text-zinc-50"
        >
          <Info size={11} weight="bold" />
          {citations.length} {label}
        </button>
      </PopoverTrigger>
      <PopoverContent
        align="end"
        className="w-[360px] max-h-[420px] overflow-y-auto border-zinc-800 bg-zinc-950 p-0"
        data-testid="citation-drawer"
      >
        <div className="border-b border-zinc-800 px-3 py-2">
          <p className="overline text-zinc-500">Where every number came from</p>
        </div>
        <div className="divide-y divide-zinc-900">
          {citations.map((c, i) => (
            <div key={i} className="px-3 py-2.5" data-testid={`citation-item-${i}`}>
              <p className="text-sm font-medium text-zinc-200">{c.label}</p>
              <p className="mono mt-0.5 break-words text-sm text-zinc-100">
                {c.value === null || c.value === undefined ? "\u2014" : String(c.value)}
                {c.unit ? <span className="text-zinc-500"> {c.unit}</span> : null}
              </p>
              <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                <SourceBadge type={c.source_type} />
                <span className="mono text-xs text-zinc-500">
                  conf: {c.confidence || "n/a"}
                </span>
                {c.observed_at ? (
                  <span className="mono text-xs text-zinc-600">{fmtDate(c.observed_at)}</span>
                ) : null}
              </div>
              <p className="mt-1 text-sm leading-snug text-zinc-500">{c.source_name}</p>
              {c.note ? (
                <p className="mt-1 text-sm leading-snug text-zinc-500">{c.note}</p>
              ) : null}
              {c.source_url ? (
                <a
                  href={c.source_url}
                  target="_blank"
                  rel="noreferrer"
                  data-testid={`citation-link-${i}`}
                  className="mono mt-1.5 inline-flex items-center gap-1 text-xs text-zinc-50 underline-offset-2 hover:underline"
                >
                  <ArrowSquareOut size={11} /> {hostOf(c.source_url)}
                </a>
              ) : null}
            </div>
          ))}
        </div>
      </PopoverContent>
    </Popover>
  );
};
