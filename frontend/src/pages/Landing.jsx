import { Link } from "react-router-dom";
import {
  ArrowRight, Broadcast, ChartLineUp, Cube, Detective, Eye, GitDiff, HardHat,
  Scales, ShieldCheck, Wind,
} from "@phosphor-icons/react";
import { ThemeToggle } from "@/context/ThemeToggle";

const HERO = "https://images.pexels.com/photos/14845309/pexels-photo-14845309.jpeg";

const SOURCE_TAGS = [
  { label: "Live API", cls: "text-blue-300 border-blue-500/40" },
  { label: "Computed · OSM", cls: "text-violet-300 border-violet-500/40" },
  { label: "Official", cls: "text-emerald-300 border-emerald-500/40" },
  { label: "News / Media", cls: "text-amber-300 border-amber-500/40" },
  { label: "Community-verified", cls: "text-teal-300 border-teal-500/40" },
  { label: "Forum / Unverified", cls: "text-slate-400 border-slate-600/40" },
];

const AGENTS = [
  { name: "Intake", desc: "Resolves the locality, infers your persona, picks which modules even matter to you." },
  { name: "Collectors ×7", desc: "Air, geodata, safety & news, water/power, education, infrastructure, community — in parallel." },
  { name: "Verifier", desc: "Drops any claim it cannot trace back to a page it actually opened. Flags contradictions." },
  { name: "Scorer", desc: "Deterministic published rubric. No language model ever produces a score." },
  { name: "Synthesizer", desc: "Writes what living there looks like — for you, from verified facts only." },
  { name: "Presenter", desc: "Decides the shape of the page: which chart, which card, which order." },
];

export default function Landing() {
  return (
    <div className="min-h-screen">
      <header className="glass sticky top-0 z-50 border-b border-zinc-900">
        <div className="mx-auto flex h-14 max-w-[1400px] items-center px-4 sm:px-6">
          <span className="flex items-center gap-2">
            <span className="grid h-6 w-6 place-items-center bg-indigo-600">
              <ChartLineUp size={14} weight="bold" className="text-white" />
            </span>
            <span className="font-[Outfit] text-[15px] font-semibold tracking-tight">LocalIQ</span>
            <span className="overline ml-2 hidden border border-zinc-800 px-1.5 py-[2px] text-zinc-500 sm:inline">
              Bengaluru
            </span>
          </span>
          <div className="ml-auto flex items-center gap-2">
            <ThemeToggle />
            <Link
              to="/auth"
              data-testid="landing-signin"
              className="mono hidden rounded-full border border-zinc-800 bg-surface px-3 py-1.5 text-[11px] uppercase tracking-wider text-zinc-400 transition-colors hover:border-zinc-600 hover:text-zinc-100 sm:inline-block"
            >
              Sign in
            </Link>
            <Link
              to="/auth?mode=register"
              data-testid="landing-cta-top"
              className="mono rounded-full border border-indigo-500 bg-indigo-600 px-3.5 py-1.5 text-[11px] uppercase tracking-wider text-white shadow-[0_10px_24px_-12px_rgb(79_70_229/0.9)] transition-colors hover:bg-indigo-500"
            >
              Get 5 free reports
            </Link>
          </div>
        </div>
      </header>

      {/* hero — asymmetric tetris grid */}
      <section className="mx-auto max-w-[1400px] px-4 pt-14 sm:px-6 lg:pt-20">
        <div className="grid gap-10 lg:grid-cols-[1.15fr_minmax(0,0.85fr)]">
          <div className="lq-in">
            <p className="overline text-indigo-400">A credit score for neighbourhoods</p>
            <h1 className="mt-4 font-[Outfit] text-4xl font-light leading-[1.05] tracking-tight text-zinc-50 sm:text-5xl lg:text-6xl">
              Every portal wants you to buy.
              <br />
              <span className="font-semibold">This one wants you to know.</span>
            </h1>
            <p className="mt-6 max-w-xl text-base leading-relaxed text-zinc-400">
              LocalIQ runs a multi-agent research system over any Bengaluru locality — live air quality,
              computed walking distances, media-reported incidents, water and power reliability, the
              infrastructure pipeline and what residents actually say. Then it scores it{" "}
              <span className="text-zinc-100">for the person you actually are</span>, and shows you every
              source behind every number.
            </p>

            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Link
                to="/auth?mode=register"
                data-testid="landing-cta-main"
                className="group inline-flex items-center gap-2 rounded-full border border-indigo-500 bg-indigo-600 px-6 py-3 text-sm font-medium text-white shadow-[0_16px_34px_-16px_rgb(79_70_229/0.95)] transition-colors hover:bg-indigo-500"
              >
                Build my first report
                <ArrowRight size={15} className="transition-transform group-hover:translate-x-1" />
              </Link>
              <Link
                to="/auth"
                data-testid="landing-cta-secondary"
                className="mono rounded-full border border-zinc-800 bg-surface px-5 py-3 text-xs uppercase tracking-wider text-zinc-400 transition-colors hover:border-zinc-600 hover:text-zinc-100"
              >
                I already have an account
              </Link>
            </div>

            <div className="mt-8 flex flex-wrap gap-1.5">
              {SOURCE_TAGS.map((t) => (
                <span key={t.label} className={`overline border px-2 py-1 ${t.cls}`}>
                  {t.label}
                </span>
              ))}
            </div>
          </div>

          <div className="lq-in relative" style={{ animationDelay: "120ms" }}>
            <div className="panel relative overflow-hidden rounded-xl border border-zinc-900">
              <img
                src={HERO}
                alt="Bengaluru skyline at dusk"
                className="h-[260px] w-full object-cover lg:h-[300px] dark:opacity-70"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-zinc-950 via-zinc-950/20 to-transparent" />
              <div className="absolute bottom-3 left-4">
                <p className="overline text-zinc-400">34 localities · one city · zero listings</p>
              </div>
            </div>

            {/* dual score demo */}
            <div className="grid-skeleton mt-4 grid grid-cols-2 border-r border-b border-zinc-900">
              <div className="bg-indigo-600/90 px-4 py-4">
                <p className="overline text-indigo-100/80">Scored for you</p>
                <p className="mono mt-1 text-5xl font-semibold leading-none text-white">78</p>
                <p className="mt-1.5 text-[11px] leading-snug text-indigo-100/80">
                  WFH professional, one dog, ₹45k budget
                </p>
              </div>
              <div className="bg-surface2 px-4 py-4">
                <p className="overline text-zinc-500">Neutral baseline</p>
                <p className="mono mt-1 text-5xl font-light leading-none text-zinc-300">64</p>
                <p className="mt-1.5 text-[11px] leading-snug text-zinc-500">
                  Every module weighted equally
                </p>
              </div>
            </div>
            <p className="mono mt-2 text-[10px] leading-relaxed text-zinc-600">
              Whitefield can score 78 for an investor and 54 for a bachelor. Both are correct. That is
              the point — and the label is always attached to the number.
            </p>
          </div>
        </div>
      </section>

      {/* what's actually missing */}
      <section className="mx-auto mt-24 max-w-[1400px] px-4 sm:px-6">
        <p className="overline text-zinc-600">What no portal will tell you</p>
        <div className="grid-skeleton mt-5 grid border-b border-r border-zinc-900 sm:grid-cols-2 lg:grid-cols-4">
          {[
            { icon: Wind, t: "Air by micro-zone", d: "Live CPCB AQI at the locality centroid, with a 48-hour forecast — not a city-wide average." },
            { icon: Detective, t: "Incidents, dated & linked", d: "Media-reported incidents with a source article each, and an honest caveat that this is not a crime rate." },
            { icon: HardHat, t: "The pipeline", d: "Metro extensions, road projects, water upgrades — pulled from authority announcements and press coverage." },
            { icon: Broadcast, t: "Water & power truth", d: "Outage patterns and tanker dependence, from utility notices and photo-backed resident claims." },
          ].map((f) => (
            <div key={f.t} className="lift bg-surface px-5 py-6">
              <f.icon size={22} weight="duotone" className="text-indigo-400" />
              <h3 className="mt-3 text-base font-medium text-zinc-100">{f.t}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-zinc-500">{f.d}</p>
            </div>
          ))}
        </div>
      </section>

      {/* the agent system */}
      <section className="mx-auto mt-24 max-w-[1400px] px-4 sm:px-6">
        <div className="grid gap-10 lg:grid-cols-[0.9fr_minmax(0,1.1fr)]">
          <div>
            <p className="overline text-zinc-600">The machine</p>
            <h2 className="mt-3 font-[Outfit] text-3xl font-light tracking-tight text-zinc-100">
              Seven agents, one strict contract
            </h2>
            <p className="mt-4 text-sm leading-relaxed text-zinc-500">
              Expensive collection runs once per locality and is shared. Your report is a thin
              personalisation pass over that dossier — which is why regenerating means something and
              switching lens is instant. Distances are computed geometry. Scores are arithmetic. The
              model writes prose, never numbers.
            </p>
            <div className="mt-6 space-y-2">
              {[
                { icon: Eye, t: "Every number is tappable", d: "Source, date, confidence, one tap away." },
                { icon: ShieldCheck, t: "Absence stays absent", d: "Missing data widens the confidence band. It never becomes an average." },
                { icon: Scales, t: "The rubric is published", d: "Read the exact formula behind every module score, in-app." },
              ].map((x) => (
                <div key={x.t} className="flex gap-3 border border-zinc-900 px-4 py-3">
                  <x.icon size={17} weight="duotone" className="mt-0.5 shrink-0 text-indigo-400" />
                  <div>
                    <p className="text-sm font-medium text-zinc-200">{x.t}</p>
                    <p className="text-xs text-zinc-500">{x.d}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="dark panel overflow-hidden rounded-xl border border-zinc-900 bg-zinc-950">
            <div className="flex items-center gap-2 border-b border-zinc-900 px-4 py-2">
              <span className="h-2 w-2 rounded-full bg-red-500/70" />
              <span className="h-2 w-2 rounded-full bg-amber-500/70" />
              <span className="h-2 w-2 rounded-full bg-emerald-500/70" />
              <span className="mono ml-2 text-[10px] text-zinc-600">localiq · graph.run</span>
            </div>
            <div className="space-y-2.5 p-4">
              {AGENTS.map((a, i) => (
                <div key={a.name} className="flex gap-3">
                  <span className="mono w-6 shrink-0 text-[10px] text-zinc-700">{String(i + 1).padStart(2, "0")}</span>
                  <div>
                    <p className="mono text-xs text-indigo-300">{a.name}</p>
                    <p className="text-xs leading-snug text-zinc-500">{a.desc}</p>
                  </div>
                </div>
              ))}
              <div className="rule my-1" />
              <p className="mono text-[10px] text-zinc-600">
                + Chat agent · answers follow-ups against the same dossier, cites the same sources
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* pricing strip */}
      <section className="mx-auto mt-24 max-w-[1400px] px-4 sm:px-6">
        <div className="grid-skeleton grid border-b border-r border-zinc-900 md:grid-cols-3">
          <div className="bg-surface px-5 py-6">
            <p className="overline text-zinc-600">Free</p>
            <p className="mono mt-2 text-3xl text-zinc-100">₹0</p>
            <ul className="mt-3 space-y-1 text-xs text-zinc-500">
              <li>5 full locality reports</li>
              <li>Unlimited grounded chat</li>
              <li>One recommendation run</li>
              <li>Full citations on every number</li>
            </ul>
          </div>
          <div className="bg-indigo-600/10 px-5 py-6 ring-1 ring-inset ring-indigo-500/30">
            <p className="overline text-indigo-300">Pro monthly</p>
            <p className="mono mt-2 text-3xl text-zinc-100">₹499</p>
            <ul className="mt-3 space-y-1 text-xs text-zinc-400">
              <li>Unlimited reports & regeneration</li>
              <li className="flex items-center gap-1.5">
                <GitDiff size={12} className="text-indigo-400" /> Side-by-side comparison
              </li>
              <li>Unlimited recommendation runs</li>
              <li>Full agent run traces</li>
            </ul>
          </div>
          <div className="bg-surface px-5 py-6">
            <p className="overline text-zinc-600">Earn it</p>
            <p className="mono mt-2 text-3xl text-zinc-100">
              <Cube size={26} weight="duotone" className="inline text-teal-400" /> credits
            </p>
            <ul className="mt-3 space-y-1 text-xs text-zinc-500">
              <li>Post a photo-backed fact claim</li>
              <li>Get independently corroborated</li>
              <li>Earn a free report credit</li>
              <li>Fill the gaps the data misses</li>
            </ul>
          </div>
        </div>
      </section>

      <section className="mx-auto mt-24 max-w-[1400px] px-4 pb-24 sm:px-6">
        <div className="panel border border-zinc-900 bg-surface px-6 py-10 text-center">
          <h2 className="font-[Outfit] text-2xl font-light tracking-tight text-zinc-100 md:text-3xl">
            Spend twenty minutes before you spend two crore.
          </h2>
          <Link
            to="/auth?mode=register"
            data-testid="landing-cta-footer"
            className="mt-6 inline-flex items-center gap-2 rounded-full border border-indigo-500 bg-indigo-600 px-6 py-3 text-sm font-medium text-white shadow-[0_16px_34px_-16px_rgb(79_70_229/0.95)] transition-colors hover:bg-indigo-500"
          >
            Start with 5 free reports <ArrowRight size={15} />
          </Link>
          <p className="mono mt-5 text-[10px] text-zinc-700">
            Bengaluru only for now. Decision support, not advice.
          </p>
        </div>
      </section>
    </div>
  );
}
