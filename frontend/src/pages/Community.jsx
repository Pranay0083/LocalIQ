import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import {
  ArrowFatDown, ArrowFatUp, CheckCircle, Clock, Fire, Image as ImageIcon, PlusCircle,
  SealCheck, SealWarning, Trophy, WarningOctagon,
} from "@phosphor-icons/react";
import { ContributeDialog } from "@/components/community/ContributeDialog";
import { api, errMessage, fmtDate } from "@/lib/api";

const STATUS_META = {
  pending: { label: "Pending corroboration", icon: Clock, cls: "border-zinc-700 text-zinc-400" },
  unverified: { label: "Unverified · anonymous", icon: SealWarning, cls: "border-slate-500/50 text-slate-300" },
  corroborated: { label: "Corroborated", icon: CheckCircle, cls: "border-zinc-50/50 text-zinc-50" },
  verified: { label: "Verified", icon: SealCheck, cls: "border-emerald-500/50 text-emerald-300" },
  disputed: { label: "Disputed", icon: WarningOctagon, cls: "border-amber-500/50 text-amber-300" },
};

const SENTIMENT_CLS = {
  positive: "text-emerald-400", negative: "text-red-400",
  mixed: "text-amber-400", neutral: "text-zinc-500",
};

export default function Community() {
  const [params] = useSearchParams();
  const [localities, setLocalities] = useState([]);
  const [slug, setSlug] = useState(params.get("locality") || "");
  const [kind, setKind] = useState("");
  const [posts, setPosts] = useState([]);
  const [board, setBoard] = useState([]);
  const [mine, setMine] = useState(null);
  const [dialog, setDialog] = useState(false);

  const load = useCallback(async () => {
    const query = new URLSearchParams();
    if (slug) query.set("locality_slug", slug);
    if (kind) query.set("kind", kind);
    const [p, b, m] = await Promise.all([
      api.get(`/community/posts?${query.toString()}`),
      api.get(`/community/leaderboard${slug ? `?locality_slug=${slug}` : ""}`),
      api.get("/community/me"),
    ]);
    setPosts(p.data);
    setBoard(b.data);
    setMine(m.data);
  }, [slug, kind]);

  useEffect(() => {
    api.get("/localities").then((r) => setLocalities(r.data)).catch(() => {});
  }, []);
  useEffect(() => { load().catch(() => {}); }, [load]);

  const vote = async (postId, value) => {
    try {
      await api.post(`/community/posts/${postId}/vote`, { value });
      load();
    } catch (error) {
      toast.error(errMessage(error));
    }
  };

  return (
    <div className="grid gap-6 pb-16 lg:grid-cols-[minmax(0,1fr)_300px]">
      <div>
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold  text-zinc-100">
              What people who live there actually know
            </h1>
            <p className="mt-2 max-w-xl text-sm text-zinc-500">
              Experience posts are sentiment, never fact. Photo-backed fact claims can move a score —
              but only after independent residents corroborate them.
            </p>
          </div>
          <button
            data-testid="community-new-post"
            onClick={() => setDialog(true)}
            className="mono inline-flex items-center gap-1.5 border border-zinc-50 bg-zinc-50 px-4 py-2.5 text-xs text-white transition-colors hover:bg-zinc-50"
          >
            <PlusCircle size={13} /> Post
          </button>
        </div>

        <div className="mt-5 flex flex-wrap items-center gap-2">
          <select
            data-testid="community-locality-filter"
            value={slug}
            onChange={(e) => setSlug(e.target.value)}
            className="mono border border-zinc-800 bg-zinc-950 px-2 py-1.5 text-xs text-zinc-300 outline-none focus:border-zinc-50"
          >
            <option value="">All localities</option>
            {localities.map((l) => <option key={l.slug} value={l.slug}>{l.name}</option>)}
          </select>
          {[["", "Everything"], ["experience", "Experiences"], ["fact_claim", "Fact claims"]].map(([k, l]) => (
            <button
              key={k || "all"}
              data-testid={`community-filter-${k || "all"}`}
              onClick={() => setKind(k)}
              className={`mono border px-2.5 py-1.5 text-xs transition-colors ${
 kind === k ? "border-zinc-50/60 bg-zinc-50/10 text-zinc-50" : "border-zinc-800 text-zinc-500 hover:text-zinc-200"
 }`}
            >
              {l}
            </button>
          ))}
        </div>

        <div className="mt-4 space-y-3" data-testid="community-feed">
          {!posts.length ? (
            <div className="border border-dashed border-zinc-800 px-5 py-12 text-center" data-testid="community-empty">
              <p className="text-sm text-zinc-400">Nothing here yet.</p>
              <p className="mx-auto mt-1.5 max-w-md text-xs leading-relaxed text-zinc-600">
                This is the cold start, out in the open. Every report shows exactly which layers are
                thin — those are the gaps a resident can close in thirty seconds.
              </p>
              <button
                data-testid="community-empty-cta"
                onClick={() => setDialog(true)}
                className="mono mt-4 border border-zinc-50/60 bg-zinc-50/10 px-4 py-2 text-xs text-zinc-50 hover:bg-zinc-50/20"
              >
                Be the first
              </button>
            </div>
          ) : null}

          {posts.map((p) => {
            const meta = STATUS_META[p.status] || STATUS_META.pending;
            const Icon = meta.icon;
            return (
              <article key={p.id} className="panel border border-zinc-900 bg-surface px-4 py-3" data-testid={`post-${p.id}`}>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs font-medium text-zinc-200">{p.author_name}</span>
                  {p.anonymous ? (
                    <span className="overline border border-slate-500/40 px-1.5 py-[2px] text-slate-400"
                          data-testid={`post-anonymous-${p.id}`}>
                      via shared link
                    </span>
                  ) : null}
                  <span className="mono text-xs text-zinc-600">
                    {localities.find((l) => l.slug === p.locality_slug)?.name || p.locality_slug}
                  </span>
                  <span className="mono text-xs text-zinc-700">{fmtDate(p.created_at)}</span>
                  {p.kind === "fact_claim" || p.anonymous ? (
                    <span className={`overline inline-flex items-center gap-1 border px-1.5 py-[2px] ${meta.cls}`}>
                      <Icon size={9} weight="fill" /> {meta.label}
                    </span>
                  ) : (
                    <span className={`overline ${SENTIMENT_CLS[p.sentiment] || "text-zinc-500"}`}>
                      {p.sentiment}
                    </span>
                  )}
                  {p.credit_granted ? (
                    <span className="overline border border-zinc-50/40 px-1.5 py-[2px] text-zinc-50">credit earned</span>
                  ) : null}
                </div>

                {p.kind === "fact_claim" ? (
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <span className="mono border border-zinc-800 px-1.5 py-[2px] text-xs text-zinc-400">
                      {String(p.claim_type).replace(/_/g, " ")}
                    </span>
                    {p.claim_value ? (
                      <span className="mono text-xs text-zinc-100">{p.claim_value}</span>
                    ) : null}
                  </div>
                ) : null}

                <p className="mt-2 text-sm leading-relaxed text-zinc-300">{p.body}</p>

                {p.topics?.length ? (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {p.topics.map((t) => (
                      <span key={t} className="mono border border-zinc-900 px-1.5 py-[2px] text-xs text-zinc-600">
                        #{t}
                      </span>
                    ))}
                  </div>
                ) : null}

                {p.proof_url ? (
                  <a
                    href={`${process.env.REACT_APP_BACKEND_URL}${p.proof_url}`}
                    target="_blank"
                    rel="noreferrer"
                    data-testid={`post-proof-${p.id}`}
                    className="mono mt-2 inline-flex items-center gap-1 text-xs text-zinc-50 hover:underline"
                  >
                    <ImageIcon size={11} /> view proof
                  </a>
                ) : null}

                <div className="mt-3 flex items-center gap-2 border-t border-zinc-900 pt-2">
                  <button
                    data-testid={`upvote-${p.id}`}
                    onClick={() => vote(p.id, 1)}
                    className="mono inline-flex items-center gap-1 border border-zinc-800 px-2 py-1 text-xs text-zinc-400 transition-colors hover:border-emerald-500/50 hover:text-emerald-300"
                  >
                    <ArrowFatUp size={11} /> {p.upvotes || 0}
                  </button>
                  <button
                    data-testid={`downvote-${p.id}`}
                    onClick={() => vote(p.id, -1)}
                    className="mono inline-flex items-center gap-1 border border-zinc-800 px-2 py-1 text-xs text-zinc-400 transition-colors hover:border-red-500/50 hover:text-red-300"
                  >
                    <ArrowFatDown size={11} /> {p.downvotes || 0}
                  </button>
                  {p.pii_scrubbed ? (
                    <span className="mono text-xs text-zinc-700">{p.pii_scrubbed} PII item(s) auto-removed</span>
                  ) : null}
                </div>
              </article>
            );
          })}
        </div>
      </div>

      <aside className="space-y-3 lg:sticky lg:top-24 lg:self-start">
        <div className="panel border border-zinc-900 bg-surface px-4 py-3" data-testid="contributor-stats">
          <p className="overline text-zinc-600">Your contributions</p>
          <div className="mt-2 grid grid-cols-2 gap-2">
            {[
              ["posts", mine?.stats?.total ?? 0],
              ["verified", mine?.stats?.verified ?? 0],
              ["upvotes", mine?.stats?.upvotes ?? 0],
              ["credits", mine?.stats?.credits_earned ?? 0],
            ].map(([l, v]) => (
              <div key={l}>
                <p className="mono text-xl text-zinc-100">{v}</p>
                <p className="overline text-zinc-700">{l}</p>
              </div>
            ))}
          </div>
          {mine?.stats?.streak_days ? (
            <p className="mono mt-2 inline-flex items-center gap-1 text-xs text-amber-300">
              <Fire size={11} weight="fill" /> {mine.stats.streak_days}-day streak
            </p>
          ) : null}
        </div>

        <div className="panel border border-zinc-900 bg-surface px-4 py-3" data-testid="leaderboard">
          <p className="overline flex items-center gap-1.5 text-zinc-600">
            <Trophy size={11} weight="duotone" /> Top contributors
          </p>
          <div className="mt-2 space-y-1.5">
            {board.map((row, i) => (
              <div key={row.user_id} className="flex items-center justify-between gap-2">
                <span className="flex min-w-0 items-center gap-2">
                  <span className="mono w-4 text-xs text-zinc-700">{i + 1}</span>
                  <span className="truncate text-xs text-zinc-300">{row.name}</span>
                </span>
                <span className="mono shrink-0 text-xs text-zinc-500">
                  {row.verified}v · {row.upvotes}↑
                </span>
              </div>
            ))}
            {!board.length ? <p className="text-xs text-zinc-600">No contributors yet.</p> : null}
          </div>
        </div>

        <div className="panel border border-zinc-900 bg-surface px-4 py-3">
          <p className="overline text-zinc-600">How verification works</p>
          <ol className="mt-2 space-y-1.5 text-xs leading-snug text-zinc-500">
            <li><span className="text-zinc-300">1.</span> Post a fact claim with a photo or screenshot.</li>
            <li><span className="text-zinc-300">2.</span> Two independent residents with proof → corroborated.</li>
            <li><span className="text-zinc-300">3.</span> Three → verified, and the scorer can use it.</li>
            <li><span className="text-zinc-300">4.</span> Contradicts an official source → disputed, sent to moderation.</li>
            <li><span className="text-zinc-300">5.</span> Corroborated claims earn you a free report credit.</li>
          </ol>
        </div>
      </aside>

      <ContributeDialog
        open={dialog}
        onClose={() => setDialog(false)}
        localitySlug={slug || localities[0]?.slug}
        onDone={() => { setDialog(false); load(); toast.success("Posted."); }}
      />
    </div>
  );
}
