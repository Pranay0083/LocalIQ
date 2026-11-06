import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Camera, X } from "@phosphor-icons/react";
import { api, errMessage } from "@/lib/api";

const CLAIM_TYPES = [
  ["water_hours", "Water supply hours"],
  ["water_quality", "Water quality"],
  ["power_cuts", "Power cuts"],
  ["noise", "Noise / construction"],
  ["parking", "Parking"],
  ["rent_paid", "Rent actually paid"],
  ["safety_night", "Late-night safety"],
  ["internet", "Internet reliability"],
  ["other", "Something else"],
];

const MODULE_CLAIM = {
  water: "water_hours", power: "power_cuts", noise: "noise", cost: "rent_paid",
  safety_night: "safety_night", internet_wfh: "internet", infrastructure: "other",
};

export const ContributeDialog = ({ open, onClose, localitySlug, card, onDone, defaultKind }) => {
  const [kind, setKind] = useState(defaultKind || "experience");
  const [body, setBody] = useState("");
  const [claimType, setClaimType] = useState("other");
  const [claimValue, setClaimValue] = useState("");
  const [proofId, setProofId] = useState(null);
  const [proofPreview, setProofPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    setKind(card ? "fact_claim" : defaultKind || "experience");
    setClaimType(card ? MODULE_CLAIM[card.module] || "other" : "other");
    setBody("");
    setClaimValue("");
    setProofId(null);
    setProofPreview(null);
  }, [open, card, defaultKind]);

  const upload = async (file) => {
    if (!file) return;
    if (file.size > 3 * 1024 * 1024) return toast.error("Image must be under 3 MB");
    const reader = new FileReader();
    reader.onload = async () => {
      try {
        const { data } = await api.post("/community/proof", { data_url: reader.result });
        setProofId(data.proof_id);
        setProofPreview(reader.result);
        toast.success("Proof attached");
      } catch (error) {
        toast.error(errMessage(error));
      }
    };
    reader.readAsDataURL(file);
  };

  const submit = async () => {
    setBusy(true);
    try {
      await api.post("/community/posts", {
        locality_slug: localitySlug,
        kind,
        body,
        claim_type: kind === "fact_claim" ? claimType : null,
        claim_value: kind === "fact_claim" ? claimValue : null,
        proof_id: kind === "fact_claim" ? proofId : null,
      });
      onDone?.();
    } catch (error) {
      toast.error(errMessage(error));
    } finally {
      setBusy(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[70] grid place-items-center bg-black/70 px-4" data-testid="contribute-dialog">
      <div className="panel max-h-[92vh] w-full max-w-lg overflow-y-auto rounded-xl border border-zinc-800 bg-surface">
        <header className="flex items-start justify-between border-b border-zinc-900 px-4 py-3">
          <div>
            <p className="overline text-zinc-50">Fill a gap</p>
            <h3 className="mt-1 text-lg font-medium text-zinc-100">
              {card ? card.title : "Tell people what it's actually like"}
            </h3>
            <p className="mt-0.5 text-xs text-zinc-500">
              {card?.empty?.missing?.length
                ? `Missing: ${card.empty.missing.join(" · ")}`
                : "Photo-backed fact claims can move a score. Experiences never do."}
            </p>
          </div>
          <button onClick={onClose} data-testid="contribute-close" className="text-zinc-600 hover:text-zinc-200">
            <X size={16} />
          </button>
        </header>

        <div className="space-y-3 px-4 py-4">
          <div className="flex border border-zinc-800">
            {[["experience", "Experience post"], ["fact_claim", "Fact claim (needs proof)"]].map(([k, l]) => (
              <button
                key={k}
                data-testid={`contribute-kind-${k}`}
                onClick={() => setKind(k)}
                className={`mono flex-1 py-2 text-xs transition-colors ${
 kind === k ? "bg-zinc-50 text-white" : "text-zinc-500 hover:text-zinc-200"
 }`}
              >
                {l}
              </button>
            ))}
          </div>

          {kind === "fact_claim" ? (
            <div className="grid gap-2 sm:grid-cols-2">
              <div>
                <p className="overline mb-1 text-zinc-600">Claim type</p>
                <select
                  data-testid="contribute-claim-type"
                  value={claimType}
                  onChange={(e) => setClaimType(e.target.value)}
                  className="mono w-full border border-zinc-800 bg-zinc-950 px-2 py-2 text-xs text-zinc-100 outline-none focus:border-zinc-50"
                >
                  {CLAIM_TYPES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
                </select>
              </div>
              <div>
                <p className="overline mb-1 text-zinc-600">The value</p>
                <input
                  data-testid="contribute-claim-value"
                  value={claimValue}
                  onChange={(e) => setClaimValue(e.target.value)}
                  placeholder="e.g. 6am–8am daily, or 4 cuts/month"
                  className="mono w-full border border-zinc-800 bg-zinc-950 px-2 py-2 text-xs text-zinc-100 outline-none placeholder:text-zinc-700 focus:border-zinc-50"
                />
              </div>
            </div>
          ) : null}

          <div>
            <p className="overline mb-1 text-zinc-600">What happened / what you know</p>
            <textarea
              data-testid="contribute-body"
              rows={4}
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder="Be specific. Phone numbers and emails are stripped automatically before publication."
              className="w-full border border-zinc-800 bg-zinc-950 px-3 py-2 text-sm leading-relaxed text-zinc-100 outline-none placeholder:text-zinc-700 focus:border-zinc-50"
            />
            <p className="mono mt-1 text-xs text-zinc-700">{body.length}/2000 · minimum 10 characters</p>
          </div>

          {kind === "fact_claim" ? (
            <div>
              <p className="overline mb-1 text-zinc-600">Proof (required)</p>
              <input
                ref={fileRef}
                type="file"
                accept="image/*"
                data-testid="contribute-proof-input"
                onChange={(e) => upload(e.target.files?.[0])}
                className="hidden"
              />
              <button
                data-testid="contribute-proof-btn"
                onClick={() => fileRef.current?.click()}
                className="mono inline-flex items-center gap-2 border border-zinc-800 px-3 py-2 text-xs text-zinc-400 transition-colors hover:border-zinc-50 hover:text-zinc-50"
              >
                <Camera size={14} /> {proofId ? "Replace photo" : "Attach photo or screenshot"}
              </button>
              {proofPreview ? (
                <img src={proofPreview} alt="proof" className="mt-2 h-24 border border-zinc-800 object-cover" />
              ) : null}
            </div>
          ) : null}

          <p className="border-l-2 border-zinc-800 pl-2 text-xs leading-snug text-zinc-600">
            Fact claims need independent corroboration from other residents before the scorer treats
            them as fact. A claim that contradicts an official source raises a dispute — it never
            silently overrides. Corroborated contributions earn a free report credit.
          </p>
        </div>

        <footer className="flex items-center justify-end gap-2 border-t border-zinc-900 px-4 py-3">
          <button onClick={onClose} className="mono border border-zinc-800 px-3 py-2 text-xs text-zinc-500 hover:text-zinc-200">
            Cancel
          </button>
          <button
            data-testid="contribute-submit"
            disabled={busy || body.trim().length < 10 || (kind === "fact_claim" && !proofId)}
            onClick={submit}
            className="mono border border-zinc-50 bg-zinc-50 px-4 py-2 text-xs text-white transition-colors hover:bg-zinc-50 disabled:opacity-40"
          >
            {busy ? "Posting…" : "Post"}
          </button>
        </footer>
      </div>
    </div>
  );
};
