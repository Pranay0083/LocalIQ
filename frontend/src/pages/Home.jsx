import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ArrowRight, Broadcast, MagnifyingGlass, Sparkle } from "@phosphor-icons/react";
import { useAuth } from "@/context/AuthContext";
import { api, errMessage, fmtDate } from "@/lib/api";

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

  const warmCount = localities.filter((l) => l.warm).length;

  return (
    <div className="space-y-10">
      <section className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <div>
          <h1 className="text-2xl font-semibold text-zinc-50">Which locality are you weighing up?</h1>
          <p className="mt-1 text-sm text-zinc-500">
            {localities.length} Bengaluru localities · {warmCount} cached, so their reports open in seconds
          </p>
          <div className="relative mt-5">
            <MagnifyingGlass size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-600" />
            <label htmlFor="locality-search" className="sr-only">Search localities</label>
            <input
              id="locality-search"
              data-testid="locality-search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Koramangala 4th Block, 560034, Whitefield…"
              className="h-10 w-full rounded-md border border-zinc-800 bg-surface pl-9 pr-3 text-sm text-zinc-50 outline-none transition-colors placeholder:text-zinc-600 focus:border-zinc-50"
            />
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <label htmlFor="home-persona-select" className="text-sm text-zinc-500">Scoring lens</label>
            <select
              id="home-persona-select"
              data-testid="home-persona-select"
              value={persona}
              onChange={(e) => setPersona(e.target.value)}
              className="btn pr-2"
            >
              {personas.map((p) => (
                <option key={p.key} value={p.key}>{p.label}</option>
              ))}
            </select>
            {activePersona ? (
              <span className="text-sm text-zinc-500">{activePersona.modules.length} of 20 modules scored for this lens</span>
            ) : null}
          </div>
        </div>

        <div className="self-start rounded-lg border border-zinc-900 bg-surface">
          <div className="grid grid-cols-2 divide-x divide-zinc-900">
            <div className="px-5 py-4">
              <p className="overline">Reports left</p>
              <p className="mono mt-1 text-2xl text-zinc-50" data-testid="home-reports-left">
                {entitlement?.pro ? "Unlimited" : entitlement?.free_left ?? "—"}
              </p>
            </div>
            <div className="px-5 py-4">
              <p className="overline">Earned credits</p>
              <p className={`mono mt-1 text-2xl ${entitlement?.credits ? "text-zinc-50" : "text-zinc-600"}`} data-testid="home-credits">
                {entitlement?.credits ?? 0}
              </p>
            </div>
          </div>
          <p className="border-t border-zinc-900 px-5 py-3 text-sm leading-snug text-zinc-500">
            Re-opening a report is free. Regenerating spends one, because it re-runs live collection.
          </p>
        </div>
      </section>

      {reports.length ? (
        <section className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
          <div className="rounded-lg border border-zinc-900 bg-surface">
            <div className="flex items-baseline justify-between px-5 pb-2 pt-4">
              <h2 className="text-base font-semibold text-zinc-50">Your reports</h2>
              <span className="hidden text-xs text-zinc-500 sm:inline">
                {reports.length} report{reports.length === 1 ? "" : "s"} · score for you, then neutral baseline
              </span>
            </div>
            <ul>
              {reports.slice(0, 4).map((r) => (
                <li key={r.id}>
                  <button
                    data-testid={`recent-report-${r.locality_slug}`}
                    onClick={() => navigate(`/app/report/${r.id}`)}
                    className="flex w-full items-center gap-4 border-t border-zinc-900/70 px-5 py-3 text-left transition-colors hover:bg-surface2"
                  >
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium text-zinc-50">{r.locality?.name}</span>
                      <span className="mono block truncate text-xs text-zinc-500">
                        {r.persona_label} · {fmtDate(r.created_at)}
                      </span>
                    </span>
                    <span className="mono w-10 text-right text-xl font-semibold text-data">{r.composite?.score ?? "—"}</span>
                    <span className="mono w-10 text-right text-sm text-zinc-500">{r.baseline_composite?.score ?? "—"}</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
          <div className="flex flex-col rounded-lg border border-zinc-900 bg-surface px-5 py-4">
            <h2 className="text-base font-semibold text-zinc-50">Not sure where to look?</h2>
            <p className="mt-1 text-sm leading-snug text-zinc-500">
              Tell the recommendation agent your budget, commute and household, and it ranks localities
              against the same rubric. Every pick links to its full, cited report.
            </p>
            <dl className="mt-3 mb-4 space-y-1.5 text-sm">
              {[
                ["Household", user?.profile?.household],
                ["Works in", user?.profile?.work_locality],
                ["Budget", user?.profile?.budget_band],
                ["Commute", user?.profile?.commute_tolerance ? `up to ${user.profile.commute_tolerance} min` : null],
              ].map(([k, v]) => (
                <div key={k} className="flex justify-between gap-3">
                  <dt className="text-zinc-500">{k}</dt>
                  <dd className="text-zinc-50">
                    {v ? String(v).replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase()) : "—"}
                  </dd>
                </div>
              ))}
            </dl>
            <button data-testid="home-recommend-link" onClick={() => navigate("/app/recommend")} className="btn mt-auto self-start">
              <Sparkle size={16} /> Get a shortlist
            </button>
          </div>
        </section>
      ) : null}

      <section>
        <div className="mb-3 flex items-baseline justify-between">
          <h2 className="text-base font-semibold text-zinc-50">
            {query ? `${filtered.length} match${filtered.length === 1 ? "" : "es"}` : "All Bengaluru localities"}
          </h2>
          {activePersona ? <span className="text-xs text-zinc-500">Reports build for {activePersona.label.toLowerCase()}</span> : null}
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {filtered.map((l) => (
            <div key={l.slug} className="lift flex flex-col rounded-lg border border-zinc-900 bg-surface px-4 py-4"
                 data-testid={`locality-card-${l.slug}`}>
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <h3 className="truncate text-sm font-semibold text-zinc-50">{l.name}</h3>
                  <p className="mono mt-0.5 text-xs text-zinc-500">
                    {l.pincode} · {l.zone}
                  </p>
                </div>
                {!l.warm ? (
                  <span className="shrink-0 rounded bg-secondary px-1.5 py-0.5 text-[11px] font-medium text-zinc-500">Not cached · full run</span>
                ) : null}
              </div>
              <p className="mt-2 flex-1 text-sm leading-snug text-zinc-500">{l.blurb}</p>
              <button
                data-testid={`generate-${l.slug}`}
                disabled={busySlug === l.slug}
                onClick={() => generate(l.slug)}
                className="mt-3 inline-flex items-center gap-1.5 self-start text-sm font-medium text-zinc-50 hover:underline disabled:text-zinc-600"
              >
                {busySlug === l.slug ? "Starting…" : "Build report"}
                <ArrowRight size={14} />
              </button>
            </div>
          ))}
        </div>
        {!filtered.length ? (
          <div className="rounded-lg border border-dashed border-zinc-800 px-5 py-8 text-center" data-testid="no-locality-match">
            <Broadcast size={20} className="mx-auto text-zinc-600" />
            <p className="mt-2 text-sm text-zinc-500">
              LocalIQ covers Bengaluru only right now. Nothing matched “{query}”.
            </p>
          </div>
        ) : null}
      </section>
    </div>
  );
}
