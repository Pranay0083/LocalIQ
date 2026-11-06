import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { api } from "@/lib/api";

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
    // Follow the newest event inside the log only; never scroll the page out from under the title.
    const log = endRef.current?.parentElement;
    if (log) log.scrollTo({ top: log.scrollHeight, behavior: "smooth" });
  }, [job?.trace?.length]);

  const trace = job?.trace || [];
  const seen = new Set(trace.map((t) => t.agent));
  const doneAgents = new Set(trace.filter((t) => t.status !== "running").map((t) => t.agent));
  const urlCount = trace.reduce((n, t) => n + (t.meta?.urls?.length || 0), 0);

  const statusLabel = job?.status === "done" ? "Done" : job?.status === "failed" ? "Failed" : job ? "Running" : "Connecting";

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-zinc-50">{job?.locality_name || "Resolving locality"}</h1>
          <p className="mt-1 text-sm text-zinc-500">
            Agent run · {job?.persona_key ? `${job.persona_key.replace(/_/g, " ")} lens · ` : ""}
            <span className="code">job {String(jobId).slice(0, 8)}</span> ·{" "}
            <span className={job?.status === "failed" ? "text-red-400" : "text-zinc-50"}>{statusLabel}</span>
          </p>
        </div>
        <div className="grid grid-cols-3 divide-x divide-zinc-900 rounded-lg border border-zinc-900 bg-surface">
          {[
            ["Elapsed", `${elapsed} s`],
            ["Agent events", trace.length],
            ["Pages read", urlCount],
          ].map(([l, v]) => (
            <div key={l} className="min-w-[104px] px-4 py-2.5">
              <p className="overline">{l}</p>
              <p className="mono text-lg text-zinc-50">{v}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-[260px_minmax(0,1fr)]">
        <section className="self-start rounded-lg border border-zinc-900 bg-surface py-2" aria-label="Pipeline">
          <h2 className="px-4 pb-1 pt-2 text-sm font-semibold text-zinc-50">Pipeline</h2>
          <ol>
            {STAGES.map(([key, label]) => {
              const started = seen.has(key);
              const finished = doneAgents.has(key);
              const failed = trace.some((t) => t.agent === key && t.status === "failed");
              const state = failed ? "Absent" : finished ? "Done" : started ? "Running" : "Waiting";
              return (
                <li
                  key={key}
                  data-testid={`stage-${key.replace(":", "-")}`}
                  className="relative flex items-center gap-3 overflow-hidden px-4 py-1.5"
                >
                  <span
                    className={`h-1.5 w-1.5 shrink-0 rounded-full ${
                      failed ? "bg-red-500" : finished ? "bg-zinc-50" : started ? "bg-data" : "bg-zinc-800"
                    }`}
                  />
                  <span className={`flex-1 text-sm ${started ? "text-zinc-50" : "text-zinc-600"}`}>{label}</span>
                  <span className={`text-xs ${failed ? "text-red-400" : started && !finished ? "text-data" : "text-zinc-500"}`}>
                    {state}
                  </span>
                  {started && !finished ? <span className="scan absolute inset-x-0 bottom-0 h-px" /> : null}
                </li>
              );
            })}
          </ol>
        </section>

        <section className="min-w-0 rounded-lg border border-zinc-900 bg-surface" aria-label="Run log">
          <div className="flex items-center justify-between border-b border-zinc-900 px-4 py-2.5">
            <h2 className="text-sm font-semibold text-zinc-50">Run log</h2>
            <span className="text-xs text-zinc-500">LangGraph · newest last</span>
          </div>
          <div className="max-h-[520px] min-h-[380px] overflow-y-auto px-4 py-2" data-testid="generation-terminal">
            {!trace.length ? (
              <p className="py-2 text-sm text-zinc-500 caret">Waiting for the first agent event</p>
            ) : null}
            {trace.map((t, i) => (
              <div key={i} className="lq-in grid grid-cols-[64px_120px_minmax(0,1fr)] gap-3 border-b border-zinc-900/60 py-2 last:border-0" data-testid={`trace-line-${i}`}>
                <span className="mono text-xs text-zinc-500">
                  {new Date(t.t).toLocaleTimeString("en-IN", { hour12: false })}
                </span>
                <span className="code truncate text-xs text-zinc-50">{t.agent}</span>
                <span className={`text-sm leading-snug ${t.status === "failed" ? "text-red-400" : "text-zinc-50"}`}>
                  {t.message}
                  {t.meta?.queries?.length ? (
                    <span className="mt-0.5 block text-xs text-zinc-500">
                      Searched: {t.meta.queries.slice(0, 3).join(" · ")}
                    </span>
                  ) : null}
                  {t.meta?.urls?.length ? (
                    <span className="mt-0.5 flex flex-wrap gap-x-3 text-xs">
                      {t.meta.urls.slice(0, 4).map((u, k) => (
                        <a key={k} href={u} target="_blank" rel="noreferrer" className="text-zinc-500 underline decoration-zinc-800 underline-offset-2 hover:text-zinc-50">
                          {(() => { try { return new URL(u).hostname.replace("www.", ""); } catch { return "source"; } })()}
                        </a>
                      ))}
                    </span>
                  ) : null}
                </span>
              </div>
            ))}
            {job?.status === "running" ? <p className="py-2 text-sm text-zinc-500 caret"> </p> : null}
            {job?.status === "done" ? <p className="py-2 text-sm text-zinc-50">Done. Opening the report…</p> : null}
            {job?.status === "failed" ? (
              <div className="py-3">
                <p className="text-sm text-red-400">The run failed: {job.error}</p>
                <button data-testid="generation-back" onClick={() => navigate("/app")} className="btn mt-2">
                  Back to search
                </button>
              </div>
            ) : null}
            <div ref={endRef} />
          </div>
        </section>
      </div>

      <p className="mt-4 max-w-3xl text-sm leading-relaxed text-zinc-500">
        Heavy collection runs once per locality and is shared by everyone. Layers that are still fresh
        are reused rather than re-fetched, which is why a cached locality returns in seconds and a cold
        one takes a minute.
      </p>
    </div>
  );
}
