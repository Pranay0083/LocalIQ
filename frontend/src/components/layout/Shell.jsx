import { Link, NavLink, useNavigate } from "react-router-dom";
import { Compass, GitDiff, Scales, SignOut, Sparkle, Users } from "@phosphor-icons/react";
import { useAuth } from "@/context/AuthContext";
import { ThemeToggle } from "@/components/layout/ThemeToggle";

const LINKS = [
  { to: "/app", label: "Search", icon: Compass, testId: "nav-search", end: true },
  { to: "/app/compare", label: "Compare", icon: GitDiff, testId: "nav-compare" },
  { to: "/app/recommend", label: "Recommend", icon: Sparkle, testId: "nav-recommend" },
  { to: "/app/community", label: "Community", icon: Users, testId: "nav-community" },
  { to: "/app/trust", label: "Rubric", icon: Scales, testId: "nav-trust" },
];

/* The mark: a score dial, three-quarters filled in the data hue, around a locality pin. */
export const Mark = ({ size = 22 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" className="shrink-0">
    <circle cx="12" cy="12" r="9.5" fill="none" stroke="rgb(var(--border))" strokeWidth="3" />
    <circle
      cx="12" cy="12" r="9.5" fill="none" stroke="rgb(var(--data))" strokeWidth="3"
      strokeDasharray={`${0.75 * 2 * Math.PI * 9.5} ${2 * Math.PI * 9.5}`}
      transform="rotate(-90 12 12)"
    />
    <circle cx="12" cy="12" r="3" fill="rgb(var(--foreground))" />
  </svg>
);

export const Logo = ({ compact }) => (
  <span className="flex items-center gap-2">
    <Mark />
    {!compact ? <span className="text-[15px] font-semibold text-zinc-50">LocalIQ</span> : null}
  </span>
);

const navClass = ({ isActive }) =>
  `flex shrink-0 items-center gap-2 rounded-md px-2.5 py-1.5 text-sm transition-colors ${
    isActive ? "bg-secondary text-zinc-50" : "text-zinc-500 hover:bg-secondary/60 hover:text-zinc-50"
  }`;

export const Shell = ({ children }) => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const free = user?.plan === "free";

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-50 border-b border-zinc-900 bg-background">
        <div className="mx-auto flex h-12 max-w-[1200px] items-center gap-6 px-4 sm:px-6">
          <Link to="/app" data-testid="nav-logo" aria-label="LocalIQ home">
            <Logo />
          </Link>
          <nav className="hidden items-center gap-1 lg:flex">
            {LINKS.map((l) => (
              <NavLink key={l.to} to={l.to} end={l.end} data-testid={l.testId} className={navClass}>
                <l.icon size={16} /> {l.label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <ThemeToggle />
            <Link
              to="/app/account"
              data-testid="nav-account"
              className="flex h-8 items-center gap-2 rounded-md border border-zinc-800 bg-surface px-2.5 text-sm text-zinc-50 transition-colors hover:border-zinc-600"
            >
              <span className="hidden max-w-[120px] truncate sm:inline">{user?.name}</span>
              <span className="mono text-xs text-zinc-500">
                {free ? `${Math.max(0, 5 - (user?.reports_used || 0))} reports left` : "Pro"}
              </span>
            </Link>
            <button
              data-testid="nav-logout"
              aria-label="Sign out"
              onClick={async () => {
                await logout();
                navigate("/");
              }}
              className="grid h-8 w-8 place-items-center rounded-md border border-zinc-800 bg-surface text-zinc-500 transition-colors hover:border-zinc-600 hover:text-zinc-50"
            >
              <SignOut size={16} />
            </button>
          </div>
        </div>
        <nav className="mx-auto grid max-w-[1200px] grid-cols-5 gap-1 px-4 pb-2 sm:flex sm:px-6 lg:hidden">
          {LINKS.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              end={l.end}
              data-testid={`${l.testId}-mobile`}
              className={(state) => `${navClass(state)} justify-center px-1 text-xs sm:px-2.5 sm:text-sm`}
            >
              {l.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="mx-auto max-w-[1200px] px-4 py-8 sm:px-6">{children}</main>
      <footer className="mt-16 border-t border-zinc-900">
        <p className="mx-auto max-w-[1200px] px-4 py-6 text-xs leading-relaxed text-zinc-600 sm:px-6">
          LocalIQ is decision support, not advice. Scores are computed from the published rubric over
          sourced, dated measurements. Media-reported incident counts are not crime rates. No listings,
          no brokerage, nothing to sell you.
        </p>
      </footer>
    </div>
  );
};
