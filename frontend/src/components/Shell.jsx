import { Link, NavLink, useNavigate } from "react-router-dom";
import {
  ChartLineUp, Compass, GitDiff, Scales, SignOut, Sparkle, Users,
} from "@phosphor-icons/react";
import { useAuth } from "@/context/AuthContext";
import { ThemeToggle } from "@/context/ThemeToggle";

const LINKS = [
  { to: "/app", label: "Search", icon: Compass, testId: "nav-search", end: true },
  { to: "/app/compare", label: "Compare", icon: GitDiff, testId: "nav-compare" },
  { to: "/app/recommend", label: "Recommend", icon: Sparkle, testId: "nav-recommend" },
  { to: "/app/community", label: "Community", icon: Users, testId: "nav-community" },
  { to: "/app/trust", label: "Rubric", icon: Scales, testId: "nav-trust" },
];

export const Logo = ({ compact }) => (
  <span className="flex items-center gap-2">
    <span className="grid h-7 w-7 place-items-center rounded-md bg-indigo-600 shadow-[0_6px_16px_-6px_rgb(79_70_229/0.9)]">
      <ChartLineUp size={15} weight="bold" className="text-white" />
    </span>
    {!compact ? (
      <span className="font-[Outfit] text-[15px] font-semibold tracking-tight text-zinc-100">
        LocalIQ
      </span>
    ) : null}
  </span>
);

export const Shell = ({ children }) => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <div className="min-h-screen">
      <header className="glass sticky top-0 z-50 border-b border-zinc-900">
        <div className="mx-auto flex h-14 max-w-[1400px] items-center gap-4 px-4 sm:gap-6 sm:px-6">
          <Link to="/app" data-testid="nav-logo">
            <Logo />
          </Link>
          <nav className="hidden items-center gap-1 md:flex">
            {LINKS.map((l) => (
              <NavLink
                key={l.to}
                to={l.to}
                end={l.end}
                data-testid={l.testId}
                className={({ isActive }) =>
                  `mono flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[11px] uppercase tracking-wider transition-colors ${
                    isActive
                      ? "border-indigo-500/60 bg-indigo-500/10 text-indigo-300"
                      : "border-transparent text-zinc-500 hover:border-zinc-800 hover:bg-surface2 hover:text-zinc-200"
                  }`
                }
              >
                <l.icon size={13} weight="duotone" /> {l.label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <ThemeToggle />
            <Link
              to="/app/account"
              data-testid="nav-account"
              className="mono flex items-center gap-2 rounded-full border border-zinc-800 bg-surface px-2.5 py-1.5 text-[11px] text-zinc-400 transition-colors hover:border-indigo-500 hover:text-indigo-400"
            >
              <span className="hidden max-w-[100px] truncate sm:inline">{user?.name}</span>
              <span
                className={`rounded-full px-2 py-[2px] text-[9px] uppercase tracking-widest ${
                  user?.plan === "free" ? "bg-zinc-800 text-zinc-400" : "bg-indigo-600 text-white"
                }`}
              >
                {user?.plan === "free" ? `${Math.max(0, 5 - (user?.reports_used || 0))} left` : "pro"}
              </span>
            </Link>
            <button
              data-testid="nav-logout"
              onClick={async () => {
                await logout();
                navigate("/");
              }}
              className="grid h-8 w-8 place-items-center rounded-full border border-zinc-800 bg-surface text-zinc-500 transition-colors hover:border-red-500 hover:text-red-400"
            >
              <SignOut size={14} />
            </button>
          </div>
        </div>
        <nav className="no-scrollbar flex items-center gap-1.5 overflow-x-auto border-t border-zinc-900 px-4 py-2 md:hidden">
          {LINKS.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              end={l.end}
              data-testid={`${l.testId}-mobile`}
              className={({ isActive }) =>
                `mono shrink-0 rounded-full border px-2.5 py-1 text-[10px] uppercase tracking-wider ${
                  isActive
                    ? "border-indigo-500/60 bg-indigo-500/10 text-indigo-300"
                    : "border-zinc-900 bg-surface text-zinc-500"
                }`
              }
            >
              {l.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="mx-auto max-w-[1400px] px-4 py-6 sm:px-6">{children}</main>
      <footer className="mt-16 border-t border-zinc-900 px-4 py-6 sm:px-6">
        <p className="mono mx-auto max-w-[1400px] text-[10px] leading-relaxed text-zinc-700">
          LocalIQ is decision support, not advice. Scores are computed from the published rubric over
          sourced, dated measurements. Media-reported incident counts are not crime rates. No listings,
          no brokerage, nothing to sell you.
        </p>
      </footer>
    </div>
  );
};
