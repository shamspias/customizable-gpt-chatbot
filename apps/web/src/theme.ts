// Runtime theme: persisted appearance (system/light/dark) + accent preset, applied by
// setting data-theme / data-accent on <html>. The CSS variables (style.css) react, and
// since Tailwind tokens are mapped @theme inline, every utility re-themes live too.
export type Mode = "system" | "light" | "dark";
export const ACCENTS = ["indigo", "violet", "emerald", "amber", "rose", "cyan", "slate"] as const;
export type Accent = (typeof ACCENTS)[number];

const MODE_KEY = "veldra.theme";
const ACCENT_KEY = "veldra.accent";

export function getMode(): Mode {
  return (localStorage.getItem(MODE_KEY) as Mode) || "system";
}
export function getAccent(): Accent {
  return (localStorage.getItem(ACCENT_KEY) as Accent) || "indigo";
}

export function applyTheme() {
  const root = document.documentElement;
  const mode = getMode();
  if (mode === "system") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", mode);
  const accent = getAccent();
  if (accent === "indigo") root.removeAttribute("data-accent"); // indigo is the default
  else root.setAttribute("data-accent", accent);
}

export function setMode(mode: Mode) {
  localStorage.setItem(MODE_KEY, mode);
  applyTheme();
}
export function setAccent(accent: Accent) {
  localStorage.setItem(ACCENT_KEY, accent);
  applyTheme();
}

// Swatch colors for the picker (the filled accent of each preset).
export const ACCENT_SWATCH: Record<Accent, string> = {
  indigo: "#5566ef", violet: "#7c3aed", emerald: "#0d9f6e",
  amber: "#b45309", rose: "#e11d48", cyan: "#0e7490", slate: "#475569",
};
