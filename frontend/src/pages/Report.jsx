import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import {
  ArrowClockwise, ChatCircleDots, Copy, GitDiff, Scales, ShareNetwork, Sparkle, UsersThree,
  Warning,
} from "@phosphor-icons/react";
import { ModuleCard } from "@/components/report/ModuleCard";
import { SourceBadge } from "@/components/report/Citation";
import { ChatPanel } from "@/components/report/ChatPanel";
import { ScoreLedger } from "@/components/report/ScoreLedger";
import { ScorePair } from "@/components/report/ScorePair";
import { ContributeDialog } from "@/components/community/ContributeDialog";
import { api, errMessage, fmtDate } from "@/lib/api";

export default function Report() {
  const { reportId } = useParams();
  const navigate = useNavigate();
  const [report, setReport] = useState(null);
  const [personas, setPersonas] = useState([]);
  const [chatOpen, setChatOpen] = useState(false);
  const [contribute, setContribute] = useState(null);
  const [busy, setBusy] = useState(false);
  const [pinned, setPinned] = useState([]);
  const [shareUrl, setShareUrl] = useState("");
  const [inviteUrl, setInviteUrl] = useState("");
  const [dropped, setDropped] = useState([]);
  const [showSources, setShowSources] = useState(false);

  const load = useCallback(async () => {
    const { data } = await api.get(`/reports/${reportId}`);
    setReport(data);
    setPinned([]);
    setDropped([]);
  }, [reportId]);

  useEffect(() => {
    load().catch(() => toast.error("Could not load that report"));
    api.get("/personas").then((r) => setPersonas(r.data)).catch(() => {});
    window.scrollTo(0, 0);
  }, [load]);

  const switchLens = async (personaKey) => {
    setBusy(true);
    try {
      const { data } = await api.post(`/reports/${reportId}/lens`, { persona_key: personaKey });
      toast.success(`Re-scored as ${data.persona_label}. No credit spent.`);
      navigate(`/app/report/${data.id}`, { replace: true });
    } catch (error) {
      toast.error(errMessage(error));
    } finally {
      setBusy(false);
    }
  };

  const copyLink = async (url) => {
    try {
      await navigator.clipboard.writeText(url);
      toast.success("Link copied. Anyone can open it, no account needed.");
    } catch {
      toast.message("Copy the link below to share it.");
    }
  };

  const share = async () => {
    try {
      const { data } = await api.post(`/reports/${reportId}/share`);
      const url = `${window.location.origin}${data.path}`;
      setShareUrl(url);
      await copyLink(url);
    } catch (error) {
      toast.error(errMessage(error));
    }
  };

  const invite = async () => {
    try {
      const { data } = await api.post("/contribute/links", {
        locality_slug: report.locality_slug, report_id: reportId,
      });
      const url = `${window.location.origin}${data.path}`;
      setInviteUrl(url);
      await copyLink(url);
    } catch (error) {
      toast.error(errMessage(error));
    }
  };

  const regenerate = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/reports/generate", {
        locality: report.locality_slug, persona_key: report.persona_key, force: true,
      });
      navigate(`/app/generating/${data.job_id}`);
    } catch (error) {
      const detail = error?.response?.data?.detail;
      if (detail?.code === "paywall") { toast.error(detail.message); navigate("/app/account"); }
      else toast.error(errMessage(error));
    } finally {
      setBusy(false);
    }
  };

  if (!report) {
    return <p className="mono py-20 text-center text-sm text-zinc-600 caret">loading report</p>;
  }

  const cards = (report.cards || [])
    .filter((c) => !dropped.includes(c.module))
    .sort((a, b) => (pinned.includes(b.module) ? 1 : 0) - (pinned.includes(a.module) ? 1 : 0));

  const narrative = report.narrative || {};
  const layers = Object.entries(report.layers || {});

  return (
    <div className="pb-16">
      <div className="mb-6 border-b border-zinc-900 pb-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <h1 className="text-2xl font-semibold text-zinc-50" data-testid="report-title">
              {report.locality?.name}
            </h1>
            <p className="mono mt-1 text-sm text-zinc-500">
              {report.locality?.pincode} · {report.locality?.zone} Bengaluru · generated {fmtDate(report.created_at)} ·{" "}
              {report.sources?.length || 0} source{report.sources?.length === 1 ? "" : "s"} · {report.composite?.coverage ?? 0}% module coverage
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <label className="sr-only" htmlFor="lens-switcher">Scoring lens</label>
            <select
              id="lens-switcher"
              data-testid="lens-switcher"
              disabled={busy}
              value={report.persona_key}
              onChange={(e) => switchLens(e.target.value)}
              className="btn pr-2"
            >
              {personas.map((p) => (
                <option key={p.key} value={p.key}>{p.label}</option>
              ))}
            </select>
            <button data-testid="report-chat-open" onClick={() => setChatOpen(true)} className="btn">
              <ChatCircleDots size={16} /> Ask
            </button>
            <button data-testid="report-compare" onClick={() => navigate(`/app/compare?a=${report.locality_slug}`)} className="btn">
              <GitDiff size={16} /> Compare
            </button>
            <button data-testid="report-share" onClick={share} className="btn">
              <ShareNetwork size={16} /> Share
            </button>
            <button data-testid="report-invite" onClick={invite} className="btn">
              <UsersThree size={16} /> Ask residents
            </button>
            <button data-testid="report-regenerate" disabled={busy} onClick={regenerate} className="btn">
              <ArrowClockwise size={16} /> Regenerate
            </button>
          </div>
        </div>
        <div className="mt-6">
          <ScorePair report={report} />
        </div>
        {shareUrl ? (
          <div className="mt-3 flex items-center gap-2 rounded-lg border border-zinc-50/40 bg-zinc-50/10 px-3 py-2">
            <input
              readOnly
              value={shareUrl}
              data-testid="share-link"
              onFocus={(e) => e.target.select()}
              className="mono min-w-0 flex-1 bg-transparent text-xs text-zinc-50 outline-none"
            />
            <button
              data-testid="share-copy"
              onClick={() => copyLink(shareUrl)}
              className="mono inline-flex shrink-0 items-center gap-1 rounded-md border border-zinc-50/50 px-2.5 py-1 text-xs text-zinc-50 transition-colors hover:bg-zinc-50/20"
            >
              <Copy size={12} /> Copy
            </button>
          </div>
        ) : null}
        {inviteUrl ? (
          <div className="mt-2 rounded-lg border border-zinc-50/40 bg-zinc-50/10 px-3 py-2" data-testid="invite-panel">
            <p className="mono text-sm text-zinc-50">
              Send this to someone who lives here
            </p>
            <div className="mt-1.5 flex items-center gap-2">
              <input
                readOnly
                value={inviteUrl}
                data-testid="invite-link"
                onFocus={(e) => e.target.select()}
                className="mono min-w-0 flex-1 bg-transparent text-xs text-zinc-50 outline-none"
              />
              <button
                data-testid="invite-copy"
                onClick={() => copyLink(inviteUrl)}
                className="mono inline-flex shrink-0 items-center gap-1 rounded-md border border-zinc-50/50 px-2.5 py-1 text-xs text-zinc-50 transition-colors hover:bg-zinc-50/20"
              >
                <Copy size={12} /> Copy
              </button>
            </div>
            <p className="mt-1 text-sm leading-snug text-zinc-500">
              No account needed. What they post publishes immediately as unverified: visible, but it
              cannot move a score on its own.
            </p>
          </div>
        ) : null}
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-w-0 space-y-4">
          <ScoreLedger cards={cards} />
          {/* narrative */}
          <section className="panel border border-zinc-900 bg-surface px-5 py-5" data-testid="report-narrative">
            <p className="overline text-zinc-50">What living here looks like — for you</p>
            <h2 className="mt-2 text-xl font-medium leading-snug tracking-tight text-zinc-50">
              {narrative.headline}
            </h2>
            {narrative.living_here ? (
              <p className="mt-3 text-sm leading-relaxed text-zinc-300">{narrative.living_here}</p>
            ) : null}
            {narrative.for_you ? (
              <p className="mt-3 border-l-2 border-zinc-50/60 pl-3 text-sm leading-relaxed text-zinc-300">
                {narrative.for_you}
              </p>
            ) : null}

            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <div>
                <p className="overline mb-1.5 text-emerald-400">Where it wins</p>
                <ul className="space-y-1.5">
                  {(narrative.wins || []).map((w, i) => (
                    <li key={i} className="text-xs leading-snug text-zinc-400" data-testid={`narrative-win-${i}`}>
                      <span className="text-zinc-200">{w.title}</span> — {w.detail}
                    </li>
                  ))}
                  {!narrative.wins?.length ? <li className="text-xs text-zinc-600">—</li> : null}
                </ul>
              </div>
              <div>
                <p className="overline mb-1.5 text-amber-400">Watch outs</p>
                <ul className="space-y-1.5">
                  {(narrative.watchouts || []).map((w, i) => (
                    <li key={i} className="text-xs leading-snug text-zinc-400" data-testid={`narrative-watchout-${i}`}>
                      <span className="text-zinc-200">{w.title}</span> — {w.detail}
                    </li>
                  ))}
                  {!narrative.watchouts?.length ? <li className="text-xs text-zinc-600">—</li> : null}
                </ul>
              </div>
            </div>

            {narrative.blind_spots?.length ? (
              <div className="mt-4 border-l-2 border-zinc-700 pl-3">
                <p className="overline mb-1 text-zinc-600">What the data cannot tell you</p>
                {narrative.blind_spots.map((b, i) => (
                  <p key={i} className="text-xs leading-snug text-zinc-500">{b}</p>
                ))}
              </div>
            ) : null}
            {narrative.verdict ? (
              <p className="mt-4 border-t border-zinc-900 pt-3 text-sm leading-relaxed text-zinc-400">
                {narrative.verdict}
              </p>
            ) : null}
          </section>

          {/* disputes */}
          {report.disputes?.length ? (
            <section className="border border-amber-900/60 bg-amber-950/10 px-4 py-3" data-testid="report-disputes">
              <p className="overline flex items-center gap-1.5 text-amber-400">
                <Warning size={12} weight="fill" /> Disputed — queued for human moderation
              </p>
              {report.disputes.map((d, i) => (
                <div key={i} className="mt-2 text-xs text-zinc-400">
                  <p><span className="text-zinc-200">{d.module}</span>: community says “{d.community_claim}”, official source says “{d.official_claim}”.</p>
                  <p className="mt-0.5 text-sm text-zinc-500">{d.note}</p>
                </div>
              ))}
            </section>
          ) : null}

          {(dropped.length || pinned.length) ? (
            <div className="flex flex-wrap items-center gap-2 border border-zinc-900 px-3 py-2" data-testid="module-override-bar">
              <span className="overline text-zinc-600">Your overrides</span>
              {pinned.map((m) => (
                <span key={m} className="mono border border-zinc-50/50 px-1.5 py-[2px] text-xs text-zinc-50">pinned {m}</span>
              ))}
              {dropped.map((m) => (
                <button key={m} data-testid={`restore-${m}`} onClick={() => setDropped((d) => d.filter((x) => x !== m))}
                        className="mono border border-zinc-800 px-1.5 py-[2px] text-xs text-zinc-500 hover:text-zinc-200">
                  dropped {m} · restore
                </button>
              ))}
            </div>
          ) : null}

          {/* declarative module stack */}
          <div className="space-y-3" data-testid="module-stack">
            {cards.map((card, i) => (
              <ModuleCard
                key={card.module}
                card={card}
                index={i}
                pinned={pinned.includes(card.module)}
                onPin={(m) => setPinned((p) => (p.includes(m) ? p.filter((x) => x !== m) : [...p, m]))}
                onDrop={(m) => setDropped((d) => [...d, m])}
                onContribute={(c) => setContribute({ card: c, slug: report.locality_slug })}
              />
            ))}
          </div>
        </div>

        {/* right rail */}
        <aside className="space-y-3 lg:sticky lg:top-56 lg:self-start">
          <div className="panel border border-zinc-900 bg-surface px-4 py-3">
            <p className="overline text-zinc-600">Data layers in this run</p>
            <div className="mt-2 space-y-1">
              {layers.map(([name, l]) => (
                <div key={name} className="flex items-center justify-between" data-testid={`layer-${name}`}>
                  <span className="text-sm text-zinc-50">{name}</span>
                  <span className={`mono text-sm ${l.ok ? "text-zinc-500" : "text-red-400"}`}>
                    {l.ok ? "collected" : "absent"}
                  </span>
                </div>
              ))}
            </div>
            <p className="mt-2 text-sm leading-snug text-zinc-600">
              An absent layer is shown as absent throughout the report. It is never estimated.
            </p>
          </div>

          <div className="panel border border-zinc-900 bg-surface px-4 py-3">
            <div className="flex items-center justify-between">
              <p className="overline text-zinc-600">Sources ({report.sources?.length || 0})</p>
              <button
                data-testid="toggle-sources"
                onClick={() => setShowSources((v) => !v)}
                className="mono text-xs text-zinc-50 hover:underline"
              >
                {showSources ? "hide" : "show all"}
              </button>
            </div>
            {showSources ? (
              <div className="mt-2 max-h-72 space-y-2 overflow-y-auto">
                {(report.sources || []).map((s, i) => (
                  <a
                    key={i}
                    href={s.url}
                    target="_blank"
                    rel="noreferrer"
                    data-testid={`source-link-${i}`}
                    className="block border border-zinc-900 px-2 py-1.5 transition-colors hover:border-zinc-50/50"
                  >
                    <SourceBadge type={s.type} />
                    <p className="mt-1 truncate text-sm text-zinc-500">{s.name}</p>
                  </a>
                ))}
              </div>
            ) : (
              <div className="mt-2 flex flex-wrap gap-1">
                {[...new Set((report.sources || []).map((s) => s.type))].map((t) => (
                  <SourceBadge key={t} type={t} />
                ))}
              </div>
            )}
          </div>

          <div className="panel border border-zinc-900 bg-surface px-4 py-3" data-testid="verifier-panel">
            <p className="overline text-zinc-600">Verifier</p>
            <div className="mt-2 grid grid-cols-3 gap-2">
              {[
                ["kept", report.verifier_stats?.kept ?? 0, "text-zinc-50"],
                ["dropped", report.verifier_stats?.dropped ?? 0, "text-red-400"],
                ["disputed", report.verifier_stats?.disputed ?? 0, "text-amber-400"],
              ].map(([l, v, c]) => (
                <div key={l}>
                  <p className={`mono text-lg ${v ? c : "text-zinc-600"}`}>{v}</p>
                  <p className="overline text-zinc-700">{l}</p>
                </div>
              ))}
            </div>
            {report.dropped?.length ? (
              <div className="mt-2 space-y-1">
                {report.dropped.slice(0, 4).map((d, i) => (
                  <p key={i} className="text-xs leading-snug text-zinc-600">
                    dropped “{d.label}” — {d.reason}
                  </p>
                ))}
              </div>
            ) : null}
          </div>

          <div className="panel border border-zinc-900 bg-surface px-4 py-3" data-testid="cost-panel">
            <p className="overline text-zinc-600">Run cost</p>
            <div className="mt-2 space-y-1">
              {[
                ["LLM calls", report.cost?.llm_calls],
                ["Web searches", report.cost?.web_searches],
                ["Prompt tokens", report.cost?.prompt_tokens],
                ["Output tokens", report.cost?.completion_tokens],
                ["Model", report.cost?.model || "not recorded"],
                ["Est. cost", report.cost?.model ? `$${report.cost?.est_cost_usd ?? 0}` : "not recorded"],
              ].map(([l, v]) => (
                <div key={l} className="flex items-center justify-between">
                  <span className="mono text-xs text-zinc-500">{l}</span>
                  <span className="mono text-xs text-zinc-300">{v ?? 0}</span>
                </div>
              ))}
            </div>
          </div>

          <button
            data-testid="report-trust-link"
            onClick={() => navigate("/app/trust")}
            className="mono flex w-full items-center justify-center gap-1.5 border border-zinc-800 py-2.5 text-xs text-zinc-400 transition-colors hover:border-zinc-50 hover:text-zinc-50"
          >
            <Scales size={13} weight="duotone" /> Read the scoring rubric
          </button>
          <button
            data-testid="report-community-link"
            onClick={() => navigate(`/app/community?locality=${report.locality_slug}`)}
            className="mono flex w-full items-center justify-center gap-1.5 border border-zinc-800 py-2.5 text-xs text-zinc-400 transition-colors hover:border-zinc-50 hover:text-zinc-50"
          >
            <Sparkle size={13} weight="duotone" /> What residents are saying
          </button>
        </aside>
      </div>

      <ChatPanel reportId={reportId} report={report} open={chatOpen} onClose={() => setChatOpen(false)} />
      <ContributeDialog
        open={!!contribute}
        onClose={() => setContribute(null)}
        localitySlug={contribute?.slug}
        card={contribute?.card}
        onDone={() => { setContribute(null); toast.success("Posted. Thanks — this is how the cold start gets solved."); }}
      />

      {!chatOpen ? (
        <button
          data-testid="chat-fab"
          onClick={() => setChatOpen(true)}
          className="fixed bottom-6 right-6 z-50 inline-flex items-center gap-2 border border-primary bg-primary px-4 py-3 text-xs font-medium text-primary-foreground shadow-xl transition-transform hover:-translate-y-0.5"
        >
          <ChatCircleDots size={15} weight="duotone" /> Ask about {report.locality?.name?.split(" ")[0]}
        </button>
      ) : null}
    </div>
  );
}
