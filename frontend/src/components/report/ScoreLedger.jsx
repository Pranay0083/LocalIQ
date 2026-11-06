

export const ScoreLedger = ({ cards }) => {
  const rows = [...cards].sort((a, b) => (b.weight || 0) - (a.weight || 0) || (b.score ?? -1) - (a.score ?? -1));
  return (
    <section className="rounded-lg border border-zinc-900 bg-surface" data-testid="score-ledger">
      <div className="flex flex-wrap items-baseline justify-between gap-2 px-5 pb-2 pt-4">
        <h2 className="text-base font-semibold text-zinc-50">Score ledger</h2>
        <p className="flex items-center gap-2 text-sm text-zinc-500">
          <span className="inline-block h-3 w-px bg-zinc-50" /> Bengaluru median across {rows.find((r) => r.city)?.city?.n ?? 34} localities
        </p>
      </div>
      <div className="grid grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-x-4 px-5 pb-3 text-xs text-zinc-500 sm:grid-cols-[minmax(0,180px)_minmax(0,1fr)_auto_auto]">
        <span>Module · weight</span>
        <span className="hidden sm:block" />
        <span className="text-right">Score</span>
        <span className="w-12 text-right">vs city</span>
      </div>
      <ul>
        {rows.map((c) => {
          const score = c.score == null ? null : Math.round(c.score);
          const median = c.city?.city_median;
          const delta = c.city?.delta;
          const tone = delta == null || Math.abs(delta) < 5 ? "text-zinc-500" : delta > 0 ? "text-emerald-400" : "text-red-400";
          return (
            <li key={c.module} className="grid grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-x-4 border-t border-zinc-900/70 px-5 py-2.5 sm:grid-cols-[minmax(0,180px)_minmax(0,1fr)_auto_auto]">
              <span className="min-w-0 truncate text-sm text-zinc-50">
                {c.title} <span className="mono text-zinc-600">×{c.weight}</span>
              </span>
              <span className="relative col-span-3 row-start-2 mt-1.5 h-1.5 rounded-full bg-secondary sm:col-span-1 sm:row-start-auto sm:mt-0">
                {score != null ? <span className="absolute inset-y-0 left-0 rounded-full bg-data" style={{ width: `${score}%` }} /> : null}
                {median != null ? <span className="absolute -inset-y-1 w-px bg-zinc-50" style={{ left: `${median}%` }} /> : null}
              </span>
              <span className={`mono text-right text-sm ${score == null ? "text-zinc-600" : "text-zinc-50"}`}>{score ?? "—"}</span>
              <span className={`mono w-12 text-right text-sm ${tone}`}>
                {delta == null ? "—" : `${delta > 0 ? "+" : ""}${Math.round(delta)}`}
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
};
