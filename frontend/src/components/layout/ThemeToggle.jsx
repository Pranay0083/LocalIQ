import { Moon, Sun } from "@phosphor-icons/react";
import { useTheme } from "next-themes";

export const ThemeToggle = ({ className = "" }) => {
  const { resolvedTheme, setTheme } = useTheme();
  const dark = resolvedTheme === "dark";
  return (
    <button
      type="button"
      data-testid="theme-toggle"
      aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
      onClick={() => setTheme(dark ? "light" : "dark")}
      className={`relative grid h-8 w-8 shrink-0 place-items-center rounded-md border border-zinc-800 bg-surface text-zinc-500 transition-colors hover:border-zinc-600 hover:text-zinc-100 ${className}`}
    >
      <Sun
        size={14}
        weight="bold"
        className={`absolute transition-[opacity,transform] duration-300 ${dark ? "rotate-90 opacity-0" : "rotate-0 opacity-100"}`}
      />
      <Moon
        size={14}
        weight="bold"
        className={`absolute transition-[opacity,transform] duration-300 ${dark ? "rotate-0 opacity-100" : "-rotate-90 opacity-0"}`}
      />
    </button>
  );
};
