import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
  ArrowRight, Broadcast, Lightning, MagnifyingGlass, Sparkle, Warning,
} from "@phosphor-icons/react";
import { useAuth } from "@/context/AuthContext";
import { api, errMessage, fmtDate, scoreTone, toneClass } from "@/lib/api";

export default function Home() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [localities, setLocalities] = useState([]);
  const [reports, setReports] = useState([]);
  const [entitlement, setEntitlement] = useState(null);
  const [personas, setPersonas] = useState([]);
  const [persona, setPersona] = useState(user?.persona_key || "bachelor");
  const [busySlug, setBusySlug] = useState(null);

  const load = useCallback(async () => {
    const [loc, rep, ent, per] = await Promise.all([
      api.get("/localities"), api.get("/reports"), api.get("/entitlement"), api.get("/personas"),
    ]);
    setLocalities(loc.data);
    setReports(rep.data);
    setEntitlement(ent.data);
    setPersonas(per.data);
  }, []);

  useEffect(() => { load().catch(() => {}); }, [load]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return localities;
    return localities.filter(
      (l) => l.name.toLowerCase().includes(q) || l.pincode.includes(q) ||
             l.zone.toLowerCase().includes(q) || l.blurb.toLowerCase().includes(q)
    );
  }, [query, localities]);

  const generate = async (slug) => {
    setBusySlug(slug);
    try {
      const { data } = await api.post("/reports/generate", {
        locality: slug, persona_key: persona,
      });
      if (data.cached && data.report_id) {
        toast.success("You already have this report — opening it, free.");
        navigate(`/app/report/${data.report_id}`);
      } else {
        navigate(`/app/generating/${data.job_id}`);
      }
    } catch (error) {
      const detail = error?.response?.data?.detail;
      if (detail?.code === "paywall") {
        toast.error(detail.message);
        navigate("/app/account");
      } else {
        toast.error(errMessage(error));
      }
    } finally {
      setBusySlug(null);
    }
  };

  const activePersona = personas.find((p) => p.key === persona);

  return (
    <div className="space-y-8">
      <section className="grid gap-4 lg:grid-cols-[minmax(0,1.6fr)_1fr]">
        <div>
          <p className="overline text-indigo-400">Bengaluru · {localities.length} localities</p>
          <h1 className="mt-2 font-[Outfit] text-3xl font-light tracking-tight text-zinc-100 sm:text-4xl">
            Which locality are you weighing up?
          </h1>
          <div className="relative mt-5">
            <MagnifyingGlass size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-600" />
            <input
              data-testid="locality-search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Koramangala 4th Block, 560034, Whitefield…"
              className="mono w-full border border-zinc-800 bg-zinc-950 py-3 pl-9 pr-3 text-sm text-zinc-100 outline-none transition-colors placeholder:text-zinc-700 focus:border-indigo-500"
            />
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span className="overline text-zinc-600">Scoring lens</span>
            <select
              data-testid="home-persona-select"
              value={persona}
              onChange={(e) => setPersona(e.target.value)}
              className="mono border border-zinc-800 bg-zinc-950 px-2 py-1.5 text-[11px] text-indigo-300 outline-none focus:border-indigo-500"
            >
              {personas.map((p) => (
                <option key={p.key} value={p.key}>{p.label}</option>
              ))}
            </select>
            {activePersona ? (
              <span className="text-[11px] text-zinc-600">{activePersona.modules.length} modules will run</span>
            ) : null}
          </div>
        </div>

        <div className="grid-skeleton grid grid-cols-2 self-start border-b border-r border-zinc-900">
          <div className="px-4 py-3">
            <p className="overline text-zinc-600">Reports left</p>
            <p className="mono mt-1 text-3xl text-zinc-100" data-testid="home-reports-left">
              {entitlement?.pro ? "∞" : entitlement?.free_left ?? "—"}
            </p>
          </div>
          <div className="px-4 py-3">
            <p className="overline text-zinc-600">Earned credits</p>
            <p className="mono mt-1 text-3xl text-teal-300" data-testid="home-credits">
              {entitlement?.credits ?? 0}
            </p>
          </div>
          <div className="col-span-2 px-4 py-3">
            <p className="text-[11px] leading-snug text-zinc-500">
              Re-opening a report you already generated is always free. Regenerating spends one — it
              re-runs live collection and costs real money.
            </p>
          </div>
        </div>
      </section>

      {reports.length ? (
        <section>
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <p className="overline text-zinc-600">Your reports</p>
            <button
              data-testid="home-recommend-link"
              onClick={() => navigate("/app/recommend")}
              className="mono inline-flex items-center gap-1.5 text-[11px] text-indigo-400 hover:underline"
            >
              <Sparkle size={12} weight="duotone" /> Not sure where to look? Ask the agent
            </button>
          </div>
          <div className="grid-skeleton grid border-b border-r border-zinc-900 sm:grid-cols-2 lg:grid-cols-3">
            {reports.slice(0, 6).map((r) => (
              <button
                key={r.id}
                data-testid={`recent-report-${r.locality_slug}`}
                onClick={() => navigate(`/app/report/${r.id}`)}
                className="lift bg-surface px-4 py-3 text-left"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-zinc-100">{r.locality?.name}</p>
                    <p className="mono mt-0.5 text-[10px] text-zinc-600">
                      {r.persona_label} · {fmtDate(r.created_at)}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className={`mono text-2xl ${toneClass[scoreTone(r.composite?.score)]}`}>
                      {r.composite?.score ?? "—"}
                    </p>
                    <p className="mono text-[9px] text-zinc-600">base {r.baseline_composite?.score ?? "—"}</p>
                  </div>
                </div>
              </button>
            ))}
          </div>
        </section>
      ) : null}

      <section>
        <p className="overline mb-3 text-zinc-600">
          {query ? `${filtered.length} match${filtered.length === 1 ? "" : "es"}` : "All Bengaluru localities"}
        </p>
        <div className="grid-skeleton grid border-b border-r border-zinc-900 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {filtered.map((l) => (
            <div key={l.slug} className="lift group flex flex-col bg-surface px-4 py-4"
                 data-testid={`locality-card-${l.slug}`}>
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <h3 className="truncate text-sm font-medium text-zinc-100">{l.name}</h3>
                  <p className="mono mt-0.5 text-[10px] text-zinc-600">
                    {l.pincode} · {l.zone}
                  </p>
                </div>
                {l.warm ? (
                  <span className="overline inline-flex shrink-0 items-center gap-1 border border-emerald-500/40 px-1.5 py-[2px] text-emerald-300">
                    <Lightning size={9} weight="fill" /> warm
                  </span>
                ) : (
                  <span className="overline inline-flex shrink-0 items-center gap-1 border border-zinc-800 px-1.5 py-[2px] text-zinc-600">
                    <Warning size={9} /> cold
                  </span>
                )}
              </div>
              <p className="mt-2 flex-1 text-[11px] leading-snug text-zinc-500">{l.blurb}</p>
              <button
                data-testid={`generate-${l.slug}`}
                disabled={busySlug === l.slug}
                onClick={() => generate(l.slug)}
                className="mono mt-3 inline-flex items-center justify-between border border-zinc-800 px-3 py-2 text-[11px] uppercase tracking-wider text-zinc-400 transition-colors hover:border-indigo-500 hover:bg-indigo-500/10 hover:text-indigo-300 disabled:opacity-40"
              >
                {busySlug === l.slug ? "Starting…" : "Build report"}
                <ArrowRight size={12} />
              </button>
            </div>
          ))}
        </div>
        {!filtered.length ? (
          <div className="border border-dashed border-zinc-800 px-5 py-8 text-center" data-testid="no-locality-match">
            <Broadcast size={20} className="mx-auto text-zinc-700" />
            <p className="mt-2 text-sm text-zinc-400">
              LocalIQ covers Bengaluru only right now. Nothing matched “{query}”.
            </p>
          </div>
        ) : null}
      </section>
    </div>
  );
}
