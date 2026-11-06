import { useEffect, useState } from "react";
import { toast } from "sonner";
import { CheckCircle, Flask, Scales, XCircle } from "@phosphor-icons/react";
import { ModuleIcon } from "@/components/report/ModuleIcon";
import { SourceBadge } from "@/components/report/Citation";
import { api } from "@/lib/api";

export default function Trust() {
  const [doc, setDoc] = useState(null);
  const [evals, setEvals] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get("/trust/rubric").then((r) => setDoc(r.data)).catch(() => {});
  }, []);

  const runEvals = async () => {
    setBusy(true);
    try {
      const { data } = await api.get("/evals/golden");
      setEvals(data);
      toast.success(`${data.summary.passed}/${data.summary.total} checks passed`);
    } finally {
      setBusy(false);
    }
  };

  if (!doc) return <p className="mono py-20 text-center text-xs text-zinc-600 caret">loading rubric</p>;

  return (
    <div className="mx-auto max-w-4xl space-y-10 pb-20">
      <header>
        <p className="overline flex items-center gap-1.5 text-zinc-50">
          <Scales size={12} weight="duotone" /> Methodology, published
        </p>
        <h1 className="mt-3 text-2xl font-semibold  text-zinc-50">
          A score you cannot interrogate is a score you should not trust.
        </h1>
        <p className="mt-4 max-w-2xl text-sm leading-relaxed text-zinc-400">
          Every module score below is produced by deterministic arithmetic over sourced, dated
          measurements. No language model produces a number. Here is the exact formula for each one,
          the persona weights applied on top, and the freshness policy that decides when data is
          re-collected.
        </p>
      </header>

      <section>
        <p className="overline mb-3 text-zinc-600">Principles</p>
        <div className="space-y-2">
          {doc.principles.map((p, i) => (
            <div key={i} className="flex gap-3 border-l-2 border-zinc-50/50 pl-3" data-testid={`principle-${i}`}>
              <span className="mono text-xs text-zinc-700">{String(i + 1).padStart(2, "0")}</span>
              <p className="text-sm leading-relaxed text-zinc-300">{p}</p>
            </div>
          ))}
        </div>
      </section>

      <section>
        <p className="overline mb-3 text-zinc-600">Source types</p>
        <div className="grid-skeleton grid border-b border-r border-zinc-900 sm:grid-cols-2 lg:grid-cols-4">
          {Object.entries(doc.source_types).map(([key, v]) => (
            <div key={key} className="bg-surface px-3 py-3">
              <SourceBadge type={key} />
              <p className="mono mt-2 text-xs text-zinc-600">trust weight {v.trust}/5</p>
            </div>
          ))}
        </div>
      </section>

      <section>
        <p className="overline mb-3 text-zinc-600">The rubric — {doc.rubric.length} modules</p>
        <div className="space-y-2">
          {doc.rubric.map((r) => {
            const meta = doc.modules.find((m) => m.key === r.module);
            return (
              <div key={r.module} className="panel border border-zinc-900 bg-surface px-4 py-3" data-testid={`rubric-${r.module}`}>
                <div className="flex flex-wrap items-center gap-2">
                  <ModuleIcon module={r.module} size={16} className="text-zinc-50" />
                  <h3 className="text-sm font-medium text-zinc-100">{meta?.label || r.module}</h3>
                  <span className="overline border border-zinc-800 px-1.5 py-[2px] text-zinc-600">{meta?.tier}</span>
                </div>
                <p className="mono mt-2 border-l-2 border-zinc-800 pl-2 text-xs leading-relaxed text-emerald-300/80">
                  {r.formula}
                </p>
                <p className="mt-1.5 text-xs leading-snug text-zinc-500">Inputs: {r.inputs}</p>
              </div>
            );
          })}
        </div>
      </section>

      <section>
        <p className="overline mb-3 text-zinc-600">Persona weights</p>
        <div className="panel overflow-x-auto rounded-lg border border-zinc-900 bg-surface">
          <table className="w-full text-left" data-testid="persona-weight-table">
            <thead>
              <tr className="border-b border-zinc-900">
                <th className="overline sticky left-0 z-10 border-r border-zinc-900 bg-surface px-3 py-2 text-zinc-600">Module</th>
                {doc.personas.map((p) => (
                  <th key={p.key} className="overline px-2 py-2 text-zinc-500">{p.label.split(" ")[0]}</th>
                ))}
                <th className="overline px-2 py-2 text-zinc-600">Baseline</th>
              </tr>
            </thead>
            <tbody>
              {doc.modules.map((m) => (
                <tr key={m.key} className="border-b border-zinc-900/60">
                  <td className="sticky left-0 z-10 border-r border-zinc-900 bg-surface px-3 py-1.5 text-xs text-zinc-300">{m.label}</td>
                  {doc.personas.map((p) => {
                    const w = p.weights[m.key] ?? 0;
                    return (
                      <td key={p.key} className="px-2 py-1.5">
                        <span className={`mono text-xs ${w === 3 ? "text-zinc-50" : w === 2 ? "text-zinc-300" : w === 1 ? "text-zinc-500" : "text-zinc-800"}`}>
                          {w}
                        </span>
                      </td>
                    );
                  })}
                  <td className="px-2 py-1.5"><span className="mono text-xs text-zinc-500">1</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-xs leading-snug text-zinc-600">
          Weight 0 means the module does not appear in that persona's report at all. Weight 3 means it
          dominates. The neutral baseline weights every module at 1 — that is the number shown beside
          your personalised score, so you can always see how much the lens moved it.
        </p>
      </section>

      <section>
        <p className="overline mb-3 text-zinc-600">Freshness policy</p>
        <div className="grid-skeleton grid border-b border-r border-zinc-900 sm:grid-cols-4 lg:grid-cols-7">
          {Object.entries(doc.freshness_policy).map(([layer, v]) => (
            <div key={layer} className="bg-surface px-3 py-3">
              <p className="mono text-xs text-zinc-200">{layer}</p>
              <p className="overline mt-1 text-zinc-600">{v.label}</p>
            </div>
          ))}
        </div>
      </section>

      <section>
        <div className="flex items-center justify-between">
          <p className="overline text-zinc-600">Golden-set regression</p>
          <button
            data-testid="run-evals"
            disabled={busy}
            onClick={runEvals}
            className="mono inline-flex items-center gap-1.5 border border-zinc-50/60 bg-zinc-50/10 px-3 py-1.5 text-xs text-zinc-50 transition-colors hover:bg-zinc-50/20 disabled:opacity-40"
          >
            <Flask size={12} weight="duotone" /> {busy ? "Running…" : "Run checks now"}
          </button>
        </div>
        <p className="mt-2 text-xs leading-snug text-zinc-500">
          Deterministic checks over hand-verified fixtures: primitive arithmetic, CPCB conversion,
          score regression, determinism across runs, absence handling, persona sensitivity, and
          groundedness sampling over real stored reports.
        </p>
        {evals ? (
          <div className="mt-3" data-testid="eval-results">
            <div className="grid-skeleton grid grid-cols-3 border-b border-r border-zinc-900">
              {[
                ["total", evals.summary.total, "text-zinc-200"],
                ["passed", evals.summary.passed, "text-emerald-400"],
                ["failed", evals.summary.failed, "text-red-400"],
              ].map(([l, v, c]) => (
                <div key={l} className="bg-surface px-3 py-2.5">
                  <p className={`mono text-2xl ${c}`}>{v}</p>
                  <p className="overline text-zinc-700">{l}</p>
                </div>
              ))}
            </div>
            <div className="mt-2 flex flex-wrap gap-2" data-testid="eval-suites">
              {Object.entries(evals.summary.suites || {}).map(([suite, s]) => (
                <span
                  key={suite}
                  className={`mono border px-2 py-1 text-xs ${
 s.passed === s.total
 ? "border-emerald-500/40 text-emerald-300"
 : "border-red-500/40 text-red-300"
 }`}
                >
                  {suite} {s.passed}/{s.total}
                </span>
              ))}
            </div>
            <div className="mt-2 space-y-1">
              {evals.results.map((r, i) => (
                <div key={i} className="flex items-start gap-2 border border-zinc-900 px-2.5 py-1.5" data-testid={`eval-${i}`}>
                  {r.status === "pass" ? (
                    <CheckCircle size={13} weight="fill" className="mt-0.5 shrink-0 text-emerald-500" />
                  ) : (
                    <XCircle size={13} weight="fill" className="mt-0.5 shrink-0 text-red-500" />
                  )}
                  <div className="min-w-0">
                    <p className="mono text-xs text-zinc-300">{r.check}</p>
                    {r.detail ? <p className="mono text-xs text-zinc-600">{r.detail}</p> : null}
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-3 border border-zinc-900 px-3 py-2">
              <p className="overline text-zinc-600">Persona sensitivity on the fixture</p>
              <div className="mt-1.5 flex flex-wrap gap-3">
                {Object.entries(evals.summary.persona_scores).map(([k, v]) => (
                  <span key={k} className="mono text-xs text-zinc-400">
                    {k}: <span className="text-zinc-50">{v}</span>
                  </span>
                ))}
                <span className="mono text-xs text-zinc-500">baseline: {evals.summary.baseline}</span>
              </div>
            </div>
          </div>
        ) : null}
      </section>

      <section className="panel border border-zinc-900 bg-surface px-5 py-5">
        <p className="overline text-amber-400">Known limitations, stated plainly</p>
        <ul className="mt-2 space-y-2 text-xs leading-relaxed text-zinc-400">
          <li>
            <span className="text-zinc-200">Media-reported incidents are coverage-biased.</span> A
            locality the press writes about often will look worse than an equally risky one nobody
            covers. This is not a crime rate and must not be read as one.
          </li>
          <li>
            <span className="text-zinc-200">OpenStreetMap is incomplete in places.</span> Counts and
            distances are exact for what is mapped, and silent about what is not.
          </li>
          <li>
            <span className="text-zinc-200">Rent bands are listing-derived.</span> They are not
            transaction data and are marked low confidence.
          </li>
          <li>
            <span className="text-zinc-200">Water and power often have no data at all.</span> That is
            shown as absent, and it is exactly the gap the community layer exists to close.
          </li>
          <li>
            <span className="text-zinc-200">Schools are inventory, not a ranking.</span> LocalIQ does
            not invent a school ranking it cannot defend.
          </li>
        </ul>
      </section>
    </div>
  );
}
