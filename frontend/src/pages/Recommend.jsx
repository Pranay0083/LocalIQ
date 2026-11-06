import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ArrowRight, LockKey, Sparkle } from "@phosphor-icons/react";
import { ModuleIcon } from "@/components/report/ModuleIcon";
import { useAuth } from "@/context/AuthContext";
import { api, errMessage, scoreTone, toneBg, toneClass } from "@/lib/api";

export default function Recommend() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [locked, setLocked] = useState(false);
  const [entitlement, setEntitlement] = useState(null);

  useEffect(() => {
    api.get("/entitlement").then((r) => {
      setEntitlement(r.data);
      setLocked(!r.data.can_recommend);
    }).catch(() => {});
  }, []);

  const run = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/recommend");
      setResult(data);
      const ent = await api.get("/entitlement");
      setEntitlement(ent.data);
    } catch (error) {
      const detail = error?.response?.data?.detail;
      if (detail?.code === "premium") { setLocked(true); toast.error(detail.message); }
      else toast.error(errMessage(error));
    } finally {
      setBusy(false);
    }
  };

  const profile = user?.profile || {};
  const hasProfile = Object.values(profile).some(Boolean);

  return (
    <div className="space-y-6 pb-16">
      <div>
        <h1 className="text-2xl font-semibold  text-zinc-100">
          Given who you are, where should you even look?
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-zinc-500">
          The agent scores Bengaluru localities against your persona weights using live air data and
          computed OpenStreetMap geometry, then ranks the shortlist and explains why. Web-research
          layers stay cached — this run costs almost nothing.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_300px]">
        <div>
          {!result && !busy ? (
            <div className="panel border border-zinc-900 bg-surface px-5 py-10 text-center" data-testid="recommend-empty">
              <Sparkle size={26} weight="duotone" className="mx-auto text-zinc-50" />
              <p className="mt-3 text-sm text-zinc-400">
                {hasProfile
                  ? "Your profile is set. Run the agent and it will rank localities for you."
                  : "You have not filled a profile yet — the agent will fall back to your persona defaults."}
              </p>
              {locked ? (
                <>
                  <div className="mx-auto mt-5 grid h-11 w-11 place-items-center border border-zinc-50/40 bg-zinc-50/10">
                    <LockKey size={20} weight="duotone" className="text-zinc-50" />
                  </div>
                  <p className="mt-3 text-sm text-zinc-400">
                    You have used your free recommendation run.
                  </p>
                  <button
                    data-testid="recommend-upgrade"
                    onClick={() => navigate("/app/account")}
                    className="mono mt-4 border border-primary bg-primary px-5 py-2.5 text-xs text-primary-foreground hover:bg-primary/90"
                  >
                    Upgrade for unlimited runs
                  </button>
                </>
              ) : (
                <button
                  data-testid="recommend-run"
                  onClick={run}
                  className="mono mt-5 inline-flex items-center gap-2 border border-primary bg-primary px-5 py-3 text-xs text-primary-foreground transition-colors hover:bg-primary/90"
                >
                  <Sparkle size={13} weight="duotone" /> Rank localities for me
                </button>
              )}
            </div>
          ) : null}

          {busy ? (
            <p className="mono py-14 text-center text-xs text-zinc-600 caret">
              scoring candidate localities
            </p>
          ) : null}

          {result ? (
            <div className="space-y-3 lq-in" data-testid="recommend-result">
              {result.candidates.map((c, i) => {
                const pick = (result.narrative?.picks || []).find((p) => p.slug === c.slug);
                return (
                  <div key={c.slug} className="lift panel border border-zinc-900 bg-surface px-4 py-4"
                       data-testid={`recommend-card-${c.slug}`}>
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="mono grid h-6 w-6 shrink-0 place-items-center border border-zinc-50/50 text-xs text-zinc-50">
                            {i + 1}
                          </span>
                          <h3 className="truncate text-base font-medium text-zinc-100">{c.name}</h3>
                          <span className="overline border border-zinc-800 px-1.5 py-[2px] text-zinc-600">{c.zone}</span>
                        </div>
                        <p className="mt-1.5 text-xs leading-snug text-zinc-500">{c.blurb}</p>
                      </div>
                      <div className="shrink-0 text-right">
                        <p className={`mono text-3xl leading-none ${toneClass[scoreTone(c.score)]}`}>{c.score}</p>
                        <p className="mono text-xs text-zinc-600">base {c.baseline}</p>
                      </div>
                    </div>

                    {pick?.why ? (
                      <p className="mt-3 border-l-2 border-zinc-50/60 pl-3 text-sm leading-relaxed text-zinc-300">
                        {pick.why}
                      </p>
                    ) : null}
                    {pick?.watch ? (
                      <p className="mt-2 text-xs text-amber-300/80">Watch: {pick.watch}</p>
                    ) : null}

                    <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-5">
                      {c.top_modules.map((m) => (
                        <div key={m.module} className="border border-zinc-900 px-2 py-1.5">
                          <span className="flex items-center gap-1 text-zinc-600">
                            <ModuleIcon module={m.module} size={11} />
                            <span className="overline truncate">{m.label.split(" ")[0]}</span>
                          </span>
                          <div className="mt-1 h-[3px] w-full bg-zinc-900">
                            <div className={`h-full ${toneBg[scoreTone(m.score)]}`} style={{ width: `${m.score || 0}%` }} />
                          </div>
                          <p className="mono mt-1 text-xs text-zinc-400">{m.score ?? "—"}</p>
                        </div>
                      ))}
                    </div>

                    <button
                      data-testid={`recommend-open-${c.slug}`}
                      onClick={async () => {
                        try {
                          const { data } = await api.post("/reports/generate", { locality: c.slug });
                          if (data.cached) navigate(`/app/report/${data.report_id}`);
                          else navigate(`/app/generating/${data.job_id}`);
                        } catch (error) {
                          const detail = error?.response?.data?.detail;
                          if (detail?.code === "paywall") { toast.error(detail.message); navigate("/app/account"); }
                          else toast.error(errMessage(error));
                        }
                      }}
                      className="mono mt-3 inline-flex items-center gap-1.5 border border-zinc-800 px-3 py-1.5 text-xs text-zinc-400 transition-colors hover:border-zinc-50 hover:text-zinc-50"
                    >
                      Full report <ArrowRight size={11} />
                    </button>
                  </div>
                );
              })}
            </div>
          ) : null}
        </div>

        <aside className="space-y-3 lg:sticky lg:top-24 lg:self-start">
          <div className="panel border border-zinc-900 bg-surface px-4 py-3">
            <p className="overline text-zinc-600">Your inputs</p>
            <div className="mt-2 space-y-1">
              {Object.entries(profile).filter(([, v]) => v).map(([k, v]) => (
                <div key={k} className="flex items-start justify-between gap-2">
                  <span className="mono text-xs text-zinc-600">{k.replace(/_/g, " ")}</span>
                  <span className="max-w-[60%] text-right text-xs text-zinc-300">{String(v)}</span>
                </div>
              ))}
              {!hasProfile ? <p className="text-xs text-zinc-600">No profile saved.</p> : null}
            </div>
            <button
              data-testid="recommend-edit-profile"
              onClick={() => navigate("/onboarding")}
              className="mono mt-3 w-full border border-zinc-800 py-2 text-xs text-zinc-500 hover:border-zinc-50 hover:text-zinc-50"
            >
              Edit profile
            </button>
          </div>

          {result?.narrative?.reasoning ? (
            <div className="panel border border-zinc-900 bg-surface px-4 py-3">
              <p className="overline text-zinc-600">How it ranked</p>
              <p className="mt-2 text-xs leading-relaxed text-zinc-400">{result.narrative.reasoning}</p>
              {result.narrative.ignored ? (
                <p className="mt-2 border-t border-zinc-900 pt-2 text-xs text-zinc-600">
                  Not addressed by the data: {result.narrative.ignored}
                </p>
              ) : null}
              <p className="mono mt-2 text-xs text-zinc-700">{result.evaluated} localities evaluated</p>
            </div>
          ) : null}

          <div className="panel border border-zinc-900 bg-surface px-4 py-3">
            <p className="overline text-zinc-600">Runs</p>
            <p className="mono mt-1 text-2xl text-zinc-200">
              {entitlement?.pro ? "unlimited" : `${Math.max(0, 1 - (entitlement?.recommend_runs || 0))} free left`}
            </p>
          </div>
        </aside>
      </div>
    </div>
  );
}
