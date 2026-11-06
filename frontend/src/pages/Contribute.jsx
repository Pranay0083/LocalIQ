import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { toast } from "sonner";
import {
  ArrowRight, Camera, ChartLineUp, CheckCircle, Info, MapPin, SealWarning,
} from "@phosphor-icons/react";
import { ThemeToggle } from "@/components/layout/ThemeToggle";
import { api, errMessage, fmtDate } from "@/lib/api";

const Field = ({ label, hint, children }) => (
  <div>
    <p className="overline mb-1 text-zinc-600">{label}</p>
    {children}
    {hint ? <p className="mono mt-1 text-xs text-zinc-600">{hint}</p> : null}
  </div>
);

export default function Contribute() {
  const { token } = useParams();
  const [link, setLink] = useState(null);
  const [error, setError] = useState("");
  const [kind, setKind] = useState("fact_claim");
  const [claimType, setClaimType] = useState("water_hours");
  const [claimValue, setClaimValue] = useState("");
  const [body, setBody] = useState("");
  const [name, setName] = useState("");
  const [proofId, setProofId] = useState(null);
  const [proofPreview, setProofPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [posted, setPosted] = useState(null);
  const fileRef = useRef(null);

  useEffect(() => {
    api.get(`/public/contribute/${token}`)
      .then((r) => {
        setLink(r.data);
        const firstGap = (r.data.gaps || [])[0];
        if (firstGap?.claim_type) setClaimType(firstGap.claim_type);
        document.title = `Tell buyers about ${r.data.locality?.name || "your area"} — LocalIQ`;
      })
      .catch(() => setError("This contribution link is not valid, or it was withdrawn."));
  }, [token]);

  const upload = (file) => {
    if (!file) return;
    if (file.size > 3 * 1024 * 1024) return toast.error("Image must be under 3 MB");
    const reader = new FileReader();
    reader.onload = async () => {
      try {
        const { data } = await api.post(`/public/contribute/${token}/proof`, { data_url: reader.result });
        setProofId(data.proof_id);
        setProofPreview(reader.result);
        toast.success("Photo attached");
      } catch (err) {
        toast.error(errMessage(err));
      }
    };
    reader.readAsDataURL(file);
  };

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const { data } = await api.post(`/public/contribute/${token}`, {
        kind,
        claim_type: kind === "fact_claim" ? claimType : null,
        claim_value: kind === "fact_claim" ? claimValue : null,
        body,
        proof_id: proofId,
        display_name: name || null,
      });
      setPosted(data);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (err) {
      toast.error(errMessage(err));
    } finally {
      setBusy(false);
    }
  };

  if (error) {
    return (
      <div className="grid min-h-screen place-items-center px-6">
        <div className="text-center" data-testid="contribute-error">
          <p className="overline text-zinc-600">Dead link</p>
          <h1 className="mt-2 text-2xl font-medium text-zinc-100">{error}</h1>
          <Link
            to="/auth?mode=register"
            data-testid="contribute-error-cta"
            className="mono mt-6 inline-flex rounded-md border border-primary bg-primary px-5 py-2.5 text-xs text-primary-foreground"
          >
            Run your own report
          </Link>
        </div>
      </div>
    );
  }

  if (!link) {
    return (
      <p className="mono py-32 text-center text-xs text-zinc-600 caret">
        opening contribution link
      </p>
    );
  }

  const locality = link.locality || {};

  return (
    <div className="min-h-screen pb-20" data-testid="contribute-page">
      <header className="glass sticky top-0 z-50 border-b border-zinc-900">
        <div className="mx-auto flex h-14 max-w-[880px] items-center gap-3 px-4 sm:px-6">
          <Link to="/" className="flex items-center gap-2">
            <span className="grid h-7 w-7 place-items-center rounded-md bg-zinc-50">
              <ChartLineUp size={15} weight="bold" className="text-white" />
            </span>
            <span className="text-[15px] font-semibold tracking-tight text-zinc-100">
              LocalIQ
            </span>
          </Link>
          <span className="mono hidden text-xs text-zinc-600 sm:inline">
            resident contribution
          </span>
          <div className="ml-auto flex items-center gap-2">
            <ThemeToggle />
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[880px] px-4 sm:px-6">
        <section className="py-8 lq-in">
          <p className="overline inline-flex items-center gap-1.5 text-zinc-50">
            <MapPin size={12} weight="duotone" /> {locality.pincode} · {locality.zone} Bengaluru
          </p>
          <h1 className="mt-2 text-3xl font-medium tracking-tight text-zinc-50 sm:text-4xl"
              data-testid="contribute-locality">
            What is {locality.name} actually like to live in?
          </h1>
          <p className="mt-3 max-w-2xl text-sm leading-relaxed text-zinc-400">
            {link.invited_by} is comparing localities on LocalIQ and hit the same wall everyone does:
            water hours, power cuts, real rents and night-time noise are not in any dataset. You live
            there. No account needed — {link.locality_total} contribution(s) so far.
          </p>
        </section>

        {posted ? (
          <section className="panel rounded-xl border border-zinc-50/40 bg-zinc-50/5 px-5 py-6"
                   data-testid="contribute-success">
            <p className="overline inline-flex items-center gap-1.5 text-zinc-50">
              <CheckCircle size={13} weight="fill" /> Published
            </p>
            <h2 className="mt-2 text-xl font-medium text-zinc-50">
              It is live on {locality.name} right now.
            </h2>
            <p className="mt-2 max-w-xl text-sm leading-relaxed text-zinc-400">{posted.message}</p>
            <div className="panel mt-4 rounded-lg border border-zinc-900 bg-surface px-4 py-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-medium text-zinc-200">{posted.post.author_name}</span>
                <span className="overline inline-flex items-center gap-1 border border-slate-500/50 px-1.5 py-[2px] text-slate-300">
                  <SealWarning size={9} weight="fill" /> Unverified · anonymous
                </span>
              </div>
              <p className="mt-2 text-sm leading-relaxed text-zinc-300">{posted.post.body}</p>
            </div>
            <div className="mt-5 flex flex-wrap gap-2">
              <button
                data-testid="contribute-again"
                onClick={() => { setPosted(null); setBody(""); setClaimValue(""); setProofId(null); setProofPreview(null); }}
                className="mono rounded-md border border-zinc-800 px-4 py-2 text-xs text-zinc-400 hover:border-zinc-50 hover:text-zinc-50"
              >
                Add another
              </button>
              <Link
                to="/auth?mode=register"
                data-testid="contribute-cta-signup"
                className="mono inline-flex items-center gap-2 rounded-md border border-primary bg-primary px-4 py-2 text-xs text-primary-foreground hover:bg-primary/90"
              >
                See the full {locality.name} report — 5 free
                <ArrowRight size={13} weight="bold" />
              </Link>
            </div>
          </section>
        ) : (
          <>
            {link.gaps?.length ? (
              <section className="mb-5" data-testid="contribute-gaps">
                <p className="overline text-zinc-600">The gaps in this report right now</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {link.gaps.map((gap) => (
                    <button
                      key={gap.module}
                      data-testid={`contribute-gap-${gap.module}`}
                      onClick={() => { setKind("fact_claim"); setClaimType(gap.claim_type); }}
                      className={`rounded-lg border px-3 py-2 text-left transition-colors ${
 claimType === gap.claim_type
 ? "border-zinc-50/60 bg-zinc-50/10"
 : "border-zinc-900 bg-surface hover:border-zinc-50/50"
 }`}
                    >
                      <p className="text-xs font-medium text-zinc-200">{gap.title}</p>
                      <p className="mono mt-0.5 text-xs text-zinc-600">
                        {(gap.missing || []).slice(0, 3).join(" · ")}
                      </p>
                    </button>
                  ))}
                </div>
              </section>
            ) : null}

            <form onSubmit={submit} className="panel rounded-xl border border-zinc-900 bg-surface px-5 py-5"
                  data-testid="contribute-form">
              <div className="flex overflow-hidden rounded-lg border border-zinc-800">
                {[["fact_claim", "Fact claim"], ["experience", "Experience"]].map(([k, label]) => (
                  <button
                    key={k}
                    type="button"
                    data-testid={`contribute-kind-${k}`}
                    onClick={() => setKind(k)}
                    className={`mono flex-1 py-2 text-xs transition-colors ${
 kind === k ? "bg-zinc-50 text-white" : "text-zinc-500 hover:text-zinc-200"
 }`}
                  >
                    {label}
                  </button>
                ))}
              </div>

              <div className="mt-4 space-y-3">
                {kind === "fact_claim" ? (
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Field label="What is it about">
                      <select
                        data-testid="contribute-claim-type"
                        value={claimType}
                        onChange={(e) => setClaimType(e.target.value)}
                        className="mono w-full rounded-lg border border-zinc-800 bg-surface2 px-2 py-2 text-xs text-zinc-100 outline-none focus:border-zinc-50"
                      >
                        {link.claim_types.map((c) => (
                          <option key={c.key} value={c.key}>{c.label}</option>
                        ))}
                      </select>
                    </Field>
                    <Field label="The value" hint="A number or a window beats an adjective.">
                      <input
                        data-testid="contribute-claim-value"
                        value={claimValue}
                        onChange={(e) => setClaimValue(e.target.value)}
                        placeholder="e.g. 6am–8am daily, or 4 cuts/month"
                        className="mono w-full rounded-lg border border-zinc-800 bg-surface2 px-2 py-2 text-xs text-zinc-100 outline-none placeholder:text-zinc-700 focus:border-zinc-50"
                      />
                    </Field>
                  </div>
                ) : null}

                <Field label="What you know" hint={`${body.length}/2000 · minimum 10 characters`}>
                  <textarea
                    data-testid="contribute-body"
                    rows={5}
                    value={body}
                    onChange={(e) => setBody(e.target.value)}
                    placeholder="Be specific — which street, which months, how often. Phone numbers and emails are stripped automatically before publication."
                    className="w-full rounded-lg border border-zinc-800 bg-surface2 px-3 py-2 text-sm leading-relaxed text-zinc-100 outline-none placeholder:text-zinc-700 focus:border-zinc-50"
                  />
                </Field>

                <div className="grid gap-3 sm:grid-cols-2">
                  <Field label="Name to show" hint="Optional. Leave blank to stay anonymous.">
                    <input
                      data-testid="contribute-name"
                      value={name}
                      maxLength={32}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="Anonymous resident"
                      className="mono w-full rounded-lg border border-zinc-800 bg-surface2 px-2 py-2 text-xs text-zinc-100 outline-none placeholder:text-zinc-700 focus:border-zinc-50"
                    />
                  </Field>
                  <Field label="Photo or screenshot" hint="Optional, but proof is what gets a claim promoted later.">
                    <input
                      ref={fileRef}
                      type="file"
                      accept="image/*"
                      data-testid="contribute-proof-input"
                      onChange={(e) => upload(e.target.files?.[0])}
                      className="hidden"
                    />
                    <button
                      type="button"
                      data-testid="contribute-proof-btn"
                      onClick={() => fileRef.current?.click()}
                      className="mono inline-flex items-center gap-2 rounded-lg border border-zinc-800 px-3 py-2 text-xs text-zinc-400 transition-colors hover:border-zinc-50 hover:text-zinc-50"
                    >
                      <Camera size={14} /> {proofId ? "Replace photo" : "Attach"}
                    </button>
                    {proofPreview ? (
                      <img src={proofPreview} alt="proof" className="mt-2 h-20 rounded border border-zinc-800 object-cover" />
                    ) : null}
                  </Field>
                </div>

                <div className="flex gap-2 rounded-lg border border-zinc-900 bg-surface2 px-3 py-2">
                  <Info size={13} weight="duotone" className="mt-[1px] shrink-0 text-slate-400" />
                  <p className="text-xs leading-snug text-zinc-500">
                    Anonymous contributions publish immediately and are labelled{" "}
                    <span className="text-slate-300">unverified</span>. They are shown in the report
                    for context, they cannot move a score on their own, and they cannot corroborate another
                    resident&apos;s claim — only accounts with photo proof can do that.
                  </p>
                </div>
              </div>

              <div className="mt-4 flex items-center justify-end gap-2">
                <button
                  data-testid="contribute-submit"
                  disabled={busy || body.trim().length < 10}
                  className="mono rounded-md border border-zinc-50 bg-zinc-50 px-5 py-2.5 text-xs text-white transition-colors hover:bg-zinc-50 disabled:opacity-40"
                >
                  {busy ? "Publishing…" : "Publish"}
                </button>
              </div>
            </form>
          </>
        )}

        {link.recent?.length ? (
          <section className="mt-8" data-testid="contribute-recent">
            <p className="overline text-zinc-600">Recently added for {locality.name}</p>
            <div className="mt-2 space-y-2">
              {link.recent.map((post) => (
                <div key={post.id} className="panel rounded-lg border border-zinc-900 bg-surface px-4 py-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs font-medium text-zinc-300">{post.author_name}</span>
                    <span className="mono text-xs text-zinc-700">{fmtDate(post.created_at)}</span>
                    {post.claim_type ? (
                      <span className="mono rounded border border-zinc-800 px-1.5 py-[1px] text-xs text-zinc-500">
                        {String(post.claim_type).replace(/_/g, " ")}
                      </span>
                    ) : null}
                  </div>
                  <p className="mt-1.5 text-xs leading-relaxed text-zinc-500">{post.body}</p>
                </div>
              ))}
            </div>
          </section>
        ) : null}

        <p className="mono mt-10 text-xs leading-relaxed text-zinc-700">
          LocalIQ is decision support, not advice. Contributions are scrubbed for phone numbers,
          emails and ID numbers before they are published, and are screened for harassment.
        </p>
      </main>
    </div>
  );
}
