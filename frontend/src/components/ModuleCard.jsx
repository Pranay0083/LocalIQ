import { useState } from "react";
import { CaretDown, PlusCircle, PushPin, X } from "@phosphor-icons/react";
import { CitationDrawer } from "@/components/Citation";
import { ModuleIcon } from "@/components/ModuleIcon";
import { Render } from "@/components/Renderers";
import { scoreTone, toneBg, toneClass } from "@/lib/api";

const CONFIDENCE_COPY = {
  high: "High confidence",
  medium: "Medium confidence",
  low: "Low confidence \u2014 thin data",
  none: "No data",
};

export const ModuleCard = ({ card, index, onContribute, onDrop, onPin, pinned, readOnly }) => {
  const [open, setOpen] = useState(index < 4);
  const tone = scoreTone(card.score);

  return (
    <section
      data-testid={`module-card-${card.module}`}
      className="lq-in panel min-w-0 overflow-hidden rounded-lg border border-zinc-900 bg-surface"
      style={{ animationDelay: `${Math.min(index, 8) * 45}ms` }}
    >
      <header className="flex items-start justify-between gap-3 border-b border-zinc-900 px-4 py-3">
        <button
          onClick={() => setOpen((v) => !v)}
          data-testid={`module-toggle-${card.module}`}
          className="flex min-w-0 flex-1 items-start gap-3 text-left"
        >
          <span className={`mt-0.5 ${toneClass[tone]}`}>
            <ModuleIcon module={card.module} size={20} />
          </span>
          <span className="min-w-0">
            <span className="flex flex-wrap items-center gap-2">
              <h3 className="text-base font-medium text-zinc-100">{card.title}</h3>
              <span className="overline border border-zinc-800 px-1.5 py-[2px] text-zinc-500">
                {card.tier}
              </span>
              <span className="overline text-zinc-700">weight {card.weight}</span>
            </span>
            <span className="mt-1 flex flex-wrap items-center gap-2">
              <span className={`mono text-[10px] ${card.score === null ? "text-zinc-600" : toneClass[tone]}`}>
                {CONFIDENCE_COPY[card.confidence] || card.confidence}
              </span>
              <span className="mono text-[10px] text-zinc-700">updated {card.freshness}</span>
              {card.city?.city_rank ? (
                <span className="mono text-[10px] text-zinc-600">{card.city.city_rank} of Bengaluru</span>
              ) : null}
            </span>
          </span>
        </button>

        <div className="flex shrink-0 items-center gap-2">
          <div className="text-right">
            <p className={`mono text-3xl font-semibold leading-none ${card.score === null ? "text-zinc-700" : "text-zinc-50"}`}>
              {card.score === null ? "\u2014" : Math.round(card.score)}
            </p>
            {card.city?.city_median !== undefined ? (
              <p className="mono mt-0.5 text-[10px] text-zinc-600" data-testid={`city-compare-${card.module}`}>
                city med {card.city.city_median}
                <span className={card.city.delta > 0 ? "text-emerald-500" : card.city.delta < 0 ? "text-red-500" : ""}>
                  {" "}{card.city.delta > 0 ? "+" : ""}{card.city.delta}
                </span>
              </p>
            ) : null}
          </div>
          {readOnly ? null : (
            <div className="flex flex-col gap-1">
              <button
                onClick={() => onPin?.(card.module)}
                data-testid={`module-pin-${card.module}`}
                title="Pin this module to the top"
                className={`border border-zinc-800 p-1 transition-colors hover:border-indigo-500/60 ${pinned ? "text-indigo-400" : "text-zinc-600"}`}
              >
                <PushPin size={12} weight={pinned ? "fill" : "regular"} />
              </button>
              <button
                onClick={() => onDrop?.(card.module)}
                data-testid={`module-drop-${card.module}`}
                title="Drop this module from my report"
                className="border border-zinc-800 p-1 text-zinc-600 transition-colors hover:border-red-500/60 hover:text-red-400"
              >
                <X size={12} />
              </button>
            </div>
          )}
          <button onClick={() => setOpen((v) => !v)} className="text-zinc-600">
            <CaretDown size={14} className={`transition-transform ${open ? "rotate-180" : ""}`} />
          </button>
        </div>
      </header>

      <div className="h-[2px] w-full bg-zinc-900">
        <div
          className={`h-full ${card.score === null ? "bg-zinc-800" : toneBg[tone]}`}
          style={{ width: `${card.score === null ? 0 : card.score}%`, transition: "width 700ms cubic-bezier(0.22,1,0.36,1)" }}
        />
      </div>

      {open ? (
        <div className="space-y-4 px-4 py-4">
          {card.narrative ? (
            <p className="border-l-2 border-indigo-500/50 pl-3 text-sm leading-relaxed text-zinc-300">
              {card.narrative}
            </p>
          ) : null}

          {card.empty ? (
            <div className="border border-dashed border-zinc-800 bg-surface2 px-4 py-4" data-testid={`module-empty-${card.module}`}>
              <p className="text-sm text-zinc-300">{card.empty.message}</p>
              {card.empty.missing?.length ? (
                <ul className="mt-2 space-y-1">
                  {card.empty.missing.map((m) => (
                    <li key={m} className="mono text-[11px] text-zinc-600">missing · {m}</li>
                  ))}
                </ul>
              ) : null}
              <button
                onClick={() => onContribute?.(card)}
                data-testid={`module-contribute-${card.module}`}
                className="mono mt-3 inline-flex items-center gap-1.5 border border-indigo-500/50 bg-indigo-500/10 px-3 py-1.5 text-[11px] text-indigo-300 transition-colors hover:bg-indigo-500/20"
              >
                <PlusCircle size={13} /> {card.empty.cta_label}
              </button>
            </div>
          ) : (
            (card.renders || []).map((block, i) => <Render key={i} block={block} />)
          )}

          <div className="flex flex-wrap items-center justify-between gap-2 border-t border-zinc-900 pt-3">
            <p className="max-w-[70%] text-[11px] leading-snug text-zinc-600">{card.reason}</p>
            <CitationDrawer citations={card.citations} testId={`citations-${card.module}`} />
          </div>

          {!card.empty && card.contribute && !readOnly ? (
            <button
              onClick={() => onContribute?.(card)}
              data-testid={`module-contribute-${card.module}`}
              className="mono inline-flex items-center gap-1.5 border border-zinc-800 px-3 py-1.5 text-[11px] text-zinc-400 transition-colors hover:border-indigo-500/50 hover:text-indigo-300"
            >
              <PlusCircle size={13} /> {card.contribute.cta}
            </button>
          ) : null}
        </div>
      ) : null}
    </section>
  );
};
