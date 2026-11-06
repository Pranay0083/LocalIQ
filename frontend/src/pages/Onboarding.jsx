import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ArrowLeft, ArrowRight, Check } from "@phosphor-icons/react";
import { useAuth } from "@/context/AuthContext";
import { api, errMessage } from "@/lib/api";
import { ModuleIcon } from "@/components/ModuleIcon";

const STAGES = [
  ["buyer", "Buying a home", "Multi-crore decision, months of research"],
  ["renter", "Renting", "Deciding between shortlisted localities"],
  ["investor", "Investing", "Evaluating emerging areas for ROI"],
  ["student", "Studying", "Near campus, tight budget"],
];

const HOUSEHOLDS = [
  ["solo", "Just me"],
  ["couple", "Couple"],
  ["kids", "With young kids"],
  ["elderly", "With elderly parents"],
  ["flatmates", "With flatmates"],
];

const WORK_MODES = [
  ["wfh", "Fully remote"],
  ["hybrid", "Hybrid"],
  ["office", "In office daily"],
  ["na", "Not working"],
];

const BUDGETS = [
  ["under_20k", "Under ₹20k / mo"],
  ["20_35k", "₹20k – 35k"],
  ["35_60k", "₹35k – 60k"],
  ["60k_plus", "₹60k+"],
];

const COMMUTE = [
  ["walk", "Walkable only"],
  ["30", "Up to 30 min"],
  ["60", "Up to 60 min"],
  ["any", "Distance is fine"],
];

const suggestPersona = (p) => {
  if (p.stage === "investor") return "investor";
  if (p.stage === "student") return "student";
  if (p.household === "kids") return "family_kids";
  if (p.household === "elderly") return "elderly";
  if (p.work_mode === "wfh") return "wfh_pro";
  return "bachelor";
};

export default function Onboarding() {
  const { user, setUser, loading } = useAuth();
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [personas, setPersonas] = useState([]);
  const [localities, setLocalities] = useState([]);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    stage: "", household: "", work_locality: "", work_mode: "", budget_band: "",
    commute_tolerance: "", free_text: "", persona_key: "",
  });

  useEffect(() => {
    if (!loading && !user) navigate("/auth");
  }, [loading, user, navigate]);

  useEffect(() => {
    api.get("/personas").then((r) => setPersonas(r.data)).catch(() => {});
    api.get("/localities").then((r) => setLocalities(r.data)).catch(() => {});
  }, []);

  useEffect(() => {
    if (step === 3 && !form.persona_key) {
      setForm((f) => ({ ...f, persona_key: suggestPersona(f) }));
    }
  }, [step, form.persona_key, form]);

  const save = async (skip = false) => {
    setBusy(true);
    try {
      const payload = skip
        ? { persona_key: "bachelor" }
        : { ...form, persona_key: form.persona_key || suggestPersona(form) };
      const { data } = await api.put("/auth/profile", payload);
      setUser(data);
      toast.success(skip ? "You can fill this in later from Account." : "Profile saved.");
      navigate("/app");
    } catch (error) {
      toast.error(errMessage(error));
    } finally {
      setBusy(false);
    }
  };

  const Chip = ({ active, onClick, title, sub, testId }) => (
    <button
      onClick={onClick}
      data-testid={testId}
      className={`border px-4 py-3 text-left transition-colors ${
        active
          ? "border-indigo-500 bg-indigo-500/10"
          : "border-zinc-800 bg-surface hover:border-zinc-700"
      }`}
    >
      <p className={`text-sm font-medium ${active ? "text-indigo-200" : "text-zinc-200"}`}>{title}</p>
      {sub ? <p className="mt-0.5 text-[11px] leading-snug text-zinc-500">{sub}</p> : null}
    </button>
  );

  const steps = [
    {
      title: "What are you doing here?",
      hint: "This decides which modules the agent even bothers to run.",
      body: (
        <div className="grid gap-2 sm:grid-cols-2">
          {STAGES.map(([k, t, s]) => (
            <Chip key={k} testId={`onb-stage-${k}`} active={form.stage === k} title={t} sub={s}
                  onClick={() => setForm({ ...form, stage: k })} />
          ))}
        </div>
      ),
    },
    {
      title: "Who is moving with you?",
      hint: "Household shape changes the weighting more than anything else.",
      body: (
        <div className="grid gap-2 sm:grid-cols-2">
          {HOUSEHOLDS.map(([k, t]) => (
            <Chip key={k} testId={`onb-household-${k}`} active={form.household === k} title={t}
                  onClick={() => setForm({ ...form, household: k })} />
          ))}
        </div>
      ),
    },
    {
      title: "Work, money, and how far you'll travel",
      hint: "Work location anchors the recommender. Budget shapes the affordability curve.",
      body: (
        <div className="space-y-5">
          <div>
            <p className="overline mb-2 text-zinc-600">Work / campus locality</p>
            <select
              data-testid="onb-work-locality"
              value={form.work_locality}
              onChange={(e) => setForm({ ...form, work_locality: e.target.value })}
              className="mono w-full border border-zinc-800 bg-zinc-950 px-3 py-2.5 text-sm text-zinc-100 outline-none focus:border-indigo-500"
            >
              <option value="">Not sure / not applicable</option>
              {localities.map((l) => (
                <option key={l.slug} value={l.slug}>{l.name}</option>
              ))}
            </select>
          </div>
          <div>
            <p className="overline mb-2 text-zinc-600">Work mode</p>
            <div className="grid gap-2 sm:grid-cols-4">
              {WORK_MODES.map(([k, t]) => (
                <Chip key={k} testId={`onb-workmode-${k}`} active={form.work_mode === k} title={t}
                      onClick={() => setForm({ ...form, work_mode: k })} />
              ))}
            </div>
          </div>
          <div>
            <p className="overline mb-2 text-zinc-600">Monthly budget</p>
            <div className="grid gap-2 sm:grid-cols-4">
              {BUDGETS.map(([k, t]) => (
                <Chip key={k} testId={`onb-budget-${k}`} active={form.budget_band === k} title={t}
                      onClick={() => setForm({ ...form, budget_band: k })} />
              ))}
            </div>
          </div>
          <div>
            <p className="overline mb-2 text-zinc-600">Commute tolerance</p>
            <div className="grid gap-2 sm:grid-cols-4">
              {COMMUTE.map(([k, t]) => (
                <Chip key={k} testId={`onb-commute-${k}`} active={form.commute_tolerance === k} title={t}
                      onClick={() => setForm({ ...form, commute_tolerance: k })} />
              ))}
            </div>
          </div>
        </div>
      ),
    },
    {
      title: "Anything else the agent should know?",
      hint: "Free text goes straight into the synthesis prompt. Be specific and it will show.",
      body: (
        <div className="space-y-5">
          <textarea
            data-testid="onb-freetext"
            rows={4}
            value={form.free_text}
            onChange={(e) => setForm({ ...form, free_text: e.target.value })}
            placeholder="I'm a backend engineer, fully remote, I have a labrador and I play badminton four evenings a week. I hate traffic noise and I need power that doesn't drop during calls."
            className="w-full border border-zinc-800 bg-zinc-950 px-3 py-2.5 text-sm leading-relaxed text-zinc-100 outline-none placeholder:text-zinc-700 focus:border-indigo-500"
          />
          <div>
            <p className="overline mb-2 text-zinc-600">Your lens — you can change this any time</p>
            <div className="grid gap-2 sm:grid-cols-2">
              {personas.map((p) => (
                <button
                  key={p.key}
                  data-testid={`onb-persona-${p.key}`}
                  onClick={() => setForm({ ...form, persona_key: p.key })}
                  className={`border px-4 py-3 text-left transition-colors ${
                    form.persona_key === p.key
                      ? "border-indigo-500 bg-indigo-500/10"
                      : "border-zinc-800 bg-surface hover:border-zinc-700"
                  }`}
                >
                  <p className="flex items-center gap-2 text-sm font-medium text-zinc-100">
                    {p.label}
                    {form.persona_key === p.key ? <Check size={13} className="text-indigo-400" /> : null}
                  </p>
                  <p className="mt-1 text-[11px] leading-snug text-zinc-500">{p.summary}</p>
                  <div className="mt-2 flex flex-wrap gap-1">
                    {p.modules.slice(0, 6).map((m) => (
                      <span key={m} className="text-zinc-600">
                        <ModuleIcon module={m} size={13} />
                      </span>
                    ))}
                    <span className="mono text-[9px] text-zinc-700">+{Math.max(0, p.modules.length - 6)}</span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>
      ),
    },
  ];

  const current = steps[step];

  return (
    <div className="mx-auto min-h-screen max-w-3xl px-5 py-12">
      <div className="mb-8 flex items-center gap-2">
        {steps.map((_, i) => (
          <div key={i} className={`h-[3px] flex-1 ${i <= step ? "bg-indigo-500" : "bg-zinc-900"}`}
               style={{ transition: "background-color 300ms ease" }} />
        ))}
      </div>

      <p className="overline text-indigo-400">Step {step + 1} of {steps.length}</p>
      <h1 className="mt-3 font-[Outfit] text-3xl font-light tracking-tight text-zinc-100">{current.title}</h1>
      <p className="mt-2 text-sm text-zinc-500">{current.hint}</p>

      <div className="mt-7 lq-in" key={step}>{current.body}</div>

      <div className="mt-9 flex items-center justify-between">
        <button
          data-testid="onb-back"
          onClick={() => (step === 0 ? save(true) : setStep(step - 1))}
          className="mono inline-flex items-center gap-1.5 border border-zinc-800 px-4 py-2.5 text-[11px] uppercase tracking-wider text-zinc-500 transition-colors hover:border-zinc-600 hover:text-zinc-200"
        >
          {step === 0 ? "Skip for now" : <><ArrowLeft size={13} /> Back</>}
        </button>
        <button
          data-testid="onb-next"
          disabled={busy}
          onClick={() => (step === steps.length - 1 ? save() : setStep(step + 1))}
          className="group inline-flex items-center gap-2 border border-indigo-500 bg-indigo-600 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-indigo-500 disabled:opacity-50"
        >
          {step === steps.length - 1 ? "Save and start" : "Continue"}
          <ArrowRight size={14} className="transition-transform group-hover:translate-x-1" />
        </button>
      </div>
    </div>
  );
}
