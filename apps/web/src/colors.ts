// Deterministic per-agent colours — a stable, vibrant hue per agent name, used for
// avatars and accents across the board. Wider palette than the old 4-hue hash so
// agents are visually distinct at a glance. Each hue reads on light + dark surfaces.
export const AGENT_PALETTE = [
  "#6366f1", "#8b5cf6", "#a855f7", "#ec4899", "#f43f5e", "#ef4444",
  "#f59e0b", "#eab308", "#10b981", "#14b8a6", "#06b6d4", "#3b82f6",
];

export function agentColor(name: string): string {
  let h = 0;
  for (const ch of name || "·") h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return AGENT_PALETTE[h % AGENT_PALETTE.length];
}

/** Inline style for a soft-tinted avatar chip in the agent's colour. */
export function agentAvatar(name: string): Record<string, string> {
  const c = agentColor(name);
  return {
    background: `color-mix(in srgb, ${c} 16%, transparent)`,
    color: c,
    boxShadow: `inset 0 0 0 1px color-mix(in srgb, ${c} 28%, transparent)`,
  };
}

export function initial(name: string): string {
  return (name || "·").trim().charAt(0).toUpperCase();
}
