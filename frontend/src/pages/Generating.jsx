import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { api } from "@/lib/api";

const AGENT_COLOR = (agent) => {
  if (agent.startsWith("collector")) return "text-cyan-300";
  if (agent === "intake") return "text-indigo-300";
  if (agent === "verifier") return "text-amber-300";
  if (agent === "scorer") return "text-emerald-300";
  if (agent === "synthesizer") return "text-violet-300";
  if (agent === "presenter") return "text-pink-300";
  return "text-zinc-400";
};

const STAGES = [
  ["intake", "Intake / Router"],
  ["collector:air", "Air quality"],
  ["collector:geo", "Geodata"],
  ["collector:safety", "Safety & news"],
  ["collector:civic", "Water & power"],
  ["collector:infra", "Infrastructure"],
  ["collector:chatter", "Reputation"],
  ["collector:community", "Community"],
  ["verifier", "Verifier"],
  ["scorer", "Scorer"],
  ["synthesizer", "Synthesizer"],
  ["presenter", "Presenter"],
];

export default function Generating() {
  const { jobId } = useParams();
  const navigate = useNavigate();
  const [job, setJob] = useState(null);
  const [elapsed, setElapsed] = useState(0);
  const endRef = useRef(null);

  useEffect(() => {
    const tick = setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => clearInterval(tick);
  }, []);

  useEffect(() => {
    let alive = true;
    const poll = async () => {
      try {
        const { data } = await api.get(`/reports/job/${jobId}`);
        if (!alive) return;
        setJob(data);
        if (data.status === "done" && data.report_id) {
          setTimeout(() => navigate(`/app/report/${data.report_id}`, { replace: true }), 900);
          return;
        }
        if (data.status === "failed") {
          toast.error("Report generation failed. Nothing was charged for a failed run.");
          return;
        }
      } catch {
        /* keep polling */
      }
      if (alive) setTimeout(poll, 1400);
    };
    poll();
    return () => { alive = false; };
  }, [jobId, navigate]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [job?.trace?.length]);

  const trace = job?.trace || [];
  const seen = new Set(trace.map((t) => t.agent));
  const doneAgents = new Set(trace.filter((t) => t.status !== "running").map((t) => t.agent));
  const urlCount = trace.reduce((n, t) => n + (t.meta?.urls?.length || 0), 0);

  return (
    <div className="mx-auto max-w-5xl">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="overline text-indigo-400">Multi-agent run in progress</p>
          <h1 className="mt-2 font-[Outfit] text-3xl font-light tracking-tight text-zinc-100">
            {job?.locality_name || "Resolving locality"}
          </h1>
        </div>
        <div className="grid-skeleton grid grid-cols-3 border-b border-r border-zinc-900">
          {[
            ["elapsed", `${elapsed}s`],
            ["events", trace.length],
            ["pages read", urlCount],
          ].map(([l, v]) => (
            <div key={l} className="px-3 py-2">
              <p className="overline text-zinc-600">{l}</p>
              <p className="mono text-lg text-zinc-100">{v}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-[240px_minmax(0,1fr)]">
        <aside className="space-y-1">
          {STAGES.map(([key, label]) => {
            const started = seen.has(key);
            const finished = doneAgents.has(key);
            const failed = trace.some((t) => t.agent === key && t.status === "failed");
            return (
              <div
                key={key}
                data-testid={`stage-${key.replace(":", "-")}`}
                className={`relative flex items-center gap-2 overflow-hidden border px-2.5 py-1.5 ${
                  failed
                    ? "border-red-900/60 bg-red-950/20"
                    : finished
                      ? "border-emerald-900/60 bg-emerald-950/10"
                      : started
                        ? "border-indigo-800/60 bg-indigo-950/20"
                        : "border-zinc-900"
                }`}
              >
                <span
                  className={`h-1.5 w-1.5 shrink-0 ${
                    failed ? "bg-red-500" : finished ? "bg-emerald-500" : started ? "bg-indigo-400" : "bg-zinc-800"
                  }`}
                />
                <span className={`mono text-[10px] uppercase tracking-wider ${started ? "text-zinc-300" : "text-zinc-700"}`}>
                  {label}
                </span>
                {started && !finished ? <span className="scan absolute inset-0" /> : null}
              </div>
            );
          })}
        </aside>

        <div className="dark panel min-w-0 overflow-hidden rounded-xl border border-zinc-900 bg-zinc-950">
          <div className="flex items-center gap-2 border-b border-zinc-900 px-3 py-2">
            <span className="h-2 w-2 rounded-full bg-red-500/70" />
            <span className="h-2 w-2 rounded-full bg-amber-500/70" />
            <span className="h-2 w-2 rounded-full bg-emerald-500/70" />
            <span className="mono ml-2 text-[10px] text-zinc-600">
              localiq · langgraph · job {String(jobId).slice(0, 8)}
            </span>
            <span className={`mono ml-auto text-[10px] ${job?.status === "failed" ? "text-red-400" : "text-emerald-400"}`}>
              {job?.status || "connecting"}
            </span>
          </div>
          <div className="max-h-[520px] min-h-[380px] space-y-1 overflow-y-auto p-3" data-testid="generation-terminal">
            {!trace.length ? (
              <p className="mono text-xs text-zinc-600 caret">waiting for first agent event</p>
            ) : null}
            {trace.map((t, i) => (
              <div key={i} className="lq-in flex gap-2" data-testid={`trace-line-${i}`}>
                <span className="mono shrink-0 text-[10px] text-zinc-700">
                  {new Date(t.t).toLocaleTimeString("en-IN", { hour12: false })}
                </span>
                <span className={`mono shrink-0 text-[10px] ${AGENT_COLOR(t.agent)}`}>
                  [{t.agent}]
                </span>
                <span className={`mono text-[11px] leading-snug ${t.status === "failed" ? "text-red-400" : "text-zinc-300"}`}>
                  {t.message}
                  {t.meta?.queries?.length ? (
                    <span className="mt-0.5 block text-[10px] text-zinc-600">
                      queries: {t.meta.queries.slice(0, 3).join(" | ")}
                    </span>
                  ) : null}
                  {t.meta?.urls?.length ? (
                    <span className="mt-0.5 block space-x-2 text-[10px]">
                      {t.meta.urls.slice(0, 4).map((u, k) => (
                        <a key={k} href={u} target="_blank" rel="noreferrer" className="text-cyan-500 hover:underline">
                          {(() => { try { return new URL(u).hostname.replace("www.", ""); } catch { return "src"; } })()}
                        </a>
                      ))}
                    </span>
                  ) : null}
                </span>
              </div>
            ))}
            {job?.status === "running" ? (
              <p className="mono text-[11px] text-zinc-600 caret"> </p>
            ) : null}
            {job?.status === "done" ? (
              <p className="mono mt-2 text-[11px] text-emerald-400">
                done · opening report…
              </p>
            ) : null}
            {job?.status === "failed" ? (
              <div className="mt-3">
                <p className="mono text-[11px] text-red-400">run failed: {job.error}</p>
                <button
                  data-testid="generation-back"
                  onClick={() => navigate("/app")}
                  className="mono mt-2 border border-zinc-800 px-3 py-1.5 text-[10px] uppercase tracking-wider text-zinc-400 hover:border-zinc-600"
                >
                  Back to search
                </button>
              </div>
            ) : null}
            <div ref={endRef} />
          </div>
        </div>
      </div>

      <p className="mono mt-4 text-[10px] leading-relaxed text-zinc-700">
        Heavy collection runs once per locality and is shared across everyone. Layers that are still
        fresh are reused rather than re-fetched — that is why a warm locality returns in seconds and a
        cold one takes a minute.
      </p>
    </div>
  );
}
