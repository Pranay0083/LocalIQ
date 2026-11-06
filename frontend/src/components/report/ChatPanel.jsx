import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { ArrowUp, X } from "@phosphor-icons/react";
import { API, api, errMessage } from "@/lib/api";

/* Grounded chat over one report: suggested questions, streamed answers, cited sources. */
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

export const ChatPanel = ({ reportId, report, open, onClose }) => {
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
          <p className="overline text-zinc-50">Grounded chat</p>
          <p className="text-sm text-zinc-500">Answers only from this dossier, with the same sources.</p>
        </div>
        <button data-testid="chat-close" onClick={onClose} className="text-zinc-600 hover:text-zinc-200">
          <X size={16} />
        </button>
      </header>

      <div className="flex-1 space-y-3 overflow-y-auto px-4 py-4" data-testid="chat-messages">
        {!messages.length ? (
          <div className="space-y-2">
            <p className="text-sm text-zinc-600">
              Built from the {suggestions.length} strongest modules in this report:
            </p>
            {suggestions.map((s) => (
              <button
                key={s.key}
                data-testid={`chat-suggestion-${s.key}`}
                onClick={() => send(null, s.q)}
                className="block w-full border border-zinc-900 px-3 py-2 text-left text-xs text-zinc-400 transition-colors hover:border-zinc-50/50 hover:text-zinc-50"
              >
                {s.q}
              </button>
            ))}
          </div>
        ) : null}
        {messages.map((m, i) => (
          <div key={i} className={m.role === "user" ? "flex justify-end" : ""} data-testid={`chat-message-${m.role}`}>
            <div className={`max-w-[92%] px-3 py-2 text-xs leading-relaxed ${
 m.role === "user" ? "bg-primary text-primary-foreground" : "panel border border-zinc-900 bg-surface2 text-zinc-300"
 }`}>
              {m.streaming && !m.content ? (
                <p className="mono text-sm text-zinc-600 caret" data-testid="chat-streaming">reading the dossier</p>
              ) : (
                <p className={`whitespace-pre-wrap ${m.streaming ? "caret" : ""}`}
                   data-testid={m.streaming ? "chat-streaming" : undefined}>{m.content}</p>
              )}
              {m.used_sources?.length ? (
                <div className="mt-2 flex flex-wrap gap-1 border-t border-zinc-800 pt-2">
                  {m.used_sources.slice(0, 6).map((s, k) => (
                    <span key={k} className="mono border border-zinc-800 px-1.5 py-[2px] text-xs text-zinc-500">
                      {s}
                    </span>
                  ))}
                </div>
              ) : null}
              {m.missing ? (
                <p className="mt-2 border-l-2 border-amber-500/60 pl-2 text-sm text-amber-300/80">
                  Can't answer: {m.missing}
                </p>
              ) : null}
              {m.error ? (
                <p className="mono mt-2 border-l-2 border-red-500/60 pl-2 text-sm text-red-400"
                   data-testid="chat-stream-error">
                  Stream interrupted: {m.error}
                </p>
              ) : null}
            </div>
          </div>
        ))}
        {busy && !messages.some((m) => m.streaming) ? (
          <p className="mono text-sm text-zinc-600 caret">thinking</p>
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
                className="mono shrink-0 whitespace-nowrap rounded-md border border-zinc-800 px-2.5 py-1 text-xs text-zinc-500 transition-colors hover:border-zinc-50/60 hover:text-zinc-50 disabled:opacity-40"
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
            className="mono flex-1 border border-zinc-800 bg-zinc-950 px-3 py-2 text-xs text-zinc-100 outline-none placeholder:text-zinc-700 focus:border-zinc-50"
          />
          <button
            data-testid="chat-send"
            disabled={busy}
            className="grid w-10 place-items-center border border-primary bg-primary text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-40"
          >
            <ArrowUp size={14} weight="bold" />
          </button>
        </div>
        <p className="mono mt-1.5 text-sm text-zinc-700">Unlimited inside an unlocked report.</p>
      </form>
    </aside>
    </>
  );
};
