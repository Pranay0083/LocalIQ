import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import {
  ArrowClockwise, ArrowUp, ChatCircleDots, Copy, Eye, GitDiff, Scales, ShareNetwork, Sparkle,
  UsersThree, Warning, X,
} from "@phosphor-icons/react";
import { ModuleCard } from "@/components/ModuleCard";
import { SourceBadge } from "@/components/Citation";
import { ContributeDialog } from "@/components/ContributeDialog";
import { API, api, errMessage, fmtDate, scoreTone, toneClass } from "@/lib/api";

const ScorePair = ({ report }) => {
  const persona = report.composite?.score;
  const baseline = report.baseline_composite?.score;
  return (
    <div className="grid-skeleton grid w-full grid-cols-2 overflow-hidden rounded-lg border-b border-r border-zinc-900 sm:w-auto" data-testid="score-pair">
      <div className="bg-indigo-600 px-4 py-3">
        <p className="overline text-indigo-100/80">Scored for you</p>
        <p className="mono text-4xl font-semibold leading-none text-white" data-testid="persona-score">
          {persona ?? "—"}
        </p>
        <p className="mt-1 text-[10px] leading-snug text-indigo-100/85">{report.persona_label}</p>
      </div>
      <div className="bg-surface2 px-4 py-3">
        <p className="overline text-zinc-500">Neutral baseline</p>
        <p className="mono text-4xl font-light leading-none text-zinc-300" data-testid="baseline-score">
          {baseline ?? "—"}
        </p>
        <p className="mt-1 text-[10px] leading-snug text-zinc-500">All modules weighted equally</p>
      </div>
    </div>
  );
};

const MODULE_QUESTIONS = {
  air_quality: "Is the air here actually bad, or just average for Bengaluru?",
  commute: "How far is the nearest metro, and how long is that on foot?",
  safety_day: "What do the reported incidents here actually say?",
  safety_night: "What is this place like after 10pm?",
  nightlife: "Where would I go out on a Friday here?",
  food: "How deep is the food scene compared with the city?",
  schools: "Which schools are closest, and how far are they?",
  parks: "Is there real green space within walking distance?",
  healthcare: "If something happens at 2am, where do I go?",
  daily_needs: "Can I do a full grocery run on foot?",
  fitness: "What are my options for a gym or a run?",
  worship: "What places of worship are nearby?",
  water: "How reliable is the water supply here?",
  power: "How often does the power actually go out?",
  noise: "How noisy is this area, and when?",
  internet_wfh: "Would this work for full-time work from home?",
  pet_friendly: "Is this a workable area for a dog?",
  cost: "What rent should I expect here?",
  infrastructure: "What is being built here over the next few years?",
  investment: "What do the trajectory signals say about this area?",
};

const buildSuggestions = (report) => {
  const withData = (report?.cards || [])
    .filter((c) => !c.empty && c.score !== null && MODULE_QUESTIONS[c.module])
    .sort((a, b) => (b.weight || 0) - (a.weight || 0))
    .slice(0, 5)
    .map((c) => ({ key: c.module, q: MODULE_QUESTIONS[c.module] }));
  const thin = (report?.cards || []).find((c) => c.empty);
  return [
    ...withData,
    ...(thin ? [{ key: `gap-${thin.module}`, q: `Why is there no ${thin.title.toLowerCase()} data?` }] : []),
    { key: "blindspots", q: "What can't you tell me about this locality?" },
  ];
};

const ChatPanel = ({ reportId, report, open, onClose }) => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const bottom = useRef(null);
  const suggestions = buildSuggestions(report);

  useEffect(() => {
    if (!open) return;
    api.get(`/reports/${reportId}/chat`).then((r) => setMessages(r.data)).catch(() => {});
  }, [reportId, open]);

  const last = messages[messages.length - 1];
  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: last?.streaming ? "auto" : "smooth" });
  }, [messages.length, last?.content?.length, last?.streaming, busy]);

  const send = async (e, override) => {
    e?.preventDefault();
    const text = (override ?? input).trim();
    if (!text || busy) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", content: text },
                              { role: "assistant", content: "", streaming: true }]);
    setBusy(true);

    const patchLast = (fn) => setMessages((m) => {
      const next = [...m];
      next[next.length - 1] = fn(next[next.length - 1]);
      return next;
    });

    try {
      const res = await fetch(`${API}/reports/${reportId}/chat/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("lq_token")}`,
        },
        body: JSON.stringify({ message: text }),
      });
      if (!res.ok || !res.body) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || "Chat is unavailable right now.");
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const frames = buffer.split("\n\n");
        buffer = frames.pop();
        for (const frame of frames) {
          if (!frame.startsWith("data:")) continue;
          const evt = JSON.parse(frame.slice(5).trim());
          if (evt.type === "delta") {
            patchLast((last) => ({ ...last, content: last.content + evt.text }));
          } else if (evt.type === "done") {
            patchLast((last) => ({
              ...last, content: evt.answer || last.content, used_sources: evt.used_sources,
              missing: evt.missing, streaming: false,
            }));
          } else if (evt.type === "error") {
            throw new Error(evt.detail);
          }
        }
      }
      patchLast((last) => ({ ...last, streaming: false }));
    } catch (error) {
      const message = error.message || errMessage(error);
      setMessages((m) => {
        const next = [...m];
        const last = next[next.length - 1];
        if (!last?.streaming) return next;
        if (!last.content) return next.slice(0, -1);
        next[next.length - 1] = { ...last, streaming: false, error: message };
        return next;
      });
      toast.error(message);
    } finally {
      setBusy(false);
    }
  };

  if (!open) return null;
  return (
    <>
    <div
      data-testid="chat-backdrop"
      onClick={onClose}
      className="fixed inset-0 z-[55] bg-black/40"
    />
    <aside
      data-testid="chat-panel"
      className="fixed inset-y-0 right-0 z-[60] flex w-full max-w-md flex-col border-l border-zinc-800 bg-zinc-950 shadow-2xl lg:w-[420px]"
    >
      <header className="flex items-center justify-between border-b border-zinc-900 px-4 py-3">
        <div>
          <p className="overline text-indigo-400">Grounded chat</p>
          <p className="text-xs text-zinc-500">Answers only from this dossier, with the same sources.</p>
        </div>
        <button data-testid="chat-close" onClick={onClose} className="text-zinc-600 hover:text-zinc-200">
          <X size={16} />
        </button>
      </header>

      <div className="flex-1 space-y-3 overflow-y-auto px-4 py-4" data-testid="chat-messages">
        {!messages.length ? (
          <div className="space-y-2">
            <p className="text-xs text-zinc-600">
              Built from the {suggestions.length} strongest modules in this report:
            </p>
            {suggestions.map((s) => (
              <button
                key={s.key}
                data-testid={`chat-suggestion-${s.key}`}
                onClick={() => send(null, s.q)}
                className="block w-full border border-zinc-900 px-3 py-2 text-left text-xs text-zinc-400 transition-colors hover:border-indigo-500/50 hover:text-indigo-300"
              >
                {s.q}
              </button>
            ))}
          </div>
        ) : null}
        {messages.map((m, i) => (
          <div key={i} className={m.role === "user" ? "flex justify-end" : ""} data-testid={`chat-message-${m.role}`}>
            <div className={`max-w-[92%] px-3 py-2 text-xs leading-relaxed ${
              m.role === "user" ? "bg-indigo-600 text-white" : "panel border border-zinc-900 bg-surface2 text-zinc-300"
            }`}>
              {m.streaming && !m.content ? (
                <p className="mono text-[11px] text-zinc-600 caret" data-testid="chat-streaming">reading the dossier</p>
              ) : (
                <p className={`whitespace-pre-wrap ${m.streaming ? "caret" : ""}`}
                   data-testid={m.streaming ? "chat-streaming" : undefined}>{m.content}</p>
              )}
              {m.used_sources?.length ? (
                <div className="mt-2 flex flex-wrap gap-1 border-t border-zinc-800 pt-2">
                  {m.used_sources.slice(0, 6).map((s, k) => (
                    <span key={k} className="mono border border-zinc-800 px-1.5 py-[2px] text-[9px] text-zinc-500">
                      {s}
                    </span>
                  ))}
                </div>
              ) : null}
              {m.missing ? (
                <p className="mt-2 border-l-2 border-amber-500/60 pl-2 text-[10px] text-amber-300/80">
                  Can't answer: {m.missing}
                </p>
              ) : null}
              {m.error ? (
                <p className="mono mt-2 border-l-2 border-red-500/60 pl-2 text-[10px] text-red-400"
                   data-testid="chat-stream-error">
                  Stream interrupted: {m.error}
                </p>
              ) : null}
            </div>
          </div>
        ))}
        {busy && !messages.some((m) => m.streaming) ? (
          <p className="mono text-[11px] text-zinc-600 caret">thinking</p>
        ) : null}
        <div ref={bottom} />
      </div>

      <form onSubmit={send} className="border-t border-zinc-900 p-3">
        {messages.length ? (
          <div className="mb-2 flex gap-1.5 overflow-x-auto pb-1" data-testid="chat-suggestion-chips">
            {suggestions.map((s) => (
              <button
                key={s.key}
                type="button"
                disabled={busy}
                data-testid={`chat-chip-${s.key}`}
                onClick={() => send(null, s.q)}
                className="mono shrink-0 whitespace-nowrap rounded-full border border-zinc-800 px-2.5 py-1 text-[10px] text-zinc-500 transition-colors hover:border-indigo-500/60 hover:text-indigo-300 disabled:opacity-40"
              >
                {s.q.length > 38 ? `${s.q.slice(0, 36)}…` : s.q}
              </button>
            ))}
          </div>
        ) : null}
        <div className="flex gap-2">
          <input
            data-testid="chat-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask anything about this locality…"
            className="mono flex-1 border border-zinc-800 bg-zinc-950 px-3 py-2 text-xs text-zinc-100 outline-none placeholder:text-zinc-700 focus:border-indigo-500"
          />
          <button
            data-testid="chat-send"
            disabled={busy}
            className="grid w-10 place-items-center border border-indigo-500 bg-indigo-600 text-white transition-colors hover:bg-indigo-500 disabled:opacity-40"
          >
            <ArrowUp size={14} weight="bold" />
          </button>
        </div>
        <p className="mono mt-1.5 text-[9px] text-zinc-700">Unlimited inside an unlocked report.</p>
      </form>
    </aside>
    </>
  );
};

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
    return <p className="mono py-20 text-center text-xs uppercase tracking-[0.3em] text-zinc-600 caret">loading report</p>;
  }

  const cards = (report.cards || [])
    .filter((c) => !dropped.includes(c.module))
    .sort((a, b) => (pinned.includes(b.module) ? 1 : 0) - (pinned.includes(a.module) ? 1 : 0));

  const narrative = report.narrative || {};
  const layers = Object.entries(report.layers || {});

  return (
    <div className="pb-16">
      {/* sticky header */}
      <div className="glass z-40 -mx-4 mb-6 border-b border-zinc-900 px-4 py-3 sm:-mx-6 sm:px-6 md:sticky md:top-14">
        <div className="flex flex-wrap items-center gap-4">
          <div className="min-w-0 flex-1">
            <p className="overline text-zinc-600">
              {report.locality?.pincode} · {report.locality?.zone} Bengaluru
            </p>
            <h1 className="truncate font-[Outfit] text-2xl font-light tracking-tight text-zinc-50" data-testid="report-title">
              {report.locality?.name}
            </h1>
            <p className="mono mt-0.5 text-[10px] text-zinc-600">
              generated {fmtDate(report.created_at)} · {report.sources?.length || 0} distinct sources ·{" "}
              {report.composite?.coverage ?? 0}% module coverage
            </p>
          </div>
          <ScorePair report={report} />
          <div className="flex flex-wrap items-center gap-2">
            <select
              data-testid="lens-switcher"
              disabled={busy}
              value={report.persona_key}
              onChange={(e) => switchLens(e.target.value)}
              className="mono border border-indigo-500/50 bg-indigo-500/10 px-2.5 py-2 text-[11px] text-indigo-300 outline-none focus:border-indigo-400"
            >
              {personas.map((p) => (
                <option key={p.key} value={p.key} className="bg-zinc-950">{p.label}</option>
              ))}
            </select>
            <button
              data-testid="report-chat-open"
              onClick={() => setChatOpen(true)}
              className="mono inline-flex items-center gap-1.5 border border-zinc-800 px-2.5 py-2 text-[11px] uppercase tracking-wider text-zinc-400 transition-colors hover:border-indigo-500 hover:text-indigo-300"
            >
              <ChatCircleDots size={13} weight="duotone" /> Ask
            </button>
            <button
              data-testid="report-compare"
              onClick={() => navigate(`/app/compare?a=${report.locality_slug}`)}
              className="mono inline-flex items-center gap-1.5 border border-zinc-800 px-2.5 py-2 text-[11px] uppercase tracking-wider text-zinc-400 transition-colors hover:border-indigo-500 hover:text-indigo-300"
            >
              <GitDiff size={13} weight="duotone" /> Compare
            </button>
            <button
              data-testid="report-share"
              onClick={share}
              className="mono inline-flex items-center gap-1.5 border border-zinc-800 px-2.5 py-2 text-[11px] uppercase tracking-wider text-zinc-400 transition-colors hover:border-teal-500 hover:text-teal-300"
            >
              <ShareNetwork size={13} weight="duotone" /> Share
            </button>
            <button
              data-testid="report-invite"
              onClick={invite}
              className="mono inline-flex items-center gap-1.5 border border-zinc-800 px-2.5 py-2 text-[11px] uppercase tracking-wider text-zinc-400 transition-colors hover:border-teal-500 hover:text-teal-300"
            >
              <UsersThree size={13} weight="duotone" /> Ask residents
            </button>
            <button
              data-testid="report-regenerate"
              disabled={busy}
              onClick={regenerate}
              className="mono inline-flex items-center gap-1.5 border border-zinc-800 px-2.5 py-2 text-[11px] uppercase tracking-wider text-zinc-500 transition-colors hover:border-amber-500/60 hover:text-amber-300"
            >
              <ArrowClockwise size={13} /> Regenerate
            </button>
          </div>
        </div>
        {shareUrl ? (
          <div className="mt-3 flex items-center gap-2 rounded-lg border border-teal-500/40 bg-teal-500/10 px-3 py-2">
            <input
              readOnly
              value={shareUrl}
              data-testid="share-link"
              onFocus={(e) => e.target.select()}
              className="mono min-w-0 flex-1 bg-transparent text-[11px] text-teal-300 outline-none"
            />
            <button
              data-testid="share-copy"
              onClick={() => copyLink(shareUrl)}
              className="mono inline-flex shrink-0 items-center gap-1 rounded-full border border-teal-500/50 px-2.5 py-1 text-[10px] uppercase tracking-wider text-teal-300 transition-colors hover:bg-teal-500/20"
            >
              <Copy size={12} /> Copy
            </button>
          </div>
        ) : null}
        {inviteUrl ? (
          <div className="mt-2 rounded-lg border border-teal-500/40 bg-teal-500/10 px-3 py-2" data-testid="invite-panel">
            <p className="mono text-[10px] uppercase tracking-wider text-teal-300">
              Send this to someone who lives here
            </p>
            <div className="mt-1.5 flex items-center gap-2">
              <input
                readOnly
                value={inviteUrl}
                data-testid="invite-link"
                onFocus={(e) => e.target.select()}
                className="mono min-w-0 flex-1 bg-transparent text-[11px] text-teal-300 outline-none"
              />
              <button
                data-testid="invite-copy"
                onClick={() => copyLink(inviteUrl)}
                className="mono inline-flex shrink-0 items-center gap-1 rounded-full border border-teal-500/50 px-2.5 py-1 text-[10px] uppercase tracking-wider text-teal-300 transition-colors hover:bg-teal-500/20"
              >
                <Copy size={12} /> Copy
              </button>
            </div>
            <p className="mt-1 text-[10px] leading-snug text-zinc-500">
              No account needed. What they post publishes immediately as unverified — visible, but it
              never moves a score.
            </p>
          </div>
        ) : null}
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-w-0 space-y-4">
          {/* narrative */}
          <section className="panel border border-zinc-900 bg-surface px-5 py-5 lq-in" data-testid="report-narrative">
            <p className="overline text-indigo-400">What living here looks like — for you</p>
            <h2 className="mt-2 font-[Outfit] text-xl font-medium leading-snug tracking-tight text-zinc-50">
              {narrative.headline}
            </h2>
            {narrative.living_here ? (
              <p className="mt-3 text-sm leading-relaxed text-zinc-300">{narrative.living_here}</p>
            ) : null}
            {narrative.for_you ? (
              <p className="mt-3 border-l-2 border-indigo-500/60 pl-3 text-sm leading-relaxed text-zinc-300">
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
                  <p className="mt-0.5 text-[11px] text-zinc-500">{d.note}</p>
                </div>
              ))}
            </section>
          ) : null}

          {(dropped.length || pinned.length) ? (
            <div className="flex flex-wrap items-center gap-2 border border-zinc-900 px-3 py-2" data-testid="module-override-bar">
              <span className="overline text-zinc-600">Your overrides</span>
              {pinned.map((m) => (
                <span key={m} className="mono border border-indigo-500/50 px-1.5 py-[2px] text-[10px] text-indigo-300">pinned {m}</span>
              ))}
              {dropped.map((m) => (
                <button key={m} data-testid={`restore-${m}`} onClick={() => setDropped((d) => d.filter((x) => x !== m))}
                        className="mono border border-zinc-800 px-1.5 py-[2px] text-[10px] text-zinc-500 hover:text-zinc-200">
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
                  <span className="mono text-[11px] text-zinc-400">{name}</span>
                  <span className={`mono text-[10px] ${l.ok ? "text-emerald-400" : "text-red-400"}`}>
                    {l.ok ? "collected" : "absent"}
                  </span>
                </div>
              ))}
            </div>
            <p className="mt-2 text-[10px] leading-snug text-zinc-600">
              An absent layer is shown as absent throughout the report. It is never estimated.
            </p>
          </div>

          <div className="panel border border-zinc-900 bg-surface px-4 py-3">
            <div className="flex items-center justify-between">
              <p className="overline text-zinc-600">Sources ({report.sources?.length || 0})</p>
              <button
                data-testid="toggle-sources"
                onClick={() => setShowSources((v) => !v)}
                className="mono text-[10px] text-indigo-400 hover:underline"
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
                    className="block border border-zinc-900 px-2 py-1.5 transition-colors hover:border-indigo-500/50"
                  >
                    <SourceBadge type={s.type} />
                    <p className="mt-1 truncate text-[10px] text-zinc-500">{s.name}</p>
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
                ["kept", report.verifier_stats?.kept ?? 0, "text-emerald-400"],
                ["dropped", report.verifier_stats?.dropped ?? 0, "text-red-400"],
                ["disputed", report.verifier_stats?.disputed ?? 0, "text-amber-400"],
              ].map(([l, v, c]) => (
                <div key={l}>
                  <p className={`mono text-lg ${c}`}>{v}</p>
                  <p className="overline text-zinc-700">{l}</p>
                </div>
              ))}
            </div>
            {report.dropped?.length ? (
              <div className="mt-2 space-y-1">
                {report.dropped.slice(0, 4).map((d, i) => (
                  <p key={i} className="text-[10px] leading-snug text-zinc-600">
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
                  <span className="mono text-[11px] text-zinc-500">{l}</span>
                  <span className="mono text-[11px] text-zinc-300">{v ?? 0}</span>
                </div>
              ))}
            </div>
          </div>

          <button
            data-testid="report-trust-link"
            onClick={() => navigate("/app/trust")}
            className="mono flex w-full items-center justify-center gap-1.5 border border-zinc-800 py-2.5 text-[11px] uppercase tracking-wider text-zinc-400 transition-colors hover:border-indigo-500 hover:text-indigo-300"
          >
            <Scales size={13} weight="duotone" /> Read the scoring rubric
          </button>
          <button
            data-testid="report-community-link"
            onClick={() => navigate(`/app/community?locality=${report.locality_slug}`)}
            className="mono flex w-full items-center justify-center gap-1.5 border border-zinc-800 py-2.5 text-[11px] uppercase tracking-wider text-zinc-400 transition-colors hover:border-teal-500 hover:text-teal-300"
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
          className="fixed bottom-6 right-6 z-50 inline-flex items-center gap-2 border border-indigo-500 bg-indigo-600 px-4 py-3 text-xs font-medium text-white shadow-xl transition-transform hover:-translate-y-0.5"
        >
          <ChatCircleDots size={15} weight="duotone" /> Ask about {report.locality?.name?.split(" ")[0]}
        </button>
      ) : null}
    </div>
  );
}
