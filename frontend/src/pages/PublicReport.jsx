import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowRight, ChartLineUp, LockKey, ShieldCheck, Warning } from "@phosphor-icons/react";
import { ModuleCard } from "@/components/report/ModuleCard";
import { ModuleIcon } from "@/components/report/ModuleIcon";
import { ThemeToggle } from "@/components/layout/ThemeToggle";
import { api, fmtDate, scoreTone, toneClass } from "@/lib/api";

const ScoreBlock = ({ label, sub, score, testId, accent }) => (
  <div className={`px-5 py-4 ${accent ? "bg-primary text-primary-foreground" : "bg-surface2"}`} data-testid={testId}>
    <p className={`overline ${accent ? "text-zinc-900/80" : "text-zinc-600"}`}>{label}</p>
    <p className={`mono mt-1 text-5xl font-semibold leading-none ${
 accent ? "text-white" : toneClass[scoreTone(score)]}`}>
      {score ?? "\u2014"}
    </p>
    <p className={`mono mt-1.5 text-xs leading-snug ${accent ? "text-zinc-900/70" : "text-zinc-600"}`}>
      {sub}
    </p>
  </div>
);

const SignupCTA = ({ locality, testId }) => (
  <Link
    to="/auth?mode=register"
    data-testid={testId}
    className="group inline-flex items-center gap-2 rounded-md border border-primary bg-primary px-6 py-3 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
  >
    Run your own {locality ? `${locality} ` : ""}report — 5 free
    <ArrowRight size={15} weight="bold" className="transition-transform group-hover:translate-x-1" />
  </Link>
);

export default function PublicReport() {
  const { token } = useParams();
  const [report, setReport] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get(`/public/reports/${token}`)
      .then((r) => setReport(r.data))
      .catch(() => setError("This link is not valid, or the report was never shared."));
  }, [token]);

  useEffect(() => {
    if (report?.locality?.name) {
      document.title = `${report.locality.name} — LocalIQ neighbourhood report`;
    }
  }, [report]);

  if (error) {
    return (
      <div className="grid min-h-screen place-items-center px-6">
        <div className="text-center" data-testid="public-report-error">
          <p className="overline text-zinc-600">Dead link</p>
          <h1 className="mt-2 text-2xl font-medium text-zinc-100">{error}</h1>
          <div className="mt-6"><SignupCTA testId="public-cta-error" /></div>
        </div>
      </div>
    );
  }

  if (!report) {
    return (
      <p className="mono py-32 text-center text-xs text-zinc-600 caret">
        opening shared report
      </p>
    );
  }

  const { locality, composite, baseline_composite: baseline, narrative, locked } = report;

  return (
    <div className="min-h-screen pb-20" data-testid="public-report">
      <header className="glass sticky top-0 z-50 border-b border-zinc-900">
        <div className="mx-auto flex h-14 max-w-[1100px] items-center gap-3 px-4 sm:px-6">
          <Link to="/" className="flex items-center gap-2" data-testid="public-logo">
            <span className="grid h-7 w-7 place-items-center rounded-md bg-primary">
              <ChartLineUp size={15} weight="bold" className="text-white" />
            </span>
            <span className="text-[15px] font-semibold tracking-tight text-zinc-100">
              LocalIQ
            </span>
          </Link>
          <span className="mono hidden text-xs text-zinc-600 sm:inline">
            shared report
          </span>
          <div className="ml-auto flex items-center gap-2">
            <ThemeToggle />
            <Link
              to="/auth?mode=register"
              data-testid="public-cta-header"
              className="mono rounded-md border border-primary bg-primary px-3.5 py-1.5 text-xs text-primary-foreground transition-colors hover:bg-primary/90"
            >
              Get 5 free
            </Link>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1100px] px-4 sm:px-6">
        <section className="py-8 lq-in">
          <p className="overline text-zinc-600">
            {locality?.pincode} · {locality?.zone} Bengaluru · generated {fmtDate(report.created_at)}
          </p>
          <h1
            className="mt-2 text-4xl font-light tracking-tight text-zinc-50 sm:text-5xl"
            data-testid="public-locality-name"
          >
            {locality?.name}
          </h1>
          {narrative?.headline ? (
            <p className="mt-3 max-w-2xl text-base leading-relaxed text-zinc-300">
              {narrative.headline}
            </p>
          ) : null}

          <div className="mt-6 grid-skeleton grid w-full max-w-md grid-cols-2 overflow-hidden rounded-lg border-b border-r border-zinc-900">
            <ScoreBlock
              accent
              testId="public-score-persona"
              label="Scored for"
              sub={report.persona_label || "this reader"}
              score={composite?.score}
            />
            <ScoreBlock
              testId="public-score-baseline"
              label="Neutral baseline"
              sub={`${composite?.coverage ?? 0}% module coverage · ${report.sources_count} sources`}
              score={baseline?.score}
            />
          </div>

          {narrative?.verdict ? (
            <p
              className="mt-5 max-w-2xl border-l-2 border-zinc-50/60 pl-4 text-sm leading-relaxed text-zinc-300"
              data-testid="public-verdict"
            >
              {narrative.verdict}
            </p>
          ) : null}

          <p className="mono mt-5 inline-flex items-center gap-1.5 rounded-md border border-emerald-500/40 bg-emerald-500/10 px-3 py-1.5 text-xs text-emerald-300">
            <ShieldCheck size={13} weight="duotone" /> every number below is citable
          </p>
        </section>

        {(narrative?.wins?.length || narrative?.watchouts?.length) ? (
          <section className="mb-8 grid gap-4 sm:grid-cols-2">
            {narrative.wins?.length ? (
              <div className="panel rounded-lg border border-zinc-900 bg-surface px-5 py-4">
                <p className="overline text-emerald-400">What works</p>
                <ul className="mt-2 space-y-2.5">
                  {narrative.wins.slice(0, 3).map((w, i) => (
                    <li key={i}>
                      <p className="text-sm font-medium text-zinc-100">{w.title}</p>
                      <p className="mt-0.5 text-xs leading-relaxed text-zinc-500">{w.detail}</p>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
            {narrative.watchouts?.length ? (
              <div className="panel rounded-lg border border-zinc-900 bg-surface px-5 py-4">
                <p className="overline flex items-center gap-1.5 text-amber-400">
                  <Warning size={12} weight="fill" /> Watch out for
                </p>
                <ul className="mt-2 space-y-2.5">
                  {narrative.watchouts.slice(0, 3).map((w, i) => (
                    <li key={i}>
                      <p className="text-sm font-medium text-zinc-100">{w.title}</p>
                      <p className="mt-0.5 text-xs leading-relaxed text-zinc-500">{w.detail}</p>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </section>
        ) : null}

        <section className="space-y-3" data-testid="public-hero-modules">
          {(report.cards || []).map((card, i) => (
            <ModuleCard key={card.module} card={card} index={i} readOnly />
          ))}
        </section>

        {locked?.length ? (
          <section className="relative mt-4" data-testid="public-locked-list">
            <div className="grid grid-cols-2 gap-2 opacity-40 blur-[2px] sm:grid-cols-3 lg:grid-cols-4">
              {locked.map((m) => (
                <div key={m.module} className="panel flex items-center gap-2 rounded-lg border border-zinc-900 bg-surface px-3 py-3">
                  <ModuleIcon module={m.module} size={16} />
                  <span className="truncate text-xs text-zinc-300">{m.title}</span>
                </div>
              ))}
            </div>
            <div className="absolute inset-0 grid place-items-center px-4">
              <div className="panel rounded-xl border border-zinc-50/50 bg-surface px-6 py-6 text-center">
                <LockKey size={20} weight="duotone" className="mx-auto text-zinc-50" />
                <p className="mt-2 text-lg font-medium text-zinc-50">
                  {locked.length} more modules in the full report
                </p>
                <p className="mx-auto mt-1 max-w-md text-xs leading-relaxed text-zinc-500">
                  Schools, safety after dark, water and power reliability, commute, rent band and the
                  rest — each scored against the Bengaluru median and weighted for how you actually live.
                </p>
                <div className="mt-4">
                  <SignupCTA locality={locality?.name} testId="public-cta-signup" />
                </div>
              </div>
            </div>
          </section>
        ) : null}

        <section className="mt-10 rounded-xl border border-zinc-900 bg-surface2 px-6 py-8 text-center">
          <p className="overline text-zinc-50">No listings. Nothing to sell you.</p>
          <h2 className="mx-auto mt-2 max-w-xl text-2xl font-medium tracking-tight text-zinc-50">
            Run this for the areas on your own shortlist.
          </h2>
          <p className="mx-auto mt-2 max-w-lg text-sm leading-relaxed text-zinc-500">
            Same rubric, same sources, re-weighted for your life stage. Five reports free, no card.
          </p>
          <div className="mt-5"><SignupCTA testId="public-cta-footer" /></div>
        </section>

        <p className="mono mt-10 text-xs leading-relaxed text-zinc-700">
          LocalIQ is decision support, not advice. Scores are computed from a published rubric over
          sourced, dated measurements. Media-reported incident counts are not crime rates.
        </p>
      </main>
    </div>
  );
}
