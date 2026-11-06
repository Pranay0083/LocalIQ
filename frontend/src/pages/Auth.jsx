import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { ArrowRight, ChartLineUp } from "@phosphor-icons/react";
import { useAuth } from "@/context/AuthContext";
import { errMessage } from "@/lib/api";

export default function Auth() {
  const [params] = useSearchParams();
  const [mode, setMode] = useState(params.get("mode") === "register" ? "register" : "login");
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [busy, setBusy] = useState(false);
  const { login, register } = useAuth();
  const navigate = useNavigate();

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      if (mode === "register") {
        await register(form.name, form.email, form.password);
        toast.success("Account created. Tell us who you are.");
        navigate("/onboarding");
      } else {
        const user = await login(form.email, form.password);
        toast.success(`Welcome back, ${user.name}`);
        navigate(user.persona_key ? "/app" : "/onboarding");
      }
    } catch (error) {
      toast.error(errMessage(error));
    } finally {
      setBusy(false);
    }
  };

  const field = "mono w-full border border-zinc-800 bg-zinc-950 px-3 py-2.5 text-sm text-zinc-100 outline-none transition-colors placeholder:text-zinc-700 focus:border-indigo-500";

  return (
    <div className="grid min-h-screen lg:grid-cols-[1fr_1.1fr]">
      <div className="hidden flex-col justify-between border-r border-zinc-900 px-10 py-10 lg:flex">
        <Link to="/" className="flex items-center gap-2" data-testid="auth-logo">
          <span className="grid h-6 w-6 place-items-center bg-indigo-600">
            <ChartLineUp size={14} weight="bold" className="text-white" />
          </span>
          <span className="font-[Outfit] text-[15px] font-semibold tracking-tight">LocalIQ</span>
        </Link>
        <div>
          <p className="overline text-indigo-400">Bengaluru neighbourhood intelligence</p>
          <h2 className="mt-4 max-w-md font-[Outfit] text-4xl font-light leading-tight tracking-tight text-zinc-100">
            The report changes depending on who is reading it.
          </h2>
          <p className="mt-4 max-w-sm text-sm leading-relaxed text-zinc-500">
            A bachelor does not need CBSE rankings. A family with a five-year-old does not need to know
            which pubs stay open past midnight. Tell us who you are and the agent picks which modules
            even run.
          </p>
        </div>
        <div className="grid-skeleton grid grid-cols-3 border-b border-r border-zinc-900">
          {[
            ["34", "localities"],
            ["20", "modules"],
            ["6", "personas"],
          ].map(([n, l]) => (
            <div key={l} className="px-4 py-3">
              <p className="mono text-2xl text-zinc-200">{n}</p>
              <p className="overline text-zinc-600">{l}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="flex items-center justify-center px-5 py-14">
        <div className="w-full max-w-sm">
          <div className="mb-6 flex border border-zinc-800">
            {["login", "register"].map((m) => (
              <button
                key={m}
                data-testid={`auth-tab-${m}`}
                onClick={() => setMode(m)}
                className={`mono flex-1 py-2.5 text-[11px] uppercase tracking-wider transition-colors ${
                  mode === m ? "bg-indigo-600 text-white" : "text-zinc-500 hover:text-zinc-200"
                }`}
              >
                {m === "login" ? "Sign in" : "Create account"}
              </button>
            ))}
          </div>

          <form onSubmit={submit} className="space-y-3" data-testid="auth-form">
            {mode === "register" ? (
              <div>
                <label className="overline mb-1.5 block text-zinc-600">Name</label>
                <input
                  data-testid="auth-name"
                  required
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="Aarti Menon"
                  className={field}
                />
              </div>
            ) : null}
            <div>
              <label className="overline mb-1.5 block text-zinc-600">Email</label>
              <input
                data-testid="auth-email"
                required
                type="email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                placeholder="you@example.com"
                className={field}
              />
            </div>
            <div>
              <label className="overline mb-1.5 block text-zinc-600">Password</label>
              <input
                data-testid="auth-password"
                required
                type="password"
                minLength={6}
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                placeholder="••••••••"
                className={field}
              />
            </div>
            <button
              data-testid="auth-submit"
              disabled={busy}
              className="group mt-2 inline-flex w-full items-center justify-center gap-2 border border-indigo-500 bg-indigo-600 py-3 text-sm font-medium text-white transition-colors hover:bg-indigo-500 disabled:opacity-50"
            >
              {busy ? "Working…" : mode === "login" ? "Sign in" : "Create account"}
              <ArrowRight size={14} className="transition-transform group-hover:translate-x-1" />
            </button>
          </form>

          <div className="mt-6 panel border border-zinc-900 bg-surface px-3 py-2.5">
            <p className="overline text-zinc-600">Demo accounts</p>
            <div className="mt-1.5 space-y-1">
              {[
                ["buyer@localiq.in", "buyer123", "free · 5 reports"],
                ["pro@localiq.in", "pro12345", "pro · compare unlocked"],
              ].map(([email, pass, note]) => (
                <button
                  key={email}
                  data-testid={`auth-demo-${email.split("@")[0]}`}
                  onClick={() => {
                    setMode("login");
                    setForm({ name: "", email, password: pass });
                  }}
                  className="mono flex w-full items-center justify-between text-[10px] text-zinc-500 transition-colors hover:text-indigo-300"
                >
                  <span>{email} / {pass}</span>
                  <span className="text-zinc-700">{note}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
