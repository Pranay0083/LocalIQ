import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { GitDiff, LockKey, Sparkle, X } from "@phosphor-icons/react";
import { useTheme } from "next-themes";
import { ModuleIcon } from "@/components/ModuleIcon";
import { api, errMessage, scoreTone, toneClass } from "@/lib/api";

const PALETTE = {
  light: ["#4f46e5", "#0d9488", "#c2410c"],
  dark: ["#818cf8", "#2dd4bf", "#fbbf24"],
};

export default function Compare() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { resolvedTheme } = useTheme();
  const dark = resolvedTheme === "dark";
  const COLORS = dark ? PALETTE.dark : PALETTE.light;
  const axisStyle = { fontSize: 10, fill: dark ? "#a1a1aa" : "#64748b", fontFamily: "IBM Plex Mono" };
  const gridStroke = dark ? "#27272a" : "#e2e8f0";
  const [localities, setLocalities] = useState([]);
  const [personas, setPersonas] = useState([]);
  const [selected, setSelected] = useState([]);
  const [persona, setPersona] = useState("");
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [locked, setLocked] = useState(false);
  const [entitlement, setEntitlement] = useState(null);

  useEffect(() => {
    api.get("/localities").then((r) => setLocalities(r.data)).catch(() => {});
    api.get("/personas").then((r) => setPersonas(r.data)).catch(() => {});
    api.get("/entitlement").then((r) => {
      setEntitlement(r.data);
      setLocked(!r.data.can_compare);
    }).catch(() => {});
    const a = params.get("a");
    if (a) setSelected([a]);
  }, [params]);

  const toggle = (slug) => {
    setSelected((s) => {
      if (s.includes(slug)) return s.filter((x) => x !== slug);
      if (s.length >= 3) { toast.error("Compare up to 3 localities at a time"); return s; }
      return [...s, slug];
    });
  };

  const run = async () => {
    if (selected.length < 2) return toast.error("Pick at least 2 localities");
    setBusy(true);
    try {
      const { data } = await api.post("/compare", {
        slugs: selected, persona_key: persona || undefined,
      });
      setResult(data);
    } catch (error) {
      const detail = error?.response?.data?.detail;
      if (detail?.code === "premium") { setLocked(true); toast.error(detail.message); }
      else toast.error(errMessage(error));
    } finally {
      setBusy(false);
    }
  };

  const chartData = useMemo(() => {
    if (!result) return [];
    return result.modules.map((m) => {
      const row = { label: m.label.length > 14 ? `${m.label.slice(0, 13)}…` : m.label };
      result.localities.forEach((l) => { row[l.slug] = l.modules[m.key] ?? 0; });
      return row;
    });
  }, [result]);

  if (locked) {
    return (
      <div className="mx-auto max-w-2xl py-14 text-center" data-testid="compare-locked">
        <div className="mx-auto grid h-14 w-14 place-items-center border border-indigo-500/40 bg-indigo-500/10">
          <LockKey size={24} weight="duotone" className="text-indigo-400" />
        </div>
        <h1 className="mt-5 font-[Outfit] text-3xl font-light tracking-tight text-zinc-100">
          Side-by-side comparison is Pro
        </h1>
        <p className="mx-auto mt-3 max-w-md text-sm leading-relaxed text-zinc-500">
          Comparison re-runs the scorer against every shortlisted locality under your persona weights,
          then has the comparator agent argue the trade-off. It is the most expensive thing LocalIQ
          does, so it sits behind the paywall.
        </p>
        <div className="grid-skeleton mx-auto mt-7 grid max-w-md grid-cols-3 border-b border-r border-zinc-900">
          {[["Reports used", entitlement?.used ?? 0], ["Free left", entitlement?.free_left ?? 0], ["Credits", entitlement?.credits ?? 0]].map(([l, v]) => (
            <div key={l} className="px-3 py-2.5">
              <p className="mono text-xl text-zinc-200">{v}</p>
              <p className="overline text-zinc-600">{l}</p>
            </div>
          ))}
        </div>
        <button
          data-testid="compare-upgrade"
          onClick={() => navigate("/app/account")}
          className="mono mt-6 border border-indigo-500 bg-indigo-600 px-5 py-3 text-[11px] uppercase tracking-wider text-white transition-colors hover:bg-indigo-500"
        >
          See Pro plans
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-16">
      <div>
        <p className="overline text-indigo-400">Premium · comparator agent</p>
        <h1 className="mt-2 font-[Outfit] text-3xl font-light tracking-tight text-zinc-100">
          Put your shortlist next to each other
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-zinc-500">
          Pick 2–3 Bengaluru localities. Every module is re-scored under the same persona weights so
          the numbers are actually comparable, and the agent argues the real trade-off.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <span className="overline text-zinc-600">Lens</span>
        <select
          data-testid="compare-persona"
          value={persona}
          onChange={(e) => setPersona(e.target.value)}
          className="mono border border-zinc-800 bg-zinc-950 px-2 py-1.5 text-[11px] text-indigo-300 outline-none focus:border-indigo-500"
        >
          <option value="">My saved persona</option>
          {personas.map((p) => <option key={p.key} value={p.key}>{p.label}</option>)}
        </select>
        <div className="ml-auto flex items-center gap-2">
          {selected.map((s, i) => (
            <span key={s} className="mono inline-flex items-center gap-1 border px-2 py-1 text-[10px]"
                  style={{ borderColor: COLORS[i], color: COLORS[i] }}>
              {localities.find((l) => l.slug === s)?.name || s}
              <button onClick={() => toggle(s)} data-testid={`compare-remove-${s}`}><X size={10} /></button>
            </span>
          ))}
          <button
            data-testid="compare-run"
            disabled={busy || selected.length < 2}
            onClick={run}
            className="mono inline-flex items-center gap-1.5 border border-indigo-500 bg-indigo-600 px-4 py-2 text-[11px] uppercase tracking-wider text-white transition-colors hover:bg-indigo-500 disabled:opacity-40"
          >
            <GitDiff size={13} /> {busy ? "Comparing…" : "Compare"}
          </button>
        </div>
      </div>

      <div className="grid-skeleton grid max-h-64 overflow-y-auto border-b border-r border-zinc-900 sm:grid-cols-3 lg:grid-cols-5">
        {localities.map((l) => {
          const idx = selected.indexOf(l.slug);
          return (
            <button
              key={l.slug}
              data-testid={`compare-pick-${l.slug}`}
              onClick={() => toggle(l.slug)}
              className={`px-3 py-2.5 text-left transition-colors ${idx >= 0 ? "bg-indigo-500/10" : "bg-surface hover:bg-surface2"}`}
              style={idx >= 0 ? { boxShadow: `inset 3px 0 0 ${COLORS[idx]}` } : undefined}
            >
              <p className="truncate text-xs text-zinc-200">{l.name}</p>
              <p className="mono text-[9px] text-zinc-600">{l.zone}</p>
            </button>
          );
        })}
      </div>

      {busy ? (
        <p className="mono py-10 text-center text-xs uppercase tracking-[0.3em] text-zinc-600 caret">
          re-scoring each locality under your weights
        </p>
      ) : null}

      {result ? (
        <div className="space-y-5 lq-in" data-testid="compare-result">
          <div className="grid-skeleton grid border-b border-r border-zinc-900 sm:grid-cols-3">
            {result.localities.map((l, i) => (
              <div key={l.slug} className="px-4 py-4" style={{ boxShadow: `inset 0 3px 0 ${COLORS[i]}` }}
                   data-testid={`compare-col-${l.slug}`}>
                <p className="text-sm font-medium text-zinc-100">{l.name}</p>
                <p className="mono text-[10px] text-zinc-600">{l.zone} · {l.sources} sources</p>
                <div className="mt-2 flex items-end gap-3">
                  <div>
                    <p className={`mono text-4xl leading-none ${toneClass[scoreTone(l.score)]}`}>{l.score ?? "—"}</p>
                    <p className="overline text-zinc-600">persona</p>
                  </div>
                  <div>
                    <p className="mono text-2xl leading-none text-zinc-500">{l.baseline ?? "—"}</p>
                    <p className="overline text-zinc-700">baseline</p>
                  </div>
                </div>
                <p className="mt-2 text-[11px] leading-snug text-zinc-500">{l.narrative}</p>
              </div>
            ))}
          </div>

          <div className="panel border border-zinc-900 bg-surface p-4">
            <p className="overline mb-3 text-zinc-600">Module by module</p>
            <div className="h-[300px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 6, right: 6, left: -22, bottom: 40 }}>
                  <CartesianGrid stroke={gridStroke} strokeDasharray="2 4" vertical={false} />
                  <XAxis dataKey="label" tick={axisStyle} angle={-38} textAnchor="end" height={60} tickLine={false} axisLine={{ stroke: gridStroke }} />
                  <YAxis domain={[0, 100]} tick={axisStyle} tickLine={false} axisLine={false} width={40} />
                  <Tooltip contentStyle={{ background: dark ? "#131317" : "#ffffff", border: `1px solid ${gridStroke}`, borderRadius: 8, fontFamily: "IBM Plex Mono", fontSize: 11, color: dark ? "#fafafa" : "#111827" }} cursor={{ fill: "rgb(99 102 241 / 0.08)" }} />
                  <Legend wrapperStyle={{ fontSize: 10, fontFamily: "IBM Plex Mono" }} />
                  {result.localities.map((l, i) => (
                    <Bar key={l.slug} dataKey={l.slug} name={l.name} fill={COLORS[i]} radius={[2, 2, 0, 0]} />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="panel overflow-x-auto rounded-lg border border-zinc-900 bg-surface">
            <table className="w-full min-w-[520px] text-left" data-testid="compare-table">
              <thead>
                <tr className="border-b border-zinc-900">
                  <th className="overline sticky left-0 z-10 border-r border-zinc-900 bg-surface shadow-[6px_0_10px_-8px_rgb(15_23_42/0.35)] px-3 py-2 text-zinc-600">Module</th>
                  {result.localities.map((l, i) => (
                    <th key={l.slug} className="overline px-3 py-2" style={{ color: COLORS[i] }}>{l.name}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.modules.map((m) => {
                  const values = result.localities.map((l) => l.modules[m.key]);
                  const best = Math.max(...values.filter((v) => v !== null && v !== undefined));
                  return (
                    <tr key={m.key} className="border-b border-zinc-900/60" data-testid={`compare-row-${m.key}`}>
                      <td className="sticky left-0 z-10 border-r border-zinc-900 bg-surface shadow-[6px_0_10px_-8px_rgb(15_23_42/0.35)] px-3 py-2">
                        <span className="flex items-center gap-2 text-xs text-zinc-300">
                          <ModuleIcon module={m.key} size={14} className="text-zinc-600" /> {m.label}
                        </span>
                      </td>
                      {result.localities.map((l) => {
                        const v = l.modules[m.key];
                        return (
                          <td key={l.slug} className="px-3 py-2">
                            <span className={`mono text-sm ${v === best && v !== null ? "text-emerald-400" : v === null || v === undefined ? "text-zinc-700" : "text-zinc-300"}`}>
                              {v ?? "no data"}
                            </span>
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="border border-indigo-900/60 bg-indigo-950/10 px-5 py-5" data-testid="compare-verdict">
            <p className="overline flex items-center gap-1.5 text-indigo-400">
              <Sparkle size={12} weight="duotone" /> Comparator verdict
            </p>
            <p className="mt-2 text-sm leading-relaxed text-zinc-200">{result.verdict?.verdict}</p>
            {result.verdict?.tradeoff ? (
              <p className="mt-3 border-l-2 border-indigo-500/60 pl-3 text-sm text-zinc-400">
                <span className="text-zinc-200">The real trade-off:</span> {result.verdict.tradeoff}
              </p>
            ) : null}
            <div className="mt-4 grid gap-3 sm:grid-cols-3">
              {(result.verdict?.per_locality || []).map((p, i) => (
                <div key={p.slug || i} className="border border-zinc-900 px-3 py-2.5">
                  <p className="text-xs font-medium text-zinc-200">
                    {result.localities.find((l) => l.slug === p.slug)?.name || p.slug}
                  </p>
                  <p className="overline mt-1.5 text-emerald-400">wins</p>
                  {(p.wins || []).map((w, k) => <p key={k} className="text-[11px] text-zinc-400">· {w}</p>)}
                  <p className="overline mt-1.5 text-amber-400">loses</p>
                  {(p.loses || []).map((w, k) => <p key={k} className="text-[11px] text-zinc-400">· {w}</p>)}
                  {p.best_for ? <p className="mt-2 text-[10px] text-zinc-600">Best for: {p.best_for}</p> : null}
                </div>
              ))}
            </div>
            {result.verdict?.decider ? (
              <p className="mt-4 text-xs text-zinc-400">
                <span className="text-zinc-200">Answer this and it's settled:</span> {result.verdict.decider}
              </p>
            ) : null}
            {result.verdict?.cannot_tell ? (
              <p className="mt-2 text-[11px] text-zinc-600">What this cannot tell you: {result.verdict.cannot_tell}</p>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}
