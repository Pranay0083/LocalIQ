import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Check, CreditCard, Cube, Lightning, Receipt } from "@phosphor-icons/react";
import { useAuth } from "@/context/AuthContext";
import { api, errMessage, fmtDate } from "@/lib/api";

const loadRazorpay = () =>
  new Promise((resolve) => {
    if (window.Razorpay) return resolve(true);
    const script = document.createElement("script");
    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    script.onload = () => resolve(true);
    script.onerror = () => resolve(false);
    document.body.appendChild(script);
  });

export default function Account() {
  const { user, refresh } = useAuth();
  const [plans, setPlans] = useState(null);
  const [entitlement, setEntitlement] = useState(null);
  const [traces, setTraces] = useState(null);
  const [busy, setBusy] = useState(null);

  const load = useCallback(async () => {
    const [p, e, t] = await Promise.all([
      api.get("/billing/plans"), api.get("/entitlement"), api.get("/traces"),
    ]);
    setPlans(p.data);
    setEntitlement(e.data);
    setTraces(t.data);
  }, []);

  useEffect(() => { load().catch(() => {}); }, [load]);

  const checkout = async (planKey) => {
    setBusy(planKey);
    try {
      const ok = await loadRazorpay();
      if (!ok) throw new Error("Could not load Razorpay checkout");
      const { data } = await api.post("/billing/order", { plan: planKey });
      const rzp = new window.Razorpay({
        key: data.key_id,
        amount: data.amount,
        currency: data.currency,
        order_id: data.order_id,
        name: "LocalIQ",
        description: `${data.plan.label} — Bengaluru neighbourhood reports`,
        theme: { color: "#4f46e5" },
        prefill: { name: user?.name, email: user?.email },
        handler: async (response) => {
          try {
            await api.post("/billing/verify", response);
            toast.success("Payment verified. Pro unlocked.");
            await refresh();
            await load();
          } catch (error) {
            toast.error(errMessage(error));
          }
        },
        modal: { ondismiss: () => toast.message("Checkout closed") },
      });
      rzp.open();
    } catch (error) {
      toast.error(errMessage(error));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="space-y-6 pb-16">
      <div>
        <p className="overline text-indigo-400">Account</p>
        <h1 className="mt-2 font-[Outfit] text-3xl font-light tracking-tight text-zinc-100">
          {user?.name}
        </h1>
        <p className="mono mt-1 text-[11px] text-zinc-600">{user?.email}</p>
      </div>

      <div className="grid-skeleton grid border-b border-r border-zinc-900 sm:grid-cols-4">
        {[
          ["Plan", entitlement?.plan?.replace("_", " ") || "free"],
          ["Reports used", entitlement?.used ?? 0],
          ["Free left", entitlement?.pro ? "∞" : entitlement?.free_left ?? 0],
          ["Credits earned", entitlement?.credits ?? 0],
        ].map(([l, v]) => (
          <div key={l} className="bg-surface px-4 py-3" data-testid={`account-stat-${l.toLowerCase().replace(/ /g, "-")}`}>
            <p className="overline text-zinc-600">{l}</p>
            <p className="mono mt-1 text-2xl text-zinc-100">{v}</p>
          </div>
        ))}
      </div>

      <section>
        <p className="overline mb-3 text-zinc-600">Plans · Razorpay test mode</p>
        <div className="grid-skeleton grid border-b border-r border-zinc-900 md:grid-cols-3">
          <div className="bg-surface px-5 py-5" data-testid="plan-free">
            <p className="overline text-zinc-600">{plans?.free?.label || "Free"}</p>
            <p className="mono mt-2 text-3xl text-zinc-100">{plans?.free?.display || "₹0"}</p>
            <ul className="mt-3 space-y-1.5">
              {(plans?.free?.features || []).map((f) => (
                <li key={f} className="flex gap-2 text-xs text-zinc-500">
                  <Check size={13} className="mt-0.5 shrink-0 text-zinc-700" /> {f}
                </li>
              ))}
            </ul>
            {entitlement?.plan === "free" ? (
              <p className="mono mt-4 border border-zinc-800 py-2 text-center text-[10px] uppercase tracking-wider text-zinc-500">
                Current plan
              </p>
            ) : null}
          </div>

          {(plans?.paid || []).map((p) => (
            <div key={p.key} className={`px-5 py-5 ${p.key === "pro_monthly" ? "bg-indigo-600/10 ring-1 ring-inset ring-indigo-500/30" : "bg-surface"}`}
                 data-testid={`plan-${p.key}`}>
              <p className="overline text-indigo-300">{p.label}</p>
              <p className="mono mt-2 text-3xl text-zinc-100">
                {p.display}
                <span className="ml-1 text-xs text-zinc-500">/{p.period}</span>
              </p>
              <ul className="mt-3 space-y-1.5">
                {p.features.map((f) => (
                  <li key={f} className="flex gap-2 text-xs text-zinc-400">
                    <Check size={13} className="mt-0.5 shrink-0 text-indigo-400" /> {f}
                  </li>
                ))}
              </ul>
              {entitlement?.plan === p.key ? (
                <p className="mono mt-4 border border-emerald-800 bg-emerald-950/30 py-2 text-center text-[10px] uppercase tracking-wider text-emerald-300">
                  Active
                </p>
              ) : (
                <button
                  data-testid={`checkout-${p.key}`}
                  disabled={busy === p.key}
                  onClick={() => checkout(p.key)}
                  className="mono mt-4 inline-flex w-full items-center justify-center gap-2 border border-indigo-500 bg-indigo-600 py-2.5 text-[11px] uppercase tracking-wider text-white transition-colors hover:bg-indigo-500 disabled:opacity-40"
                >
                  <CreditCard size={13} /> {busy === p.key ? "Opening…" : "Upgrade"}
                </button>
              )}
            </div>
          ))}
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-3 panel border border-zinc-900 bg-surface px-4 py-3">
          <Receipt size={16} className="text-zinc-600" />
          <p className="mono text-[10px] leading-relaxed text-zinc-500">
            TEST MODE. Use card 4111 1111 1111 1111, any future expiry, any CVV, OTP 1234. No real
            money moves. Signature verification and webhook handling are live — switching to
            production is a key swap, not a rebuild.
          </p>
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <div className="panel border border-zinc-900 bg-surface px-4 py-3">
          <p className="overline flex items-center gap-1.5 text-teal-400">
            <Cube size={12} weight="duotone" /> Earn reports instead of buying them
          </p>
          <p className="mt-2 text-xs leading-relaxed text-zinc-400">
            Post a photo-backed fact claim about water hours, power cuts, noise or the rent you
            actually pay. When two other residents corroborate it independently, you earn a free
            report credit — and the locality's score gets a signal nobody else has.
          </p>
          <p className="mono mt-2 text-2xl text-teal-300" data-testid="account-credits">
            {entitlement?.credits ?? 0} <span className="text-xs text-zinc-600">credits</span>
          </p>
        </div>

        <div className="panel border border-zinc-900 bg-surface px-4 py-3" data-testid="account-ledger">
          <p className="overline flex items-center gap-1.5 text-zinc-600">
            <Lightning size={12} weight="duotone" /> Agent ledger (this server)
          </p>
          <div className="mt-2 grid grid-cols-2 gap-2">
            {[
              ["LLM calls", traces?.ledger?.calls],
              ["Web searches", traces?.ledger?.searches],
              ["Prompt tokens", traces?.ledger?.prompt],
              ["Est. spend", `$${traces?.ledger?.est_cost_usd ?? 0}`],
            ].map(([l, v]) => (
              <div key={l}>
                <p className="overline text-zinc-700">{l}</p>
                <p className="mono text-lg text-zinc-200">{v ?? 0}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section>
        <p className="overline mb-3 text-zinc-600">Recent agent runs</p>
        <div className="border border-zinc-900" data-testid="account-runs">
          {(traces?.jobs || []).slice(0, 8).map((j) => (
            <div key={j.job_id} className="flex flex-wrap items-center gap-3 border-b border-zinc-900/60 px-3 py-2 last:border-0">
              <span className="mono w-20 shrink-0 text-[10px] text-zinc-700">{j.job_id.slice(0, 8)}</span>
              <span className="text-xs text-zinc-300">{j.locality_name}</span>
              <span className="mono text-[10px] text-zinc-600">{j.persona_key}</span>
              <span className={`mono text-[10px] ${j.status === "done" ? "text-emerald-400" : j.status === "failed" ? "text-red-400" : "text-amber-400"}`}>
                {j.status}
              </span>
              <span className="mono ml-auto text-[10px] text-zinc-700">{fmtDate(j.created_at)}</span>
              {j.cost ? (
                <span className="mono text-[10px] text-zinc-600">
                  {j.cost.web_searches}s · {j.cost.llm_calls}c · ${j.cost.est_cost_usd}
                </span>
              ) : null}
            </div>
          ))}
          {!traces?.jobs?.length ? (
            <p className="px-3 py-4 text-xs text-zinc-600">No runs yet.</p>
          ) : null}
        </div>
      </section>
    </div>
  );
}
